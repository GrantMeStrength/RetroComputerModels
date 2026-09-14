"""Build original BBC/CPC case geometry using supplied shape and photo references."""

import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "WebPrototypes"))
import build_prototypes as p
from reference_c64 import prism, subtract
from layouts import (bbc_keys, cpc_keys, CPC_BODY_CROP, BBC_PANEL_COLOR, BBC_EDITING_COLOR,
                     BBC_CURSOR_LABELS, BBC_CASE_WIDTH, BBC_CAP_DEPTH)
from bbc_keyboard import panel as bbc_panel, keycap as bbc_keycap

p.ROOT = ROOT


def project(obj, mat, axes, bounds, predicate, reverse=False):
    index = len(obj.data.materials)
    obj.data.materials.append(mat)
    uv = obj.data.uv_layers.active or obj.data.uv_layers.new(name="UVMap")
    for face in obj.data.polygons:
        if not predicate(face.normal):
            continue
        face.material_index = index
        for loop in face.loop_indices:
            point = obj.matrix_world @ obj.data.vertices[obj.data.loops[loop].vertex_index].co
            u, v = [(point[axis] - lo) / (hi - lo) for axis, (lo, hi) in zip(axes, bounds)]
            uv.data[loop].uv = (1 - u if reverse else u, v)


def finish(name, report):
    if name == "amstradCPC464":
        # The supplied overall height includes the raised cursor keys and feet.
        bpy.context.view_layer.update()
        heights = [(obj.matrix_world @ Vector(corner)).z for obj in p.PARTS for corner in obj.bound_box]
        factor = .070 / (max(heights) - min(heights))
        calibration = Matrix.Diagonal((1, 1, factor, 1)) @ Matrix.Translation((0, 0, -min(heights)))
        for obj in p.PARTS:
            obj.matrix_world = calibration @ obj.matrix_world
        report["overall_height_calibration"] = factor
    p.finish(name)
    obj = bpy.data.objects[name]
    report.update(vertices=len(obj.data.vertices), triangles=len(obj.data.polygons),
                  bounds_mm=[v * 1000 for v in obj.dimensions])
    if any(abs(actual - target) > .02 for actual, target in zip(report["bounds_mm"], report["target_dimensions_mm"])):
        raise ValueError(f"Model does not meet the supplied dimensions: {report['bounds_mm']}")
    obj["reference_notes"] = report["reference_notes"]
    obj["provenance"] = "Original reference-guided geometry with user-supplied photographic artwork; see BritishModels/README.md."
    obj["limitations"] = "Illustrative model, not manufacturing CAD. Some details are texture-only. Supplied photo rights are separate; see ATTRIBUTION.md."
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / (name + ".blend")))
    (ROOT / (name + "-report.json")).write_text(json.dumps(report, indent=2) + "\n")


