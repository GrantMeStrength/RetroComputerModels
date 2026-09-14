"""Original common-profile shells with photograph-measured variant details.

Headless Blender only. No STL, scan or installed asset is loaded.
"""
import json
import os
import math
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Vector
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from layouts import LAYOUTS, PLATE_WIDTH, PLATE_DEPTH, PLATE_START, keys

MM = 0.001
WIDTH, DEPTH = 233.0, 144.0
UPPER = [(0, 27.2), (0.6, 28.5), (1.5, 29.5), (3, 30),
         (40, 30), (42, 29.9), (43, 29.3), (44, 27.8),
         (45, 25.2), (46, 23.5), (47, 23), (48, 22.8),
         (139, 22.8), (141, 22.65), (142.5, 22.0), (144, 20.0)]
LOWER = [(0, 3.5), (2, 2), (5, 1.8), (130, 1.8),
         (136, 3.1), (140, 5), (144, 8)]


def interp(s, points):
    return float(np.interp(s, [p[0] for p in points], [p[1] for p in points]))


def material(name, color=(0.02, 0.023, 0.025, 1), texture=None, rough=0.6):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = color
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Specular IOR Level"].default_value = 0.22
    if texture:
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = bpy.data.images.load(str(ROOT / "Textures" / texture), check_existing=True)
        node.extension = "EXTEND"
        mat.node_tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def mesh_object(name, vertices, faces, mats):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([[v*MM for v in p] for p in vertices], [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    for mat in mats:
        mesh.materials.append(mat)
    return obj


def box(name, location, size, mat, radius=0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=[v*MM for v in location])
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = [v*MM for v in size]
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if mat:
        obj.data.materials.append(mat)
    if radius:
        bevel = obj.modifiers.new("Moulded corner roundover", "BEVEL")
        bevel.width = radius*MM
        bevel.segments = 3
        bpy.ops.object.modifier_apply(modifier=bevel.name)
    return obj


def cylinder(name, position, radius, depth, mat=None, rear=False):
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=radius*MM, depth=depth*MM,
                                      location=[v*MM for v in position],
                                      rotation=(math.pi/2, 0, 0) if rear else (0, 0, 0))
    obj = bpy.context.object
    obj.name = name
    if mat:
        obj.data.materials.append(mat)
    return obj


def subtract(body, cutters):
    bpy.ops.object.select_all(action="DESELECT")
    for cutter in cutters:
        cutter.select_set(True)
    bpy.context.view_layer.objects.active = cutters[0]
    bpy.ops.object.join()
    cutter = bpy.context.object
    bpy.context.view_layer.objects.active = body
    modifier = body.modifiers.new("Source-supported connector and vent recesses", "BOOLEAN")
    modifier.operation = "DIFFERENCE"
    modifier.solver = "EXACT"
    modifier.object = cutter
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def shell(mats):
    samples = sorted(set([p[0] for p in UPPER+LOWER] + list(np.linspace(0, 144, 74))))
    vertices, faces = [], []
    for s in samples:
        top = interp(s, UPPER)
        bottom = interp(s, LOWER)
        r = 2.2 if s >= 46 else 4.0
        inset = 0
        for distance, radius in [(s, 3), (144-s, 2.5)]:
            if distance < radius:
                inset = max(inset, radius-math.sqrt(max(0, radius*radius-(radius-distance)**2)))
        half = WIDTH/2-inset
        # Broad top, moulded side radius, joint, and tucked underbody form one
        # continuous closed contour. There is no replacement frame or scan.
        ring = []
        for angle in np.linspace(math.pi, math.pi/2, 7):
            ring.append((-half+r+r*math.cos(angle), 72-s, top-r+r*math.sin(angle)))
        ring += [(0, 72-s, top)]
        for angle in np.linspace(math.pi/2, 0, 7):
            ring.append((half-r+r*math.cos(angle), 72-s, top-r+r*math.sin(angle)))
        side = [(half, 13.5), (half-0.18, 13.2), (half-0.18, 12.9),
                (half, 12.6), (half-0.4, max(bottom+1.6, 8)),
                (half-2, bottom+0.55), (half-4, bottom)]
        ring += [(x, 72-s, z) for x, z in side]
        ring += [(0, 72-s, bottom)]
        ring += [(-x, 72-s, z) for x, z in reversed(side)]
        vertices.extend(ring)
    count = len(ring)
    for i in range(len(samples)-1):
        for j in range(count):
            faces.append((i*count+j, i*count+(j+1)%count,
                          (i+1)*count+(j+1)%count, (i+1)*count+j))
    faces += [tuple(reversed(range(count))),
              tuple((len(samples)-1)*count+j for j in range(count))]
    return mesh_object("Original_Common_Contoured_Shell", vertices, faces, mats)


def finish(obj, mapping=None):
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-7)
    bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=1e-7)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    for layer in list(mesh.uv_layers):
        mesh.uv_layers.remove(layer)
    uv = mesh.uv_layers.new(name="UVMap")
    uv.active_render = True
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            vertex = mesh.vertices[mesh.loops[li].vertex_index].co
            p = obj.matrix_world @ vertex / MM
            u, v = (p.x+116.5)/233, (p.y+72)/144
            if mapping:
                u, v = mapping(poly, p)
            uv.data[li].uv = (u, v)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bad = [e for e in bm.edges if not e.is_manifold]
    if bad:
        raise ValueError(f"{obj.name}: {len(bad)} nonmanifold edges")
    volume = bm.calc_volume(signed=True)
    if volume <= 0:
        raise ValueError(f"{obj.name}: nonpositive signed volume")
    bm.free()
    return {"name": obj.name, "vertices": len(mesh.vertices),
            "triangles": len(mesh.polygons), "volume_m3": volume}


