from __future__ import annotations
import bpy, math, json, time
from pathlib import Path
from mathutils import Vector

OUT=Path("v6_evidence"); OUT.mkdir(exist_ok=True)
T0=time.time()
bpy.ops.wm.read_factory_settings(use_empty=True)

# ---------- Materials ----------
def mat(name,c,metal=0.0,rough=.35,emit=None,strength=0.0):
    m=bpy.data.materials.new(name); m.use_nodes=True
    bs=m.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value=c
    bs.inputs["Metallic"].default_value=metal
    bs.inputs["Roughness"].default_value=rough
    if emit:
        bs.inputs["Emission Color"].default_value=emit
        bs.inputs["Emission Strength"].default_value=strength
    return m
SILVER=mat("ORBITA Silver",(.34,.40,.49,1),.86,.18)
SILVER_HI=mat("ORBITA Silver Hi",(.54,.60,.68,1),.76,.19)
BLACK=mat("ORBITA Black",(.010,.014,.022,1),.35,.18)
DARK=mat("ORBITA Graphite",(.025,.035,.052,1),.58,.22)
RUBBER=mat("Tire",(.006,.007,.009,1),0,.66)
METAL=mat("Metal",(.16,.18,.22,1),.92,.14)
SEAT=mat("Seat",(.012,.014,.019,1),0,.58)
GLASS=mat("Windscreen",(.015,.035,.060,1),.20,.08)
BLUE=mat("Blue LED",(.0,.05,.22,1),.08,.08,(0.0,.42,1.0,1),9)
RED=mat("Red LED",(.18,.002,.002,1),.05,.10,(1.0,.01,.01,1),10)
AMBER=mat("Amber",(.18,.035,.002,1),.05,.12,(1.0,.16,.01,1),7)
WHITE=mat("White",(.92,.94,.98,1),.2,.22)

# ---------- Geometry helpers ----------
def smooth(o):
    if hasattr(o.data,"polygons"):
        for p in o.data.polygons: p.use_smooth=True
def bevel(o,w=.025,segments=3):
    b=o.modifiers.new("EdgeSoft","BEVEL"); b.width=w; b.segments=segments
    return o
def box(name,loc,scale,material,rot=(0,0,0),bev=.035):
    bpy.ops.mesh.primitive_cube_add(location=loc,rotation=rot)
    o=bpy.context.object; o.name=name; o.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(material)
    if bev: bevel(o,bev,3)
    return o
def ellipsoid(name,loc,scale,material,rot=(0,0,0)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48,ring_count=24,location=loc,rotation=rot)
    o=bpy.context.object; o.name=name; o.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(material); smooth(o)
    return o
def side_prism(name,profile_yz,x_center,thickness,material,bev=.025):
    verts=[]; h=thickness/2
    for x in (x_center-h,x_center+h):
        for y,z in profile_yz: verts.append((x,y,z))
    n=len(profile_yz)
    faces=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]
    for i in range(n):
        j=(i+1)%n
        faces.append((i,j,n+j,n+i))
    me=bpy.data.meshes.new(name+"Mesh"); me.from_pydata(verts,[],faces); me.update()
    o=bpy.data.objects.new(name,me); bpy.context.collection.objects.link(o); o.data.materials.append(material)
    if bev: bevel(o,bev,3)
    return o
def front_prism(name,profile_xz,y_center,depth,material,bev=.02):
    verts=[]; h=depth/2
    for y in (y_center-h,y_center+h):
        for x,z in profile_xz: verts.append((x,y,z))
    n=len(profile_xz)
    faces=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]
    for i in range(n):
        j=(i+1)%n
        faces.append((i,j,n+j,n+i))
    me=bpy.data.meshes.new(name+"Mesh"); me.from_pydata(verts,[],faces); me.update()
    o=bpy.data.objects.new(name,me); bpy.context.collection.objects.link(o); o.data.materials.append(material)
    if bev: bevel(o,bev,3)
    return o
