"""Measured-profile Jupiter Ace model, with independently authored topology."""
import json
import math
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector

ROOT=Path(__file__).resolve().parent
MM=.001
CX=91.3753652573
CY=204.0654296875
BASE=16.44311142
HALF=111.2060709
YMIN=-303.0085449
YMAX=-105.1223145
PROFILE=[
    (-303.0085,-11.682),(-302.5,-10.801),(-300,-6.471),(-298,-3.007),
    (-297,-1.894),(-296,-1.142),(-295,-.614),(-294,-.26),(-293,-.06),
    (-292,-.06),(-214,-.06),(-212.15,.088),(-211,.983),(-200,9.539),
    (-199,10.317),(-198.5,10.65),(-198,10.84),(-197.5,10.888),
    (-175,10.888),(-174,10.888),(-173.5,10.96),(-173,11.143),
    (-172,12.143),(-166,18.143),(-165.5,18.59),(-165,18.80),
    (-164.5,18.8226),(-115,18.8226),(-114,18.8226),(-113.7,18.69),
    (-113.4,18.35),(-113,17.704),(-112,13.972),(-110,6.508),
    (-108,-.957),(-106,-8.421),(-105.3,-11.034),(-105.1223,-11.68206),
]
LOWER_PROFILE=[
    (-303.0085,-11.68206),(-302.5,-12.03418),(-302,-12.38901),
    (-301,-13.09867),(-300,-13.80833),(-299,-14.51799),(-298,-15.22765),
    (-297,-15.93731),(-296.2968,-16.44311142),(-112,-16.44311142),
    (-110.6532,-16.44311142),(-110,-16.31995),(-109,-15.54735),
    (-108,-14.54728),(-107,-13.54721),(-106,-12.54714),
    (-105.2,-11.74708),(-105.1223,-11.68206),
]
PARTS=[]


def interp(y, profile=PROFILE):
    return float(np.interp(y,[a for a,b in profile],[b for a,b in profile]))


def material(name,color,texture=None,rough=.57,metallic=0):
    mat=bpy.data.materials.new(name)
    mat.diffuse_color=(*color,1)
    mat.use_nodes=True
    bs=mat.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value=(*color,1)
    bs.inputs["Roughness"].default_value=rough
    bs.inputs["Metallic"].default_value=metallic
    bs.inputs["Specular IOR Level"].default_value=.23
    if texture:
        tex=mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image=bpy.data.images.load(str(ROOT/"Textures"/texture))
        tex.extension="EXTEND"
        mat.node_tree.links.new(tex.outputs["Color"],bs.inputs["Base Color"])
    return mat


def mesh_object(name,verts,faces,mat):
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata([[a*MM for a in v] for v in verts],[],faces)
    mesh.update()
    obj=bpy.data.objects.new(name,mesh)
    bpy.context.collection.objects.link(obj)
    mesh.materials.append(mat)
    PARTS.append(obj)
    return obj


def make_case():
    ys=sorted(set([a for a,b in PROFILE+LOWER_PROFILE]+list(np.linspace(YMIN+.01,YMAX-.01,155))))
    verts=[]; faces=[]
    for y in ys:
        h=interp(y)+BASE
        # At the feather-edge ends, retain a 0.10 mm closed cap rather than
        # degenerating the whole transverse ring to a line.
        bottom=min(interp(y,LOWER_PROFILE)+BASE,h-.10)
        endinset=0
        for dist in (y-YMIN,YMAX-y):
            if dist<3:
                endinset=max(endinset,3-math.sqrt(max(0,9-(3-dist)**2)))
        w=HALF-endinset
        radius=min(3.3,(h-bottom)*.18)
        left=[-w+radius*(1-math.cos(t)) for t in np.linspace(0,math.pi/2,9)]
        middle=[-w+radius+(2*w-2*radius)*t for t in np.linspace(.015,.985,29)]
        xs=left+middle+[-x for x in reversed(left)]
        ring=[]
        for x in xs:
            edge=max(0,abs(x)-(w-radius))
            z=h-radius+math.sqrt(max(0,radius*radius-edge*edge))
            # Subtle integrated keyboard dish; no separate frame or overlaid rail.
            recy=float(np.interp(y,[-293,-291,-215,-213],[0,.23,.23,0]))
            recx=float(np.interp(abs(x),[103,105.5,108],[1,.7,0]))
            z-=recy*recx
            ring.append((x,y+CY,z))
        seam=max(bottom+.025,min(h-radius-.025,BASE-11.68206))
        gap=min(.10,(h-radius-seam)*.5,(seam-bottom)*.2)
        # Compact authored samples of the measured lower side roundover.
        side=[(w,seam+gap),(w-.10,seam),(w-.13,seam-gap)]
        lowerheight=seam-gap-bottom
        corner_scale=max(.08,min(1,lowerheight/(BASE-11.68206)))
        side += [(w-.13-(d-.13)*corner_scale,bottom+lowerheight*f) for d,f in [
            (.18,.971),(.58,.763),(1.58,.2435),(2.58,.0303),(3.18,.0006),(3.5,0)]]
        ring += [(x,y+CY,z) for x,z in side]
        ring += [(0,y+CY,bottom)]
        ring += [(-x,y+CY,z) for x,z in reversed(side)]
        verts+=ring
    n=len(ring)
    for r in range(len(ys)-1):
        for c in range(n):
            faces.append((r*n+c,r*n+(c+1)%n,(r+1)*n+(c+1)%n,(r+1)*n+c))
    faces += [tuple(reversed(range(n))),tuple((len(ys)-1)*n+c for c in range(n))]
    body=mesh_object("Original_Profile_Case_Measured_Upper_And_Lower",verts,faces,WHITE)
    body.data.materials.append(TOP)
    return body


