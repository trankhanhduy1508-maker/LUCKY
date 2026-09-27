# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import json
from typing import Any

from .config import MAX_COMMANDS, MAX_PLAN_BYTES
from .errors import PlanValidationError

PLAN_VERSION = 1

SUPPORTED_OPS = frozenset({
    "scene.inspect",
    "object.inspect",
    "object.create",
    "object.transform",
    "object.delete",
    "material.edit",
    "camera.create",
    "camera.edit",
    "light.create",
    "light.edit",
    "checkpoint.save",
    "checkpoint.restore",
    "render.preview",
    "python.execute_bounded",
})

REQUIRED_FIELDS = {
    "scene.inspect": (),
    "object.inspect": ("target",),
    "object.create": ("name",),
    "object.transform": ("target",),
    "object.delete": ("target",),
    "material.edit": ("target",),
    "camera.create": ("name",),
    "camera.edit": ("target",),
    "light.create": ("name",),
    "light.edit": ("target",),
    "checkpoint.save": (),
    "checkpoint.restore": ("path",),
    "render.preview": ("path",),
    "python.execute_bounded": ("code",),
}


def canonical_plan(plan: Any) -> dict[str, Any]:
    if not isinstance(plan, dict):
        raise PlanValidationError("plan must be an object")
    try:
        encoded = json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise PlanValidationError("plan must be JSON serializable") from exc
    if len(encoded.encode("utf-8")) > MAX_PLAN_BYTES:
        raise PlanValidationError("plan exceeds byte limit")
    value = json.loads(encoded)
    if value.get("version") != PLAN_VERSION:
        raise PlanValidationError("unsupported plan version")
    commands = value.get("commands")
    if not isinstance(commands, list):
        raise PlanValidationError("commands must be an array")
    if len(commands) > MAX_COMMANDS:
        raise PlanValidationError("too many commands")
    return value