def bbc():
    p.reset()
    measurements = json.loads((ROOT.parent / "ReferenceStudies/bbc-measurements.json").read_text())
    parts = measurements["parts"]
    lid, base = parts["Lid Cream"], parts["Base Cream"]
    low_y = min(lid["bounds"][0][1], base["bounds"][0][1])
    high_y = max(lid["bounds"][1][1], base["bounds"][1][1])
    middle_y = (low_y + high_y) / 2
    sx, sy, sz = BBC_CASE_WIDTH / lid["size"][0], .350 / (high_y - low_y), .069 / 18.5
    x = lambda v: v * sx
    y = lambda v: (v - middle_y) * sy
    z = lambda v: .004 + v * sz
    raw_y = lambda v: v / sy + middle_y
    slope = .1972 * sz / sy
    deck = lambda v: z(18.5 + .1972 * (min(raw_y(v), 1.25) - 1.25))
    seam = lambda v: z(8.696 + raw_y(v) / 6)
    cream = p.material("BBC warm cream ABS", (206, 198, 168), .68)
    dark = p.material("BBC keyboard recess", BBC_PANEL_COLOR, .72)
    key = p.material("BBC charcoal keys", (41, 38, 33), .58)
    red = p.material("BBC red function keys", (188, 54, 34), .58)
    grey = p.material("BBC grey editing keys", BBC_EDITING_COLOR, .58)
    legends = p.material("BBC original key artwork", (41, 38, 33), texture="bbcMicro-keys.png")
    banner = p.material("BBC supplied owl and original lettering", BBC_PANEL_COLOR, .72, texture="bbcMicro-banner.png")
    rear = p.material("BBC supplied rear photograph", (72, 70, 61), texture="bbcMicro-rear.jpg")
    y0 = y(lid["bounds"][0][1])
    b0, b1 = y(base["bounds"][0][1]), y(base["bounds"][1][1])
    y1 = b1
    upper = p.profile("BBC measured sloping lid", BBC_CASE_WIDTH,
                      [(y0, seam(y0)), (y1, seam(y1)), (y1, .073),
                       (y(1.25), .073), (y0, deck(y0))], cream, .0015)
    lower = p.profile("BBC lower wedge", base["size"][0] * sx,
                      [(b0, .004), (b1, .004), (b1, seam(b1) - .00045),
                       (b0, seam(b0) - .00045)], cream, .001)
    opening = [(x(a) * 1000, y(b) * 1000) for a, b in
               [(-46.5, -38.7), (46.5, -38.7), (46.5, -1.4), (-46.5, -1.4)]]
    cut = prism(p, "BBC keyboard aperture tool", opening,
                lambda v: (deck(v / 1000) - .013) * 1000, lambda v: 120, dark)
    subtract(p, upper, cut)
    board = bbc_panel(p, x(93), y(-38.7), y(-8.5), y(-1.4), deck, dark, banner)
    atlas = json.loads((ROOT / "Textures/bbc-atlas.json").read_text())
    keyboard_report = []
    for label, rx, ry, width in bbc_keys():
        mat = red if label.startswith("f") else grey if label in BBC_CURSOR_LABELS | {"COPY"} else key
        center = (x(rx), y(ry), z(18.237 + .1972 * ry))
        bbc_keycap(p, label, center, width * sx, BBC_CAP_DEPTH, slope, mat, legends, atlas[label])
        keyboard_report.append({"label": label, "center_mm": [v * 1000 for v in center],
                                "base_width_mm": width * sx * 1000, "material": mat.name})
    for rx, label in [(-32.6507, "MOTOR"), (-27.6507, "CAPS LOCK"), (-22.6507, "SHIFT LOCK")]:
        ly = y(-36.663)
        p.box("BBC " + label + " LED", (x(rx), ly, deck(ly) - .0025), (.0028, .0028, .001),
              p.material("BBC " + label + " red indicator", (156, 29, 24), .4), .0005)
    for obj in (upper, lower):
        project(obj, rear, (0, 2), ((-BBC_CASE_WIDTH / 2, BBC_CASE_WIDTH / 2), (.004, .073)), lambda n: n.y > .7, reverse=True)
    rubber = p.material("BBC feet", (31, 30, 28), .9)
    for fx in (-.17, .17):
        for fy in (-.142, .14):
            p.box("BBC rubber foot", (fx, fy, .002), (.019, .019, .004), rubber, .001)
    finish("bbcMicro", {"keyboard_keys": len(bbc_keys()), "keyboard_layout": keyboard_report,
                       "keyboard_panel_width_mm": x(93) * 1000,
                       "unified_keyboard_panel_vertices": len(board.data.vertices),
                       "keycap_slope": slope,
                       "target_dimensions_mm": [411, 350, 73],
                       "reference_notes": "User-supplied BBC miniature measured for profiles and layout; original geometry. Scale chosen within user-supplied dimensions. Rear photo/owl supplied by user; redistribution permission confirmed by the contributor; ownership is not independently verified. No Virtualbeeb mesh used."})


