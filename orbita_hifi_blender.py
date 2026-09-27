import bpy, math, json, time
from pathlib import Path
from mathutils import Vector

OUT=Path("evidence"); OUT.mkdir(exist_ok=True)
START=time.time()

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)

def mat(name, color, metallic=0.0, rough=0.4, emission=None, strength=0.0):
    m=bpy.data.materials.new(name)
    m.use_nodes=True
    bs=m.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value=color
    bs.inputs["Metallic"].default_value=metallic
    bs.inputs["Roughness"].default_value=rough
    if emission:
        bs.inputs["Emission Color"].default_value=emission
        bs.inputs["Emission Strength"].default_value=strength
    return m

SILVER=mat("Silver",(0.42,0.48,0.56,1),0.82,0.18)
SILVER2=mat("Silver2",(0.68,0.72,0.78,1),0.72,0.22)
BLACK=mat("Black",(0.015,0.02,0.028,1),0.22,0.20)
DARK=mat("Dark",(0.035,0.045,0.06,1),0.55,0.25)
RUBBER=mat("Rubber",(0.008,0.009,0.012,1),0.0,0.62)
METAL=mat("Metal",(0.12,0.14,0.17,1),0.92,0.16)
BLUE=mat("BlueLED",(0.005,0.08,0.30,1),0.15,0.12,(0.02,0.48,1.0,1),12)
RED=mat("RedLED",(0.20,0.005,0.005,1),0.10,0.14,(1.0,0.01,0.01,1),9)
AMBER=mat("Amber",(0.25,0.06,0.005,1),0.05,0.18,(1.0,0.18,0.01,1),7)
SCREEN=mat("Screen",(0.002,0.018,0.03,1),0.0,0.16,(0.0,0.25,0.8,1),4)
WHITE=mat("White",(0.9,0.92,0.96,1),0.1,0.25)
SEAT=mat("Seat",(0.015,0.018,0.023,1),0.0,0.62)

def smooth(obj):
    if hasattr(obj.data,"polygons"):
        for p in obj.data.polygons: p.use_smooth=True

def bevel(obj,w=0.04,seg=3):
    b=obj.modifiers.new("Bevel","BEVEL"); b.width=w; b.segments=seg
    return obj

def cube(name,loc,scale,material,rot=(0,0,0),bev=0.04):
    bpy.ops.mesh.primitive_cube_add(location=loc,rotation=rot)
    o=bpy.context.object; o.name=name; o.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if material:o.data.materials.append(material)
    if bev: bevel(o,bev,3)
    return o

def prism(name, pts, width, material, y=0.0, bevel_w=0.03):
    verts=[]
    hw=width/2
    for x,z in pts: verts.append((x,y-hw,z))
    for x,z in pts: verts.append((x,y+hw,z))
    n=len(pts); faces=[]
    faces.append(tuple(range(n)))
    faces.append(tuple(range(n,2*n)))
    for i in range(n):
        j=(i+1)%n
        faces.append((i,j,n+j,n+i))
    me=bpy.data.meshes.new(name+"Mesh"); me.from_pydata(verts,[],faces); me.update()
    o=bpy.data.objects.new(name,me); bpy.context.collection.objects.link(o)
    o.data.materials.append(material)
    if bevel_w: bevel(o,bevel_w,2)
    return o

def beam(name,a,b,r,material,verts=20):
    a=Vector(a); b=Vector(b); d=b-a
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=r,depth=d.length,location=(a+b)*0.5)
    o=bpy.context.object; o.name=name; o.rotation_euler=d.to_track_quat("Z","Y").to_euler(); o.data.materials.append(material)
    return o

def curve_line(name, pts, radius, material):
    cu=bpy.data.curves.new(name,"CURVE"); cu.dimensions="3D"; cu.bevel_depth=radius; cu.bevel_resolution=4
    sp=cu.splines.new("POLY"); sp.points.add(len(pts)-1)
    for p,co in zip(sp.points,pts): p.co=(*co,1)
    o=bpy.data.objects.new(name,cu); bpy.context.collection.objects.link(o); o.data.materials.append(material)
    return o

def torus(name,loc,major,minor,material):
    bpy.ops.mesh.primitive_torus_add(major_radius=major,minor_radius=minor,major_segments=64,minor_segments=20,location=loc,rotation=(math.pi/2,0,0))
    o=bpy.context.object; o.name=name; o.data.materials.append(material); smooth(o); return o

