import bpy, math, json, time
from pathlib import Path
from mathutils import Vector

OUT=Path("evidence"); OUT.mkdir(exist_ok=True)
T0=time.time()
for o in list(bpy.data.objects): bpy.data.objects.remove(o,do_unlink=True)

def mat(name,c,metal=0,rough=.35,emit=None,strength=0):
    m=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes=True
    bs=m.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value=c; bs.inputs["Metallic"].default_value=metal; bs.inputs["Roughness"].default_value=rough
    if emit:
        bs.inputs["Emission Color"].default_value=emit; bs.inputs["Emission Strength"].default_value=strength
    return m

SILVER=mat("Silver",(.55,.62,.72,1),.84,.16)
SILVER2=mat("Silver2",(.78,.82,.88,1),.68,.19)
BLACK=mat("Black",(.012,.018,.025,1),.25,.18)
DARK=mat("Dark",(.035,.045,.06,1),.58,.24)
RUBBER=mat("Rubber",(.008,.009,.012,1),0,.62)
METAL=mat("Metal",(.16,.18,.22,1),.92,.14)
BLUE=mat("BlueLED",(.005,.055,.20,1),.1,.07,(.02,.55,1,1),16)
RED=mat("RedLED",(.18,.004,.004,1),.1,.1,(1,.01,.01,1),12)
AMBER=mat("Amber",(.2,.04,.003,1),.05,.1,(1,.18,.01,1),9)
SEAT=mat("Seat",(.015,.018,.024,1),0,.60)
GLASS=mat("Glass",(.02,.035,.055,1),.12,.08)

def smooth(o):
    if hasattr(o.data,"polygons"):
        for p in o.data.polygons:p.use_smooth=True

def bevel(o,w=.03,seg=3):
    b=o.modifiers.new("Bevel","BEVEL"); b.width=w; b.segments=seg
    return o

def cube(name,loc,scale,material,rot=(0,0,0),bev=.04):
    bpy.ops.mesh.primitive_cube_add(location=loc,rotation=rot)
    o=bpy.context.object; o.name=name; o.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(material)
    if bev: bevel(o,bev,3)
    return o

def ellipsoid(name,loc,scale,material,rot=(0,0,0)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48,ring_count=24,location=loc,rotation=rot)
    o=bpy.context.object;o.name=name;o.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(material);smooth(o);return o

def prism(name,profile,width,material,y=0,bev=.025):
    # profile list (x,z) ordered around silhouette
    verts=[]; hw=width/2
    for x,z in profile: verts.append((x,y-hw,z))
    for x,z in profile: verts.append((x,y+hw,z))
    n=len(profile);faces=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]
    for i in range(n):
        j=(i+1)%n;faces.append((i,j,n+j,n+i))
    me=bpy.data.meshes.new(name+"Mesh");me.from_pydata(verts,[],faces);me.update()
    o=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(o);o.data.materials.append(material)
    if bev: bevel(o,bev,3)
    return o

def beam(name,a,b,r,material,verts=20):
    a=Vector(a);b=Vector(b);d=b-a
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=r,depth=d.length,location=(a+b)*.5)
    o=bpy.context.object;o.name=name;o.rotation_euler=d.to_track_quat("Z","Y").to_euler();o.data.materials.append(material);smooth(o);return o

def curve(name,pts,r,material):
    cu=bpy.data.curves.new(name,"CURVE");cu.dimensions="3D";cu.bevel_depth=r;cu.bevel_resolution=5
    sp=cu.splines.new("POLY");sp.points.add(len(pts)-1)
    for p,co in zip(sp.points,pts):p.co=(*co,1)
    o=bpy.data.objects.new(name,cu);bpy.context.collection.objects.link(o);o.data.materials.append(material);return o

def torus(name,loc,major,minor,material):
    bpy.ops.mesh.primitive_torus_add(major_radius=major,minor_radius=minor,major_segments=64,minor_segments=20,location=loc,rotation=(math.pi/2,0,0))
    o=bpy.context.object;o.name=name;o.data.materials.append(material);smooth(o);return o

