"""Build a photo-textured RM 380Z enclosure in Blender, outside the app target."""

import argparse
import os
import json
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
PARTS = []


def linear(value):
    value /= 255
    return value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4


def material(name, rgb, metallic=0, texture=None, roughness=.65):
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    color = (*[linear(value) for value in rgb], 1)
    result.diffuse_color = color
    shader = result.node_tree.nodes["Principled BSDF"]
    shader.inputs["Base Color"].default_value = color
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    if texture:
        image = bpy.data.images.load(str(ROOT / "Textures" / texture), check_existing=True)
        image.pack()
        node = result.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = image
        result.node_tree.links.new(node.outputs["Color"], shader.inputs["Base Color"])
    return result


def panel_uv(obj, mat, side, region=(0, 0, 1, 1)):
    obj.data.materials.append(mat)
    slot = len(obj.data.materials) - 1
    uv = obj.data.uv_layers.active
    xs = [vertex.co.x for vertex in obj.data.vertices]
    zs = [vertex.co.z for vertex in obj.data.vertices]
    for face in obj.data.polygons:
        if face.normal.y * side < .99:
            continue
        face.material_index = slot
        for index in face.loop_indices:
            vertex = obj.data.vertices[obj.data.loops[index].vertex_index].co
            u = (vertex.x - min(xs)) / (max(xs) - min(xs))
            v = (vertex.z - min(zs)) / (max(zs) - min(zs))
            if side == 1:
                u = 1 - u
            uv.data[index].uv = (region[0] + u * (region[2] - region[0]),
                                region[1] + v * (region[3] - region[1]))


