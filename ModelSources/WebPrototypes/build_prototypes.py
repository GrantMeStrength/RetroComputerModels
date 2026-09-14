"""Build reference-guided approximations with original artwork, not photogrammetry."""

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
sys.path.insert(0, str(ROOT.parent))
from mesh_utils import finalize_mesh

ATLAS = json.loads((ROOT / "Textures" / "atlas.json").read_text())
PARTS = []


def linear(channel):
    value = channel / 255
    return value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4


def material(name, rgb, roughness=.55, texture=None, emission=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*[linear(c) for c in rgb], 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes["Principled BSDF"]
    shader.inputs["Base Color"].default_value = mat.diffuse_color
    shader.inputs["Roughness"].default_value = roughness
    if texture:
        image = bpy.data.images.load(str(ROOT / "Textures" / texture), check_existing=True)
        image.pack()
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = image
        mat.node_tree.links.new(node.outputs["Color"], shader.inputs["Base Color"])
        if emission:
            mat.node_tree.links.new(node.outputs["Color"], shader.inputs["Emission Color"])
            shader.inputs["Emission Strength"].default_value = emission
    return mat


def bevel(obj, width, segments=2):
    if not width:
        return
    bpy.context.view_layer.objects.active = obj
    modifier = obj.modifiers.new("Manufactured edge radius", "BEVEL")
    modifier.width = width
    modifier.segments = segments
    modifier.limit_method = "ANGLE"
    modifier.angle_limit = .06
    bpy.ops.object.modifier_apply(modifier=modifier.name)


def texture_face(obj, mat, direction, rectangle=(0, 0, 1, 1)):
    obj.data.materials.append(mat)
    slot = len(obj.data.materials) - 1
    uv = obj.data.uv_layers.active or obj.data.uv_layers.new(name="UVMap")
    axes = (0, 1) if direction == "top" else (0, 2)
    points = [v.co for v in obj.data.vertices]
    minimum = [min(p[axis] for p in points) for axis in axes]
    maximum = [max(p[axis] for p in points) for axis in axes]
    for face in obj.data.polygons:
        selected = face.normal.z > .99 if direction == "top" else face.normal.y < -.99
        if not selected:
            continue
        face.material_index = slot
        for index in face.loop_indices:
            vertex = obj.data.vertices[obj.data.loops[index].vertex_index].co
            u, v = [(vertex[axis] - lo) / (hi - lo) for axis, lo, hi in zip(axes, minimum, maximum)]
            uv.data[index].uv = (rectangle[0] + u * (rectangle[2] - rectangle[0]),
                                rectangle[1] + v * (rectangle[3] - rectangle[1]))


def box(name, location, dimensions, mat, radius=.001, rotation=0, top=None, front=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if top:
        texture_face(obj, top[0], "top", top[1])
    if front:
        texture_face(obj, front, "front")
    bevel(obj, radius)
    obj.rotation_euler.x = rotation
    PARTS.append(obj)
    return obj


def profile(name, width, outline, mat, radius=.003):
    count = len(outline)
    vertices = [(x, y, z) for x in (-width / 2, width / 2) for y, z in outline]
    faces = [tuple(reversed(range(count))), tuple(range(count, 2 * count))]
    faces += [(i, (i + 1) % count, (i + 1) % count + count, i + count) for i in range(count)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    mesh.materials.append(mat)
    mesh.uv_layers.new(name="UVMap")
    bevel(obj, radius)
    PARTS.append(obj)
    return obj


def key(name, label, x, y, z, width, depth, slope, plastic, artwork, *, height=.008):
    angle = math.atan(slope)
    # Extend upward along the cap's local axis, keeping its seated base fixed.
    lift = (height - .008) / 2
    center = (x, y - math.sin(angle) * lift, z + math.cos(angle) * lift)
    return box(name + " " + label.replace("\n", " "), center, (width, depth, height),
               plastic, radius=.0016, rotation=angle, top=(artwork, ATLAS[label]))


def keyboard(name, rows, left, back, pitch, z_at, slope, plastic, artwork, *, height=.008):
    for row_index, (offset, keys) in enumerate(rows):
        x = left + offset * pitch
        y = back - row_index * pitch
        for item in keys:
            label, units = item if isinstance(item, tuple) else (item, 1)
            center = x + units * pitch / 2
            key(name, label, center, y, z_at(y), units * pitch - .0025,
                pitch - .0025, slope, plastic, artwork, height=height)
            x += units * pitch


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.context.scene.unit_settings.system = "METRIC"
    PARTS.clear()


def commodore64():
    sys.path.insert(0, str(ROOT))
    from reference_c64 import build
    build(sys.modules[__name__])


def vic20():
    sys.path.insert(0, str(ROOT))
    from reference_c64 import build
    build(sys.modules[__name__], variant="vic20")






def finish(name):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in PARTS:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = PARTS[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    envelopes = {"appleII": (.3937, .4572, .1143)}
    if name in envelopes:
        scale = [target / actual for target, actual in zip(envelopes[name], obj.dimensions)]
        obj.data.transform(Matrix.Diagonal((*scale, 1)))
        obj.data.update()
    finalize_mesh(obj)
    obj["provenance"] = "Original approximate geometry and artwork, guided by published photographs and dimensions."
    obj["limitations"] = "Not a scan or CAD replica. Simplified legends, sockets and details. Separate closed parts may intersect."
    if name in {"commodore64", "vic20"}:
        obj["provenance"] = "Original reconstruction from measured Sgw32 NULLchar C64 enclosure (Pinshape 103727, CC BY 4.0); original key artwork."
        obj["limitations"] = "Replica-reference envelope, not certified original hardware. Simplified caps; rear/side sockets and internal fittings omitted."
        if name == "vic20":
            obj["provenance"] += " VIC-20 color/artwork variant of the same C64 geometry."
    bpy.ops.wm.usd_export(
        filepath=str(ROOT / (name + ".usdz")), selected_objects_only=True,
        export_materials=True, generate_preview_surface=True, convert_orientation=True,
        export_global_up_selection="Y", export_global_forward_selection="NEGATIVE_Z",
        convert_world_material=False, export_lights=False, export_cameras=False,
        export_custom_properties=False, triangulate_meshes=True, overwrite_textures=True,
    )
    render(obj, ROOT / (name + ".png"))
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            area.spaces.active.region_3d.view_location = Vector((0, 0, obj.dimensions.z / 2))
            area.spaces.active.region_3d.view_distance = max(obj.dimensions) * 2
            area.spaces.active.region_3d.view_rotation = bpy.context.scene.camera.rotation_euler.to_quaternion()
            area.spaces.active.shading.type = "MATERIAL"
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / (name + ".blend")))
    print("PROTOTYPE", name, len(obj.data.vertices), len(obj.data.polygons), flush=True)


def render(obj, path, overview=False):
    scene = bpy.context.scene
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    center = sum(points, Vector()) / 8
    size = max(obj.dimensions)
    direction = Vector((.2, -1.6, 1.25) if overview else (1.05, -1.55, 1.15))
    bpy.ops.object.camera_add(location=center + direction * size)
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = size * (1.2 if overview else 1.65)
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    scene.world = bpy.data.worlds.new("Soft studio")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.3, .3, .3, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = .35
    for offset, energy, diameter in [((-1, -1, 2), 170, 1.5), ((1, .5, 1.4), 110, 1.2)]:
        bpy.ops.object.light_add(type="AREA", location=center + Vector(offset))
        light = bpy.context.object
        light.data.energy, light.data.size = energy, diameter
        light.rotation_euler = (center - light.location).to_track_quat("-Z", "Y").to_euler()
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.004))
    ground = bpy.context.object
    ground.name = "Preview ground - not exported"
    ground.data.materials.append(material("Backdrop", (84, 90, 97), .9))
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = (1800, 900) if overview else (1400, 1050)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(path)
    if os.environ.get("RETRO_RENDER", "1") == "1":
        bpy.ops.render.render(write_still=True)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj




if __name__ == "__main__":
    builders = {"commodore64": commodore64, "vic20": vic20}
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", choices=list(builders), default=list(builders))
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    for name in args.models:
        builders[name]()
