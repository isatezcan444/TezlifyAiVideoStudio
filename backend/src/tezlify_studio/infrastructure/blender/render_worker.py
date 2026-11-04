"""Blender Headless Animation & Render Worker

This script is executed inside Blender headless mode:
blender -b --python render_worker.py -- <manifest_path>
"""
import sys
import os
import json
import math
import traceback
import bpy
import mathutils

# Blender runs this file with its own interpreter, which has no pydantic, so only
# standard-library modules may be pulled from the package. camera_framing is kept
# dependency-free for exactly that reason: the framing maths below has to be the
# same code the backend tests exercise.
_BACKEND_SRC = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
)
if _BACKEND_SRC not in sys.path:
    sys.path.insert(0, _BACKEND_SRC)

from tezlify_studio.domain.value_objects.camera_framing import (  # noqa: E402
    SubjectBounds,
    intent_for_angle,
    profile_for_aspect,
    profile_for_dimensions,
    screen_box,
    solve_camera,
    visible_extents_at_plane,
)

def log(msg: str):
    print(f"[BLENDER_WORKER] {msg}", flush=True)

def report_progress(percent: float, step: str):
    print(f"PROGRESS:{percent:.1f}:{step}", flush=True)

def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def append_blend_objects(blend_path: str, exclude_names=None, prefix=""):
    if exclude_names is None:
        exclude_names = set()
    else:
        exclude_names = set(exclude_names)

    if not os.path.exists(blend_path):
        raise FileNotFoundError(f"Blend file not found: {blend_path}")

    with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
        data_to.objects = [n for n in data_from.objects if n not in exclude_names]

    imported_objects = {}
    for obj in data_to.objects:
        if obj:
            bpy.context.collection.objects.link(obj)
            orig_name = obj.name
            if prefix:
                obj.name = f"{prefix}__{orig_name}"
            imported_objects[orig_name] = obj

    return imported_objects

def setup_lighting():
    # 3-Point lighting rig
    key_light = bpy.data.lights.new(name="KeyLight", type='SUN')
    key_light.energy = 3.2
    key_light.color = (1.0, 0.96, 0.92)
    key_obj = bpy.data.objects.new(name="Studio_KeyLight", object_data=key_light)
    key_obj.location = (2.5, -3.5, 4.0)
    key_obj.rotation_euler = (0.75, 0.2, 0.6)
    bpy.context.collection.objects.link(key_obj)

    fill_light = bpy.data.lights.new(name="FillLight", type='SUN')
    fill_light.energy = 1.4
    fill_light.color = (0.92, 0.95, 1.0)
    fill_obj = bpy.data.objects.new(name="Studio_FillLight", object_data=fill_light)
    fill_obj.location = (-2.5, -2.5, 3.0)
    fill_obj.rotation_euler = (0.8, -0.3, -0.7)
    bpy.context.collection.objects.link(fill_obj)

    rim_light = bpy.data.lights.new(name="RimLight", type='SUN')
    rim_light.energy = 1.8
    rim_light.color = (1.0, 1.0, 1.0)
    rim_obj = bpy.data.objects.new(name="Studio_RimLight", object_data=rim_light)
    rim_obj.location = (0.0, 3.0, 3.5)
    rim_obj.rotation_euler = (-0.8, 0.0, 3.14)
    bpy.context.collection.objects.link(rim_obj)

def object_world_bounds(obj):
    """World-space AABB of an object's bounding box, or None when degenerate."""
    bound_box = getattr(obj, "bound_box", None)
    if not bound_box:
        return None
    corners = [obj.matrix_world @ mathutils.Vector(corner) for corner in bound_box]
    xs = [c.x for c in corners]
    ys = [c.y for c in corners]
    zs = [c.z for c in corners]
    if max(xs) - min(xs) <= 1e-6 and max(zs) - min(zs) <= 1e-6:
        return None
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def merge_bounds(boxes):
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    return (
        min(b[0] for b in boxes),
        max(b[1] for b in boxes),
        min(b[2] for b in boxes),
        max(b[3] for b in boxes),
        min(b[4] for b in boxes),
        max(b[5] for b in boxes),
    )


