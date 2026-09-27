import bpy, math, json, time
from pathlib import Path
from mathutils import Vector

OUT=Path("evidence"); OUT.mkdir(exist_ok=True)
T0=time.time()

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)

def mat(name,c,metal=0.0,rough=0.35,emit=None,strength=0):
    m=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes=True
    bs=m.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value=c
    bs.inputs["Metallic"].default_value=metal
    bs.inputs["Roughness"].default_value=rough
    if emit:
        bs.inputs["Emission Color"].default_value=emit
        bs.inputs["Emission Strength"].default_value=strength
    return m

SILVER=mat("Silver",(0.58,0.64,0.72,1),0.82,0.16)
SILVER2=mat("Silver2",(0.82,0.85,0.9,1),0.62,0.20)
BLACK=mat("Black",(0.012,0.017,0.024,1),0.2,0.18)
DARK=mat("Dark",(0.03,0.04,0.055,1),0.55,0.22)
RUBBER=mat("Rubber",(0.008,0.009,0.012,1),0.0,0.62)
METAL=mat("Metal",(0.15,0.17,0.20,1),0.92,0.14)
BLUE=mat("BlueLED",(0.005,0.06,0.20,1),0.1,0.08,(0.02,0.55,1.0,1),14)
RED=mat("RedLED",(0.15,0.005,0.005,1),0.1,0.12,(1.0,0.01,0.01,1),11)
AMBER=mat("Amber",(0.18,0.04,0.005,1),0.05,0.12,(1.0,0.18,0.01,1),8)
SEAT=mat("Seat",(0.018,0.02,0.025,1),0,0.56)
GLASS=mat("Glass",(0.02,0.035,0.055,1),0.1,0.08)
WHITE=mat("White",(0.95,0.96,1.0,1),0.1,0.22)

def smooth(o):
    if hasattr(o.data,"polygons"):
        for p in o.data.polygons: p.use_smooth=True

def bevel(o,w=0.03,seg=3):
    m=o.modifiers.new("Bevel","BEVEL"); m.width=w; m.segments=seg
    return o

def ellipsoid(name,loc,scale,material,rot=(0,0,0),sub=2):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, location=loc, rotation=rot)
    o=bpy.context.object; o.name=name; o.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(material); smooth(o)
    if sub:
        s=o.modifiers.new("Subsurf","SUBSURF"); s.levels=sub; s.render_levels=sub
    return o

def cube(name,loc,scale,material,rot=(0,0,0),bev=0.05):
    bpy.ops.mesh.primitive_cube_add(location=loc,rotation=rot)
    o=bpy.context.object; o.name=name; o.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(material)
    bevel(o,bev,4)
    return o

def beam(name,a,b,r,material,verts=24):
    a=Vector(a); b=Vector(b); d=b-a
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=r,depth=d.length,location=(a+b)*.5)
    o=bpy.context.object; o.name=name; o.rotation_euler=d.to_track_quat("Z","Y").to_euler()
    o.data.materials.append(material); smooth(o); return o

def curve(name,pts,r,material):
    cu=bpy.data.curves.new(name,"CURVE"); cu.dimensions="3D"; cu.bevel_depth=r; cu.bevel_resolution=5
    sp=cu.splines.new("BEZIER"); sp.bezier_points.add(len(pts)-1)
    for bp,co in zip(sp.bezier_points,pts):
        bp.co=co; bp.handle_left_type="AUTO"; bp.handle_right_type="AUTO"
    o=bpy.data.objects.new(name,cu); bpy.context.collection.objects.link(o); o.data.materials.append(material)
    return o

def torus(name,loc,major,minor,material):
    bpy.ops.mesh.primitive_torus_add(major_radius=major,minor_radius=minor,major_segments=72,minor_segments=24,location=loc,rotation=(math.pi/2,0,0))
    o=bpy.context.object; o.name=name; o.data.materials.append(material); smooth(o); return o

def wheel(name,loc):
    torus(name+"_tire",loc,.36,.13,RUBBER)
    bpy.ops.mesh.primitive_cylinder_add(vertices=72,radius=.30,depth=.12,location=loc,rotation=(math.pi/2,0,0))
    rim=bpy.context.object; rim.name=name+"_rim"; rim.data.materials.append(BLACK); smooth(rim)
    bpy.ops.mesh.primitive_cylinder_add(vertices=72,radius=.12,depth=.135,location=loc,rotation=(math.pi/2,0,0))
    hub=bpy.context.object; hub.data.materials.append(METAL); smooth(hub)
    for k in range(6):
        a=2*math.pi*k/6
        p=(loc[0]+.23*math.cos(a),loc[1],loc[2]+.23*math.sin(a))
        beam(name+f"_sp{k}",loc,p,.022,SILVER2,14)

