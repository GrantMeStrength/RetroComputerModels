"""Build an original, measured-profile ZX81 exterior. Run with headless Blender."""

import json
import os
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector
import numpy as np


ROOT = Path(__file__).resolve().parent
MM = 0.001
WIDTH = 167.0
DEPTH_LIMITS = (-87.17, 87.18)
# Authored control points, fitted to independently measured STL cross sections.
# s increases rear -> front, not Blender's depth coordinate.
UPPER = [
    (-87.17, 22.98), (-87, 23.613), (-86, 27.311), (-85, 31.009),
    (-84, 34.706), (-83, 38.404), (-82.7, 39.15), (-82.4, 39.39),
    (-82.1, 39.428), (-81.7, 39.39), (-81, 39.204), (-80, 38.931),
    (-75, 37.569), (-70, 36.207), (-65, 34.859), (-62.5, 34.29),
    (-60, 33.818), (-57.5, 33.452), (-55, 33.188),
    (-50, 32.770), (-30, 31.100), (-10, 29.430), (0, 28.596),
    (9.5, 27.802), (10, 27.761), (10.6, 27.51), (12, 26.557),
    (15, 24.144), (17, 22.535), (17.5, 22.418), (20, 22.209),
    (40, 20.540), (60, 18.870), (80, 17.201), (83.5, 16.908),
    (84.2, 16.817), (84.7, 16.65), (85, 16.368), (85.35, 15.75),
    (86, 13.18), (87, 9.876), (87.18, 9.40),
]
LOWER = [
    (-87.17, 19.83), (-87, 18.413), (-86, 10.062), (-85, 1.711),
    (-84.8, 0.15), (-84.5, 0), (76.9, 0),
    (77.5, 0.41), (80, 2.757), (84, 6.398), (87, 9.129), (87.18, 9.24),
]


def interp(value, controls):
    return float(np.interp(value, [p[0] for p in controls], [p[1] for p in controls]))


def material(name, texture=None, color=(0.018, 0.019, 0.022, 1), roughness=0.56):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Specular IOR Level"].default_value = 0.18
    if texture:
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = bpy.data.images.load(str(ROOT / "Textures" / texture))
        node.extension = "EXTEND"
        mat.node_tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def cross_section(s):
    h, bottom = interp(s, UPPER), interp(s, LOWER)
    thickness = h - bottom
    radius = float(np.interp(s, [10, 17], [4, 1]))
    radius = min(radius, thickness * 0.22)
    rear_draft = float(np.interp(s, [-70, -52], [1, 0]))
    underside_height = 8 + 10.5*rear_draft
    bottom_scale = min(1, thickness * 0.65 / underside_height)
    # Each side of the upper deck includes an original moulded edge, not a rail.
    shoulder = 83.5 - radius
    # Fixed point count is required for the loft, including through radius changes.
    left = [-83.5 + radius * (1-math.cos(t)) for t in np.linspace(0, math.pi/2, 9)]
    middle = [-79.673, -79.52, -79.32, -78.9, -76, -60, -30, 0,
              30, 60, 76, 78.9, 79.32, 79.52, 79.673]
    # At the broad 4 mm rear roundover the keyboard's future edge points must
    # lie inside the edge's tangent, while keeping stable vertex correspondence.
    middle = [x * min(1, (shoulder - 0.03) / 79.673) for x in middle]
    xs = left + middle + [-v for v in reversed(left)]
    points = []
    for x in xs:
        edge = max(0, abs(x) - shoulder)
        z = h - radius + math.sqrt(max(0, radius*radius - edge*edge))
        depth_recess = float(np.interp(s, [17, 17.4, 18, 82, 82.6, 83], [0, 0, 1, 1, 0.3, 0]))
        width_recess = float(np.interp(abs(x), [79.32, 79.52, 79.673], [1, 0.88, 0]))
        z -= depth_recess * width_recess * (1.28 + max(0, s-20)*0.00228)
        points.append((x, -s, z))
    seam = 12.086 - 0.03317*s if s >= -52 else 13.811 + (-52-s)*0.28485
    seam_delta = min(0.12, thickness*0.025)
    seam = max(bottom + underside_height*bottom_scale + 2*seam_delta,
               min(h-radius-2*seam_delta, seam))
    # Smoothly tucked underside, derived from the measured lower case profile.
    lower_round = [(83.5, 8), (83.4, 7.28), (83.1, 6.65), (82.6, 6.14),
                   (81.7, 5.69), (80.75, 5.15), (80.12, 4.05), (79.18, 0)]
    # Rear sections have a taller continuous draft, rather than the front's
    # compact undercut. Measured rear widths: ~79.2 at Z=0, ~82 at Z=12 mm.
    lower_round = [(x, bottom+bottom_scale*((1-rear_draft)*z +
                     rear_draft*(x-79.18)/4.32*18.5)) for x, z in lower_round]
    side = [(83.5, seam + seam_delta), (83.36, seam), (83.5, seam - seam_delta)] + lower_round
    tuck = min(1, thickness/12)
    side = [(83.5-(83.5-x)*tuck, z) for x, z in side]
    points += [(x, -s, z) for x, z in side]
    points += [(0, -s, bottom)]
    points += [(-x, -s, z) for x, z in reversed(side)]
    inset = 0
    for distance, r in [(s-DEPTH_LIMITS[0], 2.5), (DEPTH_LIMITS[1]-s, 2)]:
        if distance < r:
            inset = max(inset, r - math.sqrt(max(0, r*r - (r-distance)**2)))
    points = [(x*(83.5-inset)/83.5, y, z) for x, y, z in points]
    return points, len(xs)