def wheel(name,loc):
    torus(name+"_tire",loc,.36,.13,RUBBER)
    bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=.30,depth=.13,location=loc,rotation=(math.pi/2,0,0))
    rim=bpy.context.object;rim.data.materials.append(BLACK);smooth(rim)
    bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=.11,depth=.15,location=loc,rotation=(math.pi/2,0,0))
    hub=bpy.context.object;hub.data.materials.append(METAL);smooth(hub)
    for k in range(6):
        a=2*math.pi*k/6
        p=(loc[0]+.23*math.cos(a),loc[1],loc[2]+.23*math.sin(a))
        beam(name+f"_sp{k}",loc,p,.022,SILVER2,14)

def arc_fender(name,cx,cy,cz,r_outer,r_inner,width,material,a0=25,a1=155,steps=24):
    verts=[];faces=[]; hw=width/2
    for y in (cy-hw,cy+hw):
        for r in (r_outer,r_inner):
            for i in range(steps+1):
                a=math.radians(a0+(a1-a0)*i/steps)
                verts.append((cx+r*math.cos(a),y,cz+r*math.sin(a)))
    # indices: yside*2*(steps+1)+radial*(steps+1)+i
    N=steps+1
    def I(s,rr,i): return s*2*N+rr*N+i
    for i in range(steps):
        # outer strip and inner strip surfaces
        faces.append((I(0,0,i),I(0,0,i+1),I(1,0,i+1),I(1,0,i)))
        faces.append((I(0,1,i+1),I(0,1,i),I(1,1,i),I(1,1,i+1)))
        # side faces
        faces.append((I(0,0,i),I(0,1,i),I(0,1,i+1),I(0,0,i+1)))
        faces.append((I(1,0,i+1),I(1,1,i+1),I(1,1,i),I(1,0,i)))
    # end caps
    faces += [(I(0,0,0),I(1,0,0),I(1,1,0),I(0,1,0)),(I(0,0,steps),I(0,1,steps),I(1,1,steps),I(1,0,steps))]
    me=bpy.data.meshes.new(name+"Mesh");me.from_pydata(verts,[],faces);me.update()
    o=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(o);o.data.materials.append(material);bevel(o,.018,2);return o

def spring(name,loc,h=.55,r=.06):
    pts=[]
    for i in range(90):
        t=i/89*8*2*math.pi;pts.append((loc[0]+r*math.cos(t),loc[1]+r*math.sin(t),loc[2]-h/2+h*i/89))
    curve(name,pts,.010,METAL);beam(name+"_core",(loc[0],loc[1],loc[2]-h/2),(loc[0],loc[1],loc[2]+h/2),.024,DARK)

FX=1.45;FY=.66;FZ=.53;RX=-1.52;RZ=.55
wheel("FrontL",(FX,FY,FZ));wheel("FrontR",(FX,-FY,FZ));wheel("Rear",(RX,0,RZ))

# lower sporty base
prism("LowerBase",[(-1.72,.43),(-1.45,.34),(.72,.36),(1.05,.58),(.82,.82),(-.55,.84),(-1.45,.67)],.76,DARK,0,.055)
prism("LowerSilver",[(-1.38,.50),(-.85,.45),(.52,.49),(.78,.61),(.55,.70),(-.75,.68)],.82,SILVER2,0,.035)
cube("Footboard",(-.15,0,.77),(.72,.32,.055),BLACK,bev=.045)

# rear black mass + sharp silver side panels
prism("RearCore",[(-1.67,.72),(-1.50,1.18),(-1.05,1.52),(-.18,1.56),(.18,1.32),(.03,.96),(-.72,.82)],.70,BLACK,0,.07)
rear_panel=[(-1.55,.87),(-1.36,1.20),(-1.02,1.44),(-.26,1.48),(.02,1.26),(-.12,1.05),(-.86,.94)]
for y in (-.40,.40):
    prism("RearPanel",rear_panel,.16,SILVER2,y,.035)
    prism("RearDarkInsert",[(-.96,.96),(-.25,1.08),(.00,1.24),(-.18,1.02),(-.80,.88)],.18,DARK,y*1.01,.025)
    curve("SideLED",[(.00,y*1.03,1.26),(-.18,y*1.03,1.10),(-.43,y*1.03,1.02)],.018,BLUE)