def spring(name,loc,h=.55,r=.065):
    pts=[]
    for i in range(100):
        t=i/99*8*2*math.pi
        pts.append((loc[0]+r*math.cos(t),loc[1]+r*math.sin(t),loc[2]-h/2+h*i/99))
    curve(name,pts,.010,METAL)
    beam(name+"_core",(loc[0],loc[1],loc[2]-h/2),(loc[0],loc[1],loc[2]+h/2),.025,DARK)

# proportions
FX=1.42; FY=.64; FZ=.53; RX=-1.52; RZ=.55
wheel("FrontL",(FX,FY,FZ)); wheel("FrontR",(FX,-FY,FZ)); wheel("Rear",(RX,0,RZ))

# lower platform and skirt
ellipsoid("LowerSkirt",(-.05,0,.78),(1.55,.46,.23),DARK)
ellipsoid("LowerSilver",(-.10,0,.80),(1.36,.43,.17),SILVER2)
cube("Footboard",(-.15,0,.83),(.78,.32,.055),BLACK,bev=.06)

# rear body, layered as smooth aerodynamic volumes
ellipsoid("RearMain",(-.72,0,1.30),(1.08,.48,.48),BLACK,rot=(0,.06,0))
for y in (-.28,.28):
    ellipsoid("RearSilver",(-.76,y,1.33),(.93,.20,.39),SILVER2,rot=(0,.10,0))
    ellipsoid("RearDarkBlade",(-.35,y*1.05,1.12),(.54,.10,.17),DARK,rot=(0,-.20,0))
    curve("SideLED",[(.05,y*1.05,1.24),(-.18,y*1.05,1.08),(-.42,y*1.05,1.02)],.018,BLUE)

# seat volumes
ellipsoid("SeatLong",(-.82,0,1.62),(.88,.39,.18),SEAT,rot=(0,-.06,0),sub=1)
ellipsoid("SeatRear",(-1.30,0,1.66),(.42,.37,.17),SEAT,rot=(0,.02,0),sub=1)
curve("RearGrab",[(-1.55,-.30,1.78),(-1.78,0,1.84),(-1.55,.30,1.78)],.035,SILVER2)

# front core silhouette
ellipsoid("FrontCore",(.78,0,1.47),(.72,.40,.78),BLACK,rot=(0,.05,0))
ellipsoid("Neck",(.55,0,1.92),(.46,.30,.35),DARK,rot=(0,-.05,0))
ellipsoid("Windscreen",(.60,0,2.18),(.36,.25,.28),GLASS,rot=(0,-.08,0),sub=1)

# silver layered front cheeks, slightly outside black core
for y in (-.27,.27):
    ellipsoid("FrontCheek",(.88,y,1.52),(.61,.18,.60),SILVER2,rot=(0,.06,0))
    ellipsoid("LowerCheek",(1.10,y*1.06,1.12),(.38,.19,.26),SILVER,rot=(0,-.12,0))
    ellipsoid("Brow",(1.26,y*1.28,1.00),(.36,.19,.10),SILVER2,rot=(0,-.12,0),sub=1)

# front wheel fenders as smooth flattened shells
for y in (-FY,FY):
    ellipsoid("Fender",(1.38,y,1.00),(.47,.20,.13),SILVER2,rot=(0,-.05,0),sub=1)
    spring("FrontShock",(1.05,y*.80,1.24),.62,.055)
    beam("UpperArm",(1.18,y,.73),(.64,y*.50,1.18),.030,METAL)
    beam("LowerArm",(1.18,y,.57),(.55,y*.52,.80),.036,METAL)
    beam("HubLink",(FX,y,FZ),(1.17,y,.72),.040,METAL)
    cube("AmberMarker",(1.36,y*1.05,1.10),(.018,.025,.16),AMBER,bev=.014)

# aggressive V headlights
for y in (-.23,.23):
    s=-1 if y<0 else 1
    curve("HeadLED",[(1.33,y,1.76),(1.26,y*1.12,1.57),(1.06,y*1.34,1.47)],.026,BLUE)
    curve("HeadLED_inner",[(1.24,y*.55,1.75),(1.05,y*.70,1.56)],.014,BLUE)

# central nose accent
ellipsoid("NoseBlade",(1.14,0,1.52),(.24,.15,.42),BLACK,rot=(0,-.07,0),sub=1)
curve("CenterAccent",[(1.31,0,1.82),(1.38,0,1.63),(1.28,0,1.45)],.010,WHITE)

# handlebar, mirrors and cockpit
beam("Stem",(.48,0,1.83),(.48,0,2.18),.042,METAL)
beam("Handlebar",(.50,-.57,2.17),(.50,.57,2.17),.032,METAL)
for y in (-.57,.57):
    beam("MirrorStem",(.50,y,2.17),(.36,y*1.26,2.47),.016,METAL)
    ellipsoid("Mirror",(.34,y*1.28,2.52),(.12,.18,.065),BLACK,rot=(0,.05,0),sub=1)

cube("Dash",(.28,0,2.00),(.06,.25,.14),BLACK,rot=(0,-.15,0),bev=.05)
cube("DashScreen",(.21,0,2.02),(.012,.20,.10),BLUE,rot=(0,-.15,0),bev=.015)

