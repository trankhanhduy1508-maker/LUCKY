import bpy, math, json, time
from pathlib import Path
from mathutils import Vector

OUT=Path("v6_evidence"); OUT.mkdir(exist_ok=True)
T0=time.time()
bpy.ops.wm.read_factory_settings(use_empty=True)

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

SILVER=mat("ORBITA Silver",(.46,.53,.62,1),.82,.19)
SILVER_HI=mat("ORBITA Silver Hi",(.69,.74,.81,1),.72,.18)
BLACK=mat("ORBITA Black",(.010,.014,.022,1),.32,.18)
DARK=mat("ORBITA Graphite",(.025,.035,.050,1),.54,.23)
RUBBER=mat("Tire",(.006,.007,.009,1),0,.66)
METAL=mat("Metal",(.16,.18,.22,1),.92,.14)
SEAT=mat("Seat",(.012,.014,.018,1),0,.56)
GLASS=mat("Glass",(.018,.035,.055,1),.18,.09)
BLUE=mat("Blue LED",(.0,.045,.18,1),.08,.08,(0,.36,1,1),7)
RED=mat("Red LED",(.16,.002,.002,1),.05,.10,(1,.01,.01,1),9)
AMBER=mat("Amber",(.16,.03,.002,1),.05,.12,(1,.15,.01,1),6)

def smooth(o):
    if hasattr(o.data,"polygons"):
        for p in o.data.polygons: p.use_smooth=True

def bevel(o,w=.025,seg=3):
    m=o.modifiers.new("Bevel","BEVEL"); m.width=w; m.segments=seg
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
    bpy.ops.mesh.primitive_torus_add(major_radius=r*.72,minor_radius=r*.28,major_segments=64,minor_segments=20,location=loc,rotation=(0,math.pi/2,0))
    tire=bpy.context.object; tire.name=name+"_Tire"; tire.data.materials.append(RUBBER); smooth(tire)
    bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=r*.58,depth=width,location=loc,rotation=(0,math.pi/2,0))
    rim=bpy.context.object; rim.name=name+"_Rim"; rim.data.materials.append(BLACK); smooth(rim)
    bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=r*.16,depth=width*1.06,location=loc,rotation=(0,math.pi/2,0))
    hub=bpy.context.object; hub.name=name+"_Hub"; hub.data.materials.append(METAL); smooth(hub)
    for k in range(6):
        a=2*math.pi*k/6
        p=(loc[0],loc[1]+r*.39*math.cos(a),loc[2]+r*.39*math.sin(a))
        beam(name+f"_Sp{k}",loc,p,.018,SILVER_HI,12)

def loft(name,stations,material):
    # station=(y,width,z_bottom,z_top), 8-point faceted cross-section
    verts=[]; rings=[]
    for y,w,zb,zt in stations:
        h=zt-zb
        ring=[
            (-w*.48,y,zt),
            (-w*.92,y,zt-h*.20),
            (-w,y,zb+h*.42),
            (-w*.66,y,zb),
            ( w*.66,y,zb),
            ( w,y,zb+h*.42),
            ( w*.92,y,zt-h*.20),
            ( w*.48,y,zt),
        ]
        rings.append(list(range(len(verts),len(verts)+8)))
        verts.extend(ring)
    faces=[]
    faces.append(tuple(reversed(rings[0])))
    faces.append(tuple(rings[-1]))
    for a,b in zip(rings[:-1],rings[1:]):
        for i in range(8):
            j=(i+1)%8
            faces.append((a[i],a[j],b[j],b[i]))
    me=bpy.data.meshes.new(name+"Mesh"); me.from_pydata(verts,[],faces); me.update()
    o=bpy.data.objects.new(name,me); bpy.context.collection.objects.link(o); o.data.materials.append(material)
    bevel(o,.045,3); smooth(o)
    return o