# seat
ellipsoid("Seat",(-.83,0,1.57),(.86,.38,.16),SEAT,rot=(0,-.05,0))
ellipsoid("SeatRear",(-1.29,0,1.62),(.40,.36,.15),SEAT)
curve("Grab",[(-1.50,-.30,1.75),(-1.74,0,1.82),(-1.50,.30,1.75)],.030,SILVER2)

# front core and layered cheeks
prism("FrontCore",[(.16,.86),(.40,1.70),(.67,2.12),(.95,2.18),(1.20,1.86),(1.30,1.32),(1.05,.96)],.48,BLACK,0,.055)
front_panel=[(.30,1.02),(.50,1.67),(.76,2.02),(1.03,2.00),(1.25,1.70),(1.25,1.28),(1.02,1.04)]
for y in (-.31,.31):
    prism("FrontPanel",front_panel,.18,SILVER2,y,.035)
    prism("FrontLowerPanel",[(.72,.98),(1.12,1.02),(1.36,1.25),(1.27,1.48),(.96,1.36)],.20,SILVER,y*1.03,.03)

# front wheel fenders
for y in (-FY,FY):
    arc_fender("Fender",FX,y,FZ,.58,.46,.22,SILVER2,30,150,28)
    spring("FrontShock",(1.03,y*.80,1.19),.60,.055)
    beam("UpperArm",(1.18,y,.74),(.64,y*.50,1.19),.030,METAL)
    beam("LowerArm",(1.18,y,.58),(.55,y*.52,.80),.036,METAL)
    beam("HubLink",(FX,y,FZ),(1.18,y,.72),.040,METAL)
    cube("Amber",(1.40,y*1.01,1.06),(.018,.022,.15),AMBER,bev=.012)

# windshield / cowl / nose
prism("Windshield",[(.43,1.82),(.61,2.24),(.92,2.30),(1.08,2.03),(.84,1.84)],.42,GLASS,0,.025)
prism("TopCowl",[(.34,1.88),(.52,2.18),(.83,2.22),(1.00,2.01),(.78,1.85)],.52,DARK,0,.035)
prism("Nose",[(.92,1.30),(1.15,1.52),(1.24,1.83),(1.07,1.96),(.90,1.68)],.26,BLACK,0,.025)

# aggressive blue eyes, pulled forward
for y in (-.25,.25):
    curve("LED",[(1.32,y,1.78),(1.40,y*1.12,1.60),(1.18,y*1.30,1.48)],.027,BLUE)
    curve("LED2",[(1.27,y*.52,1.78),(1.10,y*.72,1.58)],.016,BLUE)

# bar and mirrors
beam("Stem",(.52,0,1.92),(.52,0,2.20),.04,METAL)
beam("Handlebar",(.52,-.58,2.18),(.52,.58,2.18),.031,METAL)
for y in (-.58,.58):
    beam("MirrorStem",(.52,y,2.18),(.38,y*1.28,2.48),.016,METAL)
    ellipsoid("Mirror",(.36,y*1.31,2.53),(.12,.18,.065),BLACK)

# tail, shock, motor
curve("TailLED",[(-1.52,-.31,1.46),(-1.72,-.24,1.56),(-1.75,0,1.61),(-1.72,.24,1.56),(-1.52,.31,1.46)],.025,RED)
spring("RearShock",(-1.28,-.27,1.07),.54,.055)
bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=.25,depth=.48,location=(-1.30,-.36,.66),rotation=(math.pi/2,0,0))
o=bpy.context.object;o.data.materials.append(DARK);smooth(o)
prism("MotorCover",[(-1.33,.52),(-.84,.53),(-.72,.69),(-.82,.84),(-1.30,.82)],.32,BLACK,-.37,.04)