def make_body(mats):
    samples = sorted(set([p[0] for p in UPPER + LOWER] +
                         list(np.linspace(*DEPTH_LIMITS, 120)) +
                         [17.4, 18, 82, 82.6, 83]))
    vertices, faces, sections = [], [], []
    for s in samples:
        ring, top_count = cross_section(s)
        sections.append(ring)
        vertices.extend(ring)
    count = len(sections[0])
    for i in range(len(sections)-1):
        for j in range(count):
            faces.append((i*count+j, i*count+(j+1)%count,
                          (i+1)*count+(j+1)%count, (i+1)*count+j))
    faces += [tuple(reversed(range(count))),
              tuple((len(sections)-1)*count+j for j in range(count))]
    mesh = bpy.data.meshes.new("AuthoredMeasuredProfileLoft")
    mesh.from_pydata([[p*MM for p in v] for v in vertices], [], faces)
    mesh.update()
    body = bpy.data.objects.new("ZX81_OriginalProfileCase", mesh)
    bpy.context.collection.objects.link(body)
    for mat in mats:
        mesh.materials.append(mat)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    return body


def boolean(body, cutter):
    bpy.context.view_layer.objects.active = body
    modifier = body.modifiers.new("Shallow photographic socket recess", "BOOLEAN")
    modifier.operation = "DIFFERENCE"
    modifier.solver = "EXACT"
    modifier.object = cutter
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def sockets(body):
    for s, z, r in [(-42.6, 18.2, 2.5), (-23.7, 13.86, 2.15),
                    (-9.43, 13.73, 2.15), (5.06, 13.6, 2.2)]:
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=r*MM, depth=3.2*MM,
                                           location=(-83.5*MM, -s*MM, z*MM),
                                           rotation=(0, math.pi/2, 0))
        boolean(body, bpy.context.object)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(43.5*MM, 88.2*MM, 9.5*MM))
    cutter = bpy.context.object
    cutter.dimensions = (63*MM, 7.4*MM, 14.5*MM)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bevel = cutter.modifiers.new("Opening corner radius", "BEVEL")
    bevel.width = 0.45*MM
    bevel.segments = 3
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    boolean(body, cutter)