def measure_subject_bounds(character_maps: dict, sample_frames):
    """Real on-screen extents of the cast, measured from the animated rig.

    Returns ``({character_id: extents}, union_extents)`` where extents is
    ``(x_min, x_max, y_min, y_max, z_min, z_max)``.

    Sampling start / middle / end of the shot is what makes the solve trustworthy:
    a raised arm during a gesture widens the silhouette and a sitting pose lowers
    the head, so a single frame would let the camera solve for a body that is not
    actually on screen for the rest of the shot.
    """
    per_character = {}
    for frame in sample_frames:
        bpy.context.scene.frame_set(int(frame))
        bpy.context.view_layer.update()
        for char_id, char_map in character_maps.items():
            box = merge_bounds(object_world_bounds(obj) for obj in char_map.values())
            if box:
                per_character.setdefault(char_id, []).append(box)

    collapsed = {
        char_id: merge_bounds(boxes) for char_id, boxes in per_character.items()
    }
    collapsed = {k: v for k, v in collapsed.items() if v}
    union = merge_bounds(collapsed.values()) if collapsed else None
    return collapsed, union


def subject_box_from_extents(extents, crop: float) -> SubjectBounds:
    """Turn raw extents into the box the shot intends to keep inside the frame.

    ``crop`` is the share of the head-to-feet span the angle keeps, counted from
    the top of the head: 0.82 is a two-shot that stops mid-shin, 1.0 is a full
    body. A tall frame is allowed to open the crop up so the extra height is spent
    on the cast rather than on wall.
    """
    x_min, x_max, _y_min, _y_max, z_min, z_max = extents
    crop = max(0.05, min(1.0, crop))
    z_bottom = z_max - crop * (z_max - z_min)
    return SubjectBounds(
        x_min=x_min,
        x_max=x_max,
        z_top=z_max,
        z_bottom=z_bottom,
    )


def scaled_placement_x(position, centroid_x: float, ratio: float):
    """Pull a cast member towards the group centre for a narrower frame."""
    if ratio == 1.0 or len(position) != 3:
        return list(position)
    return [centroid_x + (position[0] - centroid_x) * ratio, position[1], position[2]]


WALL_MARKERS = ("BackWall", "_Wall", "SkyBackdrop", "Backdrop", "Wall_")
FLOOR_MARKERS = ("Floor", "Grass", "Rug")


def _is_axis_aligned_unparented(obj) -> bool:
    if obj.parent is not None:
        return False
    rot = obj.rotation_euler
    return abs(rot.x) < 1e-4 and abs(rot.y) < 1e-4 and abs(rot.z) < 1e-4


def expand_backdrop_for_frame(background_objects: dict, coverage) -> list:
    """Grow the set until it covers everything the camera can see.

    Without this, the extra vertical field of view of a portrait frame runs past
    the top of the wall and renders the black world background, which is exactly
    the "black padding" a vertical export is supposed to avoid. ``coverage`` is the
    union of the visible world rectangles measured at the set's own depth planes.
    """
    if not background_objects or not coverage:
        return []

    x_min, x_max, z_min, z_max, floor_y_min, floor_y_max = coverage
    adjusted = []

    for name, obj in background_objects.items():
        if not _is_axis_aligned_unparented(obj):
            continue
        bounds = object_world_bounds(obj)
        if not bounds:
            continue
        bx_min, bx_max, by_min, by_max, bz_min, bz_max = bounds

        if any(marker in name for marker in WALL_MARKERS):
            new_x_min = min(bx_min, x_min)
            new_x_max = max(bx_max, x_max)
            new_z_min = min(bz_min, z_min)
            new_z_max = max(bz_max, z_max)
            width = bx_max - bx_min
            height = bz_max - bz_min
            if width <= 1e-6 or height <= 1e-6:
                continue
            obj.scale.x *= (new_x_max - new_x_min) / width
            obj.scale.z *= (new_z_max - new_z_min) / height
            obj.location.x = (new_x_min + new_x_max) / 2.0
            obj.location.z = (new_z_min + new_z_max) / 2.0
            adjusted.append(name)
        elif any(marker in name for marker in FLOOR_MARKERS):
            new_x_min = min(bx_min, x_min)
            new_x_max = max(bx_max, x_max)
            new_y_min = min(by_min, floor_y_min)
            new_y_max = max(by_max, floor_y_max)
            width = bx_max - bx_min
            depth = by_max - by_min
            if width <= 1e-6 or depth <= 1e-6:
                continue
            obj.scale.x *= (new_x_max - new_x_min) / width
            obj.scale.y *= (new_y_max - new_y_min) / depth
            obj.location.x = (new_x_min + new_x_max) / 2.0
            obj.location.y = (new_y_min + new_y_max) / 2.0
            adjusted.append(name)

    return adjusted

