import bpy, json, math, os
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
if ext==".glb" or ext==".gltf":
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

mins=Vector((1e9,1e9,1e9)); maxs=Vector((-1e9,-1e9,-1e9))
for o in meshes:
    for c in o.bound_box:
        p=o.matrix_world@Vector(c)
        mins.x=min(mins.x,p.x);mins.y=min(mins.y,p.y);mins.z=min(mins.z,p.z)
        maxs.x=max(maxs.x,p.x);maxs.y=max(maxs.y,p.y);maxs.z=max(maxs.z,p.z)
center=(mins+maxs)*.5; span=maxs-mins; longest=max(span.x,span.y,span.z)
root=bpy.data.objects.new("ModelRoot",None);bpy.context.collection.objects.link(root)
for o in meshes:
    if o.parent is None:o.parent=root
scale=4.2/longest if longest else 1
root.scale=(scale,scale,scale)
root.location=(-center.x*scale,-center.y*scale,-mins.z*scale)

# ground
bpy.ops.mesh.primitive_plane_add(size=20,location=(0,0,0))
g=bpy.context.object
gm=bpy.data.materials.new("Ground");gm.diffuse_color=(.02,.025,.035,1);gm.metallic=.15;gm.roughness=.25;g.data.materials.append(gm)

for loc,e,size,col in [((4,-4,6),1200,5,(1,.45,.25)),((-3,2,5),850,4,(.15,.3,1)),((-4,-2,2.5),700,3,(.08,.25,1))]:
    bpy.ops.object.light_add(type="AREA",location=loc)
    l=bpy.context.object;l.data.energy=e;l.data.size=size;l.data.color=col

world=bpy.context.scene.world
world.color=(.02,.03,.05)

bpy.ops.object.camera_add();cam=bpy.context.object
scene=bpy.context.scene;scene.camera=cam;scene.render.engine="BLENDER_EEVEE"
scene.render.resolution_x=960;scene.render.resolution_y=540;scene.render.resolution_percentage=100
scene.render.image_settings.file_format="PNG";scene.view_settings.look="AgX - Medium High Contrast"

def aim(loc,target=(0,0,1.25),lens=60):
    cam.location=loc;cam.data.lens=lens
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat("-Z","Y").to_euler()
    bpy.context.view_layer.update()

views={
"front":(7.2,0,2.5),
"front_3q":(6.0,-5.7,3.0),
"side_left":(0,-7.5,2.4),
"rear_3q":(-5.8,-5.5,2.9),
"rear":(-7.2,0,2.5),
"side_right":(0,7.5,2.4),
}
sizes={}
for name,loc in views.items():
    aim(loc)
    p=OUT/f"{name}.png";scene.render.filepath=str(p);bpy.ops.render.render(write_still=True);sizes[name]=p.stat().st_size

blend=ROOT/"ORBITA_HUNYUAN_BLENDER.blend";bpy.ops.wm.save_as_mainfile(filepath=str(blend))
manifest={"status":"PASS","blender_version":".".join(map(str,bpy.app.version)),"source_mesh":mesh_path.name,"source_mesh_bytes":mesh_path.stat().st_size,"mesh_objects":len(meshes),"blend_bytes":blend.stat().st_size,"renders":sizes}
(OUT/"manifest.json").write_text(json.dumps(manifest,indent=2))
print("ORBITA_HUNYUAN_BLENDER_PASS")
print(json.dumps(manifest,indent=2))