def beam(name,a,b,r,material,verts=20):
    a=Vector(a); b=Vector(b); d=b-a
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=r,depth=d.length,location=(a+b)*.5)
    o=bpy.context.object; o.name=name; o.rotation_euler=d.to_track_quat("Z","Y").to_euler()
    o.data.materials.append(material); smooth(o); return o
def curve(name,pts,r,material):
    cu=bpy.data.curves.new(name,"CURVE"); cu.dimensions="3D"; cu.bevel_depth=r; cu.bevel_resolution=5
    sp=cu.splines.new("POLY"); sp.points.add(len(pts)-1)
    for p,co in zip(sp.points,pts): p.co=(*co,1)
    o=bpy.data.objects.new(name,cu); bpy.context.collection.objects.link(o); o.data.materials.append(material)
    return o
def wheel(name,loc,r=.47,width=.23):
    # axle along X
    bpy.ops.mesh.primitive_torus_add(major_radius=r*.72,minor_radius=r*.28,major_segments=64,minor_segments=20,location=loc,rotation=(0,math.pi/2,0))
    tire=bpy.context.object; tire.name=name+"_Tire"; tire.data.materials.append(RUBBER); smooth(tire)
    bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=r*.58,depth=width,location=loc,rotation=(0,math.pi/2,0))
    rim=bpy.context.object; rim.name=name+"_Rim"; rim.data.materials.append(BLACK); smooth(rim)
    bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=r*.16,depth=width*1.08,location=loc,rotation=(0,math.pi/2,0))
    hub=bpy.context.object; hub.name=name+"_Hub"; hub.data.materials.append(METAL); smooth(hub)
    for k in range(6):
        a=2*math.pi*k/6
        p=(loc[0],loc[1]+r*.39*math.cos(a),loc[2]+r*.39*math.sin(a))
        beam(name+f"_Spoke{k}",loc,p,.020,SILVER_HI,12)
def arc_fender(name,x,cy,cz,r_outer=.58,r_inner=.47,width=.22,a0=20,a1=160,material=SILVER_HI,steps=28):
    verts=[]; faces=[]; h=width/2
    # two x sides, two radii, samples around wheel in YZ plane
    for xx in (x-h,x+h):
        for r in (r_outer,r_inner):
            for i in range(steps+1):
                a=math.radians(a0+(a1-a0)*i/steps)
                verts.append((xx,cy+r*math.cos(a),cz+r*math.sin(a)))
    N=steps+1
    def I(s,rr,i): return s*2*N+rr*N+i
    for i in range(steps):
        faces += [
            (I(0,0,i),I(0,0,i+1),I(1,0,i+1),I(1,0,i)),
            (I(0,1,i+1),I(0,1,i),I(1,1,i),I(1,1,i+1)),
            (I(0,0,i),I(0,1,i),I(0,1,i+1),I(0,0,i+1)),
            (I(1,0,i+1),I(1,1,i+1),I(1,1,i),I(1,0,i)),
        ]
    faces += [
        (I(0,0,0),I(1,0,0),I(1,1,0),I(0,1,0)),
        (I(0,0,steps),I(0,1,steps),I(1,1,steps),I(1,0,steps)),
    ]
    me=bpy.data.meshes.new(name+"Mesh"); me.from_pydata(verts,[],faces); me.update()
    o=bpy.data.objects.new(name,me); bpy.context.collection.objects.link(o); o.data.materials.append(material); bevel(o,.018,2)
    return o
def spring(name,loc,h=.58,r=.055):
    pts=[]
    for i in range(90):
        t=i/89*8*2*math.pi
        pts.append((loc[0]+r*math.cos(t),loc[1]+r*math.sin(t),loc[2]-h/2+h*i/89))
    curve(name,pts,.010,METAL)
    beam(name+"_Core",(loc[0],loc[1],loc[2]-h/2),(loc[0],loc[1],loc[2]+h/2),.024,DARK)
