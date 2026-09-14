"""Headless original-geometry grey Spectrum +2 review candidate (millimetres)."""
from pathlib import Path
import os
import json
import math
import bpy
import bmesh
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
MM = .001
PARTS = []
LAYOUT = json.loads((ROOT/"artwork-layout.json").read_text())
CASE_LAYOUT = json.loads((ROOT/"case-label-layout.json").read_text())


def mat(name, color, rough=.55):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
    p=m.node_tree.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value=(*color,1)
    p.inputs["Roughness"].default_value=rough
    return m


def mesh(name, verts, faces, material):
    m=bpy.data.meshes.new(name)
    m.from_pydata([tuple(v*MM for v in p) for p in verts],[],faces); m.update()
    o=bpy.data.objects.new(name,m); bpy.context.collection.objects.link(o)
    o.data.materials.append(material); PARTS.append(o)
    return o


def box(name, loc, dims, material, bevel=.3, slope=False):
    bpy.ops.mesh.primitive_cube_add(size=1,location=tuple(v*MM for v in loc))
    o=bpy.context.object; o.name=name
    o.dimensions=tuple(v*MM for v in dims)
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(material); PARTS.append(o)
    if bevel:
        m=o.modifiers.new("Moulded radius","BEVEL"); m.width=min(bevel,min(dims)*.23)*MM; m.segments=3
        bpy.ops.object.modifier_apply(modifier=m.name)
    if slope:
        o.rotation_euler.x=math.atan(18/174)
    return o


def h(y):
    return 38+(y+87)*18/174


def body(name,zlower,zupper,material):
    verts=[]
    for z in [zlower,zupper]:
        for x,y in [(-219.5,-87),(219.5,-87),(219.5,87),(-219.5,87)]:
            if name=="Dark mould seam" or (name=="Upper sloping case" and z is zlower):
                x*=212.5/219.5
            verts.append((x,y,z(y)))
    o=mesh(name,verts,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),
                       (2,3,7,6),(3,0,4,7)],material)
    bevel=o.modifiers.new("Continuous enclosure edge radius","BEVEL")
    bevel.width=min(.9,(zupper(0)-zlower(0))*.23)*MM; bevel.segments=3
    bpy.context.view_layer.objects.active=o
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    return o


def cut(o,c):
    bpy.context.view_layer.objects.active=o
    m=o.modifiers.new("Reference located recess","BOOLEAN")
    m.operation="DIFFERENCE"; m.solver="EXACT"; m.object=c
    bpy.ops.object.modifier_apply(modifier=m.name)
    PARTS.remove(c); bpy.data.objects.remove(c,do_unlink=True)


def cylinder(name,loc,radius,depth,material,axis="Z"):
    rot={"Z":(0,0,0),"Y":(math.pi/2,0,0),"X":(0,math.pi/2,0)}[axis]
    bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=radius*MM,depth=depth*MM,
                                        location=tuple(v*MM for v in loc),rotation=rot)
    o=bpy.context.object; o.name=name; o.data.materials.append(material); PARTS.append(o)
    return o


