#!/usr/bin/env python3
"""
Blender 5.2.3 Headless 2.5D Cutout Character Generator
Builds a modular, aesthetic 2D/2.5D cutout character with full facial details,
expressions, hair styling, layered clothing, and rigged limb poses.
"""

import sys
import os
import math
import argparse
import bpy
from typing import Optional

from tezlify_studio.domain.value_objects.character_models import BodyProportions

def hex_to_linear(hex_str: str) -> tuple:
    clean = hex_str.lstrip('#')
    if len(clean) != 6:
        clean = "3B82F6"
    rgb = tuple(int(clean[i:i+2], 16) / 255.0 for i in (0, 2, 4))
    return tuple(c ** 2.2 for c in rgb) + (1.0,)

def make_material(name: str, hex_color: str, roughness: float = 0.8) -> bpy.types.Material:
    mat = bpy.data.materials.new(name=name)
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if not bsdf:
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = hex_to_linear(hex_color)
    bsdf.inputs["Roughness"].default_value = roughness
    return mat

def create_mesh_plane(name: str, width: float, height: float, location=(0, 0, 0), rotation=(0, 0, 0), parent=None, mat=None):
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (width, height, 1.0)
    if parent:
        obj.parent = parent
    if mat:
        obj.data.materials.append(mat)
    return obj

def create_mesh_cylinder(name: str, radius: float, depth: float, location=(0, 0, 0), rotation=(0, 0, 0), scale=(1,1,1), parent=None, mat=None):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    if parent:
        obj.parent = parent
    if mat:
        obj.data.materials.append(mat)
    return obj

def create_mesh_sphere(name: str, radius: float, location=(0, 0, 0), scale=(1,1,1), parent=None, mat=None):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    if parent:
        obj.parent = parent
    if mat:
        obj.data.materials.append(mat)
    return obj

def create_empty(name: str, location=(0, 0, 0), rotation=(0, 0, 0), parent=None):
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    if parent:
        obj.parent = parent
    return obj

