"""Rig plumbing for the animation plan: controls, rest pose, keyframe writing.

Only ever imported inside Blender (`render_worker.py` runs in Blender's Python),
so importing `bpy` here is safe - unlike the domain modules this one may not be.

The character assets have no armature. They are empties and primitive meshes
joined by plain parenting, and the worker's only contract with them is the
unprefixed object names. That is workable: `Anchor_Torso`, `Anchor_Head` and
`Anchor_Arm_L/R` already behave as hips, neck and shoulder joints, and the
forearm and hand are *separate meshes*, so they can be re-pivoted into real
elbow and wrist joints at load time without touching the asset files.

Everything degrades gracefully. An asset missing a control simply does not get
that channel animated, which is what keeps the ~25 hashed character assets and
any pre-5.5 project rendering instead of raising.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import bpy

from tezlify_studio.domain.services.animation_layers import Pose

# Control name -> the object names it may be found under, in preference order.
CONTROL_SOURCES: Dict[str, Tuple[str, ...]] = {
    "root": ("Root",),
    "torso": ("Anchor_Torso",),
    "head": ("Anchor_Head",),
    "arm_l": ("Anchor_Arm_L",),
    "arm_r": ("Anchor_Arm_R",),
    "elbow_l": ("Mesh_Arm_L_Lower",),
    "elbow_r": ("Mesh_Arm_R_Lower",),
    "wrist_l": ("Mesh_Hand_L",),
    "wrist_r": ("Mesh_Hand_R",),
    "brow_l": ("Mesh_Brow_L",),
    "brow_r": ("Mesh_Brow_R",),
    "eye_l": ("Mesh_EyeWhite_L",),
    "eye_r": ("Mesh_EyeWhite_R",),
    "pupil_l": ("Mesh_Pupil_L",),
    "pupil_r": ("Mesh_Pupil_R",),
    "mouth": ("Mesh_Mouth",),
}

CHANNEL_DATA_PATH = {"rot": "rotation_euler", "loc": "location", "scale": "scale"}


def build_control_map(char_map: Dict[str, bpy.types.Object]) -> Dict[str, bpy.types.Object]:
    """Resolve control names to objects, accepting the legacy "Root" substring."""
    controls: Dict[str, bpy.types.Object] = {}
    for control, sources in CONTROL_SOURCES.items():
        for source in sources:
            obj = char_map.get(source)
            if obj is None and source == "Root":
                obj = next((o for name, o in char_map.items() if "Root" in name), None)
            if obj is not None:
                controls[control] = obj
                break
    return controls


def _local_top_of(obj: bpy.types.Object) -> float:
    """Highest point of a mesh in its parent's space, used to find a joint."""
    if obj.type != "MESH" or not obj.bound_box:
        return obj.location.z
    from mathutils import Vector

    matrix = obj.matrix_local
    return max((matrix @ Vector(corner)).z for corner in obj.bound_box)


def repivot_to_top(obj: bpy.types.Object, target_z: Optional[float] = None) -> Tuple[float, float]:
    """Move an object's origin to its own top without moving it in the world.

    The forearm mesh is centred mid-forearm and the hand mid-palm, so rotating
    either one bends the limb in the middle of the bone. Re-origining the mesh
    data by the same offset keeps the silhouette identical while making the
    rotation pivot the elbow or the wrist.
    """
    before = tuple(obj.location)
    top = target_z if target_z is not None else _local_top_of(obj)
    if not math.isfinite(top):
        return before, before[2]
    shift = top - obj.location.z
    if abs(shift) < 1e-5:
        return before, obj.location.z
    from mathutils import Matrix

    obj.data.transform(Matrix.Translation((0.0, 0.0, shift)))
    obj.location.z += shift
    obj.data.update()
    return before, obj.location.z


def prepare_joint_pivots(controls: Dict[str, bpy.types.Object]) -> List[str]:
    """Re-pivot the forearm and hand meshes. Returns the controls it changed."""
    changed = []
    for control in ("elbow_l", "elbow_r", "wrist_l", "wrist_r"):
        obj = controls.get(control)
        if obj is None or obj.type != "MESH":
            continue
        repivot_to_top(obj)
        changed.append(control)
    return changed


Rest = Dict[str, Tuple[Tuple[float, float, float], ...]]


def capture_rest(controls: Dict[str, bpy.types.Object]) -> Rest:
    """Snapshot every control's local transform, before any keyframe exists."""
    rest: Rest = {}
    for control, obj in controls.items():
        rest[control] = (
            tuple(obj.location),
            tuple(obj.rotation_euler),
            tuple(obj.scale),
        )
    return rest


def set_interpolation(obj: bpy.types.Object, data_paths: Tuple[str, ...], mode: str) -> int:
    """Force one interpolation mode on an object's curves.

    Blender 5.2 removed `Action.fcurves`; the supported way to reach a curve is
    `Action.fcurve_ensure_for_datablock(obj, path, index=...)`. Stage 5.4's
    attempt at this read `action.fcurves` inside a bare `except`, so it silently
    did nothing and every viseme still eased with bezier overshoot.
    """
    action = obj.animation_data.action if obj.animation_data else None
    if action is None:
        return 0
    touched = 0
    for path in data_paths:
        for index in range(3):
            try:
                curve = action.fcurve_ensure_for_datablock(obj, path, index=index)
            except Exception:
                continue
            if curve is None or not curve.keyframe_points:
                continue
            for key in curve.keyframe_points:
                key.interpolation = mode
            touched += 1
    return touched


def write_pose(
    controls: Dict[str, bpy.types.Object],
    rest: Rest,
    pose: Pose,
    frame: int,
    skip: Tuple[str, ...] = (),
) -> int:
    """Apply one blended pose as absolute values and key it.

    Values are rest + delta, never raw deltas, because a clip that does not touch
    a channel must leave it at rest instead of zeroing a rotation or a scale.
    """
    written = 0
    for control, channels in pose.items():
        if control in skip:
            continue
        obj = controls.get(control)
        if obj is None:
            continue
        base_loc, base_rot, base_scale = rest[control]
        loc, rot, scale = list(base_loc), list(base_rot), list(base_scale)
        for channel, values in channels.items():
            if channel == "loc":
                loc = [base_loc[i] + values[i] for i in range(3)]
            elif channel == "rot":
                rot = [base_rot[i] + values[i] for i in range(3)]
            elif channel == "scale":
                scale = [base_scale[i] * values[i] for i in range(3)]
        obj.location = loc
        obj.rotation_euler = rot
        obj.scale = scale
        obj.keyframe_insert(data_path="location", frame=frame)
        obj.keyframe_insert(data_path="rotation_euler", frame=frame)
        obj.keyframe_insert(data_path="scale", frame=frame)
        written += 1
    return written


def control_inventory(controls: Dict[str, bpy.types.Object]) -> Dict[str, str]:
    """What this asset actually exposes - recorded per character in the evidence."""
    return {name: obj.type for name, obj in sorted(controls.items())}