def tile(o,index,axis="Z"):
    o.data.materials.append(ART)
    for layer in list(o.data.uv_layers):
        o.data.uv_layers.remove(layer)
    uv=o.data.uv_layers.new(name="UVMap")
    verts=[v.co for v in o.data.vertices]
    axes={"Z":(0,1),"Y":(0,2),"X":(1,2)}[axis]
    lo=[min(p[a] for p in verts) for a in axes]
    hi=[max(p[a] for p in verts) for a in axes]
    for p in o.data.polygons:
        facing={"Z":p.normal.z>.5,"Y":p.normal.y>.5,"X":p.normal.x<-.5}[axis]
        if facing: p.material_index=1
        for li in p.loop_indices:
            v=verts[o.data.loops[li].vertex_index]
            u=(v[axes[0]]-lo[0])/(hi[0]-lo[0])
            vv=(v[axes[1]]-lo[1])/(hi[1]-lo[1])
            if axis in ["Y","X"]: u=1-u
            uv.data[li].uv=((index%8+u)/8,1-(index//8+1-vv)/10)


def surface_label(text,x,y,z,axis):
    spec=CASE_LAYOUT["labels"][text]
    w,d=spec["decal_size_mm"]
    dims=(w,.10,d) if axis=="Y" else (.10,w,d)
    o=box("Original legend "+text,(x,y,z),dims,INVISIBLE,0)
    o.data.materials.append(CASE_ART)
    for layer in list(o.data.uv_layers):
        o.data.uv_layers.remove(layer)
    uv=o.data.uv_layers.new(name="UVMap")
    tx,ty,tw,th=spec["atlas_xywh_px"]
    aw,ah=CASE_LAYOUT["atlas_size_px"]
    for p in o.data.polygons:
        facing=p.normal.y>.5 if axis=="Y" else p.normal.x<-.5
        p.material_index=1 if facing else 0
        for li in p.loop_indices:
            if not facing:
                uv.data[li].uv=(.9999,.9999)
                continue
            v=o.data.vertices[o.data.loops[li].vertex_index].co/MM
            u=.5-(v.x if axis=="Y" else v.y)/w
            vv=.5+v.z/d
            uv.data[li].uv=((tx+u*tw)/aw,1-(ty+(1-vv)*th)/ah)
    if axis=="X":
        # Orthonormal tangents preserve texel density on the drafted side wall.
        across=Vector((7/28*18/174,1,0)).normalized()
        up=Vector((-.25,0,1))
        up=(up-across*up.dot(across)).normalized()
        inward=across.cross(up).normalized()
        center=Vector((-212.5-7*(z-(h(y)-28))/28-.045,y,z))*MM
        o.location=center
        for v in o.data.vertices:
            v.co=inward*v.co.x+across*v.co.y+up*v.co.z
        o.data.update()
    return o


def label(text,x,y,z,w,d,axis="Z",material=None):
    if axis in ["X","Y"]:
        return surface_label(text,x,y,z,axis)
    dims={"Z":(w,d,.10),"Y":(w,.10,d),"X":(.10,w,d)}[axis]
    o=box("Original legend "+text,(x,y,z),dims,material or DARK,0,axis=="Z")
    tile(o,LAYOUT["extras"][text],axis)
    return o


def cap(k):
    scale=291/1064
    x=-205+(k["x"]-95+k["w"]/2)*scale
    y=43-(k["y"]-82+k["h"]/2)*scale
    w,d=k["w"]*scale,k["h"]*scale
    z=h(y)-2.8
    verts=[]
    is_enter=k["label"]=="ENTER"
    count=6 if is_enter else 4
    for inset,dz in [(0,0),(.7,5.6),(2.0,6.4),(3.0,6.05)]:
        outline=[(-w/2+inset,-d/2+inset),(w/2-inset,-d/2+inset),
                 (w/2-inset,d/2-inset),(-w/2+inset,d/2-inset)]
        if is_enter:
            notch=-w/2+53*scale
            transition=d/2-79*scale
            outline=[(-w/2+inset,-d/2+inset),(w/2-inset,-d/2+inset),
                     (w/2-inset,d/2-inset),(notch+inset,d/2-inset),
                     (notch+inset,transition-inset),(-w/2+inset,transition-inset)]
        for px,py in outline:
            verts.append((px,py,dz))
    faces=[tuple(reversed(range(count)))]
    for r in range(3):
        for j in range(count):
            faces.append((r*count+j,r*count+(j+1)%count,(r+1)*count+(j+1)%count,(r+1)*count+j))
    faces.append(tuple(range(3*count,4*count)))
    o=mesh("Key "+k["label"].replace("\n"," "),verts,faces,DARK)
    o.location=(x*MM,y*MM,z*MM); o.rotation_euler.x=math.atan(18/174)
    tile(o,k["tile"])
    bevel=o.modifiers.new("Keycap softened edges","BEVEL")
    bevel.width=.35*MM; bevel.segments=2
    bpy.context.view_layer.objects.active=o; bpy.ops.object.modifier_apply(modifier=bevel.name)


def finish():
    report=[]
    for o in PARTS:
        o.location.z+=2*MM
        bm=bmesh.new(); bm.from_mesh(o.data)
        bmesh.ops.triangulate(bm,faces=list(bm.faces))
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        assert all(len(e.link_faces)==2 for e in bm.edges),o.name
        bm.to_mesh(o.data); bm.free(); o.data.update()
        if not o.data.uv_layers:
            uv=o.data.uv_layers.new(name="UVMap")
            for p in o.data.polygons:
                axes=sorted(range(3),key=lambda a:abs(p.normal[a]))[:2]
                for i in p.loop_indices:
                    v=o.data.vertices[o.data.loops[i].vertex_index].co
                    uv.data[i].uv=(v[axes[0]]/.44+.5,v[axes[1]]/.174+.5)
        report.append({"name":o.name,"vertices":len(o.data.vertices),"triangles":len(o.data.polygons)})
    bpy.context.view_layer.update()
    points=[o.matrix_world@Vector(c) for o in PARTS for c in o.bound_box]
    result={"status":"Original grey +2; estimated detail, not a scan",
            "revision":"1986 original grey +2, not +2A/B",
            "dimensions_mm":[round((max(p[i] for p in points)-min(p[i] for p in points))/MM,3) for i in range(3)],
            "meshes":len(PARTS),"vertices":sum(p["vertices"] for p in report),
            "triangles":sum(p["triangles"] for p in report),"parts":report}
    bpy.ops.object.select_all(action="DESELECT")
    for o in PARTS:o.select_set(True)
    bpy.context.view_layer.objects.active=PARTS[0]
    bpy.ops.wm.usd_export(filepath=str(ROOT/"spectrum-plus2.usdz"),
        selected_objects_only=True,export_materials=True,generate_preview_surface=True,
        export_lights=False,export_cameras=False,export_custom_properties=False,
        triangulate_meshes=True,convert_orientation=True,export_global_up_selection="Y",
        export_global_forward_selection="NEGATIVE_Z",convert_world_material=False,
        overwrite_textures=True)
    result["usdz_bytes"]=(ROOT/"spectrum-plus2.usdz").stat().st_size
    (ROOT/"evidence/metrics.json").write_text(json.dumps(result,indent=2))


def point(o,target=(0,0,.024)):
    o.rotation_euler=(Vector(target)-o.location).to_track_quat("-Z","Y").to_euler()


def render():
    scene=bpy.context.scene; scene.render.engine="CYCLES"
    scene.cycles.samples=24; scene.cycles.use_denoising=True
    scene.render.threads_mode="FIXED"; scene.render.threads=3
    scene.world.color=(.18,.18,.18); scene.view_settings.view_transform="AgX"
    scene.render.image_settings.file_format="PNG"
    for loc,energy,size in [((-.3,-.4,.6),5,.5),((.4,.2,.5),4,.4),((-.2,.35,.3),3,.3)]:
        bpy.ops.object.light_add(type="AREA",location=loc)
        o=bpy.context.object; o.name="PreviewOnly softbox"; o.data.energy=energy
        o.data.shape="DISK"; o.data.size=size; point(o)
    bpy.ops.object.camera_add()
    camera=bpy.context.object; camera.name="PreviewOnly camera"; camera.data.type="ORTHO"
    scene.camera=camera
    for name,loc,scale,res in [
        ("front-three-quarter",(-.38,-.50,.37),.54,(1300,850)),
        ("top",(0,0,.7),.49,(1400,660)),
        ("rear",(0,.8,.026),.49,(1400,380)),
        ("left-side",(-.8,0,.028),.20,(1100,440)),
        ("rear-three-quarter",(-.35,.5,.27),.54,(1300,750)),
    ]:
        camera.location=loc; point(camera); camera.data.ortho_scale=scale
        scene.render.resolution_x,scene.render.resolution_y=res
        scene.render.resolution_percentage=100; scene.render.filepath=str(ROOT/f"renders/{name}.png")
        if os.environ.get("RETRO_RENDER", "1") == "1":
            bpy.ops.render.render(write_still=True)
    camera.location=(-.38,-.50,.37); point(camera); camera.data.ortho_scale=.54
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/"spectrum-plus2.blend"))