def wheel(name,loc):
    torus(name+"_Tire",loc,0.36,0.13,RUBBER)
    bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=0.315,depth=0.12,location=loc,rotation=(math.pi/2,0,0))
    rim=bpy.context.object; rim.name=name+"_Rim"; rim.data.materials.append(METAL); bevel(rim,0.015,2)
    bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=0.19,depth=0.14,location=loc,rotation=(math.pi/2,0,0))
    hub=bpy.context.object; hub.data.materials.append(BLACK)
    for k in range(6):
        ang=2*math.pi*k/6
        x,z=loc[0]+0.23*math.cos(ang),loc[2]+0.23*math.sin(ang)
        beam(name+f"_Spoke{k}",(loc[0],loc[1]-0.065,loc[2]),(x,loc[1]-0.065,z),0.026,SILVER2,12)
    return rim

def spring(name,loc,height=0.62,radius=0.09):
    pts=[]
    turns=8
    for i in range(90):
        t=i/(89)*turns*2*math.pi
        z=loc[2]-height/2+height*i/89
        pts.append((loc[0]+radius*math.cos(t),loc[1]+radius*math.sin(t),z))
    curve_line(name,pts,0.012,METAL)
    beam(name+"_core",(loc[0],loc[1],loc[2]-height/2),(loc[0],loc[1],loc[2]+height/2),0.025,DARK)

def text_obj(txt,loc,size,material,rot=(math.pi/2,0,0),align="CENTER"):
    cu=bpy.data.curves.new("Text","FONT"); cu.body=txt; cu.align_x=align; cu.size=size; cu.extrude=0.004
    o=bpy.data.objects.new("Text_"+txt,cu); bpy.context.collection.objects.link(o); o.location=loc; o.rotation_euler=rot; o.data.materials.append(material)
    return o

# ---- Vehicle proportions ----
FX=1.48; FY=0.72; FZ=0.52; RX=-1.55; RZ=0.55
wheel("FrontL",(FX,FY,FZ)); wheel("FrontR",(FX,-FY,FZ)); wheel("Rear",(RX,0,RZ))

# fenders / wheel shoulders
for y in (FY,-FY):
    cube("FrontFender",(1.42,y,0.92),(0.42,0.17,0.10),SILVER2,rot=(0,0.05,0),bev=0.09)
    cube("WheelBrow",(1.22,y,1.02),(0.27,0.20,0.11),SILVER,rot=(0,-0.20,0),bev=0.08)

# lower chassis and step-through
prism("LowerChassis",[(-1.75,0.45),(-1.38,0.35),(0.72,0.38),(1.02,0.62),(0.78,0.86),(-0.70,0.86),(-1.42,0.72)],0.78,DARK,0,0.07)
prism("LowerSilver",[(-1.36,0.48),(-0.85,0.46),(0.55,0.49),(0.76,0.62),(0.48,0.70),(-0.82,0.68)],0.86,SILVER2,0,0.045)
cube("Footboard",(-0.12,0,0.73),(0.78,0.38,0.07),BLACK,bev=0.045)

# front central mass / angular cheeks
prism("FrontCore",[(0.35,0.80),(0.98,0.93),(1.25,1.28),(1.17,1.78),(0.86,2.10),(0.38,1.92),(0.10,1.38)],0.54,BLACK,0,0.06)
for y,sgn in ((-0.38,-1),(0.38,1)):
    prism("FrontSilverCheek",[(0.38,0.95),(0.96,1.02),(1.22,1.35),(1.10,1.82),(0.68,1.94),(0.34,1.57)],0.26,SILVER2,y,0.045)
    cube("LowerCheek",(0.98,y,1.08),(0.28,0.12,0.16),SILVER,rot=(0,-0.18,0),bev=0.05)

# windscreen + top cowl
prism("Windscreen",[(0.43,1.82),(0.70,2.19),(0.96,2.22),(1.08,1.95),(0.80,1.84)],0.42,BLACK,0,0.025)
cube("TopCowl",(0.73,0,2.02),(0.30,0.28,0.10),DARK,rot=(0,0.15,0),bev=0.055)