def plate_uv(poly, p):
    return (p.x+PLATE_WIDTH/2)/PLATE_WIDTH, 1-(72-p.y-PLATE_START)/PLATE_DEPTH


def create_model(variant):
    layout = LAYOUTS[variant]
    prefix = layout["texture"]
    timex = prefix == "timex"
    plastic = material("Silver_Textured_ABS" if timex else "Black_Textured_ABS",
                       (.36, .39, .40, 1) if timex else (.013, .016, .017, 1))
    underside = material("Lower_ABS", (.36, .39, .40, 1) if timex else (.012, .014, .016, 1))
    rubber = material("Grey_Rubber" if timex else "BlueGrey_Rubber",
                      (.23, .26, .27, 1) if timex else (.066, .13, .14, 1), rough=.8)
    black = material("Socket_And_Foot_Rubber", (.008, .009, .01, 1), rough=.8)
    metal = material("Socket_Metal", (.3, .32, .34, 1), rough=.36)
    rear_art = material("Original_Drawn_Rear_Labels", texture=prefix+"-rear-labels.png")
    body = shell([plastic, underside, rear_art])
    parts = [body]
    cutters = []
    for name, x, outer in [("Power", layout["power_x"], 4.1), ("MIC", layout["mic_x"], 3.8),
                           ("EAR", layout["ear_x"], 3.8), ("TV", layout["rf_x"], 4.5)]:
        cutters.append(cylinder("Opening_"+name, (x, 72, 14.8), outer, 6.4, rear=True))
        ring = cylinder(name+"_Socket_Rim", (x, 70.2, 14.8), outer-.65, 1.2,
                        metal if name == "TV" else black, rear=True)
        hole = cylinder("InnerCutter", (x, 70.2, 14.8), 1.85 if name != "TV" else 2.4, 3, rear=True)
        subtract(ring, [hole])
        parts += [ring, cylinder(name+"_Dark_Back", (x, 69.2, 14.8), outer-.7, .25, black, rear=True)]
    ex, ew = layout["expansion_x"], layout["expansion_width"]
    cutters.append(box("ExpansionAperture", (ex, 72, 12.2), (ew, 8, 13), None, .8))
    if timex:
        parts.append(box("Timex_Expansion_Protective_Cap", (ex, 70.9, 11.8), (ew-2, 1.8, 11), plastic, .45))
        # The real TS1500 has shallow fake upper ventilation, not Spectrum slots.
        for x in np.linspace(-106, 106, 43):
            cutters.append(box("Moulded_Fake_Vent", (x, 60, 30), (1.5, 12, .85), None, .35))
        # The supplied underside has one longitudinal row of ten slots,
        # not a Spectrum-like grille on the opposite side.
        for y in np.linspace(14, -51, 10):
            cutters.append(box("UndersideVent", (110.5, y, 2.5), (5, 1.6, 3), None, .15))
        for angle in np.linspace(0, 2*math.pi, 12, endpoint=False):
            x, y = 89.5+11*math.cos(angle), -52+11*math.sin(angle)
            cutters.append(cylinder("Photographed_Round_Underside_Hole", (x, y, 1.8), 1.25, 2.6))
        for x, y in [(108, 22), (-108, 22), (108, -62), (-108, -62), (0, 62)]:
            cutters.append(cylinder("Underside_Screw_Well", (x, y, 2.5), 2.8, 4))
            parts.append(cylinder("Recessed_Screw_Head", (x, y, 3.8), 1.65, .3, black))
        cutters.append(cylinder("Single_Underside_Hole", (-50, 15, 1.8), 1.5, 2.6))
        parts.append(box("Timex_Underside_Expansion_Cover", (48, 61, 1.72), (70, 19, .22), plastic, .1))
    else:
        parts.append(box("Spectrum_Expansion_Dark_Back", (ex, 68.3, 12.2), (ew-1, .4, 12), black))
        pcb = material("Expansion_PCB", (.11, .12, .055, 1))
        gold = material("Expansion_Contacts", (.42, .29, .08, 1), rough=.35)
        parts.append(box("Spectrum_Edge_Board", (ex, 70.0, 12.7), (ew-4, 3, 1.4), pcb))
        for x in np.linspace(ex-ew/2+4, ex+ew/2-4, 28):
            parts.append(box("Edge_Contact", (x, 71.52, 12.7), (1.35, .12, 1.2), gold))
    subtract(body, cutters)
    foot_positions = [(x, y, 17, 9) for x in [-96, 96] for y in [-60, 58]]
    if timex:
        foot_positions = [(104, 45, 11, 15), (-104, 45, 11, 15),
                          (96, -58, 16, 10), (-94, -58, 16, 10)]
    for x, y, w, d in foot_positions:
        parts.append(box("Rubber_Foot", (x, y, 1), (w, d, 2), black, .5))

    plate_mat = material("Preserved_Plate_Legends", texture=prefix+"-plate-clean.jpg", rough=.6)
    key_art = material("Preserved_Rubber_Key_Printing", texture=prefix+"-plate.jpg", rough=.8)
    plate = box("Thin_Original_Keyboard_Faceplate", (0, 72-PLATE_START-PLATE_DEPTH/2, 22.95),
                (PLATE_WIDTH, PLATE_DEPTH, .28), plastic, .12)
    plate.data.materials.append(plate_mat)
    parts.append(plate)
    for key in keys(variant):
        x, y = key["center_mm"]
        w, d = key["size_mm"]
        obj = box(f"Rubber_Key_R{key['row']}_C{key['column']}", (x, y, 24.15),
                  (w, d, 3), rubber, .75)
        obj.data.materials.append(key_art)
        parts.append(obj)
    if timex:
        badge_mat = material("Timex_Sinclair_1500_Original_Badge", texture="timex-badge.jpg")
        badge = box("Timex_Badge", (-63, 34, 30.04), (78, 7.02, .10), badge_mat, .04)
        parts.append(badge)
        label_mat = material("Photographed_Portuguese_Underside_Label", texture="timex-underside-label.jpg")
        label = box("Original_Underside_Label", (48.28, 32.46, 1.73), (57.36, 45.54, .16), label_mat)
        parts.append(label)
    else:
        apron_mat = material("Original_Sinclair_Embossed_Apron", texture="spectrum-apron.jpg")
        apron = box("Sinclair_Apron_Artwork", (0, 49, 30.035), (225, 38, .08), apron_mat, .03)
        parts.append(apron)
    bpy.context.view_layer.update()

    def shell_mapping(poly, p):
        if poly.normal.y > .7 and p.y > 71.7:
            poly.material_index = 2
            return (116.5-p.x)/233, p.z/28
        poly.material_index = 1 if p.z < 12.9 else 0
        return (p.x+116.5)/233, (p.y+72)/144

    report = [finish(body, shell_mapping)]
    for obj in parts[1:]:
        if obj == plate or obj.name.startswith("Rubber_Key"):
            def key_mapping(poly, p):
                poly.material_index = 1 if poly.normal.z > .95 else 0
                return plate_uv(poly, p)
            mapping = key_mapping
        elif obj.name == "Timex_Badge":
            mapping = lambda poly, p: ((p.x+102)/78, (p.y-30.49)/7.02)
        elif obj.name == "Original_Underside_Label":
            mapping = lambda poly, p: ((76.96-p.x)/57.36, (p.y-9.69)/45.54)
        elif obj.name == "Sinclair_Apron_Artwork":
            mapping = lambda poly, p: ((p.x+112.5)/225, (p.y-30)/38)
        else:
            mapping = None
        report.append(finish(obj, mapping))
    return parts, report


