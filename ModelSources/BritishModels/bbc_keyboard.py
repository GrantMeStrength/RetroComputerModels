"""BBC-only keyboard panel and sculpted keycaps."""

import math

import bmesh
import bpy

from layouts import BBC_CAP_INSET_X, BBC_CAP_INSET_Y


def panel(p, width, front, split, rear, deck, plastic, banner):
    vertices = [(x, y, deck(y) + offset)
                for offset in (-.004, -.003)
                for y in (front, split, rear) for x in (-width / 2, width / 2)]
    faces = [(6, 7, 9, 8), (8, 9, 11, 10), (2, 3, 1, 0), (4, 5, 3, 2),
             (0, 1, 7, 6), (5, 4, 10, 11)]
    for row in range(2):
        a = row * 2
        faces.extend([(a, a + 6, a + 8, a + 2), (a + 1, a + 3, a + 9, a + 7)])
    mesh = bpy.data.meshes.new("BBC continuous keyboard panel")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(plastic)
    mesh.materials.append(banner)
    mesh.update()
    uv = mesh.uv_layers.new(name="UVMap")
    mesh.polygons[1].material_index = 1
    for index in mesh.polygons[1].loop_indices:
        point = mesh.vertices[mesh.loops[index].vertex_index].co
        uv.data[index].uv = (point.x / width + .5, (point.y - split) / (rear - split))
    obj = bpy.data.objects.new("BBC unified keyboard and legend panel", mesh)
    bpy.context.collection.objects.link(obj)
    p.PARTS.append(obj)
    return obj


def rounded_ring(width, depth, radius):
    points = []
    for cx, cy, start in ((width / 2 - radius, depth / 2 - radius, 0),
                          (-width / 2 + radius, depth / 2 - radius, math.pi / 2),
                          (-width / 2 + radius, -depth / 2 + radius, math.pi),
                          (width / 2 - radius, -depth / 2 + radius, 3 * math.pi / 2)):
        for step in range(8):
            angle = start + step * math.pi / 14
            points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def keycap(p, label, center, width, depth, slope, plastic, artwork, rectangle):
    top_width, top_depth = width - BBC_CAP_INSET_X, depth - BBC_CAP_INSET_Y
    def top_height(y):
        crown = .00025 if label == "SPACE" else -.00055
        return .0045 + crown * (1 - (2 * y / top_depth) ** 2)
    rings = [
        [(x, y, -.0045) for x, y in rounded_ring(width, depth, .0012)],
        [(x, y, .0028) for x, y in rounded_ring(width - .0012, depth - .0008, .001)],
        [(x, y, top_height(y)) for x, y in rounded_ring(top_width, top_depth, .0009)],
        [(x, y, top_height(y)) for x, y in rounded_ring(top_width / 2, top_depth / 2, .00045)],
    ]
    count = len(rings[0])
    vertices = [point for ring in rings for point in ring] + [(0, 0, top_height(0))]
    faces = [tuple(reversed(range(count)))]
    top_faces = []
    for ring in range(3):
        for i in range(count):
            following = (i + 1) % count
            if ring == 2:
                top_faces.append(len(faces))
            faces.append((ring * count + i, ring * count + following,
                          (ring + 1) * count + following, (ring + 1) * count + i))
    for i in range(count):
        top_faces.append(len(faces))
        faces.append((3 * count + i, 3 * count + (i + 1) % count, 4 * count))
    mesh = bpy.data.meshes.new("BBC sculpted cap " + label)
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(plastic)
    mesh.materials.append(artwork)
    mesh.update()
    uv = mesh.uv_layers.new(name="UVMap")
    for index in top_faces:
        face = mesh.polygons[index]
        face.material_index = 1
        for loop in face.loop_indices:
            point = mesh.vertices[mesh.loops[loop].vertex_index].co
            u, v = point.x / top_width + .5, point.y / top_depth + .5
            uv.data[loop].uv = (rectangle[0] + u * (rectangle[2] - rectangle[0]),
                                rectangle[1] + v * (rectangle[3] - rectangle[1]))
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    if any(not edge.is_manifold for edge in bm.edges) or bm.calc_volume(signed=True) <= 0:
        raise ValueError(f"Invalid sculpted BBC key: {label}")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("BBC key " + label.replace("\n", " "), mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = center
    obj.rotation_euler.x = math.atan(slope)
    p.PARTS.append(obj)
    return obj
