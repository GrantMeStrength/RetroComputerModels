"""Original geometry of the Italian PAL Apple IIe. Headless only."""
import argparse
import os
import json
import math
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent
MM = 1.0
PARTS = []
MEASUREMENTS = json.loads((ROOT / "iie-measurements.json").read_text())
WIDTH, DEPTH, HEIGHT = MEASUREMENTS["nominal_dimensions_mm_width_depth_height"]
SLOPE = (86.67 - 56.42) / (-70.77 + 223.66)
ANGLE = math.atan(SLOPE)
LID_SLOPE = (HEIGHT - 92.2) / (11.15 + 66.17)
LID_ANGLE = math.atan(LID_SLOPE)
ATLAS = json.loads((ROOT / "Textures/atlas.json").read_text())
ROWS = json.loads((ROOT / "keyboard-layout.json").read_text())
PROFILE = MEASUREMENTS["side_profile_y_z_mm"]


def linear(v):
    v /= 255
    return v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4


def material(name, rgb, roughness=.6, texture=None):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*map(linear, rgb), 1)
    m.use_nodes = True
    shader = m.node_tree.nodes["Principled BSDF"]
    shader.inputs["Base Color"].default_value = m.diffuse_color
    shader.inputs["Roughness"].default_value = roughness
    if texture:
        image = bpy.data.images.load(str(ROOT / "Textures" / texture))
        image.pack()
        node = m.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = image
        m.node_tree.links.new(node.outputs["Color"], shader.inputs["Base Color"])
    return m