def map_materials(body):
    mesh = body.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-6)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    for layer in list(mesh.uv_layers):
        mesh.uv_layers.remove(layer)
    uv = mesh.uv_layers.new(name="UVMap")
    uv.active_render = True
    for polygon in mesh.polygons:
        center = polygon.center / MM
        x, y, z = center
        s = -y
        h = interp(s, UPPER)
        # Material indices: top, connector side, rear, unphotographed plastic.
        if s < -82.3 and polygon.normal.y > 0.15:
            index = 2
        elif x > 8 and y > 84 and z < 18:
            index = 2
        elif x < -79.0 and z < h - min(1.6, (h-interp(s, LOWER))*0.19):
            index = 1
        elif polygon.normal.z > 0.05 and z > h - 4.5:
            index = 0
        else:
            index = 3
        polygon.material_index = index
        polygon.use_smooth = True
        for li in polygon.loop_indices:
            p = mesh.vertices[mesh.loops[li].vertex_index].co / MM
            if index == 0:
                st = ((p.x+83.5)/167, 1-(-p.y+82.2)/169.38)
            elif index == 1:
                st = ((-p.y+87.18)/174.36, (p.z+0.08)/39.51)
            elif index == 2:
                st = ((83.5-p.x)/167, (p.z+0.08)/39.51)
            else:
                st = ((p.x+83.5)/167, (-p.y+87.18)/174.36)
            uv.data[li].uv = st
    # Preserve planar decks and socket rims, smooth only real shallow transitions.
    bm = bmesh.new()
    bm.from_mesh(mesh)
    for edge in bm.edges:
        if len(edge.link_faces) == 2:
            edge.smooth = edge.calc_face_angle() < math.radians(38)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def validate_blender(body):
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bad_edges = sum(not e.is_manifold for e in bm.edges)
    bad_faces = sum(f.calc_area() < 5e-13 for f in bm.faces)
    volume = bm.calc_volume(signed=True)
    result = {"vertices": len(bm.verts), "triangles": len(bm.faces),
              "nonmanifold_edges": bad_edges, "degenerate_faces": bad_faces,
              "signed_volume_m3": volume,
              "dimensions_mm_width_depth_height": [round(v/MM, 4) for v in body.dimensions]}
    if bad_edges or bad_faces or volume <= 0:
        print("SMALL_FACES", [[list(v.co / MM) for v in p.verts] for p in bm.faces if p.calc_area() < 5e-13])
        raise ValueError(result)
    bm.free()
    return result


def rubber_feet():
    parts = []
    mat = material("Photograph_Supported_Rubber_Feet", color=(0.008, 0.008, 0.009, 1),
                   roughness=0.82)
    for x in [-65, 65]:
        for s in [-52.6, 67.4]:
            bpy.ops.mesh.primitive_cube_add(size=1, location=(x*MM, -s*MM, -0.85*MM))
            foot = bpy.context.object
            foot.name = f"RubberFoot_{x}_{s}"
            foot.dimensions = (11*MM, 10*MM, 1.9*MM)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            foot.data.materials.append(mat)
            bevel = foot.modifiers.new("Soft rubber corners", "BEVEL")
            bevel.width = 0.35*MM
            bevel.segments = 4
            bpy.ops.object.modifier_apply(modifier=bevel.name)
            parts.append(foot)
    return parts


def point_at(obj, target=(0, 0, 0.018)):
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat("-Z", "Y").to_euler()