class CharacterBuilder:
    def __init__(
        self,
        char_id: str,
        name: str,
        gender: str,
        colors: dict,
        hair_style: str,
        eye_style: str,
        expression: str,
        pose: str,
        proportions: Optional[BodyProportions] = None,
    ):
        self.char_id = char_id
        self.name = name
        self.gender = gender
        self.colors = colors
        self.hair_style = hair_style
        self.eye_style = eye_style
        self.expression = expression.lower()
        self.pose = pose.lower()
        self.proportions = proportions or BodyProportions()

        # Gender-based base silhouette so male/female characters differ even when
        # stored proportions are at their defaults (backward compatible with old records).
        if gender == "male":
            self._shoulder_scale = 1.10
            self._head_scale = 1.00
            self._torso_scale = 1.00
        else:
            self._shoulder_scale = 0.90
            self._head_scale = 0.95
            self._torso_scale = 0.95

        # Apply stored proportions on top of the gender base so custom characters
        # can be further differentiated (slim / average / athletic).
        self._head_scale *= self.proportions.head_scale
        self._torso_scale *= self.proportions.torso_length
        self._arm_scale = self.proportions.arm_length
        self._leg_scale = self.proportions.leg_length
        self._shoulder_width_scale = self.proportions.shoulder_width

        # Materials
        self.mat_skin = make_material(f"{char_id}_Skin", colors.get("skin_tone", "#F5D0A9"), roughness=0.85)
        self.mat_skin_shadow = make_material(f"{char_id}_SkinShadow", "#E5B990", roughness=0.85)
        self.mat_hair = make_material(f"{char_id}_Hair", colors.get("hair_color", "#2C1810"), roughness=0.6)
        self.mat_hair_highlight = make_material(f"{char_id}_HairHighlight", "#5A3825", roughness=0.5)
        self.mat_eye_white = make_material(f"{char_id}_EyeWhite", "#FFFFFF", roughness=0.2)
        self.mat_eye_iris = make_material(f"{char_id}_EyeIris", colors.get("eye_color", "#1E293B"), roughness=0.3)
        self.mat_eye_pupil = make_material(f"{char_id}_EyePupil", "#09090B", roughness=0.2)
        self.mat_mouth = make_material(f"{char_id}_Mouth", "#BE123C", roughness=0.5)
        self.mat_teeth = make_material(f"{char_id}_Teeth", "#FFFFFF", roughness=0.2)
        self.mat_shirt = make_material(f"{char_id}_Shirt", colors.get("shirt_color", "#3B82F6"), roughness=0.7)
        self.mat_shirt_accent = make_material(f"{char_id}_ShirtAccent", "#2563EB", roughness=0.7)
        self.mat_pants = make_material(f"{char_id}_Pants", colors.get("pants_color", "#1E293B"), roughness=0.8)
        self.mat_shoes = make_material(f"{char_id}_Shoes", colors.get("shoes_color", "#0F172A"), roughness=0.5)
        self.mat_shoe_sole = make_material(f"{char_id}_ShoeSole", "#E2E8F0", roughness=0.5)

    def build(self):
        # 1. Root Empty
        root = create_empty(f"Char_{self.char_id}_Root", (0, 0, 0))

        # 2. Torso Anchor
        torso_z = 0.95 * self._torso_scale
        if self.pose in ("sitting", "sitting_table"):
            torso_z = 0.65 * self._torso_scale

        torso_anchor = create_empty("Anchor_Torso", (0, 0, torso_z), parent=root)

        # 3. Torso / Shirt
        torso_depth = 0.48 * self._torso_scale
        torso = create_mesh_cylinder("Mesh_Torso_Shirt", radius=0.20, depth=torso_depth, scale=(1.0, 0.55 * self._torso_scale, 1.0), parent=torso_anchor, mat=self.mat_shirt)
        collar = create_mesh_cylinder("Mesh_Shirt_Collar", radius=0.12, depth=0.08, location=(0, 0, torso_depth * 0.5), scale=(1.0, 0.6, 1.0), parent=torso_anchor, mat=self.mat_shirt_accent)

        # 4. Neck & Head Anchor
        neck = create_mesh_cylinder("Mesh_Neck", radius=0.08, depth=0.14 * self._torso_scale, location=(0, 0, 0.32 * self._torso_scale), scale=(1.0, 0.7, 1.0), parent=torso_anchor, mat=self.mat_skin_shadow)
        head_anchor = create_empty("Anchor_Head", (0, 0, 0.52 * self._torso_scale), parent=torso_anchor)

        # 5. Head Shape (Face base)
        head_mesh = create_mesh_sphere("Mesh_Head_Face", radius=0.22, scale=(0.92 * self._head_scale, 0.75 * self._head_scale, 1.0 * self._head_scale), parent=head_anchor, mat=self.mat_skin)

        # Ears (scale with head)
        ear_l = create_mesh_sphere("Mesh_Ear_L", radius=0.05, location=(-0.21 * self._head_scale, 0, 0), scale=(0.5 * self._head_scale, 0.8, 1.0), parent=head_anchor, mat=self.mat_skin)
        ear_r = create_mesh_sphere("Mesh_Ear_R", radius=0.05, location=(0.21 * self._head_scale, 0, 0), scale=(0.5 * self._head_scale, 0.8, 1.0), parent=head_anchor, mat=self.mat_skin)

        # 6. Eyes & Eyebrows (scale with head)
        eye_y = -0.15 * self._head_scale
        eye_z = 0.02 * self._head_scale
        eye_spacing = 0.08 * self._head_scale

        # Eye Whites
        eye_white_l = create_mesh_sphere("Mesh_EyeWhite_L", radius=0.038 * self._head_scale, location=(-eye_spacing, eye_y, eye_z), scale=(1.0, 0.3, 0.9), parent=head_anchor, mat=self.mat_eye_white)
        eye_white_r = create_mesh_sphere("Mesh_EyeWhite_R", radius=0.038 * self._head_scale, location=(eye_spacing, eye_y, eye_z), scale=(1.0, 0.3, 0.9), parent=head_anchor, mat=self.mat_eye_white)

        # Pupils & Iris
        pupil_y = eye_y - 0.012
        pupil_l = create_mesh_sphere("Mesh_Pupil_L", radius=0.022 * self._head_scale, location=(-eye_spacing, pupil_y, eye_z), scale=(1.0, 0.3, 1.0), parent=head_anchor, mat=self.mat_eye_iris)
        pupil_r = create_mesh_sphere("Mesh_Pupil_R", radius=0.022 * self._head_scale, location=(eye_spacing, pupil_y, eye_z), scale=(1.0, 0.3, 1.0), parent=head_anchor, mat=self.mat_eye_iris)

        # Glints (Cute reflection highlights)
        glint_l = create_mesh_sphere("Mesh_Glint_L", radius=0.008 * self._head_scale, location=(-eye_spacing + 0.008, pupil_y - 0.008, eye_z + 0.008), scale=(1, 0.3, 1), parent=head_anchor, mat=self.mat_eye_white)
        glint_r = create_mesh_sphere("Mesh_Glint_R", radius=0.008 * self._head_scale, location=(eye_spacing + 0.008, pupil_y - 0.008, eye_z + 0.008), scale=(1, 0.3, 1), parent=head_anchor, mat=self.mat_eye_white)

        # Eyebrows (Driven by expression)
        brow_y = eye_y - 0.01
        brow_z = eye_z + 0.06
        brow_rot_l = 0.0
        brow_rot_r = 0.0

        if self.expression == "cheerful":
            brow_z += 0.015 * self._head_scale
            brow_rot_l = math.radians(-8)
            brow_rot_r = math.radians(8)
        elif self.expression == "surprised":
            brow_z += 0.03 * self._head_scale
        elif self.expression == "angry":
            brow_rot_l = math.radians(18)
            brow_rot_r = math.radians(-18)
            brow_z -= 0.01 * self._head_scale
        elif self.expression == "sad":
            brow_rot_l = math.radians(-15)
            brow_rot_r = math.radians(15)
        elif self.expression == "thinking":
            brow_rot_l = math.radians(-12)
            brow_rot_r = math.radians(10)

        brow_l = create_mesh_cylinder("Mesh_Brow_L", radius=0.012 * self._head_scale, depth=0.06 * self._head_scale, location=(-eye_spacing, brow_y, brow_z), rotation=(0, math.radians(90) + brow_rot_l, 0), parent=head_anchor, mat=self.mat_hair)
        brow_r = create_mesh_cylinder("Mesh_Brow_R", radius=0.012 * self._head_scale, depth=0.06 * self._head_scale, location=(eye_spacing, brow_y, brow_z), rotation=(0, math.radians(90) + brow_rot_r, 0), parent=head_anchor, mat=self.mat_hair)

        # Nose (scale with head)
        nose = create_mesh_sphere("Mesh_Nose", radius=0.02 * self._head_scale, location=(0, eye_y - 0.02 * self._head_scale, -0.025 * self._head_scale), scale=(0.7 * self._head_scale, 0.6 * self._head_scale, 0.9 * self._head_scale), parent=head_anchor, mat=self.mat_skin_shadow)

        # Mouth (Driven by expression, scales with head)
        mouth_y = eye_y - 0.01
        mouth_z = -0.08 * self._head_scale
        mouth_scale = self._head_scale
        if self.expression == "cheerful":
            mouth = create_mesh_cylinder("Mesh_Mouth", radius=0.035 * mouth_scale, depth=0.02 * mouth_scale, location=(0, mouth_y, mouth_z), rotation=(math.radians(90), 0, 0), scale=(1.2 * mouth_scale, 0.6 * mouth_scale, 0.4 * mouth_scale), parent=head_anchor, mat=self.mat_mouth)
            teeth = create_mesh_cylinder("Mesh_Teeth", radius=0.025 * mouth_scale, depth=0.022 * mouth_scale, location=(0, mouth_y - 0.005 * mouth_scale, mouth_z + 0.01 * mouth_scale), rotation=(math.radians(90), 0, 0), scale=(1.0 * mouth_scale, 0.3 * mouth_scale, 0.3 * mouth_scale), parent=head_anchor, mat=self.mat_teeth)
        elif self.expression == "surprised":
            mouth = create_mesh_cylinder("Mesh_Mouth", radius=0.03 * mouth_scale, depth=0.02 * mouth_scale, location=(0, mouth_y, mouth_z), rotation=(math.radians(90), 0, 0), scale=(0.8 * mouth_scale, 1.2 * mouth_scale, 0.4 * mouth_scale), parent=head_anchor, mat=self.mat_mouth)
        elif self.expression == "angry":
            mouth = create_mesh_cylinder("Mesh_Mouth", radius=0.03 * mouth_scale, depth=0.015 * mouth_scale, location=(0, mouth_y, mouth_z), rotation=(math.radians(90), 0, 0), scale=(1.1 * mouth_scale, 0.3 * mouth_scale, 0.4 * mouth_scale), parent=head_anchor, mat=self.mat_mouth)
        else: # neutral / thinking
            mouth = create_mesh_cylinder("Mesh_Mouth", radius=0.028 * mouth_scale, depth=0.015 * mouth_scale, location=(0, mouth_y, mouth_z), rotation=(math.radians(90), 0, 0), scale=(1.0 * mouth_scale, 0.3 * mouth_scale, 0.4 * mouth_scale), parent=head_anchor, mat=self.mat_mouth)

        # 7. Hair (Gender & style variations; scales with head)
        if self.gender == "female" or self.hair_style in ("bob_cut", "long_straight", "ponytail"):
            # Ayşe style: Full bangs, side framing locks, volume top
            hair_top = create_mesh_sphere("Mesh_Hair_Top", radius=0.23 * self._head_scale, location=(0, 0.02 * self._head_scale, 0.05 * self._head_scale), scale=(0.96 * self._head_scale, 0.82 * self._head_scale, 0.95 * self._head_scale), parent=head_anchor, mat=self.mat_hair)
            bangs = create_mesh_cylinder("Mesh_Hair_Bangs", radius=0.18 * self._head_scale, depth=0.12 * self._head_scale, location=(0, -0.10 * self._head_scale, 0.12 * self._head_scale), rotation=(math.radians(35), 0, 0), scale=(1.0 * self._head_scale, 0.5 * self._head_scale, 0.6 * self._head_scale), parent=head_anchor, mat=self.mat_hair)
            side_l = create_mesh_cylinder("Mesh_Hair_Side_L", radius=0.07 * self._head_scale, depth=0.35 * self._head_scale, location=(-0.19 * self._head_scale, -0.05 * self._head_scale, -0.06 * self._head_scale), rotation=(0, math.radians(-10), 0), scale=(0.8 * self._head_scale, 0.8 * self._head_scale, 1.0 * self._head_scale), parent=head_anchor, mat=self.mat_hair)
            side_r = create_mesh_cylinder("Mesh_Hair_Side_R", radius=0.07 * self._head_scale, depth=0.35 * self._head_scale, location=(0.19 * self._head_scale, -0.05 * self._head_scale, -0.06 * self._head_scale), rotation=(0, math.radians(10), 0), scale=(0.8 * self._head_scale, 0.8 * self._head_scale, 1.0 * self._head_scale), parent=head_anchor, mat=self.mat_hair)
        else:
            # Ali style: Modern short parted haircut with volume and neat sides
            hair_top = create_mesh_sphere("Mesh_Hair_Top", radius=0.225 * self._head_scale, location=(0, 0.01 * self._head_scale, 0.05 * self._head_scale), scale=(0.95 * self._head_scale, 0.80 * self._head_scale, 0.90 * self._head_scale), parent=head_anchor, mat=self.mat_hair)
            part_fringe = create_mesh_cylinder("Mesh_Hair_Part", radius=0.16 * self._head_scale, depth=0.10 * self._head_scale, location=(-0.03 * self._head_scale, -0.11 * self._head_scale, 0.13 * self._head_scale), rotation=(math.radians(28), 0, math.radians(-15)), scale=(1.0 * self._head_scale, 0.6 * self._head_scale, 0.5 * self._head_scale), parent=head_anchor, mat=self.mat_hair)
            hair_highlight = create_mesh_cylinder("Mesh_Hair_Highlight", radius=0.12 * self._head_scale, depth=0.04 * self._head_scale, location=(-0.04 * self._head_scale, -0.12 * self._head_scale, 0.15 * self._head_scale), rotation=(math.radians(25), 0, math.radians(-15)), scale=(0.8 * self._head_scale, 0.4 * self._head_scale, 0.4 * self._head_scale), parent=head_anchor, mat=self.mat_hair_highlight)

        # 8. Arms & Hands
        arm_spacing = 0.24 * self._shoulder_width_scale
        arm_shoulder_z = 0.18 * self._torso_scale

        # Default relaxed rotations
        arm_l_rot = (0, 0, 0)
        arm_r_rot = (0, 0, 0)

        if self.pose == "gesturing":
            arm_r_rot = (math.radians(-45), 0, math.radians(-35))
            arm_l_rot = (math.radians(10), 0, math.radians(15))
        elif self.pose == "pointing":
            arm_r_rot = (math.radians(-75), 0, math.radians(-10))
        elif self.pose in ("sitting", "sitting_table"):
            arm_l_rot = (math.radians(-50), 0, math.radians(10))
            arm_r_rot = (math.radians(-50), 0, math.radians(-10))
        elif self.pose == "walking":
            arm_l_rot = (math.radians(-25), 0, 0)
            arm_r_rot = (math.radians(25), 0, 0)

        # Left Arm
        anchor_arm_l = create_empty("Anchor_Arm_L", (-arm_spacing, 0, arm_shoulder_z), rotation=arm_l_rot, parent=torso_anchor)
        arm_l_upper = create_mesh_cylinder("Mesh_Arm_L_Upper", radius=0.065 * self._arm_scale, depth=0.22 * self._arm_scale, location=(0, 0, -0.11 * self._arm_scale), scale=(1, 0.8, 1), parent=anchor_arm_l, mat=self.mat_shirt)
        arm_l_lower = create_mesh_cylinder("Mesh_Arm_L_Lower", radius=0.055 * self._arm_scale, depth=0.20 * self._arm_scale, location=(0, 0, -0.30 * self._arm_scale), scale=(1, 0.8, 1), parent=anchor_arm_l, mat=self.mat_skin)
        hand_l = create_mesh_sphere("Mesh_Hand_L", radius=0.06 * self._arm_scale, location=(0, 0, -0.42 * self._arm_scale), scale=(0.8 * self._arm_scale, 0.6 * self._arm_scale, 1.0), parent=anchor_arm_l, mat=self.mat_skin)

        # Right Arm
        anchor_arm_r = create_empty("Anchor_Arm_R", (arm_spacing, 0, arm_shoulder_z), rotation=arm_r_rot, parent=torso_anchor)
        arm_r_upper = create_mesh_cylinder("Mesh_Arm_R_Upper", radius=0.065 * self._arm_scale, depth=0.22 * self._arm_scale, location=(0, 0, -0.11 * self._arm_scale), scale=(1, 0.8, 1), parent=anchor_arm_r, mat=self.mat_shirt)
        arm_r_lower = create_mesh_cylinder("Mesh_Arm_R_Lower", radius=0.055 * self._arm_scale, depth=0.20 * self._arm_scale, location=(0, 0, -0.30 * self._arm_scale), scale=(1, 0.8, 1), parent=anchor_arm_r, mat=self.mat_skin)
        hand_r = create_mesh_sphere("Mesh_Hand_R", radius=0.06 * self._arm_scale, location=(0, 0, -0.42 * self._arm_scale), scale=(0.8 * self._arm_scale, 0.6 * self._arm_scale, 1.0), parent=anchor_arm_r, mat=self.mat_skin)

        # 9. Hips, Legs & Shoes
        hips = create_mesh_cylinder("Mesh_Hips", radius=0.19 * self._shoulder_width_scale, depth=0.16 * self._torso_scale, location=(0, 0, -0.28 * self._torso_scale), scale=(1.0 * self._shoulder_width_scale, 0.6 * self._torso_scale, 1.0), parent=torso_anchor, mat=self.mat_pants)

        leg_spacing = 0.10 * self._shoulder_width_scale
        leg_l_rot = (0, 0, 0)
        leg_r_rot = (0, 0, 0)

        if self.pose in ("sitting", "sitting_table"):
            leg_l_rot = (math.radians(-90), 0, 0)
            leg_r_rot = (math.radians(-90), 0, 0)
        elif self.pose == "walking":
            leg_l_rot = (math.radians(22), 0, 0)
            leg_r_rot = (math.radians(-22), 0, 0)

        # Left Leg
        anchor_leg_l = create_empty("Anchor_Leg_L", (-leg_spacing, 0, -0.36 * self._torso_scale), rotation=leg_l_rot, parent=torso_anchor)
        leg_l_mesh = create_mesh_cylinder("Mesh_Leg_L", radius=0.075 * self._leg_scale, depth=0.45 * self._leg_scale, location=(0, 0, -0.22 * self._leg_scale), scale=(1 * self._leg_scale, 0.8 * self._leg_scale, 1), parent=anchor_leg_l, mat=self.mat_pants)
        shoe_l = create_mesh_cylinder("Mesh_Shoe_L", radius=0.075 * self._leg_scale, depth=0.18 * self._leg_scale, location=(0, -0.04 * self._leg_scale, -0.46 * self._leg_scale), rotation=(math.radians(90), 0, 0), scale=(0.9 * self._leg_scale, 0.8 * self._leg_scale, 1.2 * self._leg_scale), parent=anchor_leg_l, mat=self.mat_shoes)
        sole_l = create_mesh_cylinder("Mesh_Sole_L", radius=0.078 * self._leg_scale, depth=0.03 * self._leg_scale, location=(0, -0.04 * self._leg_scale, -0.50 * self._leg_scale), rotation=(math.radians(90), 0, 0), scale=(0.9 * self._leg_scale, 0.8 * self._leg_scale, 1.2 * self._leg_scale), parent=anchor_leg_l, mat=self.mat_shoe_sole)

        # Right Leg
        anchor_leg_r = create_empty("Anchor_Leg_R", (leg_spacing, 0, -0.36 * self._torso_scale), rotation=leg_r_rot, parent=torso_anchor)
        leg_r_mesh = create_mesh_cylinder("Mesh_Leg_R", radius=0.075 * self._leg_scale, depth=0.45 * self._leg_scale, location=(0, 0, -0.22 * self._leg_scale), scale=(1 * self._leg_scale, 0.8 * self._leg_scale, 1), parent=anchor_leg_r, mat=self.mat_pants)
        shoe_r = create_mesh_cylinder("Mesh_Shoe_R", radius=0.075 * self._leg_scale, depth=0.18 * self._leg_scale, location=(0, -0.04 * self._leg_scale, -0.46 * self._leg_scale), rotation=(math.radians(90), 0, 0), scale=(0.9 * self._leg_scale, 0.8 * self._leg_scale, 1.2 * self._leg_scale), parent=anchor_leg_r, mat=self.mat_shoes)
        sole_r = create_mesh_cylinder("Mesh_Sole_R", radius=0.078 * self._leg_scale, depth=0.03 * self._leg_scale, location=(0, -0.04 * self._leg_scale, -0.50 * self._leg_scale), rotation=(math.radians(90), 0, 0), scale=(0.9 * self._leg_scale, 0.8 * self._leg_scale, 1.2 * self._leg_scale), parent=anchor_leg_r, mat=self.mat_shoe_sole)

        # Table prop if sitting_table pose
        if self.pose == "sitting_table":
            table_top = create_mesh_cylinder("Prop_Table_Preview", radius=0.45, depth=0.04, location=(0, -0.32, -0.15), scale=(1.2, 0.7, 1.0), parent=root, mat=make_material("TableWood", "#78350F"))

        return root