def point_at(obj, target):
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat("-Z", "Y").to_euler()


def previews(variant):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 4
    scene.world.color = (.14, .14, .14)
    scene.view_settings.view_transform = "AgX"
    for location, power in [((-.22, -.25, .42), 4), ((.25, .1, .27), 3), ((-.1, .35, .25), 2), ((0, 0, -.3), 2)]:
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.name = "PreviewOnly_Softbox"
        light.data.energy = power
        light.data.size = .3
        point_at(light, (0, 0, .015))
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.name = "PreviewOnly_Camera"
    camera.data.type = "ORTHO"
    scene.camera = camera
    scene.render.image_settings.file_format = "PNG"
    views = {
        "three-quarter": ((-.26, -.34, .28), .285, (1150, 800)),
        "top": ((0, 0, .5), .255, (1200, 850)),
        "rear-three-quarter": ((.25, .34, .19), .28, (1100, 680)),
        "rear": ((0, .5, .015), .255, (1200, 300)),
        "left": ((-.5, 0, .015), .17, (1000, 340)),
        "right": ((.5, 0, .015), .17, (1000, 340)),
        "underside": ((0, 0, -.5), .255, (1200, 850)),
    }
    for name, (location, scale, size) in views.items():
        camera.location = location
        point_at(camera, (0, 0, .015 if name not in ["top", "underside"] else 0))
        if name == "underside":
            camera.rotation_euler.z += math.pi
        camera.data.ortho_scale = scale
        scene.render.resolution_x, scene.render.resolution_y = size
        scene.render.resolution_percentage = 100
        scene.render.filepath = str(ROOT / "Previews" / f"{variant}-{name}.png")
        if os.environ.get("RETRO_RENDER", "1") == "1":
            bpy.ops.render.render(write_still=True)
    camera.location = views["three-quarter"][0]
    point_at(camera, (0, 0, .015))
    camera.data.ortho_scale = .285


