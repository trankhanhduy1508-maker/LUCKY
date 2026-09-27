# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from pathlib import Path

from .errors import PlanValidationError
from .protocol import REQUIRED_FIELDS, SUPPORTED_OPS, canonical_plan

_VECTOR_FIELDS = ("location", "rotation", "scale")


def _number(value, field: str, *, minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool):
        raise PlanValidationError(f"{field} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise PlanValidationError(f"{field} must be numeric") from exc
    if not math.isfinite(result):
        raise PlanValidationError(f"{field} must be finite")
    if minimum is not None and result < minimum:
        raise PlanValidationError(f"{field} below minimum")
    if maximum is not None and result > maximum:
        raise PlanValidationError(f"{field} above maximum")
    return result


def _vector(value, field: str) -> None:
    if value is None:
        return
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise PlanValidationError(f"{field} must have 3 numeric values")
    for index, item in enumerate(value):
        _number(item, f"{field}[{index}]")


def validate_plan(
    plan,
    object_names: Iterable[str],
    *,
    object_types: Mapping[str, str] | None = None,
    allow_bpy: bool = False,
) -> dict:
    value = canonical_plan(plan)
    virtual = {str(name) for name in object_names}
    types = {str(k): str(v).upper() for k, v in (object_types or {}).items()}

    restore_commands = [
        command for command in value["commands"]
        if isinstance(command, dict) and command.get("op") == "checkpoint.restore"
    ]
    if restore_commands and len(value["commands"]) != 1:
        raise PlanValidationError("checkpoint.restore must be the only command in a plan")

    for index, command in enumerate(value["commands"]):
        if not isinstance(command, dict):
            raise PlanValidationError(f"command {index} must be an object")
        op = str(command.get("op", ""))
        if op not in SUPPORTED_OPS:
            raise PlanValidationError(f"unsupported op: {op}")
        if op == "python.execute_bounded" and not allow_bpy:
            raise PlanValidationError("bounded bpy lane requires explicit opt-in")
        for field in REQUIRED_FIELDS[op]:
            if field not in command or command[field] in (None, ""):
                raise PlanValidationError(f"{op} missing {field}")

        if op in {
            "object.inspect",
            "object.transform",
            "object.delete",
            "material.edit",
            "camera.edit",
            "light.edit",
        }:
            target = str(command["target"])
            if target not in virtual:
                raise PlanValidationError(f"target does not exist: {target}")

        if op == "material.edit":
            target_type = types.get(str(command["target"]))
            if target_type is not None and target_type != "MESH":
                raise PlanValidationError("material target must be a mesh")
            color = command.get("base_color")
            if color is not None:
                if not isinstance(color, (list, tuple)) or len(color) not in (3, 4):
                    raise PlanValidationError("base_color must have 3 or 4 values")
                for idx, item in enumerate(color):
                    _number(item, f"base_color[{idx}]", minimum=0.0, maximum=1.0)
            if "roughness" in command:
                _number(command["roughness"], "roughness", minimum=0.0, maximum=1.0)

        if op == "camera.edit":
            target_type = types.get(str(command["target"]))
            if target_type is not None and target_type != "CAMERA":
                raise PlanValidationError("camera target must be a camera")

        if op == "light.edit":
            target_type = types.get(str(command["target"]))
            if target_type is not None and target_type != "LIGHT":
                raise PlanValidationError("light target must be a light")

        if op in {"object.create", "camera.create", "light.create"}:
            name = str(command["name"])
            if not name.strip():
                raise PlanValidationError(f"{op} name is empty")
            if name in virtual:
                raise PlanValidationError(f"name already exists: {name}")
            virtual.add(name)

        for field in _VECTOR_FIELDS:
            if field in command:
                _vector(command.get(field), field)

        if op == "object.create":
            primitive = str(command.get("primitive", "CUBE")).upper()
            if primitive not in {"CUBE", "EMPTY"}:
                raise PlanValidationError("P0 supports only CUBE or EMPTY")
            types[str(command["name"])] = "MESH" if primitive == "CUBE" else "EMPTY"
            if primitive == "CUBE":
                _number(command.get("size", 2.0), "size", minimum=0.000001)

        if op == "camera.create":
            types[str(command["name"])] = "CAMERA"

        if op == "light.create":
            light_type = str(command.get("light_type", "AREA")).upper()
            if light_type not in {"POINT", "SUN", "SPOT", "AREA"}:
                raise PlanValidationError("unsupported light type")
            types[str(command["name"])] = "LIGHT"

        if op in {"camera.create", "camera.edit"} and "lens" in command:
            _number(command["lens"], "lens", minimum=0.000001)

        if op in {"light.create", "light.edit"} and "energy" in command:
            _number(command["energy"], "energy", minimum=0.0)

        if op == "object.delete":
            target = str(command["target"])
            virtual.remove(target)
            types.pop(target, None)

        if op == "checkpoint.restore":
            path = Path(str(command["path"]))
            if path.suffix.lower() != ".blend":
                raise PlanValidationError("checkpoint restore path must end in .blend")
            if not path.name.startswith("cws-"):
                raise PlanValidationError("checkpoint restore path must be a CWS checkpoint")

        if op == "render.preview":
            path = str(command["path"])
            if not path.lower().endswith(".png"):
                raise PlanValidationError("preview path must end in .png")
            engine = str(command.get("engine", "BLENDER_EEVEE"))
            if engine not in {"BLENDER_EEVEE", "CYCLES"}:
                raise PlanValidationError("preview engine must be BLENDER_EEVEE or CYCLES")
            _number(command.get("width", 256), "width", minimum=1, maximum=4096)
            _number(command.get("height", 256), "height", minimum=1, maximum=4096)
            _number(command.get("samples", 1), "samples", minimum=1, maximum=64)

        if op == "python.execute_bounded" and not isinstance(command.get("code"), str):
            raise PlanValidationError("bounded bpy code must be a string")

    return value


_MUTATING_OPS = frozenset({
    "object.create",
    "object.transform",
    "object.delete",
    "material.edit",
    "camera.create",
    "camera.edit",
    "light.create",
    "light.edit",
    "checkpoint.restore",
    "python.execute_bounded",
})


def plan_requires_checkpoint(plan: dict) -> bool:
    """Return True when a validated plan can mutate persistent scene state.

    Render preview is intentionally excluded for P0 because it already writes a
    disposable image and adjusts render settings by design. Every geometry,
    object, material, camera, light, restore, or bounded-bpy mutation gets an
    automatic .blend checkpoint before execution.
    """
    commands = plan.get("commands", []) if isinstance(plan, dict) else []
    return any(
        isinstance(command, dict) and str(command.get("op", "")) in _MUTATING_OPS
        for command in commands
    )