def setup_studio_camera_and_lighting():
    # Camera
    cam_data = bpy.data.cameras.new("StudioCamera")
    cam_data.lens = 50.0 # 50mm portrait
    cam_obj = bpy.data.objects.new("StudioCamera", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    cam_obj.location = (0, -2.4, 1.15)
    cam_obj.rotation_euler = (math.radians(88), 0, 0)
    bpy.context.scene.camera = cam_obj

    # 3-Point Lighting
    # Key Light (Warm)
    key_light_data = bpy.data.lights.new(name="KeyLight", type='AREA')
    key_light_data.energy = 85.0
    key_light_data.size = 1.2
    key_light_data.color = (1.0, 0.95, 0.88)
    key_obj = bpy.data.objects.new("KeyLight", key_light_data)
    bpy.context.scene.collection.objects.link(key_obj)
    key_obj.location = (1.5, -1.8, 2.2)
    key_obj.rotation_euler = (math.radians(45), math.radians(20), math.radians(35))

    # Fill Light (Soft Cool)
    fill_light_data = bpy.data.lights.new(name="FillLight", type='AREA')
    fill_light_data.energy = 45.0
    fill_light_data.size = 1.5
    fill_light_data.color = (0.85, 0.92, 1.0)
    fill_obj = bpy.data.objects.new("FillLight", fill_light_data)
    bpy.context.scene.collection.objects.link(fill_obj)
    fill_obj.location = (-1.5, -1.5, 1.5)
    fill_obj.rotation_euler = (math.radians(40), math.radians(-25), math.radians(-35))

    # Rim / Back Light (Crisp Silhouette)
    rim_light_data = bpy.data.lights.new(name="RimLight", type='POINT')
    rim_light_data.energy = 120.0
    rim_light_data.color = (1.0, 1.0, 1.0)
    rim_obj = bpy.data.objects.new("RimLight", rim_light_data)
    bpy.context.scene.collection.objects.link(rim_obj)
    rim_obj.location = (0, 1.5, 2.2)

def main():
    # Parse custom args passed after '--'
    argv = sys.argv
    if "--" in argv:
        custom_args = argv[argv.index("--") + 1:]
    else:
        custom_args = []

    parser = argparse.ArgumentParser(description="Blender Character Generator")
    parser.add_argument("--char-id", type=str, default="char_ali")
    parser.add_argument("--name", type=str, default="Ali")
    parser.add_argument("--gender", type=str, default="male")
    parser.add_argument("--skin-tone", type=str, default="#F5D0A9")
    parser.add_argument("--hair-color", type=str, default="#2C1810")
    parser.add_argument("--hair-style", type=str, default="short_parted")
    parser.add_argument("--shirt-color", type=str, default="#3B82F6")
    parser.add_argument("--pants-color", type=str, default="#1E293B")
    parser.add_argument("--shoes-color", type=str, default="#0F172A")
    parser.add_argument("--eye-color", type=str, default="#1E293B")
    parser.add_argument("--eye-style", type=str, default="round")
    parser.add_argument("--expression", type=str, default="cheerful")
    parser.add_argument("--pose", type=str, default="standing")
    parser.add_argument("--head-scale", type=float, default=1.0)
    parser.add_argument("--torso-length", type=float, default=1.0)
    parser.add_argument("--arm-length", type=float, default=1.0)
    parser.add_argument("--leg-length", type=float, default=1.0)
    parser.add_argument("--shoulder-width", type=float, default=1.0)
    parser.add_argument("--output-blend", type=str, required=True)
    parser.add_argument("--output-thumb", type=str, required=True)
    parser.add_argument("--render-engine", type=str, default="CYCLES")

    args = parser.parse_args(custom_args)

    # Initialize scene
    bpy.ops.wm.read_factory_settings(use_empty=True)

    colors = {
        "skin_tone": args.skin_tone,
        "hair_color": args.hair_color,
        "shirt_color": args.shirt_color,
        "pants_color": args.pants_color,
        "shoes_color": args.shoes_color,
        "eye_color": args.eye_color,
    }

    proportions = BodyProportions(
        head_scale=args.head_scale,
        torso_length=args.torso_length,
        arm_length=args.arm_length,
        leg_length=args.leg_length,
        shoulder_width=args.shoulder_width,
    )

    builder = CharacterBuilder(
        char_id=args.char_id,
        name=args.name,
        gender=args.gender,
        colors=colors,
        hair_style=args.hair_style,
        eye_style=args.eye_style,
        expression=args.expression,
        pose=args.pose,
        proportions=proportions,
    )
    builder.build()

    setup_studio_camera_and_lighting()

    # Ensure parent output directory exists
    os.makedirs(os.path.dirname(os.path.abspath(args.output_blend)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.output_thumb)), exist_ok=True)

    # Save .blend file
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.output_blend))
    print(f"BLEND_SAVED: {args.output_blend}")

    # Render thumbnail
    scene = bpy.context.scene
    scene.render.engine = args.render_engine
    if args.render_engine == "CYCLES":
        scene.cycles.samples = 24
        scene.cycles.device = 'CPU'
    scene.render.film_transparent = True
    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    scene.render.filepath = os.path.abspath(args.output_thumb)
    bpy.ops.render.render(write_still=True)
    print(f"THUMB_SAVED: {args.output_thumb}")

if __name__ == "__main__":
    main()