# tail and drivetrain
curve("TailLED",[(-1.55,-.31,1.48),(-1.74,-.24,1.56),(-1.76,0,1.60),(-1.74,.24,1.56),(-1.55,.31,1.48)],.024,RED)
spring("RearShock",(-1.28,-.27,1.08),.54,.055)
bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=.25,depth=.46,location=(-1.30,-.34,.66),rotation=(math.pi/2,0,0))
motor=bpy.context.object; motor.data.materials.append(DARK); smooth(motor)
cube("MotorCase",(-1.03,-.34,.68),(.34,.17,.17),BLACK,rot=(0,-.04,0),bev=.07)

# rear mudguard / plate
cube("RearMudguard",(-1.80,0,1.16),(.27,.28,.055),BLACK,rot=(0,.30,0),bev=.04)
cube("Plate",(-1.94,0,.96),(.18,.28,.015),BLACK,rot=(0,.12,0),bev=.025)

# ground and skyline
GROUND=mat("Ground",(0.025,.035,.05,1),.55,.18)
bpy.ops.mesh.primitive_plane_add(size=30,location=(0,0,0)); bpy.context.object.data.materials.append(GROUND)
BUILD=mat("Building",(0.02,.025,.045,1),.2,.35)
WIN=mat("Window",(.03,.015,.005,1),0,.3,(1.0,.22,.03,1),2.0)
for i,(x,y,h,w) in enumerate([(-4.3,5.8,3.4,.55),(-3.2,5.5,2.5,.7),(-2.1,5.9,4.0,.6),(-.9,5.4,2.8,.7),(.5,5.9,4.8,.55),(1.7,5.5,3.2,.65),(2.9,5.9,4.2,.6),(4.1,5.4,2.7,.8)]):
    cube("Tower",(x,y,h/2),(w,.42,h/2),BUILD,bev=.035)
    for z in (.7,1.3,1.9,2.5,3.1,3.7):
        if z<h-.15: cube("Win",(x,y-.43,z),(w*.62,.012,.028),WIN,bev=.004)

# lights
for loc,energy,size,col in [((4.5,-4.5,6.4),1550,5.0,(1.0,.38,.16)),((-1.6,3.2,5.2),900,4.5,(.12,.28,1.0)),((-4,-2,3.0),1050,3.2,(.08,.32,1.0))]:
    bpy.ops.object.light_add(type="AREA",location=loc)
    l=bpy.context.object; l.data.energy=energy; l.data.size=size; l.data.color=col

# world
world=bpy.context.scene.world or bpy.data.worlds.new("World"); bpy.context.scene.world=world; world.use_nodes=True
nodes=world.node_tree.nodes; links=world.node_tree.links
for n in list(nodes): nodes.remove(n)
out=nodes.new("ShaderNodeOutputWorld"); bg=nodes.new("ShaderNodeBackground"); sky=nodes.new("ShaderNodeTexSky")
sky.sky_type="MULTIPLE_SCATTERING"; sky.sun_elevation=math.radians(7); sky.sun_rotation=math.radians(205)
bg.inputs["Strength"].default_value=.42
links.new(sky.outputs["Color"],bg.inputs["Color"]); links.new(bg.outputs["Background"],out.inputs["Surface"])

# render
bpy.ops.object.camera_add(location=(6.2,-5.8,3.05)); cam=bpy.context.object
scene=bpy.context.scene; scene.camera=cam; scene.render.engine="BLENDER_EEVEE"
scene.render.resolution_x=960; scene.render.resolution_y=540; scene.render.resolution_percentage=100
scene.render.image_settings.file_format="PNG"; scene.view_settings.look="AgX - Medium High Contrast"

def aim(loc,target,lens):
    cam.location=loc; cam.data.lens=lens
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat("-Z","Y").to_euler()
    bpy.context.view_layer.update()

def render(name,loc,target,lens):
    aim(loc,target,lens)
    p=OUT/name; scene.render.filepath=str(p); bpy.ops.render.render(write_still=True); return p.stat().st_size

blend=OUT/"ORBITA_HIFI_CLOUD.blend"; bpy.ops.wm.save_as_mainfile(filepath=str(blend))
sizes={}
sizes["hero"]=render("orbita_hifi_hero.png",(6.15,-5.75,3.05),(-.05,0,1.20),62)
sizes["front"]=render("orbita_hifi_front.png",(7.2,0,2.35),(.20,0,1.18),68)
sizes["side"]=render("orbita_hifi_side.png",(.0,-8.0,2.10),(-.10,0,1.18),72)

manifest={"status":"PASS","blender_version":".".join(map(str,bpy.app.version)),"blend_bytes":blend.stat().st_size,"renders":sizes,"objects":len(scene.objects),"elapsed_seconds":round(time.time()-T0,3),"version":"V3 smooth-panel"}
(OUT/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
print("CWS_ORBITA_HIFI_PASS")
print(json.dumps(manifest,indent=2))
