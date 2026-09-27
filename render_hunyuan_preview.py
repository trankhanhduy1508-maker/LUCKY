import bpy, math, json
from pathlib import Path
from mathutils import Vector

ROOT=Path("preview")
SRC=ROOT/"orbita_hunyuan.glb"
OUT=ROOT/"preview.png"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(SRC))
meshes=[o for o in bpy.context.scene.objects if o.type=="MESH"]
if not meshes: raise RuntimeError("no mesh")

# Hunyuan axes: X width, Y height, Z length.
root=bpy.data.objects.new("ORBITA_BODY",None); bpy.context.collection.objects.link(root)
for o in meshes:
    if o.parent is None:o.parent=root
root.rotation_euler=(math.radians(90),0,0)
root.scale=(1.72,1.72,1.72)
bpy.context.view_layer.update()

mn=Vector((1e9,1e9,1e9));mx=Vector((-1e9,-1e9,-1e9))
for o in meshes:
    for c in o.bound_box:
        p=o.matrix_world@Vector(c)
        for i in range(3):
            mn[i]=min(mn[i],p[i]);mx[i]=max(mx[i],p[i])
center=(mn+mx)*.5
root.location=(-center.x,-center.y,.18-mn.z)
bpy.context.view_layer.update()

def mat(name,c,metal=0,rough=.35,emit=None,strength=0):
    m=bpy.data.materials.new(name);m.use_nodes=True
    bs=m.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value=c;bs.inputs["Metallic"].default_value=metal;bs.inputs["Roughness"].default_value=rough
    if emit:
        bs.inputs["Emission Color"].default_value=emit;bs.inputs["Emission Strength"].default_value=strength
    return m
DARK=mat("Body",(.025,.035,.05,1),.55,.20)
RUBBER=mat("Tire",(.006,.007,.009,1),0,.64)
METAL=mat("Rim",(.35,.38,.42,1),.9,.15)
BLUE=mat("LED",(.0,.06,.25,1),.1,.08,(0,.38,1,1),8)
SILVER=mat("Silver",(.68,.73,.80,1),.82,.18)

for o in meshes:
    o.data.materials.clear();o.data.materials.append(DARK)
    for p in o.data.polygons:p.use_smooth=True

def wheel(name,loc,r=.48,w=.24):
    bpy.ops.mesh.primitive_torus_add(major_radius=r*.72,minor_radius=r*.28,major_segments=48,minor_segments=16,location=loc,rotation=(0,math.pi/2,0))
    t=bpy.context.object;t.name=name+"_Tire";t.data.materials.append(RUBBER)
    bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=r*.58,depth=w,location=loc,rotation=(0,math.pi/2,0))
    q=bpy.context.object;q.name=name+"_Rim";q.data.materials.append(METAL)

def curve(name,pts,r,m):
    cu=bpy.data.curves.new(name,"CURVE");cu.dimensions="3D";cu.bevel_depth=r;cu.bevel_resolution=4
    sp=cu.splines.new("POLY");sp.points.add(len(pts)-1)
    for p,co in zip(sp.points,pts):p.co=(*co,1)
    o=bpy.data.objects.new(name,cu);bpy.context.collection.objects.link(o);o.data.materials.append(m)

# explicit trike hardpoints
wheel("FrontL",(-.64,-1.50,.50));wheel("FrontR",(.64,-1.50,.50));wheel("Rear",(0,1.46,.50),.50,.28)

# silver front cheeks + LED signature as visual anchors
for x in (-.44,.44):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,location=(x,-.70,1.38))
    o=bpy.context.object;o.scale=(.18,.58,.48);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(SILVER)
curve("LED_L",[(-.38,-1.68,1.72),(-.28,-1.75,1.53),(-.10,-1.78,1.44)],.025,BLUE)
curve("LED_R",[(.38,-1.68,1.72),(.28,-1.75,1.53),(.10,-1.78,1.44)],.025,BLUE)

bpy.ops.mesh.primitive_plane_add(size=18,location=(0,0,0))
g=bpy.context.object;g.data.materials.append(mat("Ground",(.018,.024,.035,1),.25,.25))

for loc,e,size,col in [((4,-4,6),1300,5,(1,.42,.22)),((-3,2,5),850,4,(.12,.28,1))]:
    bpy.ops.object.light_add(type="AREA",location=loc);l=bpy.context.object;l.data.energy=e;l.data.size=size;l.data.color=col

bpy.ops.object.camera_add(location=(4.8,-5.7,2.8))
cam=bpy.context.object;cam.data.lens=62;cam.rotation_euler=(Vector((0,0,1.15))-cam.location).to_track_quat("-Z","Y").to_euler()
scene=bpy.context.scene;scene.camera=cam;scene.render.engine="BLENDER_EEVEE";scene.render.resolution_x=640;scene.render.resolution_y=360;scene.render.resolution_percentage=100;scene.render.image_settings.file_format="PNG";scene.view_settings.look="AgX - Medium High Contrast";scene.render.filepath=str(OUT)
bpy.ops.render.render(write_still=True)
assert OUT.stat().st_size>0
blend=ROOT/"ORBITA_PREVIEW.blend";bpy.ops.wm.save_as_mainfile(filepath=str(blend))
print(json.dumps({"status":"PASS","png":OUT.stat().st_size,"blend":blend.stat().st_size,"blender":".".join(map(str,bpy.app.version))}))
