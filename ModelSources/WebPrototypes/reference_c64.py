"""Original C64 geometry reconstructed from measured reference-shell dimensions.

Measurement source: Sgw32 NULLchar, Pinshape 103727, CC BY 4.0.
See ../../ATTRIBUTION.md. No reference mesh is imported by this builder.
"""
import math

import bmesh
import bpy


def prism(p, name, outline, bottom, top, material):
    """Extrude a millimeter footprint between two height functions."""
    vertices = [(x / 1000, y / 1000, height(y) / 1000)
                for height in (bottom, top) for x, y in outline]
    count = len(outline)
    faces = [tuple(reversed(range(count))), tuple(range(count, 2 * count))]
    faces += [(i, (i + 1) % count, (i + 1) % count + count, i + count)
              for i in range(count)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(material)
    mesh.uv_layers.new(name="UVMap")
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    p.PARTS.append(obj)
    return obj


def subtract(p, shell, cutter):
    bpy.context.view_layer.objects.active = shell
    modifier = shell.modifiers.new("Machined reference-informed opening", "BOOLEAN")
    modifier.operation = "DIFFERENCE"
    modifier.solver = "EXACT"
    modifier.object = cutter
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    p.PARTS.remove(cutter)
    bpy.data.objects.remove(cutter, do_unlink=True)


def build(p, variant="commodore64"):
    if variant not in {"commodore64", "vic20"}:
        raise ValueError(f"Unsupported breadbin variant: {variant}")
    vic20 = variant == "vic20"
    p.reset()
    case = p.material("Cream VIC-20 plastic" if vic20 else "Warm grey breadbin plastic",
                      (223, 220, 193) if vic20 else (171, 165, 143), .65)
    seam = p.material("Case seam", (140, 133, 111) if vic20 else (72, 69, 59), .8)
    dark = p.material("Keyboard recess", (36, 34, 30), .72)
    key_color = (62, 51, 42) if vic20 else (65, 59, 52)
    plastic = p.material("Brown key plastic", key_color, .52)
    artwork = p.material("Original VIC-20 legends" if vic20 else "Original C64 legends",
                         key_color, texture=variant + "-keys.png")
    function = p.material("Tan VIC-20 function keys" if vic20 else "Grey function keys",
                          (187, 142, 87) if vic20 else (136, 128, 111), .52)
    badge = p.material("Original VIC-20 nameplate" if vic20 else "Original C64 nameplate",
                       (64, 59, 49), texture=variant + "-badge.png")

    # The two print-oriented halves meet at raw heights 7.545 and 2.5 mm.
    # This gives a 25 mm seam and 67 mm rear deck, not the catalog's 76.2 mm.
    rear = [(0, 7.545), (3.8, 35.1), (5, 42.61), (8, 47.1),
            (10, 48.46), (12, 49.19), (15, 49.545), (54.507, 49.545)]
    front = [(186 + 20 * math.sin(t), 11.545 + 20 * math.cos(t))
             for t in [i * math.pi / 48 for i in range(25)]]
    top_profile = [(103 - d, h + 17.455) for d, h in rear + front]
    top_profile += [(-103, 25), (103, 25)]
    upper = p.profile("Measured breadbin upper envelope", .406,
                      [(y / 1000, z / 1000) for y, z in top_profile], case, .0007)
    bottom_profile = [(103, 24.5), (-103, 24.5), (-103, 20)]
    bottom_profile += [(-(83 + 20 * math.sin(t)), 20 - 20 * math.cos(t))
                       for t in [math.pi / 2 - i * math.pi / 48 for i in range(25)]]
    bottom_profile += [(96, 0), (99, .7), (101, 2), (103, 7)]
    p.profile("Rounded lower shell - measured 25 mm seam", .406,
              [(y / 1000, z / 1000) for y, z in bottom_profile], case, .0007)
    p.box("Fine horizontal shell joint", (0, 0, .02475), (.404, .204, .0005), seam, .0002)

    slope = .137858
    deck = lambda y: 67 + slope * (y - 48.493)
    # Outer aperture boundary stations were measured on the actual sloping deck.
    main_raw = [(17, 84.037), (324.5, 84.037), (324.5, 123.167),
                (319.5, 123.167), (319.5, 161.306), (238.5, 161.306),
                (238.5, 180.128), (64, 180.128), (64, 161.306),
                (12, 161.306), (12, 121.681), (17, 121.681)]
    function_raw = [(344.5, 84.037), (375, 84.037), (375, 161.306), (344.5, 161.306)]
    for name, raw in (("Stepped main keyboard", main_raw), ("Separate function bank", function_raw)):
        outline = [(x - 203, 103 - d) for x, d in raw]
        cutter = prism(p, "Aperture cutter", outline, lambda y: 26, lambda y: 100, dark)
        subtract(p, upper, cutter)
        prism(p, name + " recessed floor", outline, lambda y: deck(y) - 7,
              lambda y: deck(y) - 6, dark)

    rows = [
        (0, ["LEFT", *list("1234567890"), "+", "-", "=", "CLR\nHOME", "INST\nDEL"]),
        (0, [("CTRL", 1.25), *list("QWERTYUIOP"), "@", "*", "UP", ("RESTORE", 1.5)]),
        (-.25, ["RUN\nSTOP", "SHIFT\nLOCK", *list("ASDFGHJKL"), ":", ";", "=", ("RETURN", 1.5)]),
        (-.25, ["C=", ("SHIFT", 1.5), *list("ZXCVBNM"), ",", ".", "/", ("SHIFT", 1.5), "UP", "RIGHT"]),
        (2.5, [("SPACE", 9)]),
    ]
    key_height = .014
    p.keyboard("VIC-20" if vic20 else "C64", rows, -.186, .0087, .01905, lambda y: deck(y * 1000) / 1000 + .001,
               slope, plastic, artwork, height=key_height)
    for i, label in enumerate(["F1", "F3", "F5", "F7"]):
        y = .0087 - .01905 * i
        p.key("Function", label, .15675, y, deck(y * 1000) / 1000 + .001,
              .0275, .01655, slope, function, artwork, height=key_height)

    for index in range(6):
        y = (103 - (22.51 + 4 * index)) / 1000
        cutter = p.box("Groove cutter", (0, y, .067), (.402, .002, .004), dark, 0)
        subtract(p, upper, cutter)
        p.box("Recessed rear groove", (0, y, .0651), (.399, .0019, .0002), seam, .00005)
    p.box("VIC-20 nameplate" if vic20 else "C64 nameplate", (-.105, .07049, .0674), (.130, .012, .0008),
          case, .0002, top=(badge, (0, 0, 1, 1)))
    p.box("Power indicator surround", (.16, .07049, .0674), (.009, .007, .0008), dark, .001)
    p.box("Power LED", (.16, .07049, .068), (.004, .003, .0008),
          p.material("Red LED", (193, 40, 24), .3), .001)
    p.finish(variant)
