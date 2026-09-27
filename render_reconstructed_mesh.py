import bpy
import json
import math
import sys
import time
from pathlib import Path
from mathutils import Vector

START = time.time()
ROOT = Path("reconstruction_evidence")
ROOT.mkdir(parents=True, exist_ok=True)
MESH = Path("triposr/output/0/mesh.glb")

if not MESH.is_file() or MESH.stat().st_size <= 0:
    raise RuntimeError(f"Missing reconstructed mesh: {MESH}")

for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

bpy.ops.import_scene.gltf(filepath=str(MESH.resolve()))
mesh_objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not mesh_objects:
    raise RuntimeError("GLB imported but no mesh objects exist")

# Parent all imported mesh objects so the reconstruction can be normalized as one asset.
bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
root = bpy.context.object
root.name = "ORBITA_Reconstructed_Root"
for obj in mesh_objects:
    obj.parent = root

def world_bbox(objects):
    pts = []
    for obj in objects:
        for c in obj.bound_box:
            pts.append(obj.matrix_world @ Vector(c))
    mins = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    maxs = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mins, maxs

bmin, bmax = world_bbox(mesh_objects)
center = (bmin + bmax) * 0.5
span = bmax - bmin

# Put the asset around origin and make its largest dimension about 4.2 Blender units.
for obj in mesh_objects:
    obj.location -= center
largest = max(span.x, span.y, span.z)
scale = 4.2 / largest if largest > 0 else 1.0
root.scale = (scale, scale, scale)
bpy.context.view_layer.update()

# Recompute bbox and lift model onto floor.
bmin, bmax = world_bbox(mesh_objects)
root.location.z -= bmin.z
bpy.context.view_layer.update()
bmin, bmax = world_bbox(mesh_objects)

# Neutral reflective floor.
def mat(name, color, metallic=0.0, rough=0.4, emission=None, strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bs = m.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value = color
    bs.inputs["Metallic"].default_value = metallic
    bs.inputs["Roughness"].default_value = rough
    if emission:
        bs.inputs["Emission Color"].default_value = emission
        bs.inputs["Emission Strength"].default_value = strength
    return m

ground_mat = mat("Ground", (0.025, 0.035, 0.055, 1), 0.45, 0.20)
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
ground = bpy.context.object
ground.data.materials.append(ground_mat)

# Add a subtle blue rim plane behind, not touching vehicle geometry.
blue = mat("BlueGlow", (0.005, 0.04, 0.16, 1), 0, 0.3, (0.01, 0.18, 0.8, 1), 2.0)
bpy.ops.mesh.primitive_plane_add(size=7, location=(-3.2, 3.8, 2.2), rotation=(math.radians(90), 0, 0))
back = bpy.context.object
back.data.materials.append(blue)

# Lighting.
for loc, energy, size, color in [
    ((4.5, -4.0, 6.0), 1500, 5.0, (1.0, 0.42, 0.20)),
    ((-2.0, 3.0, 5.0), 900, 4.0, (0.14, 0.35, 1.0)),
    ((-4.0, -2.0, 3.0), 1000, 3.0, (0.10, 0.35, 1.0)),
]:
    bpy.ops.object.light_add(type="AREA", location=loc)
    light = bpy.context.object
    light.data.energy = energy
    light.data.shape = "DISK"
    light.data.size = size
    light.data.color = color

world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0.025, 0.035, 0.055, 1)
bg.inputs["Strength"].default_value = 0.35

# Camera.
bpy.ops.object.camera_add(location=(6.2, -6.2, 3.1))
camera = bpy.context.object
scene = bpy.context.scene
scene.camera = camera
camera.data.lens = 62

scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 960
scene.render.resolution_y = 540
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.view_settings.look = "AgX - Medium High Contrast"

def point_camera(location, target=(0, 0, 1.2), lens=62):
    camera.location = location
    camera.data.lens = lens
    camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()

def render(name, location, target, lens):
    point_camera(location, target, lens)
    path = ROOT / name
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    if not path.is_file() or path.stat().st_size <= 0:
        raise RuntimeError(f"Render failed: {path}")
    return path.stat().st_size

blend_path = ROOT / "ORBITA_TRIPOSR_BLENDER.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

renders = {
    "hero": render("orbita_triposr_hero.png", (6.1, -6.0, 3.1), (0, 0, 1.25), 62),
    "front": render("orbita_triposr_front.png", (7.0, 0, 2.4), (0, 0, 1.25), 68),
    "side": render("orbita_triposr_side.png", (0, -7.5, 2.3), (0, 0, 1.20), 72),
}

manifest = {
    "status": "PASS",
    "source_mesh": str(MESH),
    "source_mesh_bytes": MESH.stat().st_size,
    "blender_version": ".".join(map(str, bpy.app.version)),
    "blend_bytes": blend_path.stat().st_size,
    "mesh_object_count": len(mesh_objects),
    "bbox_span_before_normalize": [round(span.x, 5), round(span.y, 5), round(span.z, 5)],
    "renders": renders,
    "elapsed_seconds": round(time.time() - START, 3),
}
(ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print("ORBITA_TRIPOSR_BLENDER_PASS")
print(json.dumps(manifest, indent=2))