def normals(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()


def mesh(name, vertices, faces, mat):
    data = bpy.data.meshes.new(name)
    data.from_pydata([[c * MM for c in v] for v in vertices], [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    data.materials.append(mat)
    normals(obj)
    PARTS.append(obj)
    return obj


def side_profile(name, width, outline, mat):
    n = len(outline)
    vertices = [(x, y, z) for x in (-width / 2, width / 2) for y, z in outline]
    faces = [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
    faces += [(i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n)]
    return mesh(name, vertices, faces, mat)


def xy_prism(name, outline, bottom, top, mat, part=True):
    n = len(outline)
    vertices = [(x, y, z) for z in (bottom, top) for x, y in outline]
    faces = [tuple(reversed(range(n))), tuple(range(n, n * 2))]
    faces += [(i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n)]
    obj = mesh(name, vertices, faces, mat)
    if not part:
        PARTS.remove(obj)
    return obj


def rear_prism(name, outline, y, depth, mat, part=True):
    n = len(outline)
    vertices = [(x, yy, z) for yy in (y - depth / 2, y + depth / 2) for x, z in outline]
    faces = [tuple(reversed(range(n))), tuple(range(n, n * 2))]
    faces += [(i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n)]
    obj = mesh(name, vertices, faces, mat)
    if not part:
        PARTS.remove(obj)
    return obj


def cylinder(name, location, radius, depth, mat, vertices=20):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius * MM,
                                       depth=depth * MM, location=[v * MM for v in location],
                                       rotation=(math.pi / 2, 0, 0))
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    PARTS.append(obj)
    return obj


def rear_x(pixel):
    return (581.5 - pixel) * WIDTH / 1031


def rear_z(pixel):
    return (317 - pixel) * HEIGHT / 295


def rear_uv(obj, mat):
    obj.data.materials.append(mat)
    uv = obj.data.uv_layers.active or obj.data.uv_layers.new(name="UVMap")
    for face in obj.data.polygons:
        if face.normal.y < .9:
            continue
        face.material_index = len(obj.data.materials) - 1
        for loop in face.loop_indices:
            vertex = obj.data.vertices[obj.data.loops[loop].vertex_index].co + obj.location
            px = 581.5 - vertex.x / MM * 1031 / WIDTH
            py = 317 - vertex.z / MM * 295 / HEIGHT
            uv.data[loop].uv = (px / 1186, 1 - py / 354)


def photo_box(name, bounds, y, depth, mat, radius=0, part=True):
    x1, y1, x2, y2 = bounds
    cx, cz = rear_x((x1 + x2) / 2), rear_z((y1 + y2) / 2)
    width, height = (x2 - x1) * WIDTH / 1031, (y2 - y1) * HEIGHT / 295
    if not radius:
        return box(name, (cx, y, cz), (width, depth, height), mat, part=part)
    contour = [(x + cx, z + cz) for x, z, _ in
               rounded_ring(width, height, min(radius, width * .4, height * .4), 0)]
    obj = rear_prism(name, contour, y, depth, mat, part)
    bevel(obj, min(.15, depth * .2), 2)
    return obj


def dsub(name, center, pins, vertical, metal, insert, dark):
    start = len(PARTS)
    width = 40.6 if pins == 25 else 30.8
    inner_width = 32.5 if pins == 25 else 16.9
    flange = box(name + " mounting flange", (0, 0, 0), (width, 2.0, 12.4), metal, 1.7)
    poly = [(-inner_width / 2 + 1, 4.3), (inner_width / 2 - 1, 4.3),
            (inner_width / 2, 3.1), (inner_width / 2 - 1.6, -4.3),
            (-inner_width / 2 + 1.6, -4.3), (-inner_width / 2, 3.1)]
    cut(flange, rear_prism("D-shaped connector opening", poly, 0, 5, metal, part=False))
    face = rear_prism(name + " recessed socket insert", poly, -.45, 1.25, insert)
    bevel(face, .25, 2)
    for row, count in enumerate(((13, 12) if pins == 25 else (5, 4))):
        for i in range(count):
            cylinder(name + " female contact well", ((i - (count - 1) / 2) * 2.4,
                                                     .23, 1.35 - row * 2.7),
                     .52, .18, dark, 12)
    for side in (-1, 1):
        screw = cylinder(name + " hex screw boss", (side * (width / 2 - 2.5), .35, 0),
                         1.55, 2.4, metal, 6)
        cylinder(name + " screw recess", (side * (width / 2 - 2.5), 1.59, 0),
                 .63, .12, dark, 12)
    rotation = Matrix.Rotation(math.pi / 2 if vertical else 0, 3, "Y")
    for obj in PARTS[start:]:
        obj.location = Vector([v * MM for v in center]) + rotation @ obj.location
        obj.rotation_euler = (rotation @ obj.rotation_euler.to_matrix()).to_euler()


def rear_panel(body, cream, dark):
    metal = material("IIe rear painted shielding", (84, 81, 69), .65)
    cover = material("IIe removable connector blanks", (76, 75, 64), .7)
    silver = material("Brushed connector metal", (164, 163, 150), .42)
    insert = material("Socket insert grey", (102, 102, 90), .7)
    brass = material("Mains inlet contact blades", (171, 148, 91), .4)
    labels = material("Redrawn IIe rear numbers and legends", (84, 81, 69), .7, "rear-labels.png")
    power_labels = material("Redrawn PSU legends", (29, 28, 23), .7, "rear-power.png")
    panel_bounds = [187, 79, 974, 302]
    cut(body, photo_box("Rear panel opening", [184, 77, 977, 306], 227, 28, cream, 1.2, part=False))
    panel = photo_box("IIe numbered rear shielding panel", panel_bounds, 225.4, 2.4, metal, .7)
    photo_box("Shadowed internal rear liner", [193, 83, 968, 298], 213.0, 1.5, dark, .8)
    blank_apertures = MEASUREMENTS["rear_photo_mapping"]["blank_apertures"]
    for number, bounds in blank_apertures.items():
        cut(panel, photo_box("Blank aperture " + number, bounds, 226, 8, metal, 2.0, part=False))
        inset = [bounds[0] + 1.7, bounds[1] + 1.7, bounds[2] - 1.7, bounds[3] - 1.7]
        photo_box("Recessed removable blank " + number, inset, 225.25, 1.6, cover, 1.4)
    for bounds in [[207, 96, 239, 206], [461, 102, 493, 182], [195, 235, 384, 276],
                   [785, 179, 963, 296]]:
        cut(panel, photo_box("Populated connector aperture", bounds, 226, 8, metal, 1.7, part=False))
    keyed_openings = [
        [(596, 98), (606, 98), (608, 110), (615, 111), (618, 124), (617, 149),
         (611, 154), (607, 167), (599, 168), (596, 155), (586, 153), (581, 137),
         (582, 121), (590, 117), (591, 109), (596, 108)],
        [(667, 98), (675, 98), (676, 111), (683, 115), (683, 214),
         (674, 222), (660, 222), (655, 215), (656, 120), (659, 112), (667, 110)],
    ]
    for number, outline in zip((8, 10), keyed_openings):
        points = [(rear_x(x), rear_z(z)) for x, z in outline]
        cut(panel, rear_prism(f"Keyed cable opening {number}", points, 226, 8, metal, part=False))
    for x in [211, 232, 253, 275, 296, 316, 855, 875, 895, 915, 936, 953]:
        cut(panel, photo_box("Small upper shielding vent", [x - 3, 84, x + 3, 90],
                             226, 8, metal, .75, part=False))
    for x in [356, 419, 485, 551, 616, 679, 742, 807]:
        cut(panel, photo_box("Long upper shielding vent", [x - 24, 84, x + 24, 90],
                             226, 8, metal, .75, part=False))
    map_uv(panel)
    rear_uv(panel, labels)
    dsub("Slot 1 DB25", (rear_x(222), 228.1, rear_z(151)), 25, True, silver, insert, dark)
    dsub("Slot 5 DE9", (rear_x(477), 228.1, rear_z(144)), 9, True, silver, insert, dark)
    photo_box("Built-in IIe I/O mounting plate", [195, 235, 384, 276], 226.0, 2.4, dark, 1.5)
    dsub("IIe game port DE9", (rear_x(339), 228.2, rear_z(257)), 9, False, silver, insert, dark)
    for pixel, radius, label in [(216, 4.0, "Composite video RCA"),
                                 (254, 2.8, "Cassette input"), (279, 2.8, "Cassette output")]:
        x, z = rear_x(pixel), rear_z(256)
        cylinder(label + " metal collar", (x, 229.3, z), radius, 3.2, silver, 24)
        cylinder(label + " dark socket", (x, 230.95, z), radius * .68, .18, dark, 24)
        if pixel == 216:
            cylinder(label + " center contact recess", (x, 231.06, z), .95, .12, brass, 16)
            cylinder(label + " hollow center", (x, 231.15, z), .57, .12, dark, 12)
    psu = photo_box("Power supply rear face", [785, 179, 963, 296], 225.8, 4.0, dark, 3.2)
    map_uv(psu)
    rear_uv(psu, power_labels)
    x, z = rear_x(845), rear_z(236)
    inlet = box("IEC mains inlet surround", (x, 228.8, z), (31, 6, 22), dark, 1.8)
    opening = [(x - 10.5, z - 7), (x + 10.5, z - 7), (x + 11.5, z - 5),
               (x + 11.5, z + 4), (x + 8, z + 7), (x - 8, z + 7),
               (x - 11.5, z + 4), (x - 11.5, z - 5)]
    cut(inlet, rear_prism("IEC shaped recess", opening, 231, 5.2, dark, part=False))
    for dx, dz in [(-6, -2), (6, -2), (0, 4)]:
        box("IEC metal blade", (x + dx, 230.6, z + dz), (1.6, 2.6, 4.0), brass, .2)
    rocker = photo_box("Power switch raised rocker", [918, 200, 953, 266],
                       229.0, 4.2, dark, .9)
    map_uv(rocker)
    rear_uv(rocker, power_labels)


def bevel(obj, width, segments=3):
    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new("Moulded edge radius", "BEVEL")
    mod.width, mod.segments = width * MM, segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = .12
    bpy.ops.object.modifier_apply(modifier=mod.name)


def shell_bevel(obj):
    weights = obj.data.attributes.new("bevel_weight_edge", "FLOAT", "EDGE")
    for edge in obj.data.edges:
        a, b = [obj.data.vertices[i].co / MM for i in edge.vertices]
        upper_flank = abs(a.x - b.x) < .001 and abs(a.x) > WIDTH / 2 - .1 and (a.z + b.z) / 2 > 70
        weights.data[edge.index].value = 1.0 if upper_flank else .2625
    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new("Broad upper-rail moulding and smaller lower edges", "BEVEL")
    mod.width, mod.segments, mod.limit_method = 8.0 * MM, 6, "WEIGHT"
    bpy.ops.object.modifier_apply(modifier=mod.name)


def box(name, location, size, mat, radius=0, angle=0, part=True):
    bpy.ops.mesh.primitive_cube_add(size=1, location=[x * MM for x in location])
    obj = bpy.context.object
    obj.name = name
    obj.scale = [x * MM for x in size]
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if radius:
        bevel(obj, min(radius, min(size) * .45))
    obj.rotation_euler.x = angle
    if part:
        PARTS.append(obj)
    return obj


def cut(obj, cutter):
    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new("Physical cavity", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "MANIFOLD"
    mod.object = cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.0001 * MM)
    bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=.00001 * MM)
    bad = sum(not e.is_manifold for e in bm.edges)
    bm.to_mesh(obj.data)
    bm.free()
    if bad:
        raise RuntimeError(f"{cutter.name}: Boolean produced {bad} non-manifold edges")
    bpy.data.objects.remove(cutter, do_unlink=True)


def deck(y):
    if y <= -70.77:
        return 56.42 + (y + 223.66) * SLOPE
    if y < -66.17:
        return 86.67 + (y + 70.77) * (92.2 - 86.67) / 4.6
    return 92.2 + (y + 66.17) * LID_SLOPE


def map_uv(obj, top_material=None, rectangle=(0, 0, 1, 1)):
    uv = obj.data.uv_layers.active or obj.data.uv_layers.new(name="UVMap")
    points = [v.co for v in obj.data.vertices]
    lows = [min(v[i] for v in points) for i in range(3)]
    highs = [max(v[i] for v in points) for i in range(3)]
    if top_material:
        obj.data.materials.append(top_material)
    for face in obj.data.polygons:
        axes = (0, 1) if abs(face.normal.z) > .5 else (
            (0, 2) if abs(face.normal.y) > .5 else (1, 2))
        textured = top_material and face.normal.z > .7
        if textured:
            face.material_index = len(obj.data.materials) - 1
        for loop in face.loop_indices:
            p = obj.data.vertices[obj.data.loops[loop].vertex_index].co
            u, v = [(p[a] - lows[a]) / max(highs[a] - lows[a], 1e-8) for a in axes]
            if textured:
                u = rectangle[0] + u * (rectangle[2] - rectangle[0])
                v = rectangle[1] + v * (rectangle[3] - rectangle[1])
            uv.data[loop].uv = (u, v)


def rounded_ring(width, depth, radius, z, scoop=False):
    ring = []
    for cx, cy, start in [(width / 2 - radius, depth / 2 - radius, 0),
                           (-width / 2 + radius, depth / 2 - radius, 90),
                           (-width / 2 + radius, -depth / 2 + radius, 180),
                           (width / 2 - radius, -depth / 2 + radius, 270)]:
        for j in range(5):
            angle = math.radians(start + j * 90 / 4)
            x, y = cx + radius * math.cos(angle), cy + radius * math.sin(angle)
            zz = z - (1.1 * (1 - (y / (depth / 2)) ** 2) if scoop else 0)
            ring.append((x, y, zz))
    return ring


def key(label, units, x, y, row, plastic, artwork, depth=17.5):
    width = units * 19.05 - 1.5
    height = 9.8 + (3 - min(row, 3)) * .35
    rings = [
        rounded_ring(width - .8, depth - .8, 1.2, 0),
        rounded_ring(width, depth, 1.2, 1.1),
        rounded_ring(width - 3.8, depth - 3.8, 1.65, height - .6, True),
        rounded_ring(width - 4.8, depth - 4.8, 1.6, height, True),
    ]
    verts = [v for ring in rings for v in ring]
    n = len(rings[0])
    faces = [tuple(reversed(range(n)))]
    for r in range(len(rings) - 1):
        faces += [(r * n + i, r * n + (i + 1) % n,
                   (r + 1) * n + (i + 1) % n, (r + 1) * n + i) for i in range(n)]
    # A dished fan, not a flat bevelled cube: the center sits below both rims.
    center = len(verts)
    verts.append((0, 0, height - 1.1))
    last = (len(rings) - 1) * n
    faces += [(last + i, last + (i + 1) % n, center) for i in range(n)]
    obj = mesh(f"Key_{row}_{label.replace(chr(10), '_')}", verts, faces, plastic)
    map_uv(obj, artwork, ATLAS[label])
    obj.location = (x * MM, y * MM, (deck(y) - 5.0) * MM)
    obj.rotation_euler.x = ANGLE
    return obj


def center_main_key_bank(keys, opening_x):
    bpy.context.view_layer.update()
    points = [obj.matrix_world @ vertex.co for obj in keys for vertex in obj.data.vertices]
    before = [min(p.x for p in points) / MM, max(p.x for p in points) / MM]
    opening = [value / MM for value in opening_x]
    delta = (sum(opening) - sum(before)) / 2
    for obj in keys:
        obj.location.x += delta * MM
    report = {
        "method": "One rigid X translation of the complete 62-key main bank, using actual opening bounds and key mesh bounds.",
        "root_cause": "The 15.5-unit initial placement origin was retained after Italian special-key widths and the main aperture were narrowed; this left unequal side clearance.",
        "opening_x_mm": opening,
        "key_bank_x_before_mm": before,
        "key_bank_x_after_mm": [value + delta for value in before],
        "translation_mm": [delta, 0, 0],
        "main_key_objects": [obj.name for obj in keys],
        "isolated_reset": "Unchanged: separately centered in its own pocket, as shown by the same-specimen lid-removed photograph.",
        "other_components": "Case, lid, badge, internal carrier, power lens, rear hardware, key mesh data, UVs and textures are unchanged.",
    }
    (ROOT / "keyboard-centering-operation.json").write_text(json.dumps(report, indent=2) + "\n")


def build():
    global MM
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.context.preferences.filepaths.save_version = 0
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1
    cream = material("Painted warm beige enclosure", (211, 201, 172), .67)
    dark = material("Shadowed keyboard carrier and rubber", (29, 27, 24), .82)
    brown = material("IIe warm grey sculpted keycaps", (151, 143, 117), .55)
    keys = material("Redrawn Italian PAL IIe legends", (151, 143, 117), .55, "keys.png")
    badge = material("Redrawn Apple IIe badge approximation", (40, 37, 32), .45, "badge.png")
    indicator = material("Ivory POWER lens", (230, 219, 171), .5)
    n = len(PROFILE)
    vertices = [(x, y, z) for x in (-WIDTH / 2, WIDTH / 2) for y, z in PROFILE]
    faces = [tuple(reversed(range(n))), tuple(range(n, n * 2))]
    faces += [(i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n)]
    body = mesh("Apple_IIe_integral_profile_case", vertices, faces, cream)
    shell_bevel(body)
    cut(body, box("Hollow chamber behind ventilation", (0, 120.6, 57),
                  (WIDTH - 13.35, 202, 92), cream, 1.2, part=False))
    # The cut plane follows the continuous side ramp, leaving integral shoulders.
    cutter = xy_prism("Notched main keyboard opening",
                      [(-159.5, -58.5), (136, -58.5), (136, 34),
                       (123, 34), (123, 58.5), (-159.5, 58.5)],
                      -28.5, 28.5, cream, part=False)
    bevel(cutter, 2.1)
    opening_x = (min(v.co.x for v in cutter.data.vertices),
                 max(v.co.x for v in cutter.data.vertices))
    cutter.location = (0, -131 * MM, (deck(-131) + 18) * MM)
    cutter.rotation_euler.x = ANGLE
    cut(body, cutter)
    cut(body, box("Isolated RESET pocket", (142.875, -85, deck(-85) + 18),
                  (22, 22, 57), cream, 1.5, ANGLE, part=False))
    carrier = box("Keyboard recessed carrier", (0, -129, deck(-129) - 9.7),
                  (317, 113, 3.2), dark, 1.4, ANGLE)
    map_uv(carrier)
    cut(body, box("Full sloping-lid opening", (0, 85.4, 84),
                  (294.4, 305.2, 144), cream, .8, part=False))
    lid_outline = [(-66.17, deck(-66.17) - .5), (11.15, HEIGHT - .5),
                   (216.0, HEIGHT - .5), (221.5, 103.6), (226, 87.5),
                   (222.1, 87.5), (218.0, 101.8), (214.6, HEIGHT - 4.3),
                   (11.6, HEIGHT - 4.3), (-66.17, deck(-66.17) - 4.3)]
    lid = side_profile("Removable IIe lid including badge fascia", 292, lid_outline, cream)
    bevel(lid, .7)
    for x in (-120, 120):
        cut(lid, box("Lid rear latch relief", (x, 225, 96.5), (5.6, 16, 8.5),
                      cream, 2.2, part=False))
        box("Rear lid tab", (x, 228.95, 88), (51, 12, 2.8), cream, .55)
    vent_count = 18
    for side in (-1, 1):
        for i in range(vent_count):
            y = 31 + i * 9.7
            cut(body, box("Wraparound ventilation cutter", (side * (WIDTH / 2 - 1.7), y, 100),
                          (30, 3.5, 45), cream, 1.5, part=False))
    box("Non-display interior shadow proxy, not measured electronics",
        (0, 117, 60.5), (294.6, 196, 95), dark, .3)
    rear_panel(body, cream, dark)
    main_keys = []
    for row, (offset, layout) in enumerate(ROWS):
        x = -15.5 * 19.05 / 2 + offset * 19.05
        y = -85 - row * 19.05
        for label, units in layout:
            main_keys.append(key(label, units, x + units * 19.05 / 2, y, row, brown, keys))
            x += units * 19.05
    key("reset", 1, 142.875, -85, 0, brown, keys)
    main_keys.append(key("a capo\n↵", 1, -15.5 * 19.05 / 2 + 14 * 19.05,
                         -85 - 1.5 * 19.05, 1, brown, keys, depth=36.55))
    center_main_key_bank(main_keys, opening_x)
    power = box("IIe small power indicator lens", (-169, -161, deck(-161) + .35),
                (10, 2.8, 1.4), indicator, .5, ANGLE)
    map_uv(power)
    label = box("Left-aligned IIe badge on removable fascia", (-101, -56, deck(-56) + .1),
                (68, 15.2, .8), dark, .3, LID_ANGLE)
    map_uv(label, badge)
    for x in (-152, 152):
        for y in (-140, 179):
            foot = box("Rubber foot", (x, y, 3.05), (26, 29, 6.1), dark, 2)
            map_uv(foot)
    for part in PARTS:
        if not part.data.uv_layers:
            map_uv(part)
        normals(part)
        bpy.context.view_layer.objects.active = part
        mod = part.modifiers.new("Stable export triangulation", "TRIANGULATE")
        mod.quad_method = "BEAUTY"
        mod.ngon_method = "BEAUTY"
        bpy.ops.object.modifier_apply(modifier=mod.name)
    # Boolean intersections use millimetre-sized coordinates to avoid tolerances
    # swallowing tiny rounded slot edges; delivery geometry is baked to metres.
    for part in PARTS:
        for vertex in part.data.vertices:
            vertex.co *= .001
        part.location *= .001
        part.location.y -= .003175
    MM = .001
    bpy.context.view_layer.update()
    return body


def audit():
    corners = [p.matrix_world @ Vector(c) for p in PARTS for c in p.bound_box]
    report = {
        "status": "Reference-derived Italian PAL Apple IIe",
        "dimensions_mm_width_depth_height": [
            round((max(c[i] for c in corners) - min(c[i] for c in corners)) / MM, 5)
            for i in range(3)],
        "nominal_dimensions_mm": [WIDTH, DEPTH, HEIGHT],
        "side_profile_y_z_mm": PROFILE,
        "physical_key_pitch_mm_assumption": 19.05,
        "key_count": sum(len(row) for _, row in ROWS) + 2,
        "power_indicator_count": 1,
        "side_ventilation_count_each": 18,
        "parts": [],
    }
    for part in PARTS:
        bm = bmesh.new()
        bm.from_mesh(part.data)
        row = {"name": part.name, "vertices": len(bm.verts), "triangles": len(bm.faces),
               "non_manifold_edges": sum(not e.is_manifold for e in bm.edges),
               "inconsistent_edges": sum(not e.is_contiguous for e in bm.edges),
               "signed_volume_m3": bm.calc_volume(signed=True)}
        assert row["non_manifold_edges"] == row["inconsistent_edges"] == 0, row
        assert row["signed_volume_m3"] > 0, row
        row["minimum_triangle_area_m2"] = min(face.calc_area() for face in bm.faces)
        assert row["minimum_triangle_area_m2"] >= 5e-13, row
        report["parts"].append(row)
        bm.free()
    report["vertices"] = sum(p["vertices"] for p in report["parts"])
    report["triangles"] = sum(p["triangles"] for p in report["parts"])
    (ROOT / "candidate-metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def export():
    bpy.ops.object.select_all(action="DESELECT")
    for part in PARTS:
        part.select_set(True)
    bpy.context.view_layer.objects.active = PARTS[0]
    bpy.ops.wm.usd_export(
        filepath=str(ROOT / "appleIIe.usdz"), selected_objects_only=True,
        export_materials=True, generate_preview_surface=True,
        export_lights=False, export_cameras=False, export_custom_properties=False,
        triangulate_meshes=True, convert_orientation=True,
        export_global_up_selection="Y", export_global_forward_selection="NEGATIVE_Z",
        convert_world_material=False, overwrite_textures=True)


def point_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def previews():
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 3
    scene.world.use_nodes = True
    nodes = scene.world.node_tree.nodes
    nodes.clear()
    fill = nodes.new("ShaderNodeBackground")
    fill.inputs["Color"].default_value = (.2, .2, .2, 1)
    backdrop = nodes.new("ShaderNodeBackground")
    backdrop.inputs["Color"].default_value = (1, 1, 1, 1)
    backdrop.inputs["Strength"].default_value = 16
    ray = nodes.new("ShaderNodeLightPath")
    mix = nodes.new("ShaderNodeMixShader")
    output = nodes.new("ShaderNodeOutputWorld")
    links = scene.world.node_tree.links
    links.new(ray.outputs["Is Camera Ray"], mix.inputs[0])
    links.new(fill.outputs[0], mix.inputs[1])
    links.new(backdrop.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs["Surface"])
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = -.5
    scene.render.image_settings.file_format = "PNG"
    for name, position, energy, size in [
        ("Key softbox", (-.6, -.65, 1.0), 38, .8),
        ("Fill softbox", (.6, -.2, .6), 16, .7),
        ("Rear softbox", (0, .8, .75), 24, .65)]:
        data = bpy.data.lights.new(name, "AREA")
        data.energy, data.shape, data.size = energy, "DISK", size
        light = bpy.data.objects.new(name, data)
        scene.collection.objects.link(light)
        light.location = position
        point_at(light, (0, 0, .045))
    ground_mat = material("Preview background only", (233, 233, 230), .9)
    bpy.ops.mesh.primitive_plane_add(size=2, location=(0, 0, -.0005))
    floor = bpy.context.object
    floor.name = "PREVIEW ONLY shadow plane"
    floor.data.materials.append(ground_mat)
    camera = bpy.data.objects.new("PREVIEW ONLY camera", bpy.data.cameras.new("Camera"))
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera.data.type = "ORTHO"
    views = {
        "front-three-quarter": ((.64, -.83, .64), .64, (1000, 850), (0, 0, .045)),
        "rear-three-quarter": ((-.65, .85, .55), .64, (1000, 800), (0, 0, .045)),
        "side": ((.8, -.0016, .0625), .4975, (1314, 364), (0, -.0016, .0625)),
        "rear": ((-.00427, .8, .052), .4405, (1186, 354), (-.00427, 0, .052)),
        "front": ((0, -.8, .065), .43, (1186, 430), (0, 0, .065)),
        "top": ((0, 0, 1), .51, (1050, 1100), (0, 0, 0)),
    }
    for name, (location, scale, resolution, target) in views.items():
        camera.location = location
        point_at(camera, target)
        camera.data.ortho_scale = scale
        scene.render.resolution_x, scene.render.resolution_y = resolution
        scene.render.resolution_percentage = 100
        scene.render.filepath = str(ROOT / f"preview-{name}.png")
        if os.environ.get("RETRO_RENDER", "1") == "1":
            bpy.ops.render.render(write_still=True)
    # Keep the editable delivery strictly geometry/material only, as is the USDZ.
    for obj in list(scene.objects):
        if obj not in PARTS:
            bpy.data.objects.remove(obj, do_unlink=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-render", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    build()
    audit()
    export()
    if not args.no_render:
        previews()
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "appleIIe.blend"))


if __name__ == "__main__":
    main()
