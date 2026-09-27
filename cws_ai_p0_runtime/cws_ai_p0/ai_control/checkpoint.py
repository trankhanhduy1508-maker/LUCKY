# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

import bpy

_KNOWN_CHECKPOINTS: set[str] = set()


def _resolved(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def is_known_checkpoint(path: str) -> bool:
    return str(_resolved(path)) in _KNOWN_CHECKPOINTS


def capture_scene_state() -> dict:
    objects = {}
    for obj in bpy.context.scene.objects:
        entry = {
            "location": tuple(float(v) for v in obj.location),
            "rotation": tuple(float(v) for v in obj.rotation_euler),
            "scale": tuple(float(v) for v in obj.scale),
            "hide_render": bool(obj.hide_render),
        }
        if obj.type == "MESH" and getattr(obj, "data", None):
            entry["materials"] = [m.name if m else None for m in obj.data.materials]
        objects[obj.name] = entry
    return {"objects": objects}


def restore_scene_state(state: dict) -> None:
    expected = state.get("objects", {})
    for name, entry in expected.items():
        obj = bpy.data.objects.get(name)
        if obj is None:
            continue
        obj.location = entry["location"]
        obj.rotation_euler = entry["rotation"]
        obj.scale = entry["scale"]
        obj.hide_render = entry["hide_render"]


def save_blend_checkpoint(directory: str | None = None, label: str = "ai") -> str:
    root = _resolved(directory or tempfile.gettempdir())
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"cws-{label}-{uuid.uuid4().hex[:10]}.blend"
    result = bpy.ops.wm.save_as_mainfile(
        filepath=str(path),
        copy=True,
        check_existing=False,
    )
    if "FINISHED" not in result or not path.is_file() or path.stat().st_size <= 0:
        raise RuntimeError("failed to save Blender checkpoint")
    resolved = str(_resolved(path))
    _KNOWN_CHECKPOINTS.add(resolved)
    return resolved


def restore_blend_checkpoint(path: str) -> str:
    checkpoint = _resolved(path)
    if checkpoint.suffix.lower() != ".blend" or not checkpoint.name.startswith("cws-"):
        raise ValueError("not a CWS Blender checkpoint")
    if str(checkpoint) not in _KNOWN_CHECKPOINTS:
        raise PermissionError("CWS Blender checkpoint was not created in this session")
    if not checkpoint.is_file() or checkpoint.stat().st_size <= 0:
        raise FileNotFoundError("CWS Blender checkpoint is unavailable")
    result = bpy.ops.wm.open_mainfile(filepath=str(checkpoint))
    if "FINISHED" not in result:
        raise RuntimeError("failed to restore Blender checkpoint")
    return str(checkpoint)
