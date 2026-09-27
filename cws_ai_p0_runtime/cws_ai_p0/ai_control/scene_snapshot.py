# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from typing import Any

import bpy


def _round_vec(values, digits: int = 6) -> list[float]:
    return [round(float(v), digits) for v in values]


def _world_bounds(obj) -> list[list[float]] | None:
    if not getattr(obj, "bound_box", None):
        return None
    points = [obj.matrix_world @ type(obj.location)(corner) for corner in obj.bound_box]
    return [
        [round(min(float(p[i]) for p in points), 6) for i in range(3)],
        [round(max(float(p[i]) for p in points), 6) for i in range(3)],
    ]


def object_summary(obj) -> dict[str, Any]:
    materials = []
    data = getattr(obj, "data", None)
    if data is not None and hasattr(data, "materials"):
        materials = [m.name for m in data.materials if m is not None]
    return {
        "name": obj.name,
        "type": obj.type,
        "parent": obj.parent.name if obj.parent else None,
        "location": _round_vec(obj.location),
        "rotationEuler": _round_vec(obj.rotation_euler),
        "scale": _round_vec(obj.scale),
        "bounds": _world_bounds(obj),
        "materials": materials,
        "modifiers": [m.type for m in getattr(obj, "modifiers", [])],
    }


def scene_summary(scene=None) -> dict[str, Any]:
    scene = scene or bpy.context.scene
    objects = sorted((object_summary(obj) for obj in scene.objects), key=lambda item: item["name"])
    return {
        "blenderVersion": bpy.app.version_string,
        "scene": scene.name,
        "renderEngine": scene.render.engine,
        "objectCount": len(objects),
        "objects": objects,
        "camera": scene.camera.name if scene.camera else None,
    }


def inspect_object(name: str) -> dict[str, Any]:
    obj = bpy.data.objects.get(str(name))
    if obj is None:
        raise KeyError(f"object not found: {name}")
    return object_summary(obj)