def rounded_ring(hx,hy,r,z,n=8):
    out=[]
    for cx,cy,start in [(hx-r,hy-r,0),(-hx+r,hy-r,90),
                         (-hx+r,-hy+r,180),(hx-r,-hy+r,270)]:
        for angle in np.linspace(start,start+90,n,endpoint=False):
            a=math.radians(angle)
            out.append((cx+r*math.cos(a),cy+r*math.sin(a),z))
    return out


def make_key(row,col,x,y,width=13.7):
    verts=[];faces=[]
    for inset,z,r in [(0,0,1.5),(-.15,.65,1.65),(.10,2.3,1.9),
                       (.5,3.65,2.0),(1.0,4.35,2.0),(1.45,4.60,1.8)]:
        verts+=rounded_ring(width/2-inset,6.4-inset,r,z)
    n=32
    for k in range(5):
        for i in range(n):
            faces.append((k*n+i,k*n+(i+1)%n,(k+1)*n+(i+1)%n,(k+1)*n+i))
    faces.append(tuple(reversed(range(n))))
    verts.append((0,0,4.71))
    for i in range(n):
        faces.append((5*n+i,5*n+(i+1)%n,len(verts)-1))
    obj=mesh_object(f"Rubber_Key_{row+1}_{col+1}",verts,faces,RUBBER)
    obj.location=((x-CX)*MM,(y+CY)*MM,(BASE-.49)*MM)
    obj.data.materials.append(KEYS)
    obj["key_row"]=row
    obj["key_column"]=col
    obj["key_width_mm"]=width
    return obj


def cube(name,location,dimensions,mat,bevel=0):
    bpy.ops.mesh.primitive_cube_add(size=1,location=tuple(v*MM for v in location))
    obj=bpy.context.object
    obj.name=name
    obj.dimensions=tuple(v*MM for v in dimensions)
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    obj.data.materials.append(mat)
    if bevel:
        mod=obj.modifiers.new("Small moulded radius","BEVEL")
        mod.width=bevel*MM;mod.segments=3
        bpy.ops.object.modifier_apply(modifier=mod.name)
    PARTS.append(obj)
    return obj


def difference(body,cutter):
    bpy.context.view_layer.objects.active=body
    mod=body.modifiers.new("Recessed connector pocket","BOOLEAN")
    mod.operation="DIFFERENCE";mod.solver="EXACT";mod.object=cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    if cutter in PARTS:PARTS.remove(cutter)
    bpy.data.objects.remove(cutter,do_unlink=True)


def ports(body):
    measured=json.loads((ROOT/"socket-measurements.json").read_text())
    for name,circles in measured.items():
        for circle in circles:
            side=1 if name=="right" else -1
            sy,sz=circle["center_yz_stl"]
            y,z,r=sy+CY,sz+BASE,circle["radius_assumed_mm"]
            bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=r*MM,depth=8*MM,
                location=(side*HALF*MM,y*MM,z*MM),rotation=(0,math.pi/2,0))
            difference(body,bpy.context.object)
            bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=r*.94*MM,depth=.75*MM,
                location=(side*(HALF-3.8)*MM,y*MM,z*MM),rotation=(0,math.pi/2,0))
            obj=bpy.context.object;obj.name="Recessed_Socket_Dark_Interior"
            obj.data.materials.append(DARK);PARTS.append(obj)
            # Connector insert hardware is schematic, not present in the supplied STL.
            bpy.ops.mesh.primitive_torus_add(major_segments=40,minor_segments=8,
                major_radius=r*.55*MM,minor_radius=.42*MM,
                location=(side*(HALF-2.2)*MM,y*MM,z*MM),rotation=(0,math.pi/2,0))
            obj=bpy.context.object;obj.name="Schematic_Recessed_Socket_Collar"
            obj.data.materials.append(METAL);PARTS.append(obj)
    for x,w in [(29.89608-CX,74.9),(114.17572-CX,41.721)]:
        z=BASE-6.8
        cutter=cube("Rear aperture tool",(x,98.6,z),(w,12,11.2),WHITE,.4)
        difference(body,cutter)
        cube("Expansion_Socket_Interior_Approximate",(x,93,z),(w-2,1,9),DARK,.3)


