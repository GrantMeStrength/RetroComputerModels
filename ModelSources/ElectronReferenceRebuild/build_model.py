"""Original, provisional Electron geometry. Headless only; writes beside this script."""
import json
import os
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent
MM = 0.001
PARTS = []
SLOPE = 18 / 160
PUBLISHED_OVERALL_HEIGHT_MM = 65.0
Z_FACTOR = 1.0


def deck(y):
    return 43 + SLOPE * y


def material(name, color, texture=None, metallic=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = 0.42 if metallic else 0.57
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Specular IOR Level"].default_value = 0.12
    if texture:
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(str(ROOT / "textures" / texture))
        mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def mesh_object(name, vertices, faces, mat):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(c * MM for c in v) for v in vertices], [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    PARTS.append(obj)
    return obj


def rounded_ring(width, depth, radius, count=8):
    result = []
    for cx, cy, angle in [(width/2-radius, depth/2-radius, 0),
                          (-width/2+radius, depth/2-radius, 90),
                          (-width/2+radius, -depth/2+radius, 180),
                          (width/2-radius, -depth/2+radius, 270)]:
        for i in range(count):
            a = math.radians(angle + i * 90 / (count - 1))
            result.append((cx + radius * math.cos(a), cy + radius * math.sin(a)))
    return result


def loft(name, sections, mat):
    verts, faces = [], []
    for width, depth, radius, height in sections:
        ring = rounded_ring(width, depth, radius)
        verts.extend((x, y, height(x, y)) for x, y in ring)
    n = len(ring)
    faces.append(tuple(reversed(range(n))))
    for k in range(len(sections)-1):
        for j in range(n):
            faces.append((k*n+j, k*n+(j+1)%n, (k+1)*n+(j+1)%n, (k+1)*n+j))
    faces.append(tuple((len(sections)-1)*n+j for j in range(n)))
    return mesh_object(name, verts, faces, mat)


def box(name, location, dimensions, mat, bevel=0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=tuple(v*MM*(Z_FACTOR if i == 2 else 1)
                                                         for i, v in enumerate(location)))
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = tuple(v*MM*(Z_FACTOR if i == 2 else 1) for i, v in enumerate(dimensions))
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if bevel:
        modifier = obj.modifiers.new("Moulded corner radius", "BEVEL")
        modifier.width = bevel * MM
        modifier.segments = 3
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    PARTS.append(obj)
    return obj


def difference(body, cutter):
    bpy.context.view_layer.objects.active = body
    modifier = body.modifiers.new("Authored socket or keyboard recess", "BOOLEAN")
    modifier.operation = "DIFFERENCE"
    modifier.solver = "EXACT"
    modifier.object = cutter
    bpy.ops.object.modifier_apply(modifier=modifier.name)


def discard(obj):
    if obj in PARTS:
        PARTS.remove(obj)
    bpy.data.objects.remove(obj, do_unlink=True)


def cylinder(name, location, radius, depth, mat, axis="X"):
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=radius*MM, depth=depth*MM,
                                       location=tuple(v*MM*(Z_FACTOR if i == 2 else 1)
                                                      for i, v in enumerate(location)))
    obj = bpy.context.object
    obj.name = name
    if axis == "X":
        obj.rotation_euler.y = math.pi/2
    elif axis == "Y":
        obj.rotation_euler.x = math.pi/2
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    obj.data.materials.append(mat)
    PARTS.append(obj)
    return obj


def ring(name, location, outer, inner, depth, mat, axis="X"):
    obj = cylinder(name, location, outer, depth, mat, axis)
    cutter = cylinder("Discard_ring_bore", location, inner, depth+2, mat, axis)
    difference(obj, cutter)
    discard(cutter)
    return obj


def map_uv(obj):
    if obj.data.uv_layers:
        return
    uv = obj.data.uv_layers.new(name="UVMap")
    for polygon in obj.data.polygons:
        for li in polygon.loop_indices:
            p = obj.data.vertices[obj.data.loops[li].vertex_index].co
            uv.data[li].uv = (p.x / .34 + .5, p.y / .16 + .5)


