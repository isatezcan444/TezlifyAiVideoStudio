#!/usr/bin/env python3
"""
Blender 5.2.3 Headless Scene & Asset Builder
Constructs 3D/2.5D modular backgrounds, props, and lighting presets
with aesthetic stylization, materials, camera, and renders high-res thumbnails.
"""

import sys
import os
import math
import argparse
import bpy

def hex_to_linear(hex_str: str) -> tuple:
    clean = hex_str.lstrip('#')
    if len(clean) != 6:
        clean = "3B82F6"
    rgb = tuple(int(clean[i:i+2], 16) / 255.0 for i in (0, 2, 4))
    return tuple(c ** 2.2 for c in rgb) + (1.0,)

def make_material(name: str, hex_color: str, roughness: float = 0.6, metallic: float = 0.0) -> bpy.types.Material:
    mat = bpy.data.materials.new(name=name)
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if not bsdf:
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = hex_to_linear(hex_color)
    bsdf.inputs["Roughness"].default_value = roughness
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = metallic
    return mat

def create_mesh_cube(name: str, size: float, scale=(1, 1, 1), location=(0, 0, 0), rotation=(0, 0, 0), parent=None, mat=None):
    bpy.ops.mesh.primitive_cube_add(size=size, location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    if parent:
        obj.parent = parent
    if mat:
        obj.data.materials.append(mat)
    return obj

def create_mesh_cylinder(name: str, radius: float, depth: float, scale=(1, 1, 1), location=(0, 0, 0), rotation=(0, 0, 0), parent=None, mat=None):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    if parent:
        obj.parent = parent
    if mat:
        obj.data.materials.append(mat)
    return obj

def create_mesh_plane(name: str, size: float, scale=(1, 1, 1), location=(0, 0, 0), rotation=(0, 0, 0), parent=None, mat=None):
    bpy.ops.mesh.primitive_plane_add(size=size, location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    if parent:
        obj.parent = parent
    if mat:
        obj.data.materials.append(mat)
    return obj

def build_bg_modern_cafe():
    # Materials
    m_wall = make_material("CafeWall", "#F3E8D6", roughness=0.9)
    m_accent_wall = make_material("CafeAccentWall", "#1E293B", roughness=0.8)
    m_floor = make_material("CafeFloorWood", "#854D0E", roughness=0.5)
    m_counter = make_material("CafeCounter", "#292524", roughness=0.4)
    m_counter_top = make_material("CafeCounterMarble", "#F8FAFC", roughness=0.2)
    m_window_frame = make_material("WindowFrame", "#0F172A", roughness=0.4)
    m_glass = make_material("Glass", "#93C5FD", roughness=0.1)

    # Floor
    create_mesh_plane("Cafe_Floor", size=10.0, location=(0, 0, 0), mat=m_floor)

    # Back Wall
    create_mesh_cube("Cafe_BackWall", size=1.0, scale=(10.0, 0.2, 5.0), location=(0, 4.0, 2.5), mat=m_wall)

    # Left Wall with large window
    create_mesh_cube("Cafe_LeftWall", size=1.0, scale=(0.2, 10.0, 5.0), location=(-5.0, 0, 2.5), mat=m_accent_wall)
    create_mesh_cube("Cafe_Window_Frame", size=1.0, scale=(0.25, 4.0, 2.8), location=(-4.9, 0, 2.5), mat=m_window_frame)
    create_mesh_plane("Cafe_Window_Glass", size=1.0, scale=(1.0, 3.8, 2.6), location=(-4.8, 0, 2.5), rotation=(0, math.radians(90), 0), mat=m_glass)

    # Barista Counter in the background
    create_mesh_cube("Counter_Base", size=1.0, scale=(4.5, 1.2, 1.05), location=(0, 2.8, 0.525), mat=m_counter)
    create_mesh_cube("Counter_Top", size=1.0, scale=(4.7, 1.35, 0.08), location=(0, 2.8, 1.09), mat=m_counter_top)

    # Shelves with bottles / coffee cups
    create_mesh_cube("Cafe_Shelf", size=1.0, scale=(3.5, 0.35, 0.05), location=(0, 3.85, 2.2), mat=m_counter_top)
    create_mesh_cube("Cafe_Shelf_2", size=1.0, scale=(3.5, 0.35, 0.05), location=(0, 3.85, 2.8), mat=m_counter_top)

    # Wall Art / Sign
    m_neon = make_material("NeonSign", "#F59E0B", roughness=0.2)
    create_mesh_cube("Cafe_Signboard", size=1.0, scale=(2.2, 0.08, 0.6), location=(0, 3.88, 3.8), mat=m_accent_wall)

def build_bg_office():
    m_wall = make_material("OfficeWall", "#E2E8F0", roughness=0.9)
    m_floor = make_material("OfficeCarpet", "#334155", roughness=0.9)
    m_glass = make_material("OfficeGlass", "#CBD5E1", roughness=0.2)
    m_desk = make_material("OfficeDesk", "#F8FAFC", roughness=0.3)

    create_mesh_plane("Office_Floor", size=10.0, location=(0, 0, 0), mat=m_floor)
    create_mesh_cube("Office_BackWall", size=1.0, scale=(10.0, 0.2, 5.0), location=(0, 4.0, 2.5), mat=m_wall)
    create_mesh_cube("Office_Whiteboard", size=1.0, scale=(3.5, 0.06, 1.8), location=(0, 3.88, 2.5), mat=m_glass)
    create_mesh_cube("Office_Desk_BG", size=1.0, scale=(4.0, 1.2, 0.9), location=(0, 2.5, 0.45), mat=m_desk)

def build_bg_park():
    m_grass = make_material("ParkGrass", "#15803D", roughness=0.8)
    m_path = make_material("ParkPath", "#D97706", roughness=0.9)
    m_sky = make_material("ParkSky", "#38BDF8", roughness=0.9)
    m_wood = make_material("ParkWood", "#78350F", roughness=0.7)

    create_mesh_plane("Park_Grass", size=12.0, location=(0, 0, 0), mat=m_grass)
    create_mesh_plane("Park_Path", size=1.0, scale=(3.0, 12.0, 1.0), location=(0, 0, 0.01), mat=m_path)
    create_mesh_cube("Park_SkyBackdrop", size=1.0, scale=(12.0, 0.2, 6.0), location=(0, 5.0, 3.0), mat=m_sky)
    create_mesh_cube("Park_Bench", size=1.0, scale=(2.2, 0.6, 0.5), location=(2.2, 2.5, 0.25), mat=m_wood)

def build_bg_living_room():
    m_wall = make_material("LivingWall", "#FEF3C7", roughness=0.8)
    m_floor = make_material("LivingWood", "#92400E", roughness=0.4)
    m_sofa = make_material("LivingSofa", "#2563EB", roughness=0.7)
    m_rug = make_material("LivingRug", "#FDE68A", roughness=0.9)

    create_mesh_plane("Living_Floor", size=10.0, location=(0, 0, 0), mat=m_floor)
    create_mesh_cube("Living_Wall", size=1.0, scale=(10.0, 0.2, 5.0), location=(0, 4.0, 2.5), mat=m_wall)
    create_mesh_plane("Living_Rug", size=1.0, scale=(4.0, 3.0, 1.0), location=(0, 1.0, 0.01), mat=m_rug)
    create_mesh_cube("Living_Sofa", size=1.0, scale=(3.2, 1.2, 0.8), location=(0, 2.8, 0.4), mat=m_sofa)

def build_bg_tech_studio():
    m_wall = make_material("StudioWall", "#0F172A", roughness=0.7)
    m_floor = make_material("StudioFloor", "#020617", roughness=0.3)
    m_neon_cyan = make_material("NeonCyan", "#06B6D4", roughness=0.2)
    m_neon_pink = make_material("NeonPink", "#EC4899", roughness=0.2)
    m_panel = make_material("AcousticPanel", "#1E293B", roughness=0.9)

    create_mesh_plane("Studio_Floor", size=10.0, location=(0, 0, 0), mat=m_floor)
    create_mesh_cube("Studio_BackWall", size=1.0, scale=(10.0, 0.2, 5.0), location=(0, 4.0, 2.5), mat=m_wall)

    # Acoustic Panels
    for x in (-3.0, -1.0, 1.0, 3.0):
        create_mesh_cube(f"AcousticPanel_{x}", size=1.0, scale=(1.2, 0.08, 2.2), location=(x, 3.88, 2.5), mat=m_panel)

    # Neon Strips
    create_mesh_cube("Neon_Top", size=1.0, scale=(9.0, 0.06, 0.06), location=(0, 3.87, 4.2), mat=m_neon_cyan)
    create_mesh_cube("Neon_Mid", size=1.0, scale=(9.0, 0.06, 0.06), location=(0, 3.87, 1.0), mat=m_neon_pink)

# --- PROPS ---

def build_prop_table():
    m_wood = make_material("TableWood", "#78350F", roughness=0.5)
    m_metal = make_material("TableMetal", "#1E293B", roughness=0.3, metallic=0.8)

    # Table Top
    create_mesh_cylinder("Table_Top", radius=0.6, depth=0.06, scale=(1, 1, 1), location=(0, 0, 0.75), mat=m_wood)
    # Center Leg & Base
    create_mesh_cylinder("Table_Leg", radius=0.05, depth=0.72, scale=(1, 1, 1), location=(0, 0, 0.36), mat=m_metal)
    create_mesh_cylinder("Table_Base", radius=0.45, depth=0.03, scale=(1, 1, 1), location=(0, 0, 0.015), mat=m_metal)

def build_prop_chair():
    m_cushion = make_material("ChairCushion", "#3B82F6", roughness=0.6)
    m_legs = make_material("ChairLegs", "#0F172A", roughness=0.3, metallic=0.7)

    # Seat
    create_mesh_cylinder("Chair_Seat", radius=0.28, depth=0.06, location=(0, 0, 0.45), mat=m_cushion)
    # Backrest
    create_mesh_cube("Chair_Back", size=1.0, scale=(0.46, 0.06, 0.38), location=(0, 0.22, 0.72), mat=m_cushion)
    # 4 Legs
    for dx in (-0.18, 0.18):
        for dy in (-0.18, 0.18):
            create_mesh_cylinder(f"Chair_Leg_{dx}_{dy}", radius=0.02, depth=0.44, location=(dx, dy, 0.22), mat=m_legs)

def build_prop_coffee_cup():
    m_ceramic = make_material("CupCeramic", "#FFFFFF", roughness=0.2)
    m_coffee = make_material("CoffeeLiquid", "#451A03", roughness=0.1)
    m_saucer = make_material("SaucerCeramic", "#FFFFFF", roughness=0.2)

    # Saucer
    create_mesh_cylinder("Coffee_Saucer", radius=0.16, depth=0.02, location=(0, 0, 0.01), mat=m_saucer)
    # Cup
    create_mesh_cylinder("Coffee_Cup_Body", radius=0.09, depth=0.11, location=(0, 0, 0.075), mat=m_ceramic)
    # Liquid surface
    create_mesh_cylinder("Coffee_Liquid", radius=0.082, depth=0.01, location=(0, 0, 0.12), mat=m_coffee)
    # Handle
    create_mesh_cylinder("Coffee_Handle", radius=0.02, depth=0.07, location=(0.095, 0, 0.075), rotation=(0, math.radians(90), 0), scale=(1, 0.4, 1), mat=m_ceramic)

def build_prop_coffee_machine():
    m_metal = make_material("MachineSteel", "#E2E8F0", roughness=0.2, metallic=0.9)
    m_black = make_material("MachineBlack", "#0F172A", roughness=0.4)
    m_lights = make_material("MachineLights", "#10B981", roughness=0.2)

    # Main Body
    create_mesh_cube("Machine_Body", size=1.0, scale=(0.42, 0.50, 0.55), location=(0, 0, 0.275), mat=m_metal)
    # Top warmer
    create_mesh_cube("Machine_Top", size=1.0, scale=(0.38, 0.46, 0.04), location=(0, 0, 0.57), mat=m_black)
    # Drip Tray
    create_mesh_cube("Machine_Tray", size=1.0, scale=(0.40, 0.25, 0.06), location=(0, -0.15, 0.03), mat=m_black)
    # Group Heads / Spout
    create_mesh_cylinder("Machine_Spout_1", radius=0.04, depth=0.08, location=(-0.08, -0.12, 0.25), mat=m_black)
    create_mesh_cylinder("Machine_Spout_2", radius=0.04, depth=0.08, location=(0.08, -0.12, 0.25), mat=m_black)
    # Power Button
    create_mesh_cylinder("Machine_Button", radius=0.02, depth=0.02, location=(0.14, -0.26, 0.45), rotation=(math.radians(90), 0, 0), mat=m_lights)

def build_prop_laptop():
    m_alu = make_material("LaptopAlu", "#94A3B8", roughness=0.3, metallic=0.8)
    m_screen = make_material("LaptopScreen", "#1E293B", roughness=0.1)

    # Base
    create_mesh_cube("Laptop_Base", size=1.0, scale=(0.32, 0.24, 0.015), location=(0, 0, 0.0075), mat=m_alu)
    # Lid / Screen angled at 110 deg
    create_mesh_cube("Laptop_Lid", size=1.0, scale=(0.32, 0.015, 0.22), location=(0, 0.12, 0.11), rotation=(math.radians(20), 0, 0), mat=m_alu)
    create_mesh_plane("Laptop_Display", size=1.0, scale=(0.29, 0.19, 1.0), location=(0, 0.11, 0.11), rotation=(math.radians(110), 0, 0), mat=m_screen)

def build_prop_smartphone():
    m_glass = make_material("PhoneGlass", "#020617", roughness=0.1)
    m_frame = make_material("PhoneFrame", "#475569", roughness=0.3, metallic=0.7)

    create_mesh_cube("Phone_Frame", size=1.0, scale=(0.08, 0.16, 0.01), location=(0, 0, 0.005), mat=m_frame)
    create_mesh_plane("Phone_Screen", size=1.0, scale=(0.075, 0.15, 1.0), location=(0, 0, 0.011), mat=m_glass)

def build_prop_books():
    m_book1 = make_material("Book1", "#DC2626", roughness=0.6)
    m_book2 = make_material("Book2", "#2563EB", roughness=0.6)
    m_book3 = make_material("Book3", "#16A34A", roughness=0.6)
    m_pages = make_material("BookPages", "#FEF3C7", roughness=0.9)

    # Book 1 (Bottom)
    create_mesh_cube("Book1_Cover", size=1.0, scale=(0.22, 0.30, 0.04), location=(0, 0, 0.02), mat=m_book1)
    # Book 2 (Middle, slightly turned)
    create_mesh_cube("Book2_Cover", size=1.0, scale=(0.20, 0.28, 0.035), location=(0.01, 0.01, 0.057), rotation=(0, 0, math.radians(12)), mat=m_book2)
    # Book 3 (Top)
    create_mesh_cube("Book3_Cover", size=1.0, scale=(0.18, 0.25, 0.03), location=(-0.01, -0.01, 0.09), rotation=(0, 0, math.radians(-8)), mat=m_book3)

# --- LIGHTING PRESETS ---

def setup_lighting(preset_name: str):
    scene = bpy.context.scene

    if preset_name == "light_warm_interior":
        # Warm interior: Key light warm 3200K, fill soft warm, rim accent
        key = bpy.data.lights.new("WarmKey", 'AREA')
        key.energy = 100.0
        key.size = 2.0
        key.color = (1.0, 0.88, 0.72)
        obj_key = bpy.data.objects.new("WarmKey", key)
        scene.collection.objects.link(obj_key)
        obj_key.location = (2.0, -2.5, 3.0)

        fill = bpy.data.lights.new("WarmFill", 'POINT')
        fill.energy = 50.0
        fill.color = (1.0, 0.94, 0.85)
        obj_fill = bpy.data.objects.new("WarmFill", fill)
        scene.collection.objects.link(obj_fill)
        obj_fill.location = (-2.0, -1.5, 2.0)

    elif preset_name == "light_neon_night":
        # Neon Night: Cyan & Pink dual edge lighting
        cyan = bpy.data.lights.new("NeonCyan", 'AREA')
        cyan.energy = 150.0
        cyan.size = 2.5
        cyan.color = (0.05, 0.85, 1.0)
        obj_cyan = bpy.data.objects.new("NeonCyan", cyan)
        scene.collection.objects.link(obj_cyan)
        obj_cyan.location = (-2.5, -1.0, 2.5)

        pink = bpy.data.lights.new("NeonPink", 'AREA')
        pink.energy = 150.0
        pink.size = 2.5
        pink.color = (1.0, 0.15, 0.75)
        obj_pink = bpy.data.objects.new("NeonPink", pink)
        scene.collection.objects.link(obj_pink)
        obj_pink.location = (2.5, -1.0, 2.5)

    else: # daylight
        sun = bpy.data.lights.new("DaylightSun", 'SUN')
        sun.energy = 4.0
        sun.color = (1.0, 0.98, 0.92)
        obj_sun = bpy.data.objects.new("DaylightSun", sun)
        scene.collection.objects.link(obj_sun)
        obj_sun.location = (3.0, -3.0, 6.0)
        obj_sun.rotation_euler = (math.radians(50), math.radians(20), math.radians(30))

        fill = bpy.data.lights.new("SkyFill", 'AREA')
        fill.energy = 40.0
        fill.size = 4.0
        fill.color = (0.75, 0.88, 1.0)
        obj_fill = bpy.data.objects.new("SkyFill", fill)
        scene.collection.objects.link(obj_fill)
        obj_fill.location = (0, -2.0, 4.0)

def setup_camera_for_asset(category: str):
    cam_data = bpy.data.cameras.new("AssetCamera")
    cam_obj = bpy.data.objects.new("AssetCamera", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj

    if category == "background":
        cam_data.lens = 28.0 # Wide lens for backgrounds
        cam_obj.location = (0, -5.5, 2.0)
        cam_obj.rotation_euler = (math.radians(82), 0, 0)
    elif category == "lighting":
        # Lighting preview spheres
        m_chrome = make_material("BallChrome", "#E2E8F0", roughness=0.05, metallic=1.0)
        m_diffuse = make_material("BallDiffuse", "#F8FAFC", roughness=0.85)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.4, location=(-0.5, 0, 0.4))
        b1 = bpy.context.active_object
        b1.data.materials.append(m_diffuse)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.4, location=(0.5, 0, 0.4))
        b2 = bpy.context.active_object
        b2.data.materials.append(m_chrome)

        cam_data.lens = 50.0
        cam_obj.location = (0, -2.6, 0.7)
        cam_obj.rotation_euler = (math.radians(82), 0, 0)
    else: # prop
        cam_data.lens = 50.0 # Standard portrait lens for props
        cam_obj.location = (0, -1.8, 0.75)
        cam_obj.rotation_euler = (math.radians(72), 0, 0)

def main():
    argv = sys.argv
    if "--" in argv:
        custom_args = argv[argv.index("--") + 1:]
    else:
        custom_args = []

    parser = argparse.ArgumentParser(description="Blender Scene & Prop Builder")
    parser.add_argument("--asset-id", type=str, required=True)
    parser.add_argument("--output-blend", type=str, required=True)
    parser.add_argument("--output-thumb", type=str, required=True)
    parser.add_argument("--render-engine", type=str, default="CYCLES")

    args = parser.parse_args(custom_args)

    bpy.ops.wm.read_factory_settings(use_empty=True)

    aid = args.asset_id.lower()
    category = "prop"

    if aid.startswith("bg_"):
        category = "background"
        if "cafe" in aid:
            build_bg_modern_cafe()
            setup_lighting("light_warm_interior")
        elif "office" in aid:
            build_bg_office()
            setup_lighting("light_daylight")
        elif "park" in aid:
            build_bg_park()
            setup_lighting("light_daylight")
        elif "living" in aid:
            build_bg_living_room()
            setup_lighting("light_warm_interior")
        elif "tech" in aid:
            build_bg_tech_studio()
            setup_lighting("light_neon_night")
        else:
            build_bg_modern_cafe()
            setup_lighting("light_warm_interior")

    elif aid.startswith("light_"):
        category = "lighting"
        setup_lighting(aid)

    else:
        category = "prop"
        setup_lighting("light_warm_interior")
        if "table" in aid:
            build_prop_table()
        elif "chair" in aid:
            build_prop_chair()
        elif "cup" in aid or "coffee_cup" in aid:
            build_prop_coffee_cup()
        elif "machine" in aid:
            build_prop_coffee_machine()
        elif "laptop" in aid:
            build_prop_laptop()
        elif "smartphone" in aid:
            build_prop_smartphone()
        elif "books" in aid:
            build_prop_books()
        else:
            build_prop_table()

    setup_camera_for_asset(category)

    # Ensure output directories
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