def underside(body):
    def cylinder_cut(x,y,r,depth):
        bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=r*MM,depth=(depth+.5)*MM,
            location=((x-CX)*MM,(y+CY)*MM,(depth-.5)*.5*MM))
        difference(body,bpy.context.object)
    for x in (-6.91745,189.28375):
        for y in (-287.44505,-130.845):
            cylinder_cut(x,y,5.83095,.5)
    for x in (13.3243,165.3243):
        cylinder_cut(x,-291.8869,3.2,2.5)
        cylinder_cut(x,-291.8869,1.6,4.5)
    # Rear countersink: 5.74 mm radius at the bottom, 2.50 at Z +3.24.
    bpy.ops.mesh.primitive_cone_add(vertices=64,radius1=6.24*MM,radius2=2.5*MM,
        depth=3.74*MM,location=((76.19015-CX)*MM,(-123.5888+CY)*MM,1.37*MM))
    difference(body,bpy.context.object)
    cylinder_cut(76.19015,-123.5888,2.5,4.5)
    for x,y,r in [(13.3243,-291.8869,1.6),(165.3243,-291.8869,1.6),(76.19015,-123.5888,2.5)]:
        bpy.ops.mesh.primitive_cylinder_add(vertices=40,radius=r*.98*MM,depth=.1*MM,
            location=((x-CX)*MM,(y+CY)*MM,4.42*MM))
        obj=bpy.context.object;obj.name="Recessed_Fastener_Bore_Interior"
        obj.data.materials.append(DARK);PARTS.append(obj)
    x0,y0,r=34.616875,-172.685,12.64185
    for lo,hi in [(-r,-9),(-7,-5),(-3,-1),(1,3),(5,7),(9,r)]:
        # Fresh circle/stripe intersection, not the STL aperture tessellation.
        sy=np.linspace(lo,hi,17)
        outline=[(math.sqrt(max(0,r*r-y*y)),y) for y in sy]
        outline += [(-math.sqrt(max(0,r*r-y*y)),y) for y in reversed(sy)]
        cleaned=[]
        for pt in outline:
            if not cleaned or math.dist(pt,cleaned[-1])>.0001:
                cleaned.append(pt)
        if math.dist(cleaned[0],cleaned[-1])<.0001:cleaned.pop()
        verts=[(x+x0-CX,y+y0+CY,z) for z in (-.5,3.4) for x,y in cleaned]
        n=len(cleaned)
        faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]
        faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
        cutter=mesh_object("Analytic_Circular_Grille_Slot_Tool",verts,faces,WHITE)
        difference(body,cutter)
    bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=12.7*MM,depth=.12*MM,
        location=((x0-CX)*MM,(y0+CY)*MM,3.32*MM))
    obj=bpy.context.object;obj.name="Recessed_Speaker_Grille_Dark_Interior"
    obj.data.materials.append(DARK);PARTS.append(obj)