def apply_pose(char_map: dict, pose_str: str):
    torso = char_map.get("Anchor_Torso")
    leg_l = char_map.get("Anchor_Leg_L")
    leg_r = char_map.get("Anchor_Leg_R")
    arm_l = char_map.get("Anchor_Arm_L")
    arm_r = char_map.get("Anchor_Arm_R")

    pose_lower = (pose_str or "standing").lower()
    if "sitting" in pose_lower:
        if torso:
            torso.location.z = 0.65
        if leg_l:
            leg_l.rotation_euler.x = math.radians(85)
        if leg_r:
            leg_r.rotation_euler.x = math.radians(85)
    else:
        if torso:
            torso.location.z = 0.95
        if leg_l:
            leg_l.rotation_euler.x = 0.0
        if leg_r:
            leg_r.rotation_euler.x = 0.0

    if "gesture" in pose_lower or "gesturing" in pose_lower:
        if arm_r:
            arm_r.rotation_euler.x = math.radians(-35)
            arm_r.rotation_euler.z = math.radians(15)
    elif "point" in pose_lower:
        if arm_r:
            arm_r.rotation_euler.x = math.radians(-65)
            arm_r.rotation_euler.z = math.radians(-10)

def apply_expression(char_map: dict, expr_str: str, frame: int):
    brow_l = char_map.get("Mesh_Brow_L")
    brow_r = char_map.get("Mesh_Brow_R")
    mouth = char_map.get("Mesh_Mouth")

    expr_lower = (expr_str or "neutral").lower()

    if brow_l and brow_r:
        if "cheerful" in expr_lower:
            brow_l.location.z = 0.11
            brow_r.location.z = 0.11
            brow_l.rotation_euler.y = 0.0
            brow_r.rotation_euler.y = 0.0
        elif "surprised" in expr_lower:
            brow_l.location.z = 0.13
            brow_r.location.z = 0.13
            brow_l.rotation_euler.y = 0.0
            brow_r.rotation_euler.y = 0.0
        elif "angry" in expr_lower:
            brow_l.location.z = 0.08
            brow_r.location.z = 0.08
            brow_l.rotation_euler.y = 0.25
            brow_r.rotation_euler.y = -0.25
        elif "sad" in expr_lower:
            brow_l.location.z = 0.09
            brow_r.location.z = 0.09
            brow_l.rotation_euler.y = -0.2
            brow_r.rotation_euler.y = 0.2
        elif "thinking" in expr_lower:
            brow_l.location.z = 0.12
            brow_r.location.z = 0.08
        else: # neutral
            brow_l.location.z = 0.095
            brow_r.location.z = 0.095
            brow_l.rotation_euler.y = 0.0
            brow_r.rotation_euler.y = 0.0

        brow_l.keyframe_insert(data_path="location", frame=frame)
        brow_r.keyframe_insert(data_path="location", frame=frame)
        brow_l.keyframe_insert(data_path="rotation_euler", frame=frame)
        brow_r.keyframe_insert(data_path="rotation_euler", frame=frame)