def box(name, location, size, mat, radius=.0007, texture=None, side=-1, region=(0, 0, 1, 1)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if texture:
        panel_uv(obj, texture, side, region)
    if radius:
        modifier = obj.modifiers.new("Restrained metal edge bevel", "BEVEL")
        modifier.width = radius
        modifier.segments = 2
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    PARTS.append(obj)
    return obj


def plate_handle(name, x, front_y, center_z, mat):
    thickness, projection, height, border = .003, .040, .1778, .007
    y0, y1 = front_y - projection, front_y + .002
    z0, z1 = center_z - height / 2, center_z + height / 2
    outer = [(y0, z0), (y1, z0), (y1, z1), (y0, z1)]
    inner = [(y0 + border, z0 + border), (y1 - border, z0 + border),
             (y1 - border, z1 - border), (y0 + border, z1 - border)]
    vertices = [(side, y, z) for side in (x - thickness / 2, x + thickness / 2)
                for y, z in outer + inner]
    faces = []
    for index in range(4):
        following = (index + 1) % 4
        faces.extend([
            (index, following, following + 4, index + 4),
            (index + 8, index + 12, following + 12, following + 8),
            (index, index + 8, following + 8, following),
            (index + 4, following + 4, following + 12, index + 12),
        ])
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    mesh.materials.append(mat)
    mesh.uv_layers.new(name="UVMap")
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    PARTS.append(obj)
    return obj


def render(model, path, rear=False, straight=False):
    scene = bpy.context.scene
    center = Vector((0, 0, .09))
    sign = 1 if rear else -1
    location = center + (Vector((0, sign * 1.2, 0)) if straight else Vector((.72 * -sign, sign * .95, .57)))
    scene.camera.location = location
    scene.camera.rotation_euler = (center - location).to_track_quat("-Z", "Y").to_euler()
    scene.camera.data.ortho_scale = .56 if straight else .73
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 650 if straight else 1000
    scene.render.filepath = str(path)
    if os.environ.get("RETRO_RENDER", "1") == "1":
        bpy.ops.render.render(write_still=True)


def build(depth):
    if not .2 <= depth <= .8:
        raise ValueError("Specify an enclosure depth between 0.2 and 0.8 metres")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.save_version = 0
    PARTS.clear()
    scene = bpy.context.scene
    scene.name = "RM 380Z - front and rear photo study"
    scene.unit_settings.system = "METRIC"
    front_y, back_y = -depth / 2, depth / 2
    width, height = .444, .1778
    panel_height = .164
    center_z = .010 + height / 2
    black = material("Black painted steel - chassis and faceplate", (26, 30, 31), metallic=.12, roughness=.62)
    aluminium = material("Dull metal plate handles", (145, 147, 141), metallic=.7, roughness=.72)
    rubber = material("Rubber feet", (24, 24, 23), roughness=.9)
    front = material("Front photograph - Paul Flo Williams", (30, 32, 33), texture="front-panel.png", roughness=.78)
    back = material("Rear photograph - Paul Flo Williams", (160, 163, 151), texture="back-panel.png", roughness=.78)

    box("Closed black chassis", (0, 0, center_z), (width, depth, height), black, 0)
    box("Front photograph panel", (0, front_y - .0018, center_z),
        (width, .004, panel_height), black, 0, texture=front)
    box("Rear photograph panel", (0, back_y + .0006, center_z),
        (width - .002, .002, height - .003), black, 0, texture=back, side=1)

    # Each bezel reuses its exact region of the full-face photo, avoiding double labels.
    for name, region in (
        ("Drive A bezel", (.043, .501, .360, .992)),
        ("Drive B bezel", (.043, .009, .360, .493)),
    ):
        u0, v0, u1, v1 = region
        box(name, (((u0 + u1) / 2 - .5) * width, front_y - .004,
                   center_z + ((v0 + v1) / 2 - .5) * panel_height),
            ((u1 - u0) * width, .006, (v1 - v0) * panel_height),
            black, .00025, texture=front, region=region)

    # Each handle is one flat plate in the YZ plane, not a frame facing forward.
    for sign in (-1, 1):
        plate_handle("Left plate handle" if sign == -1 else "Right plate handle",
                     sign * (width / 2 + .0015), front_y, center_z, aluminium)

    for x in (-.178, .178):
        for y in (front_y + .041, back_y - .041):
            box("Inferred rubber foot", (x, y, .006), (.035, .037, .012), rubber, .002)
    for sign in (-1, 1):
        box("Lid seam", (sign * (width / 2 + .0001), 0, center_z + height / 2 - .009),
            (.0004, depth - .012, .0006), black, .0001)

    for obj in PARTS:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        if any(not edge.is_manifold for edge in bm.edges) or bm.calc_volume(signed=True) <= 0:
            raise ValueError(f"Invalid closed part: {obj.name}")
        bm.to_mesh(obj.data)
        bm.free()
        for face in obj.data.polygons:
            face.use_smooth = False
    root = bpy.data.objects.new("researchMachines380Z", None)
    bpy.context.collection.objects.link(root)
    for obj in PARTS:
        obj.parent = root
    root["dimensions_note"] = "Approximate 444 mm wide, 4U-height chassis; dimensions not measured from hardware."
    root["depth_metres"] = depth
    root["limitations"] = "Approximate dimensions; black sides/top; photographic rear connectors/vents; simplified drives; inferred feet."
    root["photo_credit"] = "Paul Flo Williams, CC BY 3.0; supplied images cropped/rectified as textures."
    bpy.ops.object.select_all(action="DESELECT")
    root.select_set(True)
    for obj in PARTS:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = PARTS[0]
    bpy.ops.wm.usd_export(
        filepath=str(ROOT / "researchMachines380Z.usdz"),
        selected_objects_only=True, export_materials=True, generate_preview_surface=True,
        convert_orientation=True, export_global_up_selection="Y", export_global_forward_selection="NEGATIVE_Z",
        convert_world_material=False, export_lights=False, export_cameras=False,
        export_custom_properties=False, triangulate_meshes=True, overwrite_textures=True,
    )

    studio = bpy.data.collections.new("Preview studio - excluded from USDZ")
    scene.collection.children.link(studio)

    def move_to_studio(obj):
        for collection in list(obj.users_collection):
            collection.objects.unlink(obj)
        studio.objects.link(obj)

    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    scene.camera = camera
    move_to_studio(camera)
    scene.world = bpy.data.worlds.new("Neutral studio")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.4, .4, .4, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = .5
    for location, energy in (((-.6, -.8, 1.1), 100), ((.6, .8, .9), 110)):
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.data.energy, light.data.size = energy, 1.1
        light.rotation_euler = (Vector((0, 0, center_z)) - light.location).to_track_quat("-Z", "Y").to_euler()
        move_to_studio(light)
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.001))
    ground = bpy.context.object
    ground.name = "Studio ground"
    ground.data.materials.append(material("Studio background", (73, 79, 88), roughness=1))
    move_to_studio(ground)
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    for rear, straight, name in ((False, False, "front-perspective"), (True, False, "rear-perspective"),
                                  (False, True, "front-elevation"), (True, True, "rear-elevation")):
        render(root, ROOT / f"{name}.png", rear, straight)
    studio.hide_viewport = True
    bpy.ops.object.select_all(action="DESELECT")
    root.select_set(True)
    bpy.context.view_layer.objects.active = root
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            space = area.spaces.active
            space.region_3d.view_location = Vector((0, 0, center_z))
            space.region_3d.view_distance = .85
            space.region_3d.view_rotation = Vector((.72, -.95, .57)).to_track_quat("Z", "Y")
            space.region_3d.view_perspective = "ORTHO"
            space.shading.type = "MATERIAL"
            space.overlay.show_overlays = False
    report = {
        "body_dimensions_metres": [width, depth, height],
        "overall_handle_width_metres": width + .006,
        "handle_plate_thickness_metres": .003,
        "handle_forward_projection_metres": .040,
        "handle_opening_metres": [.028, .1638],
        "photo_panel_dimensions_metres": [width, panel_height],
        "parts": len(PARTS),
        "triangles": sum(len(obj.data.polygons) for obj in PARTS),
        "texture_pixels": {image.name: list(image.size) for image in bpy.data.images if image.type == "IMAGE"},
        "limitations": root["limitations"],
    }
    (ROOT / "model-report.json").write_text(json.dumps(report, indent=2) + "\n")
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "researchMachines380Z.blend"))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--depth", type=float, default=.40, help="Assumed chassis depth in metres")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    build(args.depth)