def finish(obj):
    mesh=obj.data
    bm=bmesh.new();bm.from_mesh(mesh)
    if any(not e.is_manifold for e in bm.edges):
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7)
        # Exact booleans can omit a single coplanar foot-seat wall quad.
        # Only four-edge boundary loops are eligible; larger holes still fail QA.
        boundaries=[e for e in bm.edges if len(e.link_faces)==1]
        patch=bmesh.ops.holes_fill(bm,edges=boundaries,sides=4)
        obj["numerical_boolean_wall_quads_restored"]=len(patch["faces"])
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces)
    bmesh.ops.triangulate(bm,faces=bm.faces)
    bm.to_mesh(mesh);bm.free();mesh.update()
    uv=mesh.uv_layers.new(name="UVMap")
    uv.active_render=True
    iskey="key_row" in obj
    iscase=obj.name.startswith("Original_Profile")
    for poly in mesh.polygons:
        poly.use_smooth=True
        if iskey:
            poly.material_index=int(poly.center.z>3.2*MM and poly.normal.z>.15)
        elif iscase:
            poly.material_index=int(poly.normal.z>.12 and poly.center.z/MM>interp(poly.center.y/MM-CY)-3.0+BASE)
        for li in poly.loop_indices:
            p=mesh.vertices[mesh.loops[li].vertex_index].co/MM
            if iskey:
                u=p.x/obj["key_width_mm"]+.5
                v=p.y/12.8+.5
                uv.data[li].uv=((obj["key_column"]+u)/10,(3-obj["key_row"]+v)/4)
            else:
                uv.data[li].uv=((p.x+HALF)/(2*HALF),(p.y-(YMIN+CY))/(YMAX-YMIN))
    bm=bmesh.new();bm.from_mesh(mesh)
    for e in bm.edges:
        if len(e.link_faces)==2:e.smooth=e.calc_face_angle()<math.radians(42)
    bm.to_mesh(mesh)
    report={"name":obj.name,"vertices":len(bm.verts),"triangles":len(bm.faces),
            "nonmanifold_edges":sum(not e.is_manifold for e in bm.edges),
            "degenerate_faces":sum(f.calc_area()<5e-13 for f in bm.faces),
            "signed_volume_m3":bm.calc_volume(signed=True)}
    bm.free()
    if report["nonmanifold_edges"] or report["degenerate_faces"] or report["signed_volume_m3"]<=0:
        raise ValueError(report)
    return report


if __name__=="__main__":
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.object.select_all(action="SELECT");bpy.ops.object.delete(use_global=False)
    bpy.context.scene.unit_settings.system="METRIC"
    bpy.context.scene.unit_settings.scale_length=1
    WHITE=material("Neutral_White_ABS",(.745,.745,.687))
    TOP=material("Original_Drawn_Case_Artwork",(.745,.745,.687),"case-original.png")
    RUBBER=material("Soft_Black_Rubber",(.0065,.007,.0075),rough=.76)
    KEYS=material("Original_Drawn_Key_Legends",(.007,.008,.009),"keys-original.png",rough=.76)
    DARK=material("Unlit_Connector_Interior",(.009,.01,.012),rough=.8)
    METAL=material("Schematic_Socket_Nickel",(.36,.38,.40),rough=.31,metallic=.65)
    body=make_case()
    ports(body)
    underside(body)
    for row,(x0,y) in enumerate([(-.5,-220.08),(7.94,-239.36),(13.33,-258.27),(4.13,-277.09)]):
        for col in range(10):
            x=x0+col*19.0466667
            wide=row==3 and col==9
            if wide:x=180.335
            make_key(row,col,x,y,23.27 if wide else 13.7)
    reports=[finish(o) for o in PARTS]
    bpy.context.view_layer.update()
    coords=[o.matrix_world@Vector(p) for o in PARTS for p in o.bound_box]
    report={"status":"Three measured case references, schematic connector inserts",
            "dimensions_mm_width_depth_height":[(max(v[i] for v in coords)-min(v[i] for v in coords))/MM for i in range(3)],
            "upper_profile_stl_coordinates":PROFILE,"lower_profile_stl_coordinates":LOWER_PROFILE,
            "origin_shift_mm":[-CX,CY,BASE],
            "bottom_reference":"jupiter-ace-Bottom.stl",
            "excluded_supports":"Keyboard tabs protruding below bottom, all internal ribs/bosses and disconnected bottom bar",
            "parts":reports,"triangles":sum(r["triangles"] for r in reports),
            "vertices":sum(r["vertices"] for r in reports),"key_count":40}
    bpy.ops.object.select_all(action="DESELECT")
    for obj in PARTS:obj.select_set(True)
    bpy.context.view_layer.objects.active=body
    bpy.ops.wm.usd_export(filepath=str(ROOT/"jupiterAce.usdz"),selected_objects_only=True,
        export_materials=True,generate_preview_surface=True,export_lights=False,export_cameras=False,
        export_custom_properties=False,triangulate_meshes=True,convert_orientation=True,
        export_global_up_selection="Y",export_global_forward_selection="NEGATIVE_Z",
        convert_world_material=False,overwrite_textures=True)
    report["usdz_bytes"]=(ROOT/"jupiterAce.usdz").stat().st_size
    (ROOT/"candidate-metrics.json").write_text(json.dumps(report,indent=2))
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/"jupiterAce.blend"))
    print("CANDIDATE",json.dumps({k:v for k,v in report.items() if k not in ("parts","upper_profile_stl_coordinates")}))