def main():
    selected = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else list(LAYOUTS)
    for variant in selected:
        bpy.ops.wm.read_factory_settings(use_empty=False)
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
        scene = bpy.context.scene
        scene.unit_settings.system = "METRIC"
        scene.unit_settings.scale_length = 1
        scene.render.image_settings.file_format = "PNG"
        parts, checks = create_model(variant)
        bpy.ops.object.select_all(action="DESELECT")
        for obj in parts:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = parts[0]
        bpy.ops.wm.usd_export(filepath=str(ROOT / f"{variant}.usdz"), selected_objects_only=True,
                              export_materials=True, generate_preview_surface=True,
                              export_lights=False, export_cameras=False,
                              export_custom_properties=False, triangulate_meshes=True,
                              convert_orientation=True, export_global_up_selection="Y",
                              export_global_forward_selection="NEGATIVE_Z",
                              convert_world_material=False, overwrite_textures=True)
        corners = [o.matrix_world @ Vector(c) for o in parts for c in o.bound_box]
        report = {
            "variant": variant, "status": "Awaiting visual approval",
            "dimensions_mm_width_depth_height": [round((max(p[i] for p in corners)-min(p[i] for p in corners))/MM, 4) for i in range(3)],
            "bytes": (ROOT / f"{variant}.usdz").stat().st_size,
            "triangles": sum(p["triangles"] for p in checks),
            "vertices": sum(p["vertices"] for p in checks),
            "parts": checks, "common_upper_profile_mm": UPPER, "common_lower_profile_mm": LOWER,
            "key_measurements": keys(variant), "connector_parameters": LAYOUTS[variant],
        }
        (ROOT / "Reports" / f"{variant}-metrics.json").write_text(json.dumps(report, indent=2)+"\n")
        previews(variant)
        bpy.ops.file.pack_all()
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / f"{variant}.blend"))
        print("COMPLETE", variant, report["triangles"], report["dimensions_mm_width_depth_height"])


if __name__ == "__main__":
    main()
