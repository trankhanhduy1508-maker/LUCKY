# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import bmesh
import bpy
import mathutils

from .audit import diff_snapshots
from .bpy_lane import execute_bounded
from .checkpoint import (
    capture_scene_state,
    restore_blend_checkpoint,
    restore_scene_state,
    save_blend_checkpoint,
)
from .errors import ExecutionError
from .plan_validator import plan_requires_checkpoint, validate_plan
from .scene_snapshot import inspect_object, scene_summary


def _set_vec(target, value, *, length=3):
    if value is None:
        return
    if not isinstance(value, (list, tuple)) or len(value) != length:
        raise ExecutionError("vector must have 3 values")
    for index in range(length):
        target[index] = float(value[index])


def _create_object(command: dict):
    name = str(command["name"])
    primitive = str(command.get("primitive", "CUBE")).upper()
    if primitive == "EMPTY":
        obj = bpy.data.objects.new(name, None)
    else:
        mesh = bpy.data.meshes.new(name + "_Mesh")
        obj = bpy.data.objects.new(name, mesh)
        bm = bmesh.new()
        try:
            bmesh.ops.create_cube(bm, size=float(command.get("size", 2.0)))
            bm.to_mesh(mesh)
            mesh.update()
        finally:
            bm.free()
    bpy.context.scene.collection.objects.link(obj)
    _set_vec(obj.location, command.get("location"))
    _set_vec(obj.rotation_euler, command.get("rotation"))
    _set_vec(obj.scale, command.get("scale"))
    return {"name": obj.name, "type": obj.type}


def _transform_object(command: dict):
    obj = bpy.data.objects.get(str(command["target"]))
    if obj is None:
        raise ExecutionError("transform target missing")
    _set_vec(obj.location, command.get("location"))
    _set_vec(obj.rotation_euler, command.get("rotation"))
    _set_vec(obj.scale, command.get("scale"))
    return inspect_object(obj.name)


def _delete_object(command: dict):
    obj = bpy.data.objects.get(str(command["target"]))
    if obj is None:
        raise ExecutionError("delete target missing")
    name = obj.name
    bpy.data.objects.remove(obj, do_unlink=True)
    return {"deleted": name}


def _material_edit(command: dict):
    obj = bpy.data.objects.get(str(command["target"]))
    if obj is None or obj.type != "MESH":
        raise ExecutionError("material target must be a mesh")
    name = str(command.get("material", obj.name + "_Material"))
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    color = command.get("base_color")
    if color is not None:
        rgba = [float(v) for v in color[:3]] + [float(color[3]) if len(color) == 4 else 1.0]
        material.diffuse_color = rgba
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF") if material.node_tree else None
    if bsdf is not None:
        if color is not None and "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = material.diffuse_color
        if "roughness" in command and "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = float(command["roughness"])
    if len(obj.data.materials) == 0:
        obj.data.materials.append(material)
    else:
        obj.data.materials[0] = material
    return {"object": obj.name, "material": material.name}


def _create_camera(command: dict):
    name = str(command["name"])
    data = bpy.data.cameras.new(name + "_Data")
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    _set_vec(obj.location, command.get("location"))
    _set_vec(obj.rotation_euler, command.get("rotation"))
    if "lens" in command:
        data.lens = float(command["lens"])
    if command.get("active", True):
        bpy.context.scene.camera = obj
    return {"name": obj.name}


def _edit_camera(command: dict):
    obj = bpy.data.objects.get(str(command["target"]))
    if obj is None or obj.type != "CAMERA":
        raise ExecutionError("camera target missing")
    _set_vec(obj.location, command.get("location"))
    _set_vec(obj.rotation_euler, command.get("rotation"))
    if "lens" in command:
        obj.data.lens = float(command["lens"])
    if command.get("active"):
        bpy.context.scene.camera = obj
    return {"name": obj.name, "lens": float(obj.data.lens)}


def _create_light(command: dict):
    name = str(command["name"])
    light_type = str(command.get("light_type", "AREA")).upper()
    data = bpy.data.lights.new(name + "_Data", light_type)
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    _set_vec(obj.location, command.get("location"))
    _set_vec(obj.rotation_euler, command.get("rotation"))
    if "energy" in command:
        data.energy = float(command["energy"])
    return {"name": obj.name, "type": light_type}


