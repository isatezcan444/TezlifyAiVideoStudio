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

from tezlify_studio.domain.enums.studio_status import MouthViseme
from tezlify_studio.domain.services import animation_director, animation_layers
from tezlify_studio.domain.services.mouth_poses import pose_for as mouth_pose_for
from tezlify_studio.domain.value_objects.animation_plan import (  # noqa: E402
    AnimationPlan,
    CharacterAnimationProfile,
    to_dict as animation_plan_to_dict,
)
from tezlify_studio.infrastructure.blender.character_rig import (  # noqa: E402
    build_control_map,
    capture_rest,
    control_inventory,
    prepare_joint_pivots,
    set_interpolation,
    write_pose,
)
from tezlify_studio.domain.value_objects.camera_framing import (  # noqa: E402
    SubjectBounds,
    intent_for_angle,
    intent_by_key,
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

# Lights baked into the scene/prop .blend assets. The worker always installs its
# own three-point rig, so every asset light has to be dropped on import; the
# previous list missed NeonCyan/NeonPink/DaylightSun/SkyFill, which are exactly
# the names blender_scene_asset_builder creates, so those four were being added
# on top of the rig and double-lighting every shot.
ASSET_LIGHT_NAMES = [
    "AssetCamera", "StudioCamera",
    "WarmKey", "WarmFill", "DayKey", "DayFill",
    "NeonKey", "NeonFill", "NeonCyan", "NeonPink",
    "DaylightSun", "SkyFill",
    "KeyLight", "FillLight", "RimLight",
]


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


def linear_to_srgb(c):
    """Shader colours are scene-linear; viewport display colours are not.

    Copying the Principled BSDF value straight into `viewport_display_color`
    measured 4.0 mean saturation instead of EEVEE's 60.7, because the linear
    numbers are both darker and less saturated than the sRGB encoding Workbench
    expects. Converting first makes the two engines agree.
    """
    def one(v):
        v = max(0.0, min(1.0, v))
        return 12.92 * v if v <= 0.0031308 else 1.055 * (v ** (1.0 / 2.4)) - 0.055
    return (one(c[0]), one(c[1]), one(c[2]), c[3] if len(c) > 3 else 1.0)


def sync_material_display_colors():
    """Copy each material's shader colour into the fields Workbench reads.

    Workbench with `shading.color_type = 'MATERIAL'` does not evaluate the node
    tree; it reads `viewport_display_color` (falling back to `diffuse_color`),
    and both stay at Blender's default (0.8, 0.8, 0.8) unless something writes
    them. The asset builder only ever sets Principled BSDF Base Color, which is
    why every delivered MP4 came out as grey clay while Character Studio, which
    shows a pre-rendered PNG, looked correctly coloured.

    Doing this here rather than only in the builder also repairs the ~25 .blend
    assets that already exist, without regenerating any of them.
    """
    report = {"materials": 0, "synced": 0, "no_base_color": []}
    for mat in bpy.data.materials:
        report["materials"] += 1
        base = None
        if mat.use_nodes and mat.node_tree:
            for node in mat.node_tree.nodes:
                if node.type == 'BSDF_PRINCIPLED':
                    # A colour socket reports type 'RGBA', not 'VALUE'; the only
                    # case with no constant to copy is a linked input.
                    input_socket = node.inputs.get("Base Color")
                    if input_socket is not None and not input_socket.is_linked:
                        base = tuple(input_socket.default_value)
                    break
        if base is None:
            # Linked or missing base colour: leave the asset's own colour alone.
            report["no_base_color"].append(mat.name)
            continue
        mat.diffuse_color = linear_to_srgb(base)
        try:
            mat.viewport_display_color = linear_to_srgb(base)
        except Exception:
            # Not every Blender build exposes the viewport colour; diffuse is
            # what Workbench actually falls back to, so the sync still holds.
            pass
        report["synced"] += 1
    return report


def setup_world_ambient(strength: float = 0.35, color=(0.92, 0.95, 1.0)):
    """Soft ambient fill so EEVEE does not flatten the characters into silhouettes."""
    world = bpy.context.scene.world or bpy.data.worlds.new("StudioWorld")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg is None:
        bg = world.node_tree.nodes.new('ShaderNodeBackground')
    bg.inputs["Color"].default_value = (*color, 1.0)
    bg.inputs["Strength"].default_value = strength
    return strength

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

# ---------------------------------------------------------------------------
# Lip sync (Stage 5.4)
# ---------------------------------------------------------------------------

MEASURED_SOURCES = ("ctc_forced", "elevenlabs_timing")


def measured_visemes(dlg: dict) -> list:
    """Viseme segments whose timing came from the dialogue audio.

    Segments written before this stage, or by the story planner's placeholder
    generator, carry no measured source and are ignored so the renderer can fall
    back to the legacy flap instead of animating to invented timings.
    """
    segments = []
    for item in dlg.get("visemes") or []:
        if str(item.get("source", "")) not in MEASURED_SOURCES:
            continue
        start = item.get("time")
        end = item.get("end_time")
        viseme = item.get("viseme")
        if start is None or end is None or not viseme:
            continue
        segments.append((str(viseme), float(start), float(end)))
    segments.sort(key=lambda s: s[1])
    return segments


def set_mouth_pose(mouth, pose, rest_scale, rest_location, frame: int):
    """Keyframe one viseme pose at one frame.

    Everything is relative to the character's own rest transform, which differs by
    gender and expression, so Ali and Ayşe keep their distinct mouths.
    """
    mouth.scale = (
        rest_scale[0] * pose.width_scale,
        rest_scale[1] * pose.open_scale,
        rest_scale[2],
    )
    mouth.location = (
        rest_location[0],
        rest_location[1],
        rest_location[2] + pose.jaw_offset,
    )
    mouth.keyframe_insert(data_path="scale", frame=frame)
    mouth.keyframe_insert(data_path="location", frame=frame)


def use_linear_mouth_interpolation(mouth) -> None:
    """Linear easing between visemes.

    Bezier overshoot would push the mouth past both neighbouring poses, which can
    carry the mesh outside the face and makes a short vowel look like a pop.
    """
    try:
        action = mouth.animation_data.action if mouth.animation_data else None
        if not action:
            return
        for curve in action.fcurves:
            if curve.data_path in ("scale", "location"):
                for key in curve.keyframe_points:
                    key.interpolation = "LINEAR"
    except Exception:
        # Interpolation is cosmetic; never fail a render over it.
        pass


def animate_dialogue_mouth(mouth, rest_scale, rest_location, segments, fps: int,
                           abs_start: int, abs_end: int,
                           scene_start_frame: int, scene_end_frame: int) -> list:
    """Keyframe measured viseme segments across one dialogue.

    Returns the frames that were keyed, empty when there is nothing measured.
    Those frames are also what the evidence samples, so the inspected frames are
    the ones where the mouth is guaranteed to change rather than arbitrary ones.

    Segment times are seconds relative to the dialogue start, the same reference
    the aligner produced them in, so the only offset applied here is the dialogue's
    own position in the scene. Applying a scene offset as well would push the mouth
    ahead of the voice by everything that came before it.
    """
    if not segments:
        return []

    keyed = []

    # Mouth closed just before speech begins, so the first viseme reads as an
    # opening movement rather than an instant pop. This must be the CLOSED
    # viseme, not REST: REST is the asset's own mouth, which is modelled with the
    # lips slightly apart and reads as an open mouth in a close-up.
    frame = max(scene_start_frame, abs_start - 1)
    set_mouth_pose(mouth, mouth_pose_for(MouthViseme.CLOSED), rest_scale, rest_location, frame)
    keyed.append(frame)

    for viseme_name, start, end in segments:
        if end <= start:
            continue
        frame = abs_start + int(round(start * fps))
        if frame < abs_start or frame > scene_end_frame:
            continue
        set_mouth_pose(mouth, mouth_pose_for(viseme_name), rest_scale, rest_location, frame)
        keyed.append(frame)

    # Close the mouth as soon as the audio ends: a held-open vowel after the last
    # phoneme is the clearest sign that animation is not following speech.
    frame = min(scene_end_frame, abs_end)
    set_mouth_pose(mouth, mouth_pose_for(MouthViseme.CLOSED), rest_scale, rest_location, frame)
    keyed.append(frame)

    use_linear_mouth_interpolation(mouth)
    return keyed


def mouth_screen_boxes(character_maps: dict, frames, profile, solve,
                       sensor_width_mm: float) -> dict:
    """Project each speaker's mouth into frame coordinates at the given frames.

    Evidence has to crop the mouth, not a guessed rectangle: in a 9:16 two-shot a
    hand-picked box misses the face entirely and measures nothing. This reuses the
    same projection the camera solve is reported with, so the box is the one the
    renderer actually produced.
    """
    sampled = {}
    for frame in frames:
        bpy.context.scene.frame_set(int(frame))
        bpy.context.view_layer.update()
        per_character = {}
        for char_id, char_map in character_maps.items():
            mouth = char_map.get("Mesh_Mouth")
            if mouth is None:
                continue
            box = object_world_bounds(mouth)
            if not box:
                continue
            bounds = SubjectBounds(
                x_min=box[0], x_max=box[1], z_top=box[5], z_bottom=box[4]
            )
            per_character[char_id] = {
                "frame": int(frame),
                "screen": screen_box(profile, solve, bounds),
                "world_height_m": round(box[5] - box[4], 5),
                "world_width_m": round(box[1] - box[0], 5),
            }
        if per_character:
            sampled[str(int(frame))] = per_character
    return sampled


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
            exclude_names=ASSET_LIGHT_NAMES,
            prefix="env"
        )

    # 4. Import Props (cafe table & cups if in cafe)
    if "cafe" in bg_asset_id or "office" in bg_asset_id:
        table_path = os.path.join(assets_dir, "props", "prop_table.blend")
        if os.path.exists(table_path):
            log("Importing prop_table")
            append_blend_objects(table_path, exclude_names=ASSET_LIGHT_NAMES, prefix="prop_table")
        cup_path = os.path.join(assets_dir, "props", "prop_coffee_cup.blend")
        if os.path.exists(cup_path):
            log("Importing prop_coffee_cup")
            cup_objs = append_blend_objects(cup_path, exclude_names=ASSET_LIGHT_NAMES, prefix="cup1")
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
                exclude_names=ASSET_LIGHT_NAMES,
                prefix=char_id
            )
            character_maps[char_id] = char_map
        else:
            log(f"Warning: Character blend file not found for {char_id}")

    report_progress(25.0, "Generating Animation Keyframes")

    # 6. Capture each rig's authentic rest mouth transform before anything
    # keyframes it. The built mouth differs per gender and expression (cheerful is
    # wider than neutral), and viseme poses are multipliers on this rest, so
    # capturing it late would key every character to the same invented face.
    rest_mouth = {}
    rest_teeth = {}
    for char_id, char_map in character_maps.items():
        mouth_obj = char_map.get("Mesh_Mouth")
        if mouth_obj is not None:
            rest_mouth[char_id] = (
                tuple(mouth_obj.scale),
                tuple(mouth_obj.location),
            )
            # The mouth is a flat disc a few millimetres proud of the face. Its
            # cast shadow is the black crescent that made a closed mouth read as
            # open in every close-up, so it never casts one.
            mouth_obj.visible_shadow = False
        teeth_obj = char_map.get("Mesh_Teeth")
        if teeth_obj is not None:
            rest_teeth[char_id] = tuple(teeth_obj.scale)

    # 6. Timeline and Keyframing
    current_frame = 1
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = total_frames

    framing_reports = []
    lip_sync_reports = []
    animation_reports = []
    coverages = []
    BACKDROP_PLANE_Y = 5.0
    # The legacy landscape two-shot saw 2.56m of width; camera moves are kept at
    # that same share of the frame so a pan does not sweep out of shot in portrait.
    BASELINE_VISIBLE_WIDTH = 2.56

    # 6b. Rig setup: resolve controls, turn the forearm/hand meshes into real
    # elbow/wrist joints, and record what this asset actually exposes.
    rigs = {}
    for char_id, char_map in character_maps.items():
        controls = build_control_map(char_map)
        repivoted = prepare_joint_pivots(controls)
        rigs[char_id] = {
            "controls": controls,
            "inventory": control_inventory(controls),
            "repivoted": repivoted,
            "profile": CharacterAnimationProfile.for_character(char_id),
        }
        log(f"{char_id}: {len(controls)} controls, elbow/wrist pivots set on {repivoted}")

    # 6c. The animation plan. Built from the same SceneGraph the camera and the
    # lip sync use, so gestures follow the script instead of being invented here.
    animation_plan = None
    try:
        scene_plans, plan_profiles = animation_director.plan_scene_graph(
            scene_graph, {c: r["profile"] for c, r in rigs.items()}
        )
        animation_plan = AnimationPlan(
            project_id=scene_graph.get("project_id", ""),
            fps=fps,
            scenes=tuple(scene_plans),
            profiles=plan_profiles,
        )
        animation_plan.validate()
        summary = animation_plan.summary()
        log(f"Animation plan: {summary['clips_total']} clips, "
            f"{summary['distinct_clips']} distinct, {summary['gestures']} gestures, "
            f"{summary['dropped_gestures']} dropped")
    except Exception as exc:
        # A missing plan must not kill a render: fall back to the pre-5.5 idle so
        # old projects still produce a video, and say so in the result.
        animation_plan = None
        log(f"Animation plan unavailable ({exc}); using legacy idle")

    for s_idx, scene_def in enumerate(scenes):
        scene_dur = scene_def.get("duration_seconds", 5.0)
        scene_frames = max(1, int(round(scene_dur * fps)))
        scene_start_frame = current_frame
        scene_end_frame = current_frame + scene_frames - 1

        log(f"Keyframing Scene {s_idx + 1}/{len(scenes)}: frames {scene_start_frame} to {scene_end_frame}")
        lip_sync_modes = {}

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

        placed_ids = set()
        for placement in placements:
            c_id = placement.get("character_id")
            c_map = character_maps.get(c_id)
            if not c_map:
                continue
            placed_ids.add(c_id)

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

        # The rest pose is captured per scene, after placement, base pose and
        # expression have been applied, because every clip channel is a delta on
        # top of it. Capturing it earlier would animate the character back to the
        # asset's neutral instead of to the pose this scene asked for.
        for c_id, rig in rigs.items():
            if c_id in placed_ids:
                rig["rest"] = capture_rest(rig["controls"])

        # B. Plan-driven animation.
        #
        # Replaces the old three-sine idle. Each frame samples the character's
        # own scheduled clips, blended by priority, scaled by that character's
        # personality profile, and written as absolute transforms against the
        # scene's rest pose.
        scene_plan = animation_plan.scenes[s_idx] if animation_plan else None
        key_step = max(1, int(round(fps / 15.0)))
        EPSILON = 1e-4

        def _channel_moved(base, values, scale_mode=False):
            for b, v in zip(base, values):
                if abs((v - b) if not scale_mode else (v - 1.0)) > EPSILON:
                    return True
            return False

        for c_id, rig in rigs.items():
            if "rest" not in rig:
                continue
            controls, rest = rig["controls"], rig["rest"]
            targets = sorted(controls)
            instances = scene_plan.clips_for(c_id) if scene_plan else ()
            moved_keys = 0
            for f in list(range(scene_start_frame, scene_end_frame + 1, key_step)) + [scene_end_frame]:
                t = (f - scene_start_frame) / fps
                pose = animation_layers.sample_tracks(
                    instances, rig["profile"], t, targets, skip_mouth=True
                )
                animation_layers.apply_blink(pose, f, rig["profile"])
                # Only key the controls that actually differ from rest, plus one
                # final keyframe to bring a moved control back so it cannot be
                # left mid-gesture at the cut.
                for control in targets:
                    if control == "mouth":
                        continue
                    channels = pose.get(control)
                    if not channels:
                        continue
                    base_loc, base_rot, base_scale = rest[control]
                    moved = (
                        _channel_moved(base_loc, [base_loc[i] + channels["loc"][i] for i in range(3)])
                        or _channel_moved(base_rot, [base_rot[i] + channels["rot"][i] for i in range(3)])
                        or _channel_moved(base_scale, [base_scale[i] * channels["scale"][i] for i in range(3)], True)
                    )
                    if not moved:
                        continue
                    moved_keys += 1
                    write_pose(controls, rest, {control: channels}, f)
            animation_reports.append({
                "character_id": c_id,
                "scene_id": scene_def.get("scene_id", ""),
                "clips": len(instances),
                "keyed_channels": moved_keys,
                "controls": sorted(controls),
                "profile": {
                    "energy": round(rig["profile"].energy, 3),
                    "gesture_rate": round(rig["profile"].gesture_rate, 3),
                    "head_mobility": round(rig["profile"].head_mobility, 3),
                    "leading_hand": rig["profile"].hand_bias,
                    "blink_offset_frames": rig["profile"].blink_offset_frames,
                },
            })

        if animation_plan is None:
            # Legacy path kept for projects whose plan could not be built.
            for c_id, c_map in character_maps.items():
                torso = c_map.get("Anchor_Torso")
                head = c_map.get("Anchor_Head")
                if torso is None and head is None:
                    continue
                char_hash = sum(ord(ch) for ch in c_id)
                phase_offset = (char_hash % 100) / 100.0 * math.pi * 2.0
                base_torso_z = torso.location.z if torso else 0.95
                for f in range(scene_start_frame, scene_end_frame + 1, 5):
                    t = (f - scene_start_frame) / fps
                    if torso:
                        torso.location.z = base_torso_z + 0.010 * math.sin(t * 2.8 + phase_offset)
                        torso.keyframe_insert(data_path="location", frame=f)
                    if head:
                        head.rotation_euler.y = 0.012 * math.cos(t * 1.2 + phase_offset + 0.5)
                        head.keyframe_insert(data_path="rotation_euler", frame=f)

        # Eye blink for the legacy path only; the plan path folds it in above.
        if animation_plan is None:
            for c_id, c_map in character_maps.items():
                char_hash = sum(ord(ch) for ch in c_id)
                blink_offset = (char_hash % 30)
                for blink_frame in range(scene_start_frame + 30 + blink_offset, scene_end_frame, 95):
                    for eye_name in ("Mesh_EyeWhite_L", "Mesh_EyeWhite_R", "Mesh_Pupil_L", "Mesh_Pupil_R"):
                        eye_obj = c_map.get(eye_name)
                        if not eye_obj:
                            continue
                        eye_obj.scale.z = 1.0
                        eye_obj.keyframe_insert(data_path="scale", frame=max(scene_start_frame, blink_frame - 1))
                        eye_obj.scale.z = 0.08
                        eye_obj.keyframe_insert(data_path="scale", frame=blink_frame + 1)
                        eye_obj.scale.z = 1.0
                        eye_obj.keyframe_insert(data_path="scale", frame=min(scene_end_frame, blink_frame + 3))

        # B2. Mouth baseline. Clips never write the mouth, so visemes and the
        # fallback flap are the only mouth sources. Silent characters are keyed
        # to the CLOSED viseme for the whole scene: the asset's built rest mouth
        # has parted lips and looks open in a close-up, so a listener held at
        # rest reads as if they were talking too.
        for c_id, c_map in character_maps.items():
            mouth = c_map.get("Mesh_Mouth")
            if not mouth:
                continue
            rest = rest_mouth.get(c_id)
            if not rest:
                continue
            closed = mouth_pose_for(MouthViseme.CLOSED)
            for frame in (scene_start_frame, scene_end_frame):
                set_mouth_pose(mouth, closed, rest[0], rest[1], frame)

            # The teeth strip peeks above the upper lip, so a silent character
            # with teeth at full size still reads as slightly open. Shrink it
            # while silent; the dialogue pass restores it for speech.
            teeth = c_map.get("Mesh_Teeth")
            t_rest = rest_teeth.get(c_id)
            if teeth is not None and t_rest:
                teeth.scale = tuple(value * 0.001 for value in t_rest)
                for frame in (scene_start_frame, scene_end_frame):
                    teeth.keyframe_insert(data_path="scale", frame=frame)

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

            # Teeth are part of what makes an open mouth read as open; bring
            # them back for the line and shrink them again on either side.
            teeth = speaker_map.get("Mesh_Teeth")
            t_rest = rest_teeth.get(speaker_id)
            if teeth is not None and t_rest:
                tiny = tuple(value * 0.001 for value in t_rest)
                teeth.scale = tiny
                teeth.keyframe_insert(data_path="scale", frame=max(scene_start_frame, abs_start - 1))
                teeth.scale = t_rest
                teeth.keyframe_insert(data_path="scale", frame=abs_start)
                teeth.keyframe_insert(data_path="scale", frame=abs_end)
                teeth.scale = tiny
                teeth.keyframe_insert(data_path="scale", frame=min(scene_end_frame, abs_end + 1))

            # Per-character variation so Ali and Ayşe do not flap identically.
            spk_hash = sum(ord(ch) for ch in speaker_id)
            mouth_open_amp = 1.65 + 0.25 * (spk_hash % 3) / 3.0
            mouth_mid_amp = 0.55 + 0.15 * (spk_hash % 3) / 3.0

            # 1. Mouth. Measured visemes drive it when the dialogue audio was
            # aligned; otherwise the pre-5.4 flap cycle is kept so a render never
            # fails because an aligner was unavailable.
            if mouth:
                rest = rest_mouth.get(speaker_id, (tuple(mouth.scale), tuple(mouth.location)))
                segments = measured_visemes(dlg)
                keyed = animate_dialogue_mouth(
                    mouth, rest[0], rest[1], segments, fps,
                    abs_start, abs_end, scene_start_frame, scene_end_frame,
                )
                if keyed:
                    lip_sync_modes[speaker_id] = {
                        "mode": "viseme",
                        "segments": len(segments),
                        "keyframes": len(keyed),
                        "frames": keyed,
                        "source": str((dlg.get("visemes") or [{}])[0].get("source", "")),
                    }
                else:
                    lip_sync_modes[speaker_id] = {
                        "mode": "legacy_flap",
                        "segments": len(segments),
                        "keyframes": 0,
                        "frames": [],
                        "source": "estimated",
                    }
                    # The mouth mesh is rotated, so its local Y is the vertical
                    # opening axis. This used to scale Z (depth) and therefore
                    # barely moved the mouth at all. Amplitudes are relative to
                    # the character's built rest, like the viseme poses.
                    rest_y = rest[0][1]
                    mouth.scale.y = rest_y * 0.62
                    mouth.keyframe_insert(data_path="scale", frame=max(scene_start_frame, abs_start - 1))
                    # Flap cycle every 4 frames
                    for f in range(abs_start, abs_end, 4):
                        cycle = (f - abs_start) // 4
                        # Alternate between open and medium open
                        mouth_y = mouth_open_amp if (cycle % 2 == 0) else mouth_mid_amp
                        mouth.scale.y = rest_y * mouth_y
                        mouth.keyframe_insert(data_path="scale", frame=f)

                    mouth.scale.y = rest_y * 0.62
                    mouth.keyframe_insert(data_path="scale", frame=min(scene_end_frame, abs_end + 1))

            # 2. Mouth easing. Viseme transitions must not overshoot, or a short
            # vowel pops and the mesh can leave the face. Stage 5.4 tried this
            # through `action.fcurves`, which Blender 5.2 removed, so it silently
            # did nothing; this uses the current API and reports the count.
            eased = set_interpolation(mouth, ("scale", "location"), "LINEAR")
            if eased == 0 and mouth is not None:
                log(f"{speaker_id}: could not set LINEAR mouth easing")

            # 3. The listener's mouth is held at the CLOSED viseme through the
            # partner's line. Body and head behaviour for the listener now comes
            # from the animation plan; only the mouth is deliberately excluded.
            closed = mouth_pose_for(MouthViseme.CLOSED)
            for other_id, other_map in character_maps.items():
                if other_id == speaker_id:
                    continue
                o_mouth = other_map.get("Mesh_Mouth")
                if not o_mouth:
                    continue
                o_rest = rest_mouth.get(other_id)
                if not o_rest:
                    continue
                for frame in (abs_start, abs_end):
                    set_mouth_pose(o_mouth, closed, o_rest[0], o_rest[1], frame)

                o_teeth = other_map.get("Mesh_Teeth")
                o_t_rest = rest_teeth.get(other_id)
                if o_teeth is not None and o_t_rest:
                    o_teeth.scale = tuple(value * 0.001 for value in o_t_rest)
                    for frame in (abs_start, abs_end):
                        o_teeth.keyframe_insert(data_path="scale", frame=frame)

        # D. Solve the camera per shot *and* per delivery format.
        cam_setup = scene_def.get("camera", {})
        cam_angle = cam_setup.get("angle", "two_shot")
        cam_movement = cam_setup.get("movement", "static").lower()

        # D2. Shot-by-shot camera solve.
        #
        # The plan already decided *what the audience should look at*; this turns
        # that into lens and position per shot window instead of one framing for
        # the whole scene. Every window is solved with the same Stage 5.3 solver,
        # so a close-up cannot push a character out of the safe area any more
        # than a two-shot could.
        shots = list(scene_plan.shot_plan.shots) if scene_plan else []
        if not shots:
            shots = [None]  # un-planned path: one authored framing for the scene

        shot_solves = []
        for shot in shots:
            if shot is None:
                shot_start, shot_end = scene_start_frame, scene_end_frame
                focus_id = None
                intent = intent_for_angle(cam_angle)
                shot_kind = cam_angle
            else:
                shot_start = min(scene_end_frame, scene_start_frame + int(round(shot.start * fps)))
                shot_end = max(shot_start, min(scene_end_frame,
                                               scene_start_frame + int(round(shot.end * fps)) - 1))
                focus_id = shot.focus_character_id
                shot_kind = shot.kind
                if shot.kind == "establishing":
                    intent = intent_by_key("wide")
                elif shot.kind == "speaker_close_up":
                    intent = intent_by_key("close_up")
                elif shot.kind == "listener_reaction":
                    intent = intent_by_key("shoulder")
                elif shot.kind == "action_shot":
                    intent = intent_by_key("medium_shot")
                else:
                    intent = intent_for_angle(cam_angle)

            crop = min(1.0, intent.body_crop * framing_profile.body_crop_adjust)
            shot_samples = sorted({shot_start, (shot_start + shot_end) // 2, shot_end})
            cast_bounds, union_extents = measure_subject_bounds(character_maps, shot_samples)

            if focus_id and focus_id in cast_bounds:
                # Restrict the subject to the focused character, then keep the
                # rest of the cast inside the frame as a soft constraint by
                # widening toward them only if they are close.
                extents = cast_bounds[focus_id]
                others = [e for cid, e in cast_bounds.items() if cid != focus_id]
                if others and shot.kind in ("two_shot", "establishing", "medium_shot",
                                           "action_shot"):
                    extents = merge_bounds([extents, others[0]])
            elif union_extents:
                extents = union_extents
            else:
                extents = (0.0, 0.0, 0.0, 0.0, 0.0, 1.72)

            subject_box = subject_box_from_extents(extents, crop)
            solve = solve_camera(framing_profile, subject_box, intent, sensor_width_mm)

            cam_data.lens = solve.lens
            cam_data.keyframe_insert(data_path="lens", frame=shot_start)
            cam_data.keyframe_insert(data_path="lens", frame=shot_end)

            cam_target.location = (solve.target_x, 0.0, solve.target_z)
            cam_target.keyframe_insert(data_path="location", frame=shot_start)
            cam_target.keyframe_insert(data_path="location", frame=shot_end)

            base_loc = (solve.camera_x, solve.camera_y, solve.camera_z)
            pan_amplitude = 0.25 * (solve.visible_width / BASELINE_VISIBLE_WIDTH)
            dolly_scale = solve.distance / 3.2
            # A cut-in gets a slow push so the shot is not a still frame; the
            # authored movement still applies to whole-scene shots.
            movement = cam_movement if shot is None else "push_in"
            if "pan_right" in movement:
                cam_obj.location = (base_loc[0] - pan_amplitude, base_loc[1], base_loc[2])
                cam_obj.keyframe_insert(data_path="location", frame=shot_start)
                cam_obj.location = (base_loc[0] + pan_amplitude, base_loc[1], base_loc[2])
                cam_obj.keyframe_insert(data_path="location", frame=shot_end)
            elif "pan_left" in movement:
                cam_obj.location = (base_loc[0] + pan_amplitude, base_loc[1], base_loc[2])
                cam_obj.keyframe_insert(data_path="location", frame=shot_start)
                cam_obj.location = (base_loc[0] - pan_amplitude, base_loc[1], base_loc[2])
                cam_obj.keyframe_insert(data_path="location", frame=shot_end)
            elif "zoom_in" in movement or movement == "push_in":
                cam_obj.location = (base_loc[0], base_loc[1] + 0.18 * dolly_scale, base_loc[2])
                cam_obj.keyframe_insert(data_path="location", frame=shot_start)
                cam_obj.location = (base_loc[0], base_loc[1] - 0.18 * dolly_scale, base_loc[2])
                cam_obj.keyframe_insert(data_path="location", frame=shot_end)
            elif "zoom_out" in movement:
                cam_obj.location = (base_loc[0], base_loc[1] + 0.3 * dolly_scale, base_loc[2])
                cam_obj.keyframe_insert(data_path="location", frame=shot_start)
                cam_obj.location = (base_loc[0], base_loc[1] - 0.5 * dolly_scale, base_loc[2])
                cam_obj.keyframe_insert(data_path="location", frame=shot_end)
            else:
                cam_obj.location = base_loc
                cam_obj.keyframe_insert(data_path="location", frame=shot_start)
                cam_obj.keyframe_insert(data_path="location", frame=shot_end)

            wall_x0, wall_x1, wall_z0, wall_z1 = visible_extents_at_plane(
                framing_profile, solve, BACKDROP_PLANE_Y, sensor_width_mm
            )
            coverages.append(
                (wall_x0, wall_x1, max(0.0, wall_z0), wall_z1,
                 solve.camera_y - 0.5, BACKDROP_PLANE_Y + 1.0)
            )

            shot_solves.append((shot_start, shot_end, solve))
            framing_reports.append(
                {
                    "scene_id": scene_def.get("scene_id", f"scene_{s_idx + 1:02d}"),
                    "format": framing_profile.aspect_ratio,
                    "profile": framing_profile.key,
                    "camera_angle": cam_angle,
                    "shot": intent.key,
                    "shot_kind": shot_kind,
                    "shot_focus": focus_id,
                    "window_frames": [shot_start, shot_end],
                    "body_crop": round(crop, 3),
                    # Every rig imported into the shot is measured, including one this
                    # scene never re-placed: it is still on stage, so the camera must
                    # keep it in frame too. ``placed`` records the authored blocking.
                    "placed": sorted(str(p.get("character_id", "")) for p in placements),
                    "cast": sorted(cast_bounds),
                    "solve": solve.to_dict(),
                    "screen_boxes": {
                        char_id: screen_box(
                            framing_profile, solve,
                            subject_box_from_extents(extents_one, crop),
                        )
                        for char_id, extents_one in sorted(cast_bounds.items())
                    },
                }
            )
            log(
                f"Framed {shot_kind} for {framing_profile.aspect_ratio}: "
                f"lens={solve.lens:.1f}mm distance={solve.distance:.2f}m "
                f"limited_by={solve.limited_by} fits_safe_area={solve.fits} "
                f"fill_w={solve.fill_width} fill_h={solve.fill_height}"
            )
            if not solve.fits:
                log(
                    f"WARNING: scene '{scene_def.get('scene_id')}' shot '{shot_kind}' "
                    f"cannot fill the {framing_profile.aspect_ratio} safe area from the "
                    "rig limits; the cast stays visible but the shot is looser than intended."
                )

        # Where the mouth actually lands on screen, at the frames where a viseme
        # was keyed, using the camera solve that is active in that window.
        evidence_frames = sorted({
            frame
            for mode in lip_sync_modes.values()
            for frame in mode.get("frames", [])
        })
        mouth_boxes = {}
        for shot_start, shot_end, solve in shot_solves:
            in_window = [f for f in evidence_frames if shot_start <= f <= shot_end]
            if not in_window:
                continue
            mouth_boxes.update(
                mouth_screen_boxes(character_maps, in_window, framing_profile, solve,
                                   sensor_width_mm)
            )
        lip_sync_reports.append({
            "scene_id": scene_def.get("scene_id", f"scene_{s_idx + 1:02d}"),
            "speakers": lip_sync_modes,
            "real_lip_sync": any(mode.get("mode") == "viseme" for mode in lip_sync_modes.values()),
            "mouth_boxes": mouth_boxes,
        })

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

    # Colours first: both engines benefit, and Workbench is unreadable without it.
    color_sync = sync_material_display_colors()
    setup_world_ambient()

    # EEVEE is the default because it evaluates the material graph; Workbench is
    # kept as an explicit fast option. A grey character must never be the default
    # outcome of a successful render.
    engine_clean = (engine_override or "BLENDER_EEVEE").upper()
    engine_report = {"requested": engine_override or "BLENDER_EEVEE", "color_sync": color_sync}
    if "WORKBENCH" in engine_clean:
        scene.render.engine = 'BLENDER_WORKBENCH'
        scene.display.shading.light = 'STUDIO'
        scene.display.shading.color_type = 'MATERIAL'
        scene.display.shading.show_shadows = True
        scene.display.shading.show_cavity = True
        # Blender 5.2 exposes OFF/FXAA/5/8/11/16/32 here, not the old "8X" string.
        for aa in ('8', '16', 'FXAA'):
            try:
                scene.display.render_aa = aa
                break
            except Exception:
                continue
    else:
        chosen = None
        for candidate in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
            try:
                scene.render.engine = candidate
                chosen = candidate
                break
            except Exception:
                continue
        if chosen is None:
            scene.render.engine = 'BLENDER_WORKBENCH'
            scene.display.shading.light = 'STUDIO'
            scene.display.shading.color_type = 'MATERIAL'
            scene.display.shading.show_shadows = True
            log("EEVEE unavailable, fell back to BLENDER_WORKBENCH")
        eevee = scene.eevee
        eevee.taa_render_samples = 24
        try:
            eevee.use_shadows = True
        except Exception:
            pass
        try:
            # Screen-space contact shading gives the stylised look its grounding
            # without the cost of full ray tracing.
            eevee.use_raytracing = False
            eevee.use_gtao = True
            eevee.gtao_distance = 0.25
        except Exception:
            pass
        try:
            eevee.use_bloom = False
            eevee.use_volumetric_shadows = True
        except Exception:
            pass
    engine_report["engine"] = scene.render.engine

    # 'Standard' keeps the palette the asset builder chose. AgX/Filmic would
    # desaturate the flat cartoon colours toward grey, which is the opposite of
    # what a stylised 2.5D look needs. The enum is only populated once colour
    # management data is loaded, so in a factory-startup subprocess
    # `enum_items` reports just ['NONE'] and a membership guard would never
    # match; assign directly and read the value back instead.
    applied_transform = None
    for candidate in ('Standard', 'Filmic', 'AgX'):
        try:
            scene.view_settings.view_transform = candidate
        except Exception:
            continue
        if scene.view_settings.view_transform == candidate:
            applied_transform = candidate
            break
    try:
        scene.view_settings.look = 'None'
    except Exception:
        pass
    engine_report["view_transform"] = applied_transform or scene.view_settings.view_transform
    if applied_transform != "Standard":
        log(f"view transform is {engine_report['view_transform']}, not Standard; "
            f"colours will read flatter than the asset palette")

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
        "lip_sync": {
            "scenes": lip_sync_reports,
            "real_lip_sync": any(r["real_lip_sync"] for r in lip_sync_reports),
        },
        "engine_config": engine_report,
        "animation": {
            "planned": animation_plan is not None,
            "scenes": animation_reports,
            "summary": animation_plan.summary() if animation_plan else {},
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