def render_previews(body):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.world.color = (0.12, 0.12, 0.12)
    scene.view_settings.view_transform = "AgX"
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -0.00185))
    ground = bpy.context.object
    ground.name = "PreviewOnly_Ground"
    ground.data.materials.append(material("PreviewOnly_Background", color=(0.31, 0.33, 0.36, 1)))
    for location, power, size in [((-0.2, -0.22, 0.4), 3, 0.30),
                                  ((0.25, 0.08, 0.24), 2, 0.25),
                                  ((-0.08, 0.30, 0.22), 1.6, 0.20)]:
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.name = "PreviewOnly_Softbox"
        light.data.energy = power
        light.data.shape = "DISK"
        light.data.size = size
        point_at(light)
    bpy.ops.object.light_add(type="AREA", location=(-0.15, -0.1, -0.3))
    underlight = bpy.context.object
    underlight.name = "PreviewOnly_UndersideInspection"
    underlight.data.energy = 2
    underlight.data.size = 0.25
    point_at(underlight, (0, 0, 0))
    underlight.hide_render = True
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.name = "PreviewOnly_Camera"
    scene.camera = camera
    camera.data.type = "ORTHO"
    views = {
        "front-three-quarter": ((-0.25, -0.31, 0.23), 0.26, (1200, 1000)),
        "rear-three-quarter": ((-0.24, 0.31, 0.18), 0.26, (1200, 900)),
        "top": ((0, 0, 0.5), 0.198, (1200, 1200)),
        "connector-side": ((-0.5, 0, 0.02), 0.195, (1400, 420)),
        "plain-side": ((0.5, 0, 0.02), 0.195, (1400, 420)),
        "rear": ((0, 0.5, 0.020), 0.19, (1400, 420)),
        "front": ((0, -0.5, 0.020), 0.19, (1400, 420)),
        "underside": ((0, 0, -0.5), 0.198, (1000, 1000)),
    }
    for name, (location, scale, resolution) in views.items():
        ground.hide_render = name == "underside"
        underlight.hide_render = name != "underside"
        camera.location = location
        point_at(camera, (0, 0, 0.020 if name not in ["top", "underside"] else 0))
        camera.data.ortho_scale = scale
        scene.render.resolution_x, scene.render.resolution_y = resolution
        scene.render.resolution_percentage = 100
        scene.render.filepath = str(ROOT / f"preview-{name}.png")
        if os.environ.get("RETRO_RENDER", "1") == "1":
            bpy.ops.render.render(write_still=True)
    ground.hide_render = False
    underlight.hide_render = True
    camera.location = views["front-three-quarter"][0]
    point_at(camera)
    camera.data.ortho_scale = 0.26


def main():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1
    mats = [material("Photo_Top_Membrane_And_Logo", "top.jpg"),
            material("Photo_Left_Connectors", "side.jpg"),
            material("Photo_Rear_Expansion", "back.jpg"),
            material("Unphotographed_Black_ABS")]
    body = make_body(mats)
    sockets(body)
    map_materials(body)
    parts = [body] + rubber_feet()
    bpy.context.view_layer.update()
    report = validate_blender(body)
    report["case_dimensions_mm_width_depth_height"] = report.pop("dimensions_mm_width_depth_height")
    report["parts"] = [validate_blender(part) for part in parts]
    report["vertices"] = sum(part["vertices"] for part in report["parts"])
    report["triangles"] = sum(part["triangles"] for part in report["parts"])
    corners = [part.matrix_world @ Vector(corner) for part in parts for corner in part.bound_box]
    report["dimensions_mm_width_depth_height"] = [
        round((max(p[i] for p in corners)-min(p[i] for p in corners))/MM, 4) for i in range(3)]
    report.update({"units": "authored in millimetres, stored in metres",
                   "upper_profile_mm": UPPER, "lower_profile_mm": LOWER,
                   "method": "Original cross-sectional loft; STL meshes never imported into scene.",
                   "status": "Reference-derived exterior model"})
    bpy.ops.object.select_all(action="DESELECT")
    for part in parts:
        part.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.wm.usd_export(
        filepath=str(ROOT / "zx81.usdz"),
        selected_objects_only=True, export_materials=True,
        generate_preview_surface=True, export_lights=False, export_cameras=False,
        export_custom_properties=False, triangulate_meshes=True,
        convert_orientation=True, export_global_up_selection="Y",
        export_global_forward_selection="NEGATIVE_Z", convert_world_material=False,
        overwrite_textures=True,
    )
    report["usdz_bytes"] = (ROOT / "zx81.usdz").stat().st_size
    (ROOT / "candidate-metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    render_previews(body)
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "zx81.blend"))
    print("CANDIDATE_METRICS", json.dumps(report))


if __name__ == "__main__":
    main()