# floor + skyline
GROUND=mat("Ground",(.025,.035,.05,1),.55,.18)
bpy.ops.mesh.primitive_plane_add(size=30,location=(0,0,0));bpy.context.object.data.materials.append(GROUND)
BUILD=mat("Building",(.02,.026,.045,1),.2,.35);WIN=mat("Window",(.03,.015,.005,1),0,.3,(1,.22,.03,1),2)
for x,y,h,w in [(-4.3,5.8,3.4,.55),(-3.2,5.5,2.5,.7),(-2.1,5.9,4.0,.6),(-.9,5.4,2.8,.7),(.5,5.9,4.8,.55),(1.7,5.5,3.2,.65),(2.9,5.9,4.2,.6),(4.1,5.4,2.7,.8)]:
    cube("Tower",(x,y,h/2),(w,.42,h/2),BUILD,bev=.035)
    for z in (.7,1.3,1.9,2.5,3.1,3.7):
        if z<h-.15:cube("Win",(x,y-.43,z),(w*.62,.012,.028),WIN,bev=.004)

for loc,e,size,col in [((4.5,-4.5,6.4),1600,5,(1,.38,.16)),((-1.7,3.3,5.1),900,4.4,(.12,.30,1)),((-4,-2,3.0),1050,3.2,(.08,.35,1))]:
    bpy.ops.object.light_add(type="AREA",location=loc);l=bpy.context.object;l.data.energy=e;l.data.size=size;l.data.color=col

world=bpy.context.scene.world or bpy.data.worlds.new("World");bpy.context.scene.world=world;world.use_nodes=True
nodes=world.node_tree.nodes;links=world.node_tree.links
for n in list(nodes):nodes.remove(n)
ow=nodes.new("ShaderNodeOutputWorld");bg=nodes.new("ShaderNodeBackground");sky=nodes.new("ShaderNodeTexSky")
sky.sky_type="MULTIPLE_SCATTERING";sky.sun_elevation=math.radians(7);sky.sun_rotation=math.radians(205);bg.inputs["Strength"].default_value=.42
links.new(sky.outputs["Color"],bg.inputs["Color"]);links.new(bg.outputs["Background"],ow.inputs["Surface"])

bpy.ops.object.camera_add(location=(6.1,-5.7,3.05));cam=bpy.context.object
scene=bpy.context.scene;scene.camera=cam;scene.render.engine="BLENDER_EEVEE";scene.render.resolution_x=960;scene.render.resolution_y=540;scene.render.resolution_percentage=100
scene.render.image_settings.file_format="PNG";scene.view_settings.look="AgX - Medium High Contrast"
def aim(loc,target,lens):
    cam.location=loc;cam.data.lens=lens;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat("-Z","Y").to_euler();bpy.context.view_layer.update()
def render(name,loc,target,lens):
    aim(loc,target,lens);p=OUT/name;scene.render.filepath=str(p);bpy.ops.render.render(write_still=True);return p.stat().st_size

blend=OUT/"ORBITA_HIFI_CLOUD.blend";bpy.ops.wm.save_as_mainfile(filepath=str(blend))
sizes={}
sizes["hero"]=render("orbita_hifi_hero.png",(6.1,-5.75,3.05),(0,0,1.18),62)
sizes["front"]=render("orbita_hifi_front.png",(7.15,0,2.30),(.25,0,1.18),68)
sizes["side"]=render("orbita_hifi_side.png",(0,-8.1,2.12),(-.08,0,1.16),72)
manifest={"status":"PASS","blender_version":".".join(map(str,bpy.app.version)),"blend_bytes":blend.stat().st_size,"renders":sizes,"objects":len(scene.objects),"elapsed_seconds":round(time.time()-T0,3),"version":"V4 angular-panel"}
(OUT/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
print("CWS_ORBITA_HIFI_PASS");print(json.dumps(manifest,indent=2))