def side_prism(name,profile_yz,x,thickness,material,bev=.018):
    verts=[];h=thickness/2
    for xx in (x-h,x+h):
        for y,z in profile_yz: verts.append((xx,y,z))
    n=len(profile_yz); faces=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]
    for i in range(n):
        j=(i+1)%n; faces.append((i,j,n+j,n+i))
    me=bpy.data.meshes.new(name+"Mesh"); me.from_pydata(verts,[],faces); me.update()
    o=bpy.data.objects.new(name,me); bpy.context.collection.objects.link(o); o.data.materials.append(material)
    if bev: bevel(o,bev,2)
    return o

def front_prism(name,profile_xz,y,depth,material,bev=.016):
    verts=[];h=depth/2
    for yy in (y-h,y+h):
        for x,z in profile_xz: verts.append((x,yy,z))
    n=len(profile_xz); faces=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]
    for i in range(n):
        j=(i+1)%n; faces.append((i,j,n+j,n+i))
    me=bpy.data.meshes.new(name+"Mesh"); me.from_pydata(verts,[],faces); me.update()
    o=bpy.data.objects.new(name,me); bpy.context.collection.objects.link(o); o.data.materials.append(material)
    if bev: bevel(o,bev,2)
    return o

def spring(name,loc,h=.58,r=.052):
    pts=[]
    for i in range(88):
        t=i/87*8*2*math.pi
        pts.append((loc[0]+r*math.cos(t),loc[1]+r*math.sin(t),loc[2]-h/2+h*i/87))
    curve(name,pts,.009,METAL)
    beam(name+"_Core",(loc[0],loc[1],loc[2]-h/2),(loc[0],loc[1],loc[2]+h/2),.022,DARK)

# Wheels / proportions
FX=.63; FY=-1.36; FZ=.50; RY=1.38; RZ=.53
wheel("Front_L",(-FX,FY,FZ),.47,.23)
wheel("Front_R",( FX,FY,FZ),.47,.23)
wheel("Rear",(0,RY,RZ),.50,.27)

# Continuous front and rear shells
front_st=[
    (-1.28,.28,.78,1.42),
    (-1.12,.48,.76,1.72),
    (-.92,.52,.74,1.98),
    (-.72,.45,.72,2.18),
    (-.54,.33,.76,2.08),
    (-.40,.29,.78,1.78),
]
rear_st=[
    (.08,.36,.70,1.20),
    (.34,.46,.70,1.46),
    (.72,.48,.72,1.60),
    (1.08,.43,.70,1.62),
    (1.36,.34,.66,1.50),
    (1.56,.24,.62,1.28),
]
loft("FrontBody",front_st,BLACK)
loft("RearBody",rear_st,BLACK)

# Low step-through chassis
loft("LowerChassis",[(-.52,.34,.55,.80),(-.20,.38,.54,.82),(.20,.40,.54,.84),(.55,.39,.55,.86),(.82,.34,.56,.87)],DARK)

# Seat
ellipsoid("Seat",(0,.86,1.63),(.39,.78,.16),SEAT,rot=(math.radians(-2),0,0))
ellipsoid("SeatRear",(0,1.28,1.66),(.34,.34,.14),SEAT)
curve("Grab",[(-.31,1.50,1.78),(0,1.68,1.82),(.31,1.50,1.78)],.027,SILVER_HI)

# Front armor panels, thinner and following shell
front_panel=[(-1.22,.90),(-1.15,1.48),(-.95,1.84),(-.73,2.02),(-.56,1.78),(-.47,1.30),(-.54,.96),(-.78,.84)]
for x in (-.47,.47):
    side_prism("FrontPanel",front_panel,x,.065,SILVER_HI,.020)

rear_panel=[(.18,.86),(.35,1.28),(.60,1.50),(1.10,1.55),(1.39,1.42),(1.35,1.02),(1.10,.86),(.55,.78)]
for x in (-.48,.48):
    side_prism("RearPanel",rear_panel,x,.060,SILVER,.018)
    side_prism("RearDarkInsert",[(.44,.96),(.66,1.32),(1.20,1.36),(1.12,1.04),(.72,.88)],x*1.02,.035,DARK,.012)
    curve("SideLED",[(x*1.05,.38,1.12),(x*1.05,.66,1.02),(x*1.05,.88,.96)],.014,BLUE)