# rear body / side pods
prism("RearBody",[(-1.62,0.72),(-1.38,1.21),(-0.96,1.52),(-0.18,1.55),(0.18,1.28),(-0.02,0.94),(-0.82,0.82)],0.72,BLACK,0,0.08)
for y in (-0.39,0.39):
    prism("RearSilverPanel",[(-1.52,0.88),(-1.29,1.26),(-0.94,1.43),(-0.22,1.45),(0.03,1.22),(-0.14,1.02),(-0.92,0.94)],0.18,SILVER2,y,0.05)
    cube("BlueSideBlade",(-0.40,y,1.08),(0.42,0.035,0.035),BLUE,rot=(0,-0.30,0),bev=0.018)

# seat
cube("SeatBase",(-0.78,0,1.50),(0.75,0.40,0.12),SEAT,rot=(0,-0.05,0),bev=0.14)
cube("SeatRear",(-1.28,0,1.58),(0.35,0.38,0.12),SEAT,rot=(0,0.03,0),bev=0.12)
cube("RearGrab",(-1.53,0,1.72),(0.30,0.34,0.045),SILVER2,rot=(0,0.08,0),bev=0.05)

# headlights as bright V-like strokes, close to front plane
for y,sgn in ((-0.30,-1),(0.30,1)):
    curve_line("HeadLED",[(1.225,y,1.73),(1.29,y*1.18,1.55),(1.08,y*1.30,1.48)],0.026,BLUE)
    curve_line("HeadLED2",[(1.21,y*0.62,1.73),(1.04,y*0.70,1.57)],0.018,BLUE)
    cube("AmberMarker",(1.31,y*1.72,1.05),(0.025,0.026,0.18),AMBER,bev=0.018)

# tail light
curve_line("TailLED",[(-1.58,-0.31,1.43),(-1.74,-0.25,1.53),(-1.73,-0.04,1.58),(-1.73,0.04,1.58),(-1.74,0.25,1.53),(-1.58,0.31,1.43)],0.025,RED)

# front suspension + A arms
for y in (-FY,FY):
    spring("FrontSpring",(1.08,y*0.92,1.18),0.60,0.075)
    beam("UpperArm",(1.12,y,0.76),(0.64,y*0.55,1.22),0.032,METAL)
    beam("LowerArm",(1.16,y,0.60),(0.56,y*0.58,0.78),0.038,METAL)
    beam("HubLink",(FX,y,FZ),(1.12,y,0.76),0.040,METAL)

# rear shock
spring("RearShock",(-1.30,-0.28,1.02),0.58,0.065)

# drivetrain housing
bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=0.25,depth=0.48,location=(-1.33,-0.37,0.64),rotation=(math.pi/2,0,0))
motor=bpy.context.object; motor.name="MotorHousing"; motor.data.materials.append(DARK); bevel(motor,0.03,2)
cube("MotorCover",(-1.08,-0.38,0.68),(0.34,0.17,0.18),BLACK,rot=(0,-0.05,0),bev=0.07)

# handlebar/stem/mirrors
beam("Stem",(0.55,0,1.78),(0.55,0,2.17),0.045,METAL)
beam("Handlebar",(0.58,-0.58,2.16),(0.58,0.58,2.16),0.035,METAL)
for y in (-0.58,0.58):
    beam("MirrorStem",(0.58,y,2.16),(0.42,y*1.28,2.52),0.018,METAL)
    cube("Mirror",(0.40,y*1.32,2.56),(0.11,0.16,0.065),BLACK,rot=(0.1,0.25*sgn if 'sgn' in globals() else 0,0.08*sgn if 'sgn' in globals() else 0),bev=0.04)

# cockpit display
cube("Dash",(0.34,0,1.96),(0.08,0.27,0.17),BLACK,rot=(0,-0.12,0),bev=0.05)
cube("DashScreen",(0.245,-0.005,1.98),(0.012,0.22,0.12),SCREEN,rot=(0,-0.12,0),bev=0.02)

# branding
text_obj("ORBITA",(-0.72,-0.505,1.27),0.18,WHITE,(math.pi/2,0,math.pi/2))
text_obj("SPORT",(-0.92,-0.515,1.12),0.12,BLUE,(math.pi/2,0,math.pi/2))

# front badge
text_obj("A",(1.31,-0.01,1.92),0.14,WHITE,(math.pi/2,0,math.pi/2))

# floor
ground=mat("Ground",(0.025,0.035,0.05,1),0.55,0.17)
bpy.ops.mesh.primitive_plane_add(size=30,location=(0,0,0)); bpy.context.object.data.materials.append(ground)