def text_obj(txt,loc,size,material,rot=(math.pi/2,0,0)):
    cu=bpy.data.curves.new("Text","FONT"); cu.body=txt; cu.align_x="CENTER"; cu.size=size; cu.extrude=.006
    o=bpy.data.objects.new("Text_"+txt,cu); bpy.context.collection.objects.link(o)
    o.location=loc; o.rotation_euler=rot; o.data.materials.append(material); return o

# ---------- Vehicle hard points ----------
FX=.64; FY=-1.32; FZ=.51; RY=1.30; RZ=.54
wheel("FrontWheel_L",(-FX,FY,FZ),.48,.24)
wheel("FrontWheel_R",( FX,FY,FZ),.48,.24)
wheel("RearWheel",(0,RY,RZ),.50,.28)

# Front fenders and suspension
for x in (-FX,FX):
    arc_fender("FrontFender",x,FY,FZ,.59,.47,.22,18,162,SILVER_HI)
    spring("FrontSpring",(x*.92,-1.03,1.15),.61,.052)
    beam("UpperArm",(x,FY,FZ+.10),(x*.55,-.73,1.14),.030,METAL)
    beam("LowerArm",(x,FY,FZ-.05),(x*.55,-.68,.76),.036,METAL)
    beam("HubLink",(x,FY,FZ),(x*.92,-1.05,.84),.038,METAL)
    box("AmberMarker",(x,-1.61,.98),(.025,.025,.14),AMBER,bev=.012)

# Main black body, split for scooter step-through
front_core=[(-1.43,.70),(-1.42,1.46),(-1.10,1.96),(-.68,2.14),(-.42,1.96),(-.25,1.44),(-.28,.92),(-.55,.72)]
rear_core=[(-.10,.72),(0.05,1.15),(.28,1.52),(1.10,1.67),(1.48,1.53),(1.58,1.26),(1.50,.88),(1.22,.72),(.28,.66)]
side_prism("FrontCore",front_core,0,.66,BLACK,.055)
side_prism("RearCore",rear_core,0,.74,BLACK,.060)
box("Floorboard",(0,.08,.70),(.43,.64,.075),DARK,bev=.045)

# Silver side armor panels
front_panel=[(-1.32,.91),(-1.25,1.48),(-.99,1.84),(-.70,1.96),(-.48,1.76),(-.36,1.30),(-.42,.98),(-.72,.86)]
rear_panel=[(.08,.88),(.23,1.25),(.46,1.48),(1.12,1.55),(1.43,1.42),(1.38,1.04),(1.13,.88),(.46,.79)]
lower_panel=[(-.58,.71),(-.22,.78),(.40,.78),(1.12,.82),(1.32,.94),(.75,.93),(.05,.88),(-.46,.83)]
for x in (-.39,.39):
    side_prism("FrontSilverPanel",front_panel,x,.13,SILVER_HI,.035)
    side_prism("RearSilverPanel",rear_panel,x,.13,SILVER,.035)
    side_prism("LowerSilverBlade",lower_panel,x*.98,.10,SILVER_HI,.028)
    # dark triangular insert + blue blade
    side_prism("RearDarkInsert",[(.34,1.04),(.62,1.35),(1.24,1.38),(1.12,1.02),(.64,.91)],x*1.04,.06,DARK,.020)
    curve("SideBlueLED",[(x*1.08,.28,1.14),(x*1.08,.58,1.04),(x*1.08,.84,.98)],.016,BLUE)

# Front face: black central mask + silver angular cheeks
front_mask=[(-.48,.90),(-.56,1.35),(-.43,1.80),(-.22,2.06),(0,2.13),(.22,2.06),(.43,1.80),(.56,1.35),(.48,.90),(0,.82)]
front_prism("FrontMask",front_mask,-1.39,.22,DARK,.035)
left_cheek=[(-.60,1.04),(-.56,1.47),(-.44,1.80),(-.25,1.91),(-.20,1.73),(-.30,1.39),(-.41,1.08)]
right_cheek=[(-x,z) for x,z in reversed(left_cheek)]
front_prism("FrontCheek_L",left_cheek,-1.45,.12,SILVER_HI,.022)
front_prism("FrontCheek_R",right_cheek,-1.45,.12,SILVER_HI,.022)