def main():
    args = sys.argv
    if "--" not in args:
        log("No manifest file provided after '--'")
        sys.exit(1)

    manifest_idx = args.index("--") + 1
    if manifest_idx >= len(args):
        log("Manifest path missing")
        sys.exit(1)

    manifest_path = args[manifest_idx]
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    project_id = manifest["project_id"]
    job_id = manifest["job_id"]
    assets_dir = manifest.get("assets_dir", "")
    frames_dir = manifest["frames_dir"]
    scene_save_path = manifest.get("scene_save_path", "")
    result_path = manifest["result_path"]
    engine_override = manifest.get("engine_override", "BLENDER_WORKBENCH")

    scene_graph = manifest["scene_graph"]
    resolution = scene_graph.get("resolution", {})
    width = resolution.get("width", 1920)
    height = resolution.get("height", 1080)
    fps = resolution.get("fps", 30)
    aspect_ratio = resolution.get("aspect_ratio") or (
        "9:16" if height > width else ("1:1" if width == height else "16:9")
    )
    # The delivery format decides the camera, not only the pixel count. The
    # rendered dimensions win when a legacy project recorded an aspect ratio that
    # contradicts them, because the frame is what the audience sees.
    framing_profile = profile_for_aspect(aspect_ratio)
    if (framing_profile.width, framing_profile.height) != (width, height):
        log(
            f"WARNING: recorded aspect {aspect_ratio} does not match {width}x{height}; "
            "framing from the pixel dimensions"
        )
        framing_profile = profile_for_dimensions(width, height)
    sensor_width_mm = 36.0

    scenes = scene_graph.get("scenes", [])
    if not scenes:
        raise ValueError("SceneGraph contains no scenes")

    total_duration = sum(s.get("duration_seconds", 5.0) for s in scenes)
    total_frames = max(1, int(round(total_duration * fps)))

    log(
        f"Starting render: {len(scenes)} scene(s), total {total_duration:.2f}s, "
        f"{total_frames} frames @ {fps}fps, framing={framing_profile.label}"
    )
    report_progress(10.0, f"Building 3D Scene ({framing_profile.label})")

    clear_scene()

    # 1. Setup Camera and Camera Target
    cam_target = bpy.data.objects.new("CameraTarget", None)
    cam_target.location = (0.0, 0.0, 1.05)
    bpy.context.collection.objects.link(cam_target)

    cam_data = bpy.data.cameras.new("MainStudioCamera")
    # Horizontal sensor fit: the horizontal field of view is set by the lens, and
    # the vertical one follows the frame. Every framing decision below is solved
    # against that relationship, per delivery format.
    cam_data.sensor_fit = 'HORIZONTAL'
    sensor_width_mm = float(cam_data.sensor_width)
    cam_obj = bpy.data.objects.new("MainStudioCamera", cam_data)
    cam_obj.location = (0.0, -3.2, 1.25)
    bpy.context.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj

    track_to = cam_obj.constraints.new(type='TRACK_TO')
    track_to.target = cam_target
    track_to.track_axis = 'TRACK_NEGATIVE_Z'
    track_to.up_axis = 'UP_Y'

    # 2. Setup Lighting
    setup_lighting()

    # 3. Find and Append Background for Scene 1 (or common background)
    first_scene = scenes[0]
    bg_asset_id = first_scene.get("background", {}).get("asset_id", "bg_modern_cafe")
    bg_blend_path = os.path.join(assets_dir, "backgrounds", f"{bg_asset_id}.blend")
    if not os.path.exists(bg_blend_path):
        # Fallback to default cafe if requested does not exist
        bg_blend_path = os.path.join(assets_dir, "backgrounds", "bg_modern_cafe.blend")

    background_objects = {}
    if os.path.exists(bg_blend_path):
        log(f"Importing background: {bg_blend_path}")
        background_objects = append_blend_objects(
            bg_blend_path,
            exclude_names=["AssetCamera", "WarmFill", "WarmKey", "DayKey", "DayFill", "NeonKey", "NeonFill"],
            prefix="env"
        )

    # 4. Import Props (cafe table & cups if in cafe)
    if "cafe" in bg_asset_id or "office" in bg_asset_id:
        table_path = os.path.join(assets_dir, "props", "prop_table.blend")
        if os.path.exists(table_path):
            log("Importing prop_table")
            append_blend_objects(table_path, exclude_names=["AssetCamera", "WarmFill", "WarmKey"], prefix="prop_table")
        cup_path = os.path.join(assets_dir, "props", "prop_coffee_cup.blend")
        if os.path.exists(cup_path):
            log("Importing prop_coffee_cup")
            cup_objs = append_blend_objects(cup_path, exclude_names=["AssetCamera", "WarmFill", "WarmKey"], prefix="cup1")
            for c_obj in cup_objs.values():
                c_obj.location.x += -0.25
                c_obj.location.y += -0.15
                c_obj.location.z += 0.72

    # 5. Import Characters
    characters_meta = {c["id"]: c for c in scene_graph.get("characters", [])}
    character_maps = {}  # char_id -> dict of component objects

    for char_id in characters_meta.keys():
        char_blend_path = os.path.join(assets_dir, "characters", char_id, f"{char_id}.blend")
        if not os.path.exists(char_blend_path):
            # Check if builtin char_ali / char_ayse fallback
            alt_id = "char_ali" if "ali" in char_id.lower() else "char_ayse"
            char_blend_path = os.path.join(assets_dir, "characters", alt_id, f"{alt_id}.blend")

        if os.path.exists(char_blend_path):
            log(f"Importing character {char_id} from {char_blend_path}")
            char_map = append_blend_objects(
                char_blend_path,
                exclude_names=["StudioCamera", "KeyLight", "FillLight", "RimLight"],
                prefix=char_id
            )
            character_maps[char_id] = char_map
        else:
            log(f"Warning: Character blend file not found for {char_id}")

    report_progress(25.0, "Generating Animation Keyframes")

    # 6. Timeline and Keyframing
    current_frame = 1
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = total_frames

    framing_reports = []
    coverages = []
    BACKDROP_PLANE_Y = 5.0
    # The legacy landscape two-shot saw 2.56m of width; camera moves are kept at
    # that same share of the frame so a pan does not sweep out of shot in portrait.
    BASELINE_VISIBLE_WIDTH = 2.56

    for s_idx, scene_def in enumerate(scenes):
        scene_dur = scene_def.get("duration_seconds", 5.0)
        scene_frames = max(1, int(round(scene_dur * fps)))
        scene_start_frame = current_frame
        scene_end_frame = current_frame + scene_frames - 1

        log(f"Keyframing Scene {s_idx + 1}/{len(scenes)}: frames {scene_start_frame} to {scene_end_frame}")

        # A. Placements & Poses.
        #
        # These run before the camera is solved, because the solve has to answer
        # "where is this cast, and how tall is it" rather than assume a fixed
        # blocking that only ever worked for a landscape frame.
        placements = scene_def.get("character_placements", [])
        placed_x = [
            placement.get("position", [0.0, 0.0, 0.0])[0]
            for placement in placements
            if len(placement.get("position", [])) == 3
        ]
        centroid_x = sum(placed_x) / len(placed_x) if placed_x else 0.0
        spacing_ratio = framing_profile.horizontal_spacing_ratio
        if spacing_ratio != 1.0 and len(placed_x) > 1:
            log(
                f"Narrowing cast spacing to {spacing_ratio:.2f} for "
                f"{framing_profile.aspect_ratio} delivery"
            )

        for placement in placements:
            c_id = placement.get("character_id")
            c_map = character_maps.get(c_id)
            if not c_map:
                continue

            root_obj = None
            for name, obj in c_map.items():
                if "Root" in name:
                    root_obj = obj
                    break

            pos = scaled_placement_x(
                placement.get("position", [0.0, 0.0, 0.0]), centroid_x, spacing_ratio
            )
            rot_y = placement.get("rotation_y", 0.0)
            pose_str = placement.get("pose", "standing")
            expr_str = placement.get("expression", "neutral")

            if root_obj:
                root_obj.location = (pos[0], pos[1], pos[2])
                # In Blender coordinate system, yaw is Z rotation
                root_obj.rotation_euler.z = math.radians(rot_y)
                root_obj.keyframe_insert(data_path="location", frame=scene_start_frame)
                root_obj.keyframe_insert(data_path="rotation_euler", frame=scene_start_frame)
                # Hold the blocking until the cut. Without the closing keyframe the
                # rig lerps towards the next scene's position across the shot, and
                # the camera solve below would measure a drifting silhouette.
                root_obj.keyframe_insert(data_path="location", frame=scene_end_frame)

            apply_pose(c_map, pose_str)
            apply_expression(c_map, expr_str, scene_start_frame)

        # B. Idle Breathing, Subtle Sway, Eye Blinking across the scene
        for c_id, c_map in character_maps.items():
            torso = c_map.get("Anchor_Torso")
            head = c_map.get("Anchor_Head")
            eye_l = c_map.get("Mesh_EyeWhite_L")
            eye_r = c_map.get("Mesh_EyeWhite_R")
            pupil_l = c_map.get("Mesh_Pupil_L")
            pupil_r = c_map.get("Mesh_Pupil_R")
            mouth = c_map.get("Mesh_Mouth")

            base_torso_z = torso.location.z if torso else 0.95
            # Per-character phase/amplitude so Ali and Ayşe do not breathe in unison.
            char_hash = sum(ord(ch) for ch in c_id)
            phase_offset = (char_hash % 100) / 100.0 * math.pi * 2.0
            breath_amp = 0.010 + 0.004 * (char_hash % 5) / 5.0
            head_tilt_amp = 0.012 + 0.006 * (char_hash % 3) / 3.0

            # Step through frames at 5-frame intervals for smooth continuous curves
            for f in range(scene_start_frame, scene_end_frame + 1, 5):
                t = (f - scene_start_frame) / fps
                # Idle breathing on Torso
                if torso:
                    torso.location.z = base_torso_z + breath_amp * math.sin(t * 2.8 + phase_offset)
                    torso.rotation_euler.y = 0.006 * math.sin(t * 1.4 + phase_offset + 1.0)
                    torso.keyframe_insert(data_path="location", frame=f)
                    torso.keyframe_insert(data_path="rotation_euler", frame=f)

                # Idle subtle head tilt (per-character phase)
                if head:
                    head.rotation_euler.y = head_tilt_amp * math.cos(t * 1.2 + phase_offset + 0.5)
                    head.keyframe_insert(data_path="rotation_euler", frame=f)

            # Eye Blinks (every ~90 frames / 3 seconds), staggered per character
            blink_interval = 95
            blink_offset = (char_hash % 30)
            for blink_frame in range(scene_start_frame + 30 + blink_offset, scene_end_frame, blink_interval):
                for eye_obj in (eye_l, eye_r, pupil_l, pupil_r):
                    if eye_obj:
                        eye_obj.scale.z = 1.0
                        eye_obj.keyframe_insert(data_path="scale", frame=max(scene_start_frame, blink_frame - 1))
                        eye_obj.scale.z = 0.08
                        eye_obj.keyframe_insert(data_path="scale", frame=blink_frame + 1)
                        eye_obj.scale.z = 1.0
                        eye_obj.keyframe_insert(data_path="scale", frame=min(scene_end_frame, blink_frame + 3))

            # Resting mouth shape
            if mouth:
                mouth.scale.x = 1.0
                mouth.scale.y = 1.0
                mouth.scale.z = 1.0
                mouth.keyframe_insert(data_path="scale", frame=scene_start_frame)
                mouth.keyframe_insert(data_path="scale", frame=scene_end_frame)

        # C. Dialogue Keyframing: Mouth Flap, Gestures, Head Orientation
        dialogues = scene_def.get("dialogues", [])
        for dlg in dialogues:
            speaker_id = dlg.get("character_id")
            dlg_start = dlg.get("start_time", 0.0)
            dlg_end = dlg.get("end_time", 1.0)

            abs_start = scene_start_frame + int(round(dlg_start * fps))
            abs_end = min(scene_end_frame, scene_start_frame + int(round(dlg_end * fps)))

            speaker_map = character_maps.get(speaker_id)
            if not speaker_map:
                continue

            mouth = speaker_map.get("Mesh_Mouth")
            head = speaker_map.get("Anchor_Head")
            arm_r = speaker_map.get("Anchor_Arm_R")
            arm_l = speaker_map.get("Anchor_Arm_L")

            # Per-character variation so Ali and Ayşe do not move identically.
            spk_hash = sum(ord(ch) for ch in speaker_id)
            mouth_open_amp = 1.65 + 0.25 * (spk_hash % 3) / 3.0
            mouth_mid_amp = 0.55 + 0.15 * (spk_hash % 3) / 3.0
            # Turn direction derived from character id (not hardcoded names).
            turn_dir = 0.15 if (spk_hash % 2 == 0) else -0.15
            # Alternate which arm gestures so speakers do not move in sync.
            gesture_arm = "r" if (spk_hash % 2 == 0) else "l"

            # 1. Mouth flapping during speech
            if mouth:
                mouth.scale.z = 1.0
                mouth.keyframe_insert(data_path="scale", frame=max(scene_start_frame, abs_start - 1))
                # Flap cycle every 4 frames
                for f in range(abs_start, abs_end, 4):
                    cycle = (f - abs_start) // 4
                    # Alternate between open and medium open
                    mouth_z = mouth_open_amp if (cycle % 2 == 0) else mouth_mid_amp
                    mouth.scale.z = mouth_z
                    mouth.keyframe_insert(data_path="scale", frame=f)

                mouth.scale.z = 1.0
                mouth.keyframe_insert(data_path="scale", frame=min(scene_end_frame, abs_end + 1))

            # 2. Head turning toward partner when speaking
            if head:
                head.rotation_euler.z = turn_dir
                head.keyframe_insert(data_path="rotation_euler", frame=abs_start)
                head.keyframe_insert(data_path="rotation_euler", frame=abs_end)
                head.rotation_euler.z = 0.0
                head.keyframe_insert(data_path="rotation_euler", frame=min(scene_end_frame, abs_end + 10))

            # 3. Gesturing with one arm during speech (alternates per speaker)
            gesture_arm_obj = arm_r if gesture_arm == "r" else arm_l
            if gesture_arm_obj:
                gesture_arm_obj.rotation_euler.x = math.radians(-38)
                gesture_arm_obj.rotation_euler.z = math.radians(12 if gesture_arm == "r" else -12)
                gesture_arm_obj.keyframe_insert(data_path="rotation_euler", frame=abs_start + 4)
                gesture_arm_obj.rotation_euler.x = math.radians(-25)
                gesture_arm_obj.keyframe_insert(data_path="rotation_euler", frame=(abs_start + abs_end) // 2)
                gesture_arm_obj.rotation_euler.x = 0.0
                gesture_arm_obj.rotation_euler.z = 0.0
                gesture_arm_obj.keyframe_insert(data_path="rotation_euler", frame=min(scene_end_frame, abs_end + 8))

            # 4. Listener behavior: strict mouth rest and attentive head orientation
            for other_id, other_map in character_maps.items():
                if other_id != speaker_id:
                    # Guarantee listener's mouth does not flap during partner's speech
                    o_mouth = other_map.get("Mesh_Mouth")
                    if o_mouth:
                        o_mouth.scale.z = 1.0
                        o_mouth.keyframe_insert(data_path="scale", frame=abs_start)
                        o_mouth.keyframe_insert(data_path="scale", frame=abs_end)

                    o_head = other_map.get("Anchor_Head")
                    if o_head:
                        # Listener turns toward the speaker
                        o_turn = -turn_dir
                        o_head.rotation_euler.z = o_turn
                        o_head.keyframe_insert(data_path="rotation_euler", frame=abs_start)
                        # Small nod halfway
                        nod_f = (abs_start + abs_end) // 2
                        o_head.rotation_euler.x = 0.08
                        o_head.keyframe_insert(data_path="rotation_euler", frame=nod_f)
                        o_head.rotation_euler.x = 0.0
                        o_head.keyframe_insert(data_path="rotation_euler", frame=nod_f + 8)

        # D. Solve the camera for this shot *and* this delivery format.
        cam_setup = scene_def.get("camera", {})
        cam_angle = cam_setup.get("angle", "two_shot")
        cam_movement = cam_setup.get("movement", "static").lower()
        intent = intent_for_angle(cam_angle)
        crop = min(1.0, intent.body_crop * framing_profile.body_crop_adjust)

        sample_frames = sorted(
            {
                scene_start_frame,
                (scene_start_frame + scene_end_frame) // 2,
                scene_end_frame,
            }
        )
        cast_bounds, union_extents = measure_subject_bounds(character_maps, sample_frames)

        if union_extents:
            extents_by_id = cast_bounds
            union_box = subject_box_from_extents(union_extents, crop)
        else:
            # Nothing measurable on stage (empty cast or a failed asset import):
            # fall back to a neutral standing-person box so the shot still gets a
            # sane camera instead of a divide-by-zero distance.
            fallback = (0.0, 0.0, 0.0, 0.0, 0.0, 1.72)
            extents_by_id = {}
            union_box = subject_box_from_extents(fallback, crop)

        solve = solve_camera(framing_profile, union_box, intent, sensor_width_mm)

        cam_data.lens = solve.lens
        cam_data.keyframe_insert(data_path="lens", frame=scene_start_frame)
        cam_data.keyframe_insert(data_path="lens", frame=scene_end_frame)

        cam_target.location = (solve.target_x, 0.0, solve.target_z)
        cam_target.keyframe_insert(data_path="location", frame=scene_start_frame)
        cam_target.keyframe_insert(data_path="location", frame=scene_end_frame)

        base_loc = (solve.camera_x, solve.camera_y, solve.camera_z)
        pan_amplitude = 0.25 * (solve.visible_width / BASELINE_VISIBLE_WIDTH)
        dolly_scale = solve.distance / 3.2

        if "pan_right" in cam_movement:
            cam_obj.location = (base_loc[0] - pan_amplitude, base_loc[1], base_loc[2])
            cam_obj.keyframe_insert(data_path="location", frame=scene_start_frame)
            cam_obj.location = (base_loc[0] + pan_amplitude, base_loc[1], base_loc[2])
            cam_obj.keyframe_insert(data_path="location", frame=scene_end_frame)
        elif "pan_left" in cam_movement:
            cam_obj.location = (base_loc[0] + pan_amplitude, base_loc[1], base_loc[2])
            cam_obj.keyframe_insert(data_path="location", frame=scene_start_frame)
            cam_obj.location = (base_loc[0] - pan_amplitude, base_loc[1], base_loc[2])
            cam_obj.keyframe_insert(data_path="location", frame=scene_end_frame)
        elif "zoom_in" in cam_movement:
            cam_obj.location = (base_loc[0], base_loc[1] - 0.6 * dolly_scale, base_loc[2])
            cam_obj.keyframe_insert(data_path="location", frame=scene_start_frame)
            cam_obj.location = (base_loc[0], base_loc[1] + 0.4 * dolly_scale, base_loc[2])
            cam_obj.keyframe_insert(data_path="location", frame=scene_end_frame)
        elif "zoom_out" in cam_movement:
            cam_obj.location = (base_loc[0], base_loc[1] + 0.3 * dolly_scale, base_loc[2])
            cam_obj.keyframe_insert(data_path="location", frame=scene_start_frame)
            cam_obj.location = (base_loc[0], base_loc[1] - 0.5 * dolly_scale, base_loc[2])
            cam_obj.keyframe_insert(data_path="location", frame=scene_end_frame)
        else:  # static
            cam_obj.location = base_loc
            cam_obj.keyframe_insert(data_path="location", frame=scene_start_frame)
            cam_obj.keyframe_insert(data_path="location", frame=scene_end_frame)

        wall_x0, wall_x1, wall_z0, wall_z1 = visible_extents_at_plane(
            framing_profile, solve, BACKDROP_PLANE_Y, sensor_width_mm
        )
        coverages.append(
            (
                wall_x0,
                wall_x1,
                max(0.0, wall_z0),
                wall_z1,
                solve.camera_y - 0.5,
                BACKDROP_PLANE_Y + 1.0,
            )
        )

        framing_reports.append(
            {
                "scene_id": scene_def.get("scene_id", f"scene_{s_idx + 1:02d}"),
                "format": framing_profile.aspect_ratio,
                "profile": framing_profile.key,
                "camera_angle": cam_angle,
                "shot": intent.key,
                "body_crop": round(crop, 3),
                # Every rig imported into the shot is measured, including one this
                # scene never re-placed: it is still on stage, so the camera must
                # keep it in frame too. ``placed`` records the authored blocking.
                "placed": sorted(
                    str(p.get("character_id", "")) for p in placements
                ),
                "cast": sorted(extents_by_id),
                "solve": solve.to_dict(),
                "screen_boxes": {
                    char_id: screen_box(
                        framing_profile, solve, subject_box_from_extents(extents, crop)
                    )
                    for char_id, extents in sorted(extents_by_id.items())
                },
            }
        )

        log(
            f"Framed {intent.key} for {framing_profile.aspect_ratio}: "
            f"lens={solve.lens:.1f}mm distance={solve.distance:.2f}m "
            f"limited_by={solve.limited_by} fits_safe_area={solve.fits} "
            f"fill_w={solve.fill_width} fill_h={solve.fill_height}"
        )
        if not solve.fits:
            log(
                f"WARNING: scene '{scene_def.get('scene_id')}' cannot fill the "
                f"{framing_profile.aspect_ratio} safe area from the rig limits; "
                "the cast stays fully visible but the shot is looser than intended."
            )

        current_frame = scene_end_frame + 1

    # 7. Grow the set so the solved camera never sees past it. A portrait frame
    # has roughly three times the vertical field of view of the same lens in
    # landscape, and whatever that extra field exposes has to be scenery, not the
    # black world background.
    required_coverage = merge_bounds(coverages)
    if required_coverage:
        bpy.context.view_layer.update()
        adjusted = expand_backdrop_for_frame(background_objects, required_coverage)
        if adjusted:
            log(
                f"Extended {framing_profile.aspect_ratio} set coverage: "
                + ", ".join(sorted(adjusted))
            )

    bpy.context.scene.frame_set(1)

    # 8. Save populated Blender scene file for reproducibility
    if scene_save_path:
        os.makedirs(os.path.dirname(scene_save_path), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=scene_save_path)
        log(f"Saved populated Blender scene to {scene_save_path}")

    report_progress(40.0, "Configuring Render Engine")

    # 9. Configure Render Engine
    scene = bpy.context.scene
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.fps = fps
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'

    engine_clean = (engine_override or "BLENDER_WORKBENCH").upper()
    if "EEVEE" in engine_clean:
        # Check if BLENDER_EEVEE_NEXT or BLENDER_EEVEE exists
        try:
            scene.render.engine = 'BLENDER_EEVEE_NEXT'
        except Exception:
            scene.render.engine = 'BLENDER_EEVEE'
    else:
        scene.render.engine = 'BLENDER_WORKBENCH'
        scene.display.shading.light = 'STUDIO'
        scene.display.shading.color_type = 'MATERIAL'
        scene.display.shading.show_shadows = True
        scene.display.render_aa = 'FXAA'

    os.makedirs(frames_dir, exist_ok=True)
    frame_prefix = os.path.join(frames_dir, "frame_")
    scene.render.filepath = frame_prefix

    log(f"Starting frame rendering ({total_frames} frames) using {scene.render.engine}...")
    report_progress(50.0, f"Rendering {total_frames} frames headless")

    # Hook frame render callback to report progress
    def frame_post_handler(sc):
        f = sc.frame_current
        pct = 50.0 + (f / max(1, total_frames)) * 35.0
        report_progress(pct, f"Rendered frame {f}/{total_frames}")

    bpy.app.handlers.render_post.append(frame_post_handler)

    # 10. Render Animation
    bpy.ops.render.render(animation=True)

    log("Headless frame rendering complete!")
    report_progress(85.0, "Frame rendering finished")

    # Write output summary json
    result_data = {
        "status": "SUCCESS",
        "total_frames": total_frames,
        "width": width,
        "height": height,
        "fps": fps,
        "duration_seconds": total_duration,
        "engine": scene.render.engine,
        "frames_dir": frames_dir,
        "scene_path": scene_save_path,
        "framing": {
            "profile": framing_profile.key,
            "aspect_ratio": framing_profile.aspect_ratio,
            "safe_area": {
                "top": framing_profile.safe.top,
                "bottom": framing_profile.safe.bottom,
                "left": framing_profile.safe.left,
                "right": framing_profile.safe.right,
            },
            "scenes": framing_reports,
        },
    }
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2)

    log(f"Result metadata written to {result_path}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"ERROR in Blender Worker: {e}")
        traceback.print_exc()
        sys.exit(2)