def port_label(name, index, location, width, mat, axis):
    size = (.03, width, 2.8) if axis == "X" else (width, .03, 2.8)
    obj = box(name, location, size, mat)
    if axis == "X":
        for v in obj.data.vertices:
            v.co.x -= .245 * v.co.z / Z_FACTOR
    for layer in list(obj.data.uv_layers):
        obj.data.uv_layers.remove(layer)
    uv = obj.data.uv_layers.new(name="UVMap")
    for poly in obj.data.polygons:
        for li in poly.loop_indices:
            p = obj.data.vertices[obj.data.loops[li].vertex_index].co / MM
            # Viewed from left, rear is image-left; viewed from rear, +X is image-left.
            u = .5 - (p.y if axis == "X" else p.x) / width
            v = .5 - p.z / (2.8 * Z_FACTOR)
            uv.data[li].uv = (((index % 4) + u)/4, 1-((index//4)+v)/2)


def keycap(key, index, mat):
    w, d = key["width"], 17.95
    vertices, faces, zones = [], [], []
    rings = [(w-0.5, d-0.5, 0, 0.8), (w, d, 1.1, 0.9),
             (w-3, d-3.0, 11.4, 1.2), (w-3.7, d-3.7, 11.75, 1.2)]
    for width, depth, height, radius in rings:
        vertices.extend((x, y, height) for x, y in rounded_ring(width, depth, radius))
    n = 32
    faces.append(tuple(reversed(range(n))))
    zones.append("side")
    for k in range(len(rings)-1):
        for j in range(n):
            faces.append((k*n+j, k*n+(j+1)%n, (k+1)*n+(j+1)%n, (k+1)*n+j))
            zones.append("front" if k == 1 and vertices[k*n+j][1] < -d*.3 else "side")
    # Cylindrical dish: edge-high, centre-low. Spacebar is convex instead.
    for fraction in [0.72, 0.43, 0.15]:
        start = len(vertices)
        for x, y in rounded_ring((w-3.7)*fraction, (d-3.7)*fraction, 1.2*fraction):
            height = 11.75 - 1.05 * (1-(x/((w-3.7)/2))**2)
            if key["row"] == 4:
                height = 11.75 + .55 * (1-(y/((d-3.7)/2))**2)
            vertices.append((x, y, height))
        for j in range(n):
            faces.append((start-n+j, start-n+(j+1)%n, start+(j+1)%n, start+j))
            zones.append("top")
    start = len(vertices)-n
    vertices.append((0, 0, 10.7 if key["row"] != 4 else 12.3))
    for j in range(n):
        faces.append((start+j, start+(j+1)%n, len(vertices)-1))
        zones.append("top")
    obj = mesh_object(f"Key_{index:02d}_{key['label'].replace(chr(10), '_') or 'SPACE'}",
                      [(x+key["x"], y+key["y"], z+deck(y+key["y"])-2)
                       for x, y, z in vertices], faces, mat)
    uv = obj.data.uv_layers.new(name="UVMap")
    cx, cy = key["atlas_cell"]
    for poly, zone in zip(obj.data.polygons, zones):
        poly.use_smooth = True
        for li in poly.loop_indices:
            x, y, z = vertices[obj.data.loops[li].vertex_index]
            if zone == "top":
                u = .08 + .84*(x/(w-3.7)+.5)
                v = .07 + .86*(.5-y/(d-3.7))
                pixel = (u*256, v*192)
            elif zone == "front":
                pixel = (128+x/w*240, 192+(1-(z-1.1)/10.3)*64)
            else:
                pixel = (7, 180)
            uv.data[li].uv = ((cx*256+pixel[0])/2048, 1-(cy*256+pixel[1])/2048)
    return obj


def finish(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    result = {"name": obj.name, "vertices": len(bm.verts), "triangles": len(bm.faces),
              "nonmanifold_edges": sum(not e.is_manifold for e in bm.edges),
              "degenerate_faces": sum(f.calc_area() < 5e-13 for f in bm.faces),
              "signed_volume_m3": bm.calc_volume(signed=True)}
    bm.free()
    if result["nonmanifold_edges"] or result["degenerate_faces"] or result["signed_volume_m3"] <= 0:
        raise ValueError(result)
    map_uv(obj)
    return result


def point_at(obj, target=(0, 0, .0325)):
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat("-Z", "Y").to_euler()


def previews():
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 4
    scene.world.color = (.22, .22, .22)
    scene.view_settings.view_transform = "AgX"
    scene.render.image_settings.file_format = "PNG"
    for location, energy, size in [((-.3, -.3, .45), 2.5, .35), ((.3, .12, .3), 1.5, .3),
                                   ((0, .3, .4), 1.5, .3), ((0, 0, -.3), .6, .25)]:
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.name = "ReviewOnly_Softbox"
        light.data.energy, light.data.size = energy, size
        point_at(light)
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.name = "ReviewOnly_Camera"
    camera.data.type = "ORTHO"
    scene.camera = camera
    views = {
        "front-three-quarter": ((-.32, -.4, .31), .405, (1100, 760)),
        "rear-three-quarter": ((-.32, .4, .24), .405, (1100, 700)),
        "top": ((0, 0, .6), .385, (1200, 660)),
        "rear": ((0, .6, .027), .375, (1200, 300)),
        "front": ((0, -.6, .027), .375, (1200, 300)),
        "connector-side": ((-.6, 0, .0325), .205, (900, 360)),
        "plain-side": ((.6, 0, .0325), .205, (900, 360)),
        "underside": ((0, 0, -.6), .38, (1100, 600)),
    }
    for name, (location, scale, resolution) in views.items():
        camera.location = location
        point_at(camera)
        camera.data.ortho_scale = scale
        scene.render.resolution_x, scene.render.resolution_y = resolution
        scene.render.resolution_percentage = 100
        scene.render.filepath = str(ROOT / "renders" / f"{name}.png")
        if os.environ.get("RETRO_RENDER", "1") == "1":
            bpy.ops.render.render(write_still=True)
    camera.location = views["front-three-quarter"][0]
    camera.data.ortho_scale = .405
    point_at(camera)


def main():
    global Z_FACTOR
    Z_FACTOR = 1.0
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1
    ivory = material("Warm ivory ABS - photo estimate", (.68, .63, .48))
    dark = material("Recess shadow charcoal", (.038, .033, .024))
    rubber = material("Rubber feet", (.032, .032, .028))
    metal = material("Connector metal", (.36, .37, .34), metallic=.8)
    gold = material("Expansion contact brass", (.45, .3, .075), metallic=.7)
    keys = material("Original drawn key legends", (.8, .75, .61), "key-legends.png")
    badge_mat = material("Original grid badge redraw", (.2, .2, .15), "badge.png")
    label_mat = material("Original small connector legends", (.8, .75, .61), "port-legends.png")
    lower = loft("Lower_shell_rounded_tucked_base", [
        (326, 146, 6, lambda x,y: 2),
        (334, 154, 6, lambda x,y: 4),
        (339.4, 159.4, 4.6, lambda x,y: 15),
        (339.4, 159.4, 4.6, lambda x,y: 17.75)], ivory)
    upper = loft("Upper_shell_sloped_deck", [
        (339.4, 159.4, 4.6, lambda x,y: 18.25),
        (340, 160, 4.8, lambda x,y: 19.25),
        (340, 160, 4.8, lambda x,y: deck(y)-2.5),
        (339.2, 159.2, 5.0, lambda x,y: deck(y)-.9),
        (337.0, 157.0, 5.2, lambda x,y: deck(y))], ivory)
    for x in [-149, 149]:
        cutter = box("Discard_shallow_deck_parting_line", (x, 0, deck(0)+.14),
                     (.24, 160.5, .62), ivory)
        cutter.rotation_euler.x = math.atan(SLOPE)
        difference(upper, cutter)
        discard(cutter)
        for y, z, h in [(79.9, 35, 34), (-79.9, 26, 16)]:
            cutter = box("Discard_end_parting_line", (x, y, z), (.24, .7, h), ivory)
            difference(upper, cutter)
            discard(cutter)
    for x, y, width, depth in [(0, 3.4, 292.5, 80), (-9.525, -47.9, 154, 20)]:
        cutter = box("Discard_keyboard_pocket", (x, y, deck(y)+1),
                     (width, depth, 8), ivory, 1.0)
        cutter.rotation_euler.x = math.atan(SLOPE)
        difference(upper, cutter)
        discard(cutter)
    for index, key in enumerate(json.loads((ROOT / "keyboard-layout.json").read_text())):
        keycap(key, index, keys)
    badge = box("Flush_rear_grid_badge", (0, 61, deck(61)+.035),
                (294, 32, .16), badge_mat)
    badge.rotation_euler.x = math.atan(SLOPE)
    for layer in list(badge.data.uv_layers):
        badge.data.uv_layers.remove(layer)
    uv = badge.data.uv_layers.new(name="UVMap")
    for poly in badge.data.polygons:
        for li in poly.loop_indices:
            v = badge.data.vertices[badge.data.loops[li].vertex_index].co
            uv.data[li].uv = (v.x/.294+.5, v.y/.032+.5)
    bpy.context.view_layer.update()
    raw_corners = [obj.matrix_world @ Vector(c) for obj in PARTS for c in obj.bound_box]
    # Feet are constructed later with their underside at Z=0.
    raw_height = max(p.z for p in raw_corners)
    height_factor = PUBLISHED_OVERALL_HEIGHT_MM * MM / raw_height
    for obj in PARTS:
        transform = obj.matrix_world.copy()
        for vertex in obj.data.vertices:
            p = transform @ vertex.co
            p.z *= height_factor
            vertex.co = p
        obj.matrix_world = Matrix.Identity(4)
    Z_FACTOR = height_factor
    # Cut sockets after height normalization so their bores remain circular.
    for name, y, radius in [("UHF", 14, 5.8), ("VIDEO", -5, 5.8),
                            ("RGB", -24, 7.5), ("CASSETTE", -43.5, 7.5)]:
        port_label(name+"_printed_legend", ["UHF", "VIDEO", "RGB", "CASSETTE"].index(name),
                   (-167.42, y, 5.5), 16, label_mat, "X")
        cutter = cylinder("Discard_socket", (-169, y, 18), radius+.45, 12, dark)
        for shell in [upper, lower]:
            difference(shell, cutter)
        discard(cutter)
        cylinder(name+"_dark_socket_interior", (-165.0, y, 18), radius, 1, dark)
        ring(name+"_metal_recess_rim", (-168.35, y, 18), radius, radius-.75, 1.8, metal)
        if radius == 7.5:
            for n in range(7 if name == "CASSETTE" else 6):
                a = math.radians(30 + n*42)
                cylinder(name+f"_pin_{n}", (-166.2, y+3.8*math.cos(a), 18+3.8*math.sin(a)),
                         .48, 1.1, metal)
        else:
            ring(name+"_inner_socket", (-166.3, y, 18), 2.0, .8, .8, metal)
    cutter = box("Discard_expansion_slot", (0, 78.5, 11.5), (98, 12, 9), dark, .6)
    for shell in [upper, lower]:
        difference(shell, cutter)
    discard(cutter)
    box("Expansion_recess_plastic_interior", (0, 73.5, 11.5), (97, 1, 8.5), ivory)
    box("Expansion_edge_board", (0, 77.0, 8.7), (95, 3.5, 1.5), dark)
    for n in range(25):
        box(f"Expansion_contact_{n:02d}", (-45.6+n*3.8, 77, 9.51),
            (2.3, 3.4, .12), gold)
    for center in [-125, 125]:
        for n in range(10):
            x = center + (n-4.5)*4.2
            cutter = box("Discard_rear_vent", (x, 78, 10.5), (1.7, 10, 10.5), dark, .35)
            difference(lower, cutter)
            discard(cutter)
            box(f"Rear_vent_interior_{center}_{n}", (x, 73.5, 10.5), (1.7, .5, 10.5), dark)
    led = material("Caps-lock indicator amber", (.48, .2, .012))
    cylinder("Caps_lock_LED", (-151, 4, deck(4)+.3), 1.1, .5, led, "Z")
    for x in [-138, 138]:
        for y in [-53, 53]:
            box(f"Provisional_rubber_foot_{x}_{y}", (x, y, 1), (13, 11, 2), rubber, .7)
    bpy.context.view_layer.update()
    reports = [finish(obj) for obj in PARTS]
    corners = [obj.matrix_world @ Vector(c) for obj in PARTS for c in obj.bound_box]
    report = {"status": "Reference-guided exterior; not dimensionally certified",
              "dimensions_mm_width_depth_height": [
                  round((max(c[i] for c in corners)-min(c[i] for c in corners))/MM, 3)
                  for i in range(3)],
              "published_dimensions_mm": [340, 160, 65],
              "height_reconciliation": "340 x 160 x 65 mm is independently printed in the Micromundo distributor brochure, PDF page 3 / printed page 5. The original uncalibrated photo-shaped parameterization is not a measurement and cannot disprove 65 mm. Export is normalized to the published overall height; exact inclusion of feet/keycaps is not explicitly specified by either source.",
              "unscaled_photo_parameterization_height_mm": round(raw_height/MM, 6),
              "published_height_normalization_factor": height_factor,
              "dimension_source": "https://classic.technology/wp-content/uploads/2021/05/DeAcornElectron.pdf",
              "triangles": sum(r["triangles"] for r in reports), "meshes": len(PARTS),
              "key_count": 56, "parts": reports}
    bpy.ops.object.select_all(action="DESELECT")
    for obj in PARTS:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = upper
    bpy.ops.file.pack_all()
    bpy.ops.wm.usd_export(filepath=str(ROOT / "electron-review.usdz"),
        selected_objects_only=True, export_materials=True, generate_preview_surface=True,
        export_lights=False, export_cameras=False, export_custom_properties=False,
        triangulate_meshes=True, convert_orientation=True, export_global_up_selection="Y",
        export_global_forward_selection="NEGATIVE_Z", convert_world_material=False,
        overwrite_textures=True)
    report["usdz_bytes"] = (ROOT / "electron-review.usdz").stat().st_size
    (ROOT / "reports" / "geometry.json").write_text(json.dumps(report, indent=2)+"\n")
    previews()
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "electron-review.blend"))
    print("FINAL_METRICS", json.dumps({k:v for k,v in report.items() if k != "parts"}))


if __name__ == "__main__":
    main()