front_prism("LampInsert_L",[(-.53,1.20),(-.49,1.66),(-.36,1.79),(-.22,1.70),(-.28,1.42),(-.39,1.19)],-1.515,.055,BLACK,.012)
front_prism("LampInsert_R",[(.53,1.20),(.49,1.66),(.36,1.79),(.22,1.70),(.28,1.42),(.39,1.19)],-1.515,.055,BLACK,.012)

# Blue V-shaped headlight signature on the foremost surface
curve("HeadLED_L",[(-.49,-1.535,1.78),(-.38,-1.55,1.56),(-.15,-1.56,1.45)],.026,BLUE)
curve("HeadLED_R",[( .49,-1.535,1.78),( .38,-1.55,1.56),( .15,-1.56,1.45)],.026,BLUE)
curve("InnerLED_L",[(-.31,-1.55,1.79),(-.14,-1.56,1.61)],.014,BLUE)
curve("InnerLED_R",[( .31,-1.55,1.79),( .14,-1.56,1.61)],.014,BLUE)

# Nose center, windscreen and cockpit
front_prism("NoseBlade",[(-.16,1.20),(-.22,1.63),(-.12,1.92),(0,2.00),(.12,1.92),(.22,1.63),(.16,1.20)],-1.51,.12,BLACK,.020)
front_prism("Windscreen",[(-.31,1.86),(-.24,2.20),(0,2.33),(.24,2.20),(.31,1.86),(0,1.78)],-.68,.10,GLASS,.035)
beam("CockpitStem",(0,-.55,1.65),(0,-.57,2.20),.044,METAL)
beam("Handlebar",(-.56,-.60,2.18),(.56,-.60,2.18),.031,METAL)
for x in (-.56,.56):
    beam("MirrorStem",(x,-.60,2.18),(x*1.38,-.58,2.48),.015,METAL)
    box("Mirror",(x*1.43,-.57,2.51),(.14,.07,.07),BLACK,rot=(0,0,math.radians(8 if x>0 else -8)),bev=.035)

# Seat and rear top
box("SeatBase",(0,.68,1.58),(.39,.78,.13),SEAT,rot=(math.radians(-2),0,0),bev=.13)
box("SeatRear",(0,1.16,1.62),(.38,.35,.14),SEAT,bev=.12)
curve("RearGrab",[(-.35,1.44,1.73),(0,1.60,1.80),(.35,1.44,1.73)],.030,SILVER_HI)

# Rear mechanics
spring("RearShock",(.30,1.12,1.05),.55,.052)
bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=.25,depth=.50,location=(0,1.13,.66),rotation=(0,math.pi/2,0))
motor=bpy.context.object; motor.name="MotorHousing"; motor.data.materials.append(DARK); smooth(motor); bevel(motor,.025,2)
box("MotorCover",(.0,.89,.66),(.31,.25,.17),BLACK,bev=.07)
curve("TailLED",[(-.34,1.57,1.49),(0,1.65,1.58),(.34,1.57,1.49)],.025,RED)
box("RearMudguard",(0,1.67,.95),(.20,.34,.045),BLACK,rot=(math.radians(22),0,0),bev=.035)