def main():
    global DARK,ART,CASE_ART,INVISIBLE
    bpy.ops.object.select_all(action="SELECT"); bpy.ops.object.delete(use_global=False)
    bpy.context.scene.unit_settings.system="METRIC"
    grey=mat("Warm grey original +2 ABS",(.125,.13,.12))
    DARK=mat("Graphite key plastic",(.011,.012,.012))
    rubber=mat("Rubber",(.007,.008,.008),.8)
    silver=mat("Socket metal",(.34,.35,.32),.3)
    ART=mat("Original typeset artwork",(.02,.02,.02))
    tex=ART.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image=bpy.data.images.load(str(ROOT/"textures/legends.png"))
    ART.node_tree.links.new(tex.outputs["Color"],ART.node_tree.nodes.get("Principled BSDF").inputs["Base Color"])
    INVISIBLE=mat("Invisible decal support",(1,1,1))
    INVISIBLE.node_tree.nodes.get("Principled BSDF").inputs["Alpha"].default_value=0
    clear_tex=INVISIBLE.node_tree.nodes.new("ShaderNodeTexImage")
    clear_tex.image=bpy.data.images.load(str(ROOT/"textures/case-labels.png"))
    INVISIBLE.node_tree.links.new(clear_tex.outputs["Alpha"],
        INVISIBLE.node_tree.nodes.get("Principled BSDF").inputs["Alpha"])
    CASE_ART=mat("Case print alpha",(1,1,1))
    tex=CASE_ART.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image=clear_tex.image
    p=CASE_ART.node_tree.nodes.get("Principled BSDF")
    p.inputs["Specular IOR Level"].default_value=.15
    CASE_ART.node_tree.links.new(tex.outputs["Color"],p.inputs["Base Color"])
    CASE_ART.node_tree.links.new(tex.outputs["Alpha"],p.inputs["Alpha"])
    body("Lower drafted case",lambda y:0,lambda y:h(y)-28.4,grey)
    body("Dark mould seam",lambda y:h(y)-28.5,lambda y:h(y)-27.9,DARK)
    upper=body("Upper sloping case",lambda y:h(y)-28, h,grey)
    # Recesses interrupt the actual enclosure surface; not raised rigid frames.
    cut(upper,box("Keyboard recess cutter",(-59, -13, h(-13)+3),(301,120,13),DARK,2,True))
    box("Keyboard well",(-59,-13,h(-13)-3.9),(299,118,1.1),DARK,1,True)
    for k in LAYOUT["keys"]:cap(k)
    # Deck lid: image establishes the broad right-hand lid and six low front paddles.
    cut(upper,box("Cassette recess cutter",(153,0,h(0)+1),(111,135,7),DARK,1.5,True))
    box("Cassette seam",(153,5,h(5)-1.5),(110,123,1.4),DARK,1,True)
    box("Cassette lid",(153,15,h(15)-.25),(108,101,2),grey,1.1,True)
    box("Smoked cassette viewing inset",(153,25,h(25)+.8),(88,36,.8),DARK,1.6,True)
    smoked=mat("Smoked amber cassette window",(.045,.041,.03),.24)
    smoked.node_tree.nodes.get("Principled BSDF").inputs["Specular IOR Level"].default_value=.1
    box("Cassette window inner",(153,25,h(25)+1.23),(84,32,.2),smoked,.8,True)
    label("DATACORDER",153,-17,h(-17)+.9,101,17)
    for i,text in enumerate(["REC","PLAY","REW","F.F.","STOP / EJECT","PAUSE"]):
        x=106.5+i*18.4
        box("Cassette paddle "+text,(x,-54,h(-54)+.35),(17.5,25,6),DARK,.6,True)
        label(text,x,-54,h(-54)+3.5,16,10)
    label("sinclair",-166,71,h(71)+.12,64,10)
    label("128K",48,71,h(71)+.12,22,10)
    label("ZX Spectrum +2",150,72,h(72)+.15,107,10)
    for y in [-67,-48,-29,-10,9,28,47]:
        cut(upper,box("Upper deck mould line",(0,y,h(y)-.1),(440,.48,.42),DARK,0,True))
    # Rear upper vent row and lower heat sink grille, positions from supplied rear.
    for x in range(-211,214,7):
        cut(upper,box("Upper rear vent cutter",(x,85.7,51.5),(2,5.4,6),DARK,.15))
    lower=PARTS[0]
    cut(lower,box("Rear heatsink opening",(95,86,16.8),(88,8,27),DARK,.3))
    box("Rear heatsink shadow",(95,82.8,16.8),(87,.8,26),DARK,.2)
    for x in range(54,138,7):
        box("Rear grille moulded rib",(x,86.25,16.8),(2.7,2,26.2),grey,.25)
    ports=[("9V DC",32,15,5,"round"),("EXPANSION I/O",-20,8,76,"edge"),
           ("RS232 /\nMIDI",-71,21,17,"rect"),("KEYPAD",-97,21,17,"rect"),
           ("RGB",-122,21,8,"round"),("TV",-170,19,5.3,"round"),("SOUND",-189,14,4.1,"round")]
    for text,x,z,size,kind in ports:
        label(text,x,87.03,40,36 if kind=="edge" else 18,9,"Y",grey)
        if kind=="round":
            cut(lower,cylinder("Port cutter",(x,86,z),size,9,DARK,"Y"))
            cylinder("Socket dark interior "+text,(x,83,z),size*.96,1.5,DARK,"Y")
            if text!="RGB":
                cylinder("Socket ring "+text,(x,85,z),size*.72,1.2,silver,"Y")
                cylinder("Socket hollow "+text,(x,85.8,z),size*.43,.3,DARK,"Y")
            else:
                for a in range(8):
                    angle=a*math.tau/8
                    cylinder("RGB pin socket",(x+4.7*math.cos(angle),85,z+4.7*math.sin(angle)),.7,.4,rubber,"Y")
        else:
            depth=9 if kind=="edge" else 13
            cut(lower,box("Rear rectangular cutter",(x,86,z),(size,9,depth),DARK,.5))
            box("Rear connector shadow "+text,(x,82.7,z),(size-.8,1,depth-.8),DARK,.2)
            if kind=="edge":
                gold=mat("Expansion contact gold",(.35,.27,.09),.38)
                for j in range(23):
                    box("Edge connector contact",(x-size/2+3+j*3,84,z-2),(1,1,3),gold,.05)
    # Joystick 2 then 1 towards the front; reset after the two sockets.
    for y,num in [(45,2),(11,1)]:
        cut(lower,box("Joystick recess cutter",(-218,y,16),(8,23,12),DARK,.8))
        box(f"Joystick {num} surround",(-217.2,y,16),(.9,22,11),DARK,.7)
        for row,n in [(1.8,5),(-1.8,4)]:
            for j in range(n):
                cylinder("Joystick socket",(-218.0,y+(j-(n-1)/2)*3.2,16+row),.65,.6,silver,"X")
    cut(lower,box("Reset cutter",(-218,-17,14),(8,9,9),DARK,.2))
    box("Reset plunger",(-217,-17,14),(1.2,6,7),DARK,.25)
    label("USE ONLY SINCLAIR\nSJS1 JOYSTICKS",-219.53,54,34,30,11,"X",grey)
    label("JOYSTICKS",-219.53,13,29,30,8,"X",grey)
    label("RESET",-219.53,-17,27,18,7,"X",grey)
    # Narrow side mould lines rather than invented broad enclosing rails.
    for y in [-69,-49,-29,-9,11,31,51]:
        cut(upper,box("Left mould groove",(-219.5,y,h(y)-14),(20,.55,27.5),DARK,0))
    for v in lower.data.vertices:
        x,y,z=v.co/MM
        if abs(x)>205:
            taper=max(0,min(1,1-z/(h(y)-28.4)))
            v.co.x-=math.copysign((7+3*taper)*MM,x)
        v.co.y*=82.5/87
    for o in PARTS:
        if o.name.startswith(("Rear heatsink shadow","Rear grille","Socket","RGB pin",
                              "Rear connector shadow","Edge connector contact")):
            o.location.y-=4.5*MM
        if o.name.startswith(("Joystick","Reset plunger")):
            o.location.x+=7*MM
    for x in [-190,190]:
        for y in [-65,64]:
            box("Rubber foot",(x,y,-1),(14,10,2),rubber,.7)
    finish()
    render()


if __name__=="__main__":
    main()