def _edit_light(command: dict):
    obj = bpy.data.objects.get(str(command["target"]))
    if obj is None or obj.type != "LIGHT":
        raise ExecutionError("light target missing")
    _set_vec(obj.location, command.get("location"))
    _set_vec(obj.rotation_euler, command.get("rotation"))
    if "energy" in command:
        obj.data.energy = float(command["energy"])
    return {"name": obj.name, "energy": float(obj.data.energy)}


def _point_camera_at(obj, point=(0.0, 0.0, 0.0)):
    direction = mathutils.Vector(point) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _render_preview(command: dict):
    path = Path(str(command["path"])).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    if scene.camera is None:
        camera = _create_camera({
            "name": "CWS_AI_PreviewCamera",
            "location": [4.5, -4.5, 3.5],
            "active": True,
        })
        _point_camera_at(bpy.data.objects[camera["name"]], (0.0, 0.0, 0.0))
    engine = str(command.get("engine", scene.render.engine or "BLENDER_EEVEE"))
    scene.render.engine = engine
    if engine == "CYCLES":
        scene.cycles.device = "CPU"
        scene.cycles.samples = max(1, min(64, int(command.get("samples", 1))))
    scene.render.resolution_x = int(command.get("width", 256))
    scene.render.resolution_y = int(command.get("height", 256))
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(path)
    world = scene.world
    if world is not None:
        world.color = (0.05, 0.05, 0.05)
    result = bpy.ops.render.render(write_still=True)
    if "FINISHED" not in result or not path.is_file() or path.stat().st_size <= 0:
        raise ExecutionError("preview render failed")
    return {"path": str(path), "bytes": path.stat().st_size}


def execute_plan(plan: dict, *, allow_bpy: bool = False, checkpoint_dir: str | None = None) -> dict[str, Any]:
    object_types = {obj.name: obj.type for obj in bpy.data.objects}
    validated = validate_plan(
        plan,
        bpy.data.objects.keys(),
        object_types=object_types,
        allow_bpy=allow_bpy,
    )
    before = scene_summary()
    state_checkpoint = capture_scene_state()
    blend_checkpoint = None
    if validated.get("checkpoint") or plan_requires_checkpoint(validated):
        blend_checkpoint = save_blend_checkpoint(checkpoint_dir, "ai-plan")

    results = []
    try:
        for command in validated["commands"]:
            op = command["op"]
            if op == "scene.inspect":
                result = scene_summary()
            elif op == "object.inspect":
                result = inspect_object(command["target"])
            elif op == "object.create":
                result = _create_object(command)
            elif op == "object.transform":
                result = _transform_object(command)
            elif op == "object.delete":
                result = _delete_object(command)
            elif op == "material.edit":
                result = _material_edit(command)
            elif op == "camera.create":
                result = _create_camera(command)
            elif op == "camera.edit":
                result = _edit_camera(command)
            elif op == "light.create":
                result = _create_light(command)
            elif op == "light.edit":
                result = _edit_light(command)
            elif op == "checkpoint.save":
                result = {"path": save_blend_checkpoint(checkpoint_dir, "ai-explicit")}
            elif op == "checkpoint.restore":
                result = {"path": restore_blend_checkpoint(str(command["path"]))}
            elif op == "render.preview":
                result = _render_preview(command)
            elif op == "python.execute_bounded":
                result = execute_bounded(
                    str(command["code"]),
                    bpy=bpy,
                    bmesh=bmesh,
                    mathutils=mathutils,
                    math=math,
                )
            else:
                raise ExecutionError(f"unhandled op: {op}")
            results.append({"op": op, "result": result})
    except Exception as exc:
        try:
            if blend_checkpoint:
                restore_blend_checkpoint(blend_checkpoint)
            else:
                restore_scene_state(state_checkpoint)
        except Exception:
            restore_scene_state(state_checkpoint)
        raise ExecutionError(str(exc)) from exc

    after = scene_summary()
    return {
        "version": 1,
        "goal": validated.get("goal", ""),
        "results": results,
        "checkpointPath": blend_checkpoint,
        "audit": diff_snapshots(before, after),
    }