# Branding omitted in V7 geometry review to avoid mirrored typography.\n\n# ---------- Environment ----------
GROUND=mat("Ground",(.025,.032,.045,1),.38,.20)
bpy.ops.mesh.primitive_plane_add(size=24,location=(0,0,0)); bpy.context.object.data.materials.append(GROUND)
# simple skyline behind vehicle
BUILD=mat("Building",(.020,.028,.050,1),.25,.32)
WIN=mat("Window",(.04,.016,.003,1),0,.30,(1.0,.18,.03,1),1.8)
for i,(x,y,h,w) in enumerate([(-4.2,6.2,3.4,.48),(-3.2,6.0,2.5,.65),(-2.0,6.4,4.2,.55),(-.8,6.1,2.8,.65),(.5,6.5,4.8,.52),(1.7,6.0,3.2,.62),(2.9,6.4,4.1,.58),(4.1,6.0,2.7,.74)]):
    box("Tower"+str(i),(x,y,h/2),(w,.38,h/2),BUILD,bev=.03)
    for z in (.7,1.3,1.9,2.5,3.1,3.7):
        if z<h-.15: box("Win",(x,y-.39,z),(w*.58,.012,.025),WIN,bev=.003)

# warm/cool commercial lighting
for loc,e,size,col in [
    ((4.5,-4.5,6.2),1650,5.2,(1.0,.40,.16)),
    ((-3.0,2.2,5.0),950,4.0,(.12,.30,1.0)),
    ((-4.0,-1.5,3.0),850,3.0,(.08,.32,1.0)),
]:
    bpy.ops.object.light_add(type="AREA",location=loc)
    l=bpy.context.object; l.data.energy=e; l.data.size=size; l.data.color=col

world=bpy.context.scene.world or bpy.data.worlds.new("World"); bpy.context.scene.world=world; world.use_nodes=True
nodes=world.node_tree.nodes; links=world.node_tree.links
for n in list(nodes): nodes.remove(n)
ow=nodes.new("ShaderNodeOutputWorld"); bg=nodes.new("ShaderNodeBackground"); sky=nodes.new("ShaderNodeTexSky")
sky.sky_type="MULTIPLE_SCATTERING"; sky.sun_elevation=math.radians(7); sky.sun_rotation=math.radians(200)
bg.inputs["Strength"].default_value=.40; links.new(sky.outputs["Color"],bg.inputs["Color"]); links.new(bg.outputs["Background"],ow.inputs["Surface"])

# ---------- Render ----------
bpy.ops.object.camera_add(); cam=bpy.context.object
scene=bpy.context.scene; scene.camera=cam; scene.render.engine="BLENDER_EEVEE"
scene.render.resolution_x=960; scene.render.resolution_y=540; scene.render.resolution_percentage=100
scene.render.image_settings.file_format="PNG"; scene.view_settings.look="AgX - Medium High Contrast"

def aim(loc,target=(0,0,1.15),lens=62):
    cam.location=loc; cam.data.lens=lens
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat("-Z","Y").to_euler()
    bpy.context.view_layer.update()
def render(name,loc,target,lens):
    aim(loc,target,lens); p=OUT/name; scene.render.filepath=str(p); bpy.ops.render.render(write_still=True); return p.stat().st_size

blend=OUT/"ORBITA_SPORT_V6.blend"; bpy.ops.wm.save_as_mainfile(filepath=str(blend))
renders={}
renders["hero"]=render("orbita_v6_hero.png",(6.5,-7.2,3.05),(0,.02,1.13),70)
renders["front"]=render("orbita_v6_front.png",(0,-8.0,2.45),(0,-.05,1.13),72)
renders["side"]=render("orbita_v6_side.png",(-8.2,.05,2.35),(0,.08,1.10),70)
renders["rear_3q"]=render("orbita_v6_rear_3q.png",(-6.2,6.7,2.95),(0,.10,1.10),68)
manifest={
    "status":"PASS",
    "version":"ORBITA_SPORT_V7_REFINED",
    "blender_version":".".join(map(str,bpy.app.version)),
    "object_count":len(scene.objects),
    "blend_bytes":blend.stat().st_size,
    "renders":renders,
    "elapsed_seconds":round(time.time()-T0,3),
    "architecture":"3 wheels: 2 front + 1 rear",
}
(OUT/"manifest.json").write_text(json.dumps(manifest,indent=2))
print("ORBITA_V6_BLENDER_PASS")
print(json.dumps(manifest,indent=2))
