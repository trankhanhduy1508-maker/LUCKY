import bpy, json, math, os, time
from pathlib import Path
from mathutils import Vector

ROOT=Path("ai3d")
GLB=ROOT/"orbita_sf3d.glb"
OUT=ROOT/"render"
OUT.mkdir(parents=True,exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(GLB))

# collect imported mesh objects
meshes=[o for o in bpy.context.scene.objects if o.type=="MESH"]
if not meshes:
    raise RuntimeError("No meshes imported from GLB")

# compute world bbox
mins=Vector((1e9,1e9,1e9)); maxs=Vector((-1e9,-1e9,-1e9))
for o in meshes:
    for c in o.bound_box:
        p=o.matrix_world@Vector(c)
        mins.x=min(mins.x,p.x); mins.y=min(mins.y,p.y); mins.z=min(mins.z,p.z)
        maxs.x=max(maxs.x,p.x); maxs.y=max(maxs.y,p.y); maxs.z=max(maxs.z,p.z)
center=(mins+maxs)*.5
size=maxs-mins
long=max(size.x,size.y,size.z)

# normalize model around origin, keeping its intrinsic orientation
root=bpy.data.objects.new("ModelRoot",None); bpy.context.collection.objects.link(root)
for o in meshes:
    if o.parent is None:
        o.parent=root
scale=4.0/long if long>0 else 1
root.scale=(scale,scale,scale)
root.location=(-center.x*scale,-center.y*scale,-mins.z*scale)
bpy.context.view_layer.update()

# ground
bpy.ops.mesh.primitive_plane_add(size=20, location=(0,0,0))
g=bpy.context.object
m=bpy.data.materials.new("Ground");m.diffuse_color=(.025,.03,.04,1);m.metallic=.2;m.roughness=.22
g.data.materials.append(m)

# lighting
for loc,e,size,col in [((4,-4,6),1200,5,(1,.45,.25)),((-3,2,5),800,4,(.18,.32,1)),((-4,-2,2.5),700,3,(.08,.25,1))]:
    bpy.ops.object.light_add(type="AREA",location=loc)
    l=bpy.context.object;l.data.energy=e;l.data.size=size;l.data.color=col

world=bpy.context.scene.world
world.color=(.025,.035,.06)

bpy.ops.object.camera_add()
cam=bpy.context.object
scene=bpy.context.scene;scene.camera=cam;scene.render.engine="BLENDER_EEVEE"
scene.render.resolution_x=960;scene.render.resolution_y=540;scene.render.resolution_percentage=100
scene.render.image_settings.file_format="PNG";scene.view_settings.look="AgX - Medium High Contrast"

# render a turntable-ish set. Since single-image reconstruction orientation is uncertain,
# render several azimuths and later pick the closest visually.
def aim(loc,target=(0,0,1.25),lens=58):
    cam.location=loc;cam.data.lens=lens
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat("-Z","Y").to_euler()
    bpy.context.view_layer.update()

views={
"v0":(6,-6,3.0),
"v45":(7,0,2.8),
"v90":(6,6,3.0),
"v135":(0,7,2.8),
"v180":(-6,6,3.0),
"v225":(-7,0,2.8),
"v270":(-6,-6,3.0),
"v315":(0,-7,2.8),
}
sizes={}
for n,loc in views.items():
    aim(loc)
    p=OUT/f"{n}.png";scene.render.filepath=str(p);bpy.ops.render.render(write_still=True);sizes[n]=p.stat().st_size

blend=ROOT/"ORBITA_AI3D.blend";bpy.ops.wm.save_as_mainfile(filepath=str(blend))
manifest={"status":"PASS","blender_version":".".join(map(str,bpy.app.version)),"mesh_objects":len(meshes),"blend_bytes":blend.stat().st_size,"renders":sizes}
(OUT/"manifest.json").write_text(json.dumps(manifest,indent=2))
print("ORBITA_AI3D_BLENDER_PASS")
print(json.dumps(manifest,indent=2))
