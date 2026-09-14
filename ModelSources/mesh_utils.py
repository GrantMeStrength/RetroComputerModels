"""Shared mesh finalization for enclosure builders."""

import bmesh


def finalize_mesh(obj):
    bm=bmesh.new()
    bm.from_mesh(obj.data)
    for iteration in range(8):
        bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=.000001)
        collinear=[]
        for vert in bm.verts:
            if len(vert.link_edges)==2:
                a,b=[edge.other_vert(vert).co-vert.co for edge in vert.link_edges]
                if a.length>0 and b.length>0 and a.normalized().dot(b.normalized()) < -.999999:
                    collinear.append(vert)
        if collinear:
            bmesh.ops.dissolve_verts(bm,verts=collinear,use_face_split=False,use_boundary_tear=False)
        bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if len(f.verts)>3],ngon_method="EAR_CLIP")
        tiny=[f for f in bm.faces if ((f.verts[1].co-f.verts[0].co).cross(f.verts[2].co-f.verts[0].co)).length<1e-12]
        if not tiny:
            break
        for face in tiny:
            if not face.is_valid:
                continue
            for edge in sorted(face.edges,key=lambda e:e.calc_length(),reverse=True):
                if len(edge.link_faces)!=2 or any(len(f.verts)!=3 for f in edge.link_faces):
                    continue
                opposites=[next(v for v in f.verts if v not in edge.verts) for f in edge.link_faces]
                a,b=opposites
                if any(e.other_vert(a)==b for e in a.link_edges):
                    continue
                if all((a.co-v.co).cross(b.co-v.co).length>1e-11 for v in edge.verts):
                    bmesh.ops.rotate_edges(bm,edges=[edge],use_ccw=True)
                    break
    if tiny or any(len(f.verts)!=3 for f in bm.faces):
        raise ValueError("Triangulation still contains degenerate faces")
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    if any(not e.is_manifold for e in bm.edges):
        raise ValueError("Topology cleanup opened the shell")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    for face in obj.data.polygons:
        face.use_smooth=face.area<.00002 and .15<face.normal.z<.97