# Front face mask and cheeks from target front view
front_prism("FrontMask",[(-.50,1.04),(-.56,1.48),(-.43,1.84),(-.23,2.05),(0,2.12),(.23,2.05),(.43,1.84),(.56,1.48),(.50,1.04),(0,.93)],-1.30,.18,DARK,.025)
front_prism("FaceSilverL",[(-.60,1.17),(-.53,1.64),(-.39,1.91),(-.19,2.02),(-.17,1.82),(-.29,1.45),(-.42,1.16)],-1.33,.09,SILVER_HI,.015)
front_prism("FaceSilverR",[(.60,1.17),(.53,1.64),(.39,1.91),(.19,2.02),(.17,1.82),(.29,1.45),(.42,1.16)],-1.33,.09,SILVER_HI,.015)
front_prism("LampBlackL",[(-.52,1.28),(-.46,1.69),(-.33,1.78),(-.18,1.67),(-.28,1.34)],-1.385,.04,BLACK,.010)
front_prism("LampBlackR",[(.52,1.28),(.46,1.69),(.33,1.78),(.18,1.67),(.28,1.34)],-1.385,.04,BLACK,.010)
curve("LED_L",[(-.46,-1.41,1.72),(-.34,-1.42,1.52),(-.13,-1.43,1.43)],.022,BLUE)
curve("LED_R",[( .46,-1.41,1.72),( .34,-1.42,1.52),( .13,-1.43,1.43)],.022,BLUE)
curve("LED2_L",[(-.30,-1.42,1.74),(-.14,-1.43,1.58)],.012,BLUE)
curve("LED2_R",[( .30,-1.42,1.74),( .14,-1.43,1.58)],.012,BLUE)

# Nose/windscreen/handlebars
front_prism("Nose",[(-.14,1.20),(-.18,1.60),(-.10,1.91),(0,1.98),(.10,1.91),(.18,1.60),(.14,1.20)],-1.39,.06,BLACK,.012)
front_prism("Windscreen",[(-.30,1.86),(-.22,2.18),(0,2.30),(.22,2.18),(.30,1.86),(0,1.80)],-.59,.09,GLASS,.020)
beam("Stem",(0,-.54,1.72),(0,-.58,2.18),.040,METAL)
beam("Handlebar",(-.54,-.60,2.17),(.54,-.60,2.17),.029,METAL)
for x in (-.54,.54):
    beam("MirrorStem",(x,-.60,2.17),(x*1.38,-.58,2.47),.014,METAL)
    box("Mirror",(x*1.42,-.57,2.50),(.13,.065,.065),BLACK,bev=.03)

# Front suspension/fenders
for x in (-FX,FX):
    spring("FrontShock",(x*.90,-1.05,1.15),.60,.050)
    beam("UpperArm",(x,FY,FZ+.11),(x*.55,-.75,1.13),.028,METAL)
    beam("LowerArm",(x,FY,FZ-.05),(x*.55,-.70,.75),.034,METAL)
    beam("HubLink",(x,FY,FZ),(x*.90,-1.05,.84),.036,METAL)
    # fender as flattened ellipsoid cap
    ellipsoid("Fender",(x,FY,1.00),(.24,.48,.11),SILVER_HI)
    box("Amber",(x,-1.66,.97),(.022,.024,.13),AMBER,bev=.010)

# Rear mechanics / tail
spring("RearShock",(.29,1.16,1.06),.54,.050)
bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=.24,depth=.46,location=(0,1.15,.65),rotation=(0,math.pi/2,0))
motor=bpy.context.object; motor.data.materials.append(DARK); smooth(motor)
box("MotorCover",(0,.91,.66),(.30,.24,.16),BLACK,bev=.06)
curve("TailLED",[(-.31,1.58,1.48),(0,1.68,1.57),(.31,1.58,1.48)],.023,RED)
box("RearMudguard",(0,1.70,.96),(.19,.32,.045),BLACK,rot=(math.radians(22),0,0),bev=.03)

