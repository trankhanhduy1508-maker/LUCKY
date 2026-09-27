import bpy, json, math
from pathlib import Path
from mathutils import Vector

ROOT=Path("hunyuan3d")
OUT=ROOT/"render"
OUT.mkdir(parents=True,exist_ok=True)

mesh_files=list(ROOT.glob("orbita_hunyuan.*"))
if not mesh_files:
    raise RuntimeError("No Hunyuan mesh found")
mesh_path=mesh_files[0]

bpy.ops.wm.read_factory_settings(use_empty=True)
ext=mesh_path.suffix.lower()
if ext in (".glb",".gltf"):
    bpy.ops.import_scene.gltf(filepath=str(mesh_path))
elif ext==".obj":
    bpy.ops.wm.obj_import(filepath=str(mesh_path))
elif ext==".ply":
    bpy.ops.wm.ply_import(filepath=str(mesh_path))
else:
    raise RuntimeError(f"Unsupported mesh: {mesh_path}")

meshes=[o for o in bpy.context.scene.objects if o.type=="MESH"]
if not meshes:
    raise RuntimeError("No mesh objects imported")

# ---- normalize AI body ----
# Hunyuan mesh coordinates from runtime evidence:
#   X = vehicle width, Y = vehicle height, Z = vehicle length.
# Blender scene below uses X=width, Y=length, Z=height.
# Rotate +90° around X so original Z -> -Y and original Y -> +Z.
root=bpy.data.objects.new("AI_Body_Root",None);bpy.context.collection.objects.link(root)
for o in meshes:
    if o.parent is None:o.parent=root
root.rotation_euler=(math.radians(90),0,0)
root.scale=(1.72,1.72,1.72)
bpy.context.view_layer.update()

# Center rotated body in X/Y and place its lowest point slightly above ground.
mins=Vector((1e9,1e9,1e9)); maxs=Vector((-1e9,-1e9,-1e9))
for o in meshes:
    for corner in o.bound_box:
        p=o.matrix_world@Vector(corner)
        mins.x=min(mins.x,p.x);mins.y=min(mins.y,p.y);mins.z=min(mins.z,p.z)
        maxs.x=max(maxs.x,p.x);maxs.y=max(maxs.y,p.y);maxs.z=max(maxs.z,p.z)
center=(mins+maxs)*.5
root.location.x += -center.x
root.location.y += -center.y
root.location.z += 0.18-mins.z
bpy.context.view_layer.update()

# ---- materials ----
def mat(name,c,metal=0.0,rough=.35,emit=None,strength=0):
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

DARK=mat("ORBITA Dark",(.012,.018,.027,1),.48,.24)
SILVER=mat("ORBITA Silver",(.54,.61,.70,1),.82,.17)
SILVER2=mat("ORBITA Silver Hi",(.82,.86,.91,1),.65,.20)
RUBBER=mat("ORBITA Tire",(.008,.009,.012,1),0,.68)
METAL=mat("ORBITA Metal",(.12,.14,.17,1),.92,.15)
BLUE=mat("ORBITA Blue LED",(.005,.06,.28,1),.1,.08,(.0,.38,1.0,1),8)
RED=mat("ORBITA Red LED",(.18,.003,.003,1),.1,.1,(1.0,.01,.01,1),8)
AMBER=mat("ORBITA Amber",(.18,.04,.003,1),.05,.12,(1.0,.16,.01,1),6)
SEAT=mat("ORBITA Seat",(.014,.017,.022,1),0,.58)

# make AI geometry a dark sculptural underbody, preserving shape
for o in meshes:
    if hasattr(o.data,"materials"):
        o.data.materials.clear()
        o.data.materials.append(DARK)

def smooth(o):
    if hasattr(o.data,"polygons"):
        for p in o.data.polygons:p.use_smooth=True

def bevel(o,w=.025,seg=3):
    b=o.modifiers.new("Bevel","BEVEL");b.width=w;b.segments=seg
    return o

def cube(name,loc,scale,material,rot=(0,0,0),bev=.035):
    bpy.ops.mesh.primitive_cube_add(location=loc,rotation=rot)
    o=bpy.context.object;o.name=name;o.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(material)
    if bev:bevel(o,bev,3)
    return o

