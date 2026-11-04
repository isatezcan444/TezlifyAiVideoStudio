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

def get_camera_positions(angle_str: str, aspect_ratio: str = "16:9"):
    """Returns (cam_location, target_location, lens_mm) for camera angle.

    Camera sensor fit is horizontal, so changing the output aspect ratio keeps
    the same horizontal composition. Portrait/square frames add vertical
    headroom instead of cropping characters out of frame; the backdrop is
    extended separately so that headroom never turns into a black void.
    """
    angle_lower = (angle_str or "medium_shot").lower()
    if "wide" in angle_lower:
        base = ((0.0, -4.6, 1.4), (0.0, 0.0, 1.0), 38.0)
    elif "close" in angle_lower:
        base = ((0.0, -1.9, 1.35), (0.0, 0.0, 1.35), 65.0)
    elif "two_shot" in angle_lower or "two" in angle_lower:
        base = ((0.0, -3.2, 1.25), (0.0, 0.0, 1.05), 45.0)
    elif "shoulder" in angle_lower:
        base = ((-0.6, -2.1, 1.35), (0.5, 0.0, 1.25), 55.0)
    else:  # medium_shot
        base = ((0.0, -3.0, 1.3), (0.0, 0.0, 1.1), 48.0)

    loc, target, lens = base
    if str(aspect_ratio) == "9:16":
        # A mild zoom gives portrait delivery some presence without cutting
        # the two-shot cast out of frame.
        loc = (loc[0], loc[1] * 1.04, loc[2] + 0.02)
        target = (target[0], target[1], target[2] + 0.02)
        lens *= 1.05
    elif str(aspect_ratio) == "1:1":
        loc = (loc[0], loc[1] * 1.01, loc[2])
        lens *= 1.05
    return loc, target, lens

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
    aspect_ratio = resolution.get(
        "aspect_ratio",
        "9:16" if height > width else ("1:1" if width == height else "16:9"),
    )

    scenes = scene_graph.get("scenes", [])
    if not scenes:
        raise ValueError("SceneGraph contains no scenes")

    total_duration = sum(s.get("duration_seconds", 5.0) for s in scenes)
    total_frames = max(1, int(round(total_duration * fps)))

    log(f"Starting render: {len(scenes)} scene(s), total {total_duration:.2f}s, {total_frames} frames @ {fps}fps")
    report_progress(10.0, "Building 3D Scene")

    clear_scene()

    # 1. Setup Camera and Camera Target
    cam_target = bpy.data.objects.new("CameraTarget", None)
    cam_target.location = (0.0, 0.0, 1.05)
    bpy.context.collection.objects.link(cam_target)

    cam_data = bpy.data.cameras.new("MainStudioCamera")
    # Horizontal sensor fit keeps the horizontal composition identical across
    # 16:9, 9:16 and 1:1. Portrait adds vertical room instead of cropping.
    cam_data.sensor_fit = 'HORIZONTAL'
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

    if str(aspect_ratio) == "9:16":
        # A portrait frame sees much further above the set than 16:9. Extend
        # the back wall so that extra headroom stays a real café wall instead
        # of default black world background.
        back_wall = background_objects.get("Cafe_BackWall")
        if back_wall:
            back_wall.scale.z *= 2.4
            back_wall.location.z = 2.5 * 2.4
            log("Extended café back wall for 9:16 headroom")

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

    for s_idx, scene_def in enumerate(scenes):
        scene_dur = scene_def.get("duration_seconds", 5.0)
        scene_frames = max(1, int(round(scene_dur * fps)))
        scene_start_frame = current_frame
        scene_end_frame = current_frame + scene_frames - 1

        log(f"Keyframing Scene {s_idx + 1}/{len(scenes)}: frames {scene_start_frame} to {scene_end_frame}")

        # A. Camera setup & movement for this scene
        cam_setup = scene_def.get("camera", {})
        cam_angle = cam_setup.get("angle", "two_shot")
        cam_movement = cam_setup.get("movement", "static").lower()
        base_loc, target_loc, lens = get_camera_positions(cam_angle, aspect_ratio)
        cam_data.lens = lens
        cam_target.location = target_loc

        # Initial camera keyframe
        cam_obj.location = base_loc
        cam_obj.keyframe_insert(data_path="location", frame=scene_start_frame)

        if "pan_right" in cam_movement:
            cam_obj.location = (base_loc[0] - 0.25, base_loc[1], base_loc[2])
            cam_obj.keyframe_insert(data_path="location", frame=scene_start_frame)
            cam_obj.location = (base_loc[0] + 0.25, base_loc[1], base_loc[2])
            cam_obj.keyframe_insert(data_path="location", frame=scene_end_frame)
        elif "pan_left" in cam_movement:
            cam_obj.location = (base_loc[0] + 0.25, base_loc[1], base_loc[2])
            cam_obj.keyframe_insert(data_path="location", frame=scene_start_frame)
            cam_obj.location = (base_loc[0] - 0.25, base_loc[1], base_loc[2])
            cam_obj.keyframe_insert(data_path="location", frame=scene_end_frame)
        elif "zoom_in" in cam_movement:
            cam_obj.location = (base_loc[0], base_loc[1] - 0.6, base_loc[2])
            cam_obj.keyframe_insert(data_path="location", frame=scene_start_frame)
            cam_obj.location = (base_loc[0], base_loc[1] + 0.4, base_loc[2])
            cam_obj.keyframe_insert(data_path="location", frame=scene_end_frame)
        elif "zoom_out" in cam_movement:
            cam_obj.location = (base_loc[0], base_loc[1] + 0.3, base_loc[2])
            cam_obj.keyframe_insert(data_path="location", frame=scene_start_frame)
            cam_obj.location = (base_loc[0], base_loc[1] - 0.5, base_loc[2])
            cam_obj.keyframe_insert(data_path="location", frame=scene_end_frame)
        else: # static
            cam_obj.location = base_loc
            cam_obj.keyframe_insert(data_path="location", frame=scene_end_frame)

        # B. Placements & Poses
        placements = scene_def.get("character_placements", [])
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

            pos = placement.get("position", [0.0, 0.0, 0.0])
            rot_y = placement.get("rotation_y", 0.0)
            pose_str = placement.get("pose", "standing")
            expr_str = placement.get("expression", "neutral")

            if root_obj:
                root_obj.location = (pos[0], pos[1], pos[2])
                # In Blender coordinate system, yaw is Z rotation
                root_obj.rotation_euler.z = math.radians(rot_y)
                root_obj.keyframe_insert(data_path="location", frame=scene_start_frame)
                root_obj.keyframe_insert(data_path="rotation_euler", frame=scene_start_frame)

            apply_pose(c_map, pose_str)
            apply_expression(c_map, expr_str, scene_start_frame)

        # C. Idle Breathing, Subtle Sway, Eye Blinking across the scene
        for c_id, c_map in character_maps.items():
            torso = c_map.get("Anchor_Torso")
            head = c_map.get("Anchor_Head")
            eye_l = c_map.get("Mesh_EyeWhite_L")
            eye_r = c_map.get("Mesh_EyeWhite_R")
            pupil_l = c_map.get("Mesh_Pupil_L")
            pupil_r = c_map.get("Mesh_Pupil_R")
            mouth = c_map.get("Mesh_Mouth")

            base_torso_z = torso.location.z if torso else 0.95
            phase_offset = 1.5 if "ayse" in c_id else 0.0

            # Step through frames at 5-frame intervals for smooth continuous curves
            for f in range(scene_start_frame, scene_end_frame + 1, 5):
                t = (f - scene_start_frame) / fps
                # Idle breathing on Torso
                if torso:
                    torso.location.z = base_torso_z + 0.012 * math.sin(t * 2.8 + phase_offset)
                    torso.rotation_euler.y = 0.008 * math.sin(t * 1.4 + phase_offset)
                    torso.keyframe_insert(data_path="location", frame=f)
                    torso.keyframe_insert(data_path="rotation_euler", frame=f)

                # Idle subtle head tilt
                if head:
                    head.rotation_euler.y = 0.015 * math.cos(t * 1.2 + phase_offset)
                    head.keyframe_insert(data_path="rotation_euler", frame=f)

            # Eye Blinks (every ~90 frames / 3 seconds)
            blink_interval = 95
            for blink_frame in range(scene_start_frame + 30, scene_end_frame, blink_interval):
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

        # D. Dialogue Keyframing: Mouth Flap, Gestures, Head Orientation
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

            # 1. Mouth flapping during speech
            if mouth:
                mouth.scale.z = 1.0
                mouth.keyframe_insert(data_path="scale", frame=max(scene_start_frame, abs_start - 1))
                # Flap cycle every 4 frames
                for f in range(abs_start, abs_end, 4):
                    cycle = (f - abs_start) // 4
                    # Alternate between open and medium open
                    mouth_z = 1.65 if (cycle % 2 == 0) else 0.55
                    mouth.scale.z = mouth_z
                    mouth.keyframe_insert(data_path="scale", frame=f)

                mouth.scale.z = 1.0
                mouth.keyframe_insert(data_path="scale", frame=min(scene_end_frame, abs_end + 1))

            # 2. Head turning toward partner when speaking
            if head:
                # If Ali on left, turn slightly to right (+z), if Ayse on right turn to left (-z)
                turn_dir = 0.15 if "ali" in speaker_id else -0.15
                head.rotation_euler.z = turn_dir
                head.keyframe_insert(data_path="rotation_euler", frame=abs_start)
                head.keyframe_insert(data_path="rotation_euler", frame=abs_end)
                head.rotation_euler.z = 0.0
                head.keyframe_insert(data_path="rotation_euler", frame=min(scene_end_frame, abs_end + 10))

            # 3. Gesturing with right arm during speech
            if arm_r:
                arm_r.rotation_euler.x = math.radians(-38)
                arm_r.rotation_euler.z = math.radians(12)
                arm_r.keyframe_insert(data_path="rotation_euler", frame=abs_start + 4)
                arm_r.rotation_euler.x = math.radians(-25)
                arm_r.keyframe_insert(data_path="rotation_euler", frame=(abs_start + abs_end) // 2)
                arm_r.rotation_euler.x = 0.0
                arm_r.rotation_euler.z = 0.0
                arm_r.keyframe_insert(data_path="rotation_euler", frame=min(scene_end_frame, abs_end + 8))

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
                        o_turn = -0.12 if "ayse" in other_id else 0.12
                        o_head.rotation_euler.z = o_turn
                        o_head.keyframe_insert(data_path="rotation_euler", frame=abs_start)
                        # Small nod halfway
                        nod_f = (abs_start + abs_end) // 2
                        o_head.rotation_euler.x = 0.08
                        o_head.keyframe_insert(data_path="rotation_euler", frame=nod_f)
                        o_head.rotation_euler.x = 0.0
                        o_head.keyframe_insert(data_path="rotation_euler", frame=nod_f + 8)

        current_frame = scene_end_frame + 1

    # 7. Save populated Blender scene file for reproducibility
    if scene_save_path:
        os.makedirs(os.path.dirname(scene_save_path), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=scene_save_path)
        log(f"Saved populated Blender scene to {scene_save_path}")

    report_progress(40.0, "Configuring Render Engine")

    # 8. Configure Render Engine
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

    # 9. Render Animation
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