def cpc():
    p.reset()
    body = p.material("CPC dark grey case", (76, 75, 76), .67)
    recess = p.material("CPC recessed wells", (23, 22, 23), .73)
    plastic = p.material("CPC dark key sides", (42, 40, 41), .58)
    green = p.material("CPC green key sides", (77, 131, 77), .58)
    blue = p.material("CPC blue Enter sides", (77, 92, 130), .58)
    red = p.material("CPC red Escape and record", (164, 49, 39), .58)
    photo = p.material("CPC supplied top photograph", (76, 75, 76), texture="amstradCPC464-top.jpg")
    back = p.material("CPC supplied rear photograph", (76, 75, 76), texture="amstradCPC464-rear.jpg")
    left = p.material("CPC supplied left photograph", (76, 75, 76), texture="amstradCPC464-left.jpg")
    right = p.material("CPC supplied right photograph", (76, 75, 76), texture="amstradCPC464-right.jpg")
    deck = lambda yy: .05 + (yy + .085) * (.020 / .170)
    shell = p.profile("CPC sloping enclosure", .580,
                      [(-.085, .027), (-.079, .004), (.079, .004),
                       (.085, .030), (.085, .070), (-.085, .050)], body, .001)
    x0, y0, x1, y1 = CPC_BODY_CROP
    point = lambda px, py: ((px - x0) / (x1 - x0) * .580 - .290,
                           .085 - (py - y0) / (y1 - y0) * .170)
    def footprint(outline):
        return [(xx * 1000, yy * 1000) for xx, yy in (point(px, py) for px, py in outline)]
    openings = [
        [(90, 132), (696, 132), (696, 290), (609, 290), (609, 329), (215, 329), (215, 290), (90, 290)],
        [(771, 43), (812, 43), (812, 81), (852, 81), (852, 122), (812, 122),
         (812, 161), (771, 161), (771, 122), (731, 122), (731, 81), (771, 81)],
        [(731, 171), (852, 171), (852, 328), (731, 328)],
    ]
    for index, outline in enumerate(openings):
        shape = footprint(outline)
        cutter = prism(p, "CPC aperture tool", shape, lambda v: (deck(v / 1000) - .010) * 1000, lambda v: 120, recess)
        subtract(p, shell, cutter)
        prism(p, "CPC keyboard bed " + str(index), shape, lambda v: (deck(v / 1000) - .010) * 1000,
              lambda v: (deck(v / 1000) - .009) * 1000, recess)
    top_projection = lambda obj: project(obj, photo, (0, 1), ((-.290, .290), (-.085, .085)), lambda n: n.z > .7)
    top_projection(shell)
    project(shell, back, (0, 2), ((-.290, .290), (.004, .070)), lambda n: n.y > .7, reverse=True)
    project(shell, left, (1, 2), ((-.085, .085), (.004, .070)), lambda n: n.x < -.7, reverse=True)
    project(shell, right, (1, 2), ((-.085, .085), (.004, .070)), lambda n: n.x > .7)
    for label, outline in cpc_keys():
        mat = blue if "ENTER" in label else red if label == "ESC" else green if label in {
            "DEL", "TAB", "CAPS LOCK", "LEFT SHIFT", "RIGHT SHIFT", "CTRL", "COPY"} else plastic
        cap = prism(p, "CPC key " + label, footprint(outline),
                    lambda v: (deck(v / 1000) - .007) * 1000, lambda v: (deck(v / 1000) + .005) * 1000, mat)
        p.bevel(cap, .0007)
        top_projection(cap)
    door = prism(p, "CPC cassette door", footprint([(900, 122), (1135, 122), (1135, 285), (900, 285)]),
                 lambda v: deck(v / 1000) * 1000, lambda v: (deck(v / 1000) + .0015) * 1000, body)
    p.bevel(door, .0006)
    top_projection(door)
    for index, label in enumerate(["RECORD", "PLAY", "REWIND", "FAST FORWARD", "STOP EJECT", "PAUSE"]):
        px = 902 + index * 37.8
        button = prism(p, "CPC cassette " + label, footprint([(px, 307), (px + 35, 307), (px + 35, 340), (px, 340)]),
                       lambda v: deck(v / 1000) * 1000, lambda v: (deck(v / 1000) + .003) * 1000, red if index == 0 else body)
        p.bevel(button, .0006)
        top_projection(button)
    rubber = p.material("CPC feet", (25, 24, 25), .9)
    for fx in (-.25, .25):
        for fy in (-.058, .058):
            p.box("CPC rubber foot", (fx, fy, .002), (.015, .015, .004), rubber, .001)
    finish("amstradCPC464", {"keyboard_keys": len(cpc_keys()), "cassette_buttons": 6,
                           "target_dimensions_mm": [580, 170, 70],
                           "reference_notes": "User supplied overall dimensions and photographs. Original sloping case/key geometry; photographed legends, cassette detail and ports. Front/rear height split fitted to supplied side views, not separately measured."})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", choices=["bbcMicro", "amstradCPC464"], default=["bbcMicro", "amstradCPC464"])
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    for name in args.models:
        (bbc if name == "bbcMicro" else cpc)()