def ellipsoid(name,loc,scale,material,rot=(0,0,0)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48,ring_count=24,location=loc,rotation=rot)
    o=bpy.context.object;o.name=name;o.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(material);smooth(o);return o

def beam(name,a,b,r,material,verts=20):
    a=Vector(a);b=Vector(b);d=b-a
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=r,depth=d.length,location=(a+b)*.5)
    o=bpy.context.object;o.name=name;o.rotation_euler=d.to_track_quat("Z","Y").to_euler()
    o.data.materials.append(material);smooth(o);return o

def curve(name,pts,r,material):
    cu=bpy.data.curves.new(name,"CURVE");cu.dimensions="3D";cu.bevel_depth=r;cu.bevel_resolution=5
    sp=cu.splines.new("POLY");sp.points.add(len(pts)-1)
    for p,co in zip(sp.points,pts):p.co=(*co,1)
    o=bpy.data.objects.new(name,cu);bpy.context.collection.objects.link(o);o.data.materials.append(material);return o

def wheel(name,loc,r=.47,width=.23):
    # Vehicle length is Y; wheel axle is X.
    bpy.ops.mesh.primitive_torus_add(
        major_radius=r*.72,minor_radius=r*.28,
        major_segments=64,minor_segments=24,
        location=loc,rotation=(0,math.pi/2,0)
    )
    tire=bpy.context.object;tire.name=name+"_Tire";tire.data.materials.append(RUBBER);smooth(tire)
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=64,radius=r*.60,depth=width,
        location=loc,rotation=(0,math.pi/2,0)
    )
    rim=bpy.context.object;rim.name=name+"_Rim";rim.data.materials.append(METAL);smooth(rim)
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=48,radius=r*.18,depth=width*1.08,
        location=loc,rotation=(0,math.pi/2,0)
    )
    hub=bpy.context.object;hub.name=name+"_Hub";hub.data.materials.append(DARK);smooth(hub)
    for k in range(6):
        a=2*math.pi*k/6
        p=(loc[0],loc[1]+r*.42*math.cos(a),loc[2]+r*.42*math.sin(a))
        beam(name+f"_Spoke{k}",loc,p,.018,SILVER2,12)

# ---- hard points: explicit 2-front / 1-rear trike ----
front_y=-1.50
rear_y=1.46
front_x=.64
wheel_z=.50
wheel("FrontWheel_L",(-front_x,front_y,wheel_z),.48,.25)
wheel("FrontWheel_R",(front_x,front_y,wheel_z),.48,.25)
wheel("RearWheel",(0,rear_y,wheel_z),.50,.28)

# Front suspension and upright links
for x in (-front_x,front_x):
    beam("FrontUpright",(x,front_y,wheel_z),(x*.84,-1.08,1.03),.034,METAL)
    beam("UpperArm",(x,front_y,wheel_z+.12),(x*.42,-.78,1.12),.030,METAL)
    beam("LowerArm",(x,front_y,wheel_z-.06),(x*.46,-.72,.73),.036,METAL)
    ellipsoid("Fender",(x,front_y-.02,1.00),(.26,.49,.12),SILVER2,rot=(0,0,0))
    cube("Amber",(x,-1.78,.99),(.025,.03,.14),AMBER,bev=.012)

# Rear mechanical housing and shock
cube("MotorHousing",(.0,1.17,.58),(.27,.42,.22),DARK,bev=.08)
beam("RearShock",(.28,1.28,.78),(.34,.82,1.28),.035,METAL)

# Silver side body panels following the AI body silhouette
for x in (-.46,.46):
    side=1 if x>0 else -1
    ellipsoid("RearSilverPanel",(x,.58,1.25),(.15,.88,.34),SILVER2,rot=(0,0,.03*side))
    ellipsoid("FrontSilverCheek",(x*.88,-.74,1.43),(.18,.64,.54),SILVER2,rot=(0,0,-.05*side))
    ellipsoid("LowerBlade",(x*.96,.03,.83),(.12,.72,.12),SILVER,rot=(0,0,-.08*side))
    curve("BlueSideBlade",[(x*1.02,.46,1.25),(x*1.04,.12,1.05),(x*1.04,-.26,.94)],.018,BLUE)

# Center black/silver nose to give the concept's angular face
cube("NoseCore",(0,-1.25,1.42),(.30,.36,.48),DARK,rot=(math.radians(7),0,0),bev=.10)
cube("NoseTop",(0,-1.10,1.91),(.28,.34,.20),DARK,rot=(math.radians(-10),0,0),bev=.08)