# simple skyline behind vehicle
building_mat=mat("Building",(0.018,0.025,0.045,1),0.2,0.35)
window_mat=mat("Window",(0.05,0.03,0.01,1),0,0.3,(1.0,0.26,0.04,1),1.8)
for i,(x,y,h,w) in enumerate([
    (-4.2,5.6,4.0,0.55),(-3.2,5.3,2.8,0.7),(-2.2,5.7,3.6,0.6),(-1.0,5.2,2.4,0.75),
    (0.4,5.8,4.8,0.6),(1.6,5.5,3.1,0.75),(2.8,5.9,4.2,0.65),(4.0,5.4,2.6,0.8)
]):
    cube("Tower"+str(i),(x,y,h/2),(w,0.45,h/2),building_mat,bev=0.04)
    for z in [0.7,1.3,1.9,2.5,3.1]:
        if z<h-0.2:
            cube("Win",(x,y-0.47,z),(w*0.65,0.015,0.035),window_mat,bev=0.005)

# lighting
bpy.ops.object.light_add(type="AREA",location=(4.5,-4.5,6.5)); key=bpy.context.object; key.data.energy=1450; key.data.shape="DISK"; key.data.size=5.0
key.data.color=(1.0,0.42,0.20)
bpy.ops.object.light_add(type="AREA",location=(-1.5,3.0,5.0)); fill=bpy.context.object; fill.data.energy=900; fill.data.size=4.5; fill.data.color=(0.14,0.35,1.0)
bpy.ops.object.light_add(type="AREA",location=(-4,-2,2.5)); rim=bpy.context.object; rim.data.energy=1100; rim.data.size=3.0; rim.data.color=(0.1,0.4,1.0)

# world sky
world=bpy.context.scene.world or bpy.data.worlds.new("World"); bpy.context.scene.world=world; world.use_nodes=True
nodes=world.node_tree.nodes; links=world.node_tree.links
for n in list(nodes): nodes.remove(n)
out=nodes.new("ShaderNodeOutputWorld"); bg=nodes.new("ShaderNodeBackground"); sky=nodes.new("ShaderNodeTexSky")
sky.sky_type="NISHITA"; sky.sun_elevation=math.radians(6); sky.sun_rotation=math.radians(205); sky.altitude=0.2; sky.air_density=1.2
bg.inputs["Strength"].default_value=0.45
links.new(sky.outputs["Color"],bg.inputs["Color"]); links.new(bg.outputs["Background"],out.inputs["Surface"])

# camera
bpy.ops.object.camera_add(location=(6.7,-6.4,3.4)); cam=bpy.context.object
cam.data.lens=58
scene=bpy.context.scene; scene.camera=cam
scene.render.engine="BLENDER_EEVEE"
scene.render.resolution_x=960; scene.render.resolution_y=540; scene.render.resolution_percentage=100
scene.render.image_settings.file_format="PNG"
scene.render.film_transparent=False
scene.render.resolution_percentage=100
scene.view_settings.look="AgX - Medium High Contrast"

def aim(loc,target=(0,0,1.15),lens=58):
    cam.location=loc; cam.data.lens=lens
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat("-Z","Y").to_euler()
    bpy.context.view_layer.update()

def render(name,loc,target,lens):
    aim(loc,target,lens)
    p=OUT/name
    scene.render.filepath=str(p)
    bpy.ops.render.render(write_still=True)
    return p.stat().st_size

# save model before rendering
blend=OUT/"ORBITA_HIFI_CLOUD.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(blend))

sizes={}
sizes["hero"]=render("orbita_hifi_hero.png",(6.5,-6.2,3.25),(0.0,0.0,1.15),58)
sizes["front"]=render("orbita_hifi_front.png",(7.4,0.0,2.35),(0.25,0,1.15),62)
sizes["side"]=render("orbita_hifi_side.png",(0.1,-8.2,2.2),(-0.15,0,1.15),68)

manifest={
    "status":"PASS",
    "blender_version":".".join(map(str,bpy.app.version)),
    "blend_bytes":blend.stat().st_size,
    "renders":sizes,
    "objects":len(scene.objects),
    "elapsed_seconds":round(time.time()-START,3),
    "design_target":"ORBITA SPORT generated concept reference",
    "notes":"Procedural Blender reconstruction: 3-wheel geometry, layered body panels, emissive LEDs, suspension, mirrors, cockpit, branding."
}
(OUT/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
print("CWS_ORBITA_HIFI_PASS")
print(json.dumps(manifest,indent=2))