# Ground / skyline
GROUND=mat("Ground",(.022,.029,.042,1),.30,.23)
bpy.ops.mesh.primitive_plane_add(size=24,location=(0,0,0)); bpy.context.object.data.materials.append(GROUND)
BUILD=mat("Building",(.018,.025,.048,1),.2,.35)
WIN=mat("Window",(.035,.012,.003,1),0,.3,(1,.18,.03,1),1.6)
for i,(x,y,h,w) in enumerate([(-4.0,6.6,3.2,.44),(-3.1,6.4,2.4,.62),(-2.0,6.8,4.1,.54),(-.8,6.5,2.7,.62),(.5,6.9,4.7,.50),(1.7,6.4,3.1,.60),(2.9,6.8,4.0,.56),(4.0,6.4,2.6,.70)]):
    box("Tower"+str(i),(x,y,h/2),(w,.34,h/2),BUILD,bev=.025)
    for z in (.7,1.3,1.9,2.5,3.1,3.7):
        if z<h-.15: box("Win",(x,y-.35,z),(w*.56,.010,.022),WIN,bev=.002)

for loc,e,size,col in [((4.5,-4.2,6.0),1550,5.2,(1,.40,.18)),((-3,2.4,5.0),900,4.0,(.12,.28,1.0)),((-4,-1.5,3.0),780,3.0,(.08,.28,1.0))]:
    bpy.ops.object.light_add(type="AREA",location=loc)
    l=bpy.context.object; l.data.energy=e; l.data.size=size; l.data.color=col

world=bpy.context.scene.world or bpy.data.worlds.new("World"); bpy.context.scene.world=world; world.use_nodes=True
nodes=world.node_tree.nodes; links=world.node_tree.links
for n in list(nodes): nodes.remove(n)
ow=nodes.new("ShaderNodeOutputWorld"); bg=nodes.new("ShaderNodeBackground"); sky=nodes.new("ShaderNodeTexSky")
sky.sky_type="MULTIPLE_SCATTERING"; sky.sun_elevation=math.radians(7); sky.sun_rotation=math.radians(200)
bg.inputs["Strength"].default_value=.38; links.new(sky.outputs["Color"],bg.inputs["Color"]); links.new(bg.outputs["Background"],ow.inputs["Surface"])

bpy.ops.object.camera_add(); cam=bpy.context.object
scene=bpy.context.scene; scene.camera=cam; scene.render.engine="BLENDER_EEVEE"
scene.render.resolution_x=960; scene.render.resolution_y=540; scene.render.resolution_percentage=100
scene.render.image_settings.file_format="PNG"; scene.view_settings.look="AgX - Medium High Contrast"

def aim(loc,target,lens):
    cam.location=loc; cam.data.lens=lens
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat("-Z","Y").to_euler()
    bpy.context.view_layer.update()
def render(name,loc,target,lens):
    aim(loc,target,lens); p=OUT/name; scene.render.filepath=str(p); bpy.ops.render.render(write_still=True); return p.stat().st_size

blend=OUT/"ORBITA_SPORT_V8.blend"; bpy.ops.wm.save_as_mainfile(filepath=str(blend))
renders={}
renders["hero"]=render("orbita_v8_hero.png",(6.0,-7.0,2.90),(0,.05,1.12),68)
renders["front"]=render("orbita_v8_front.png",(0,-8.0,2.35),(0,-.08,1.12),72)
renders["side"]=render("orbita_v8_side.png",(-8.0,.05,2.20),(0,.08,1.08),72)
renders["rear_3q"]=render("orbita_v8_rear_3q.png",(-5.8,6.3,2.75),(0,.10,1.10),68)
manifest={"status":"PASS","version":"ORBITA_SPORT_V8_LOFTED","blender_version":".".join(map(str,bpy.app.version)),"objects":len(scene.objects),"blend_bytes":blend.stat().st_size,"renders":renders,"elapsed_seconds":round(time.time()-T0,3)}
(OUT/"manifest.json").write_text(json.dumps(manifest,indent=2))
print("ORBITA_V8_PASS")
print(json.dumps(manifest,indent=2))