# V-shaped headlight signature on true front plane
curve("HeadLED_L",[(-.38,-1.66,1.70),(-.28,-1.73,1.52),(-.10,-1.76,1.43)],.027,BLUE)
curve("HeadLED_R",[(.38,-1.66,1.70),(.28,-1.73,1.52),(.10,-1.76,1.43)],.027,BLUE)
curve("InnerLED_L",[(-.24,-1.68,1.72),(-.09,-1.73,1.56)],.015,BLUE)
curve("InnerLED_R",[(.24,-1.68,1.72),(.09,-1.73,1.56)],.015,BLUE)

# Cockpit: handlebar, mirrors, windscreen and seat cap
cube("Windscreen",(0,-.78,2.07),(.28,.08,.30),DARK,rot=(math.radians(-12),0,0),bev=.06)
beam("Handlebar",(-.56,-.66,2.13),(.56,-.66,2.13),.030,METAL)
for x in (-.56,.56):
    beam("MirrorStem",(x,-.66,2.13),(x*1.32,-.64,2.46),.015,METAL)
    ellipsoid("Mirror",(x*1.36,-.64,2.50),(.16,.08,.065),DARK)
ellipsoid("SeatCap",(0,.73,1.62),(.43,.78,.16),SEAT,rot=(0,0,0))

# Tail light
curve("TailLED",[(-.34,1.73,1.47),(0,1.80,1.57),(.34,1.73,1.47)],.024,RED)

# ---- scene ----
bpy.ops.mesh.primitive_plane_add(size=20,location=(0,0,0))
g=bpy.context.object
gm=mat("Ground",(.018,.024,.035,1),.2,.25);g.data.materials.append(gm)

for loc,e,size,col in [
    ((4,-4,6),1450,5,(1,.45,.24)),
    ((-3,2,5),950,4,(.15,.32,1)),
    ((-4,-2,2.5),800,3,(.08,.28,1))
]:
    bpy.ops.object.light_add(type="AREA",location=loc)
    l=bpy.context.object;l.data.energy=e;l.data.size=size;l.data.color=col

world=bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world=world
world.color=(.018,.028,.05)

bpy.ops.object.camera_add();cam=bpy.context.object
scene=bpy.context.scene;scene.camera=cam;scene.render.engine="BLENDER_EEVEE"
scene.render.resolution_x=960;scene.render.resolution_y=540;scene.render.resolution_percentage=100
scene.render.image_settings.file_format="PNG";scene.view_settings.look="AgX - Medium High Contrast"

def aim(loc,target=(0,0,1.18),lens=62):
    cam.location=loc;cam.data.lens=lens
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat("-Z","Y").to_euler()
    bpy.context.view_layer.update()

views={
"front":((0,-6.6,2.35),(0,-.15,1.15),68),
"front_3q":((4.8,-5.7,2.85),(0,0,1.18),64),
"side_left":((-6.2,0,2.30),(0,0,1.12),68),
"rear_3q":((-4.7,5.3,2.75),(0,.1,1.15),64),
"rear":((0,6.5,2.35),(0,.15,1.12),68),
"side_right":((6.2,0,2.30),(0,0,1.12),68),
}
sizes={}
for name,(loc,target,lens) in views.items():
    aim(loc,target,lens)
    p=OUT/f"{name}.png";scene.render.filepath=str(p);bpy.ops.render.render(write_still=True);sizes[name]=p.stat().st_size

blend=ROOT/"ORBITA_HUNYUAN_BLENDER.blend";bpy.ops.wm.save_as_mainfile(filepath=str(blend))
manifest={
    "status":"PASS",
    "version":"HUNYUAN_HYBRID_V4_AXIS_FIXED",
    "blender_version":".".join(map(str,bpy.app.version)),
    "source_mesh":mesh_path.name,
    "source_mesh_bytes":mesh_path.stat().st_size,
    "mesh_objects":len(meshes),
    "blend_bytes":blend.stat().st_size,
    "explicit_wheels":3,
    "renders":sizes
}
(OUT/"manifest.json").write_text(json.dumps(manifest,indent=2))
print("ORBITA_HUNYUAN_HYBRID_PASS")
print(json.dumps(manifest,indent=2))
