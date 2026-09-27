# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from .protocol import PLAN_VERSION, SUPPORTED_OPS


def capability_manifest() -> dict:
    return {
        "protocolVersion": PLAN_VERSION,
        "execution": "BLENDER_DATA_API_FIRST",
        "ops": sorted(SUPPORTED_OPS),
        "priority": [
            "bpy.data/RNA",
            "direct data mutation",
            "bmesh",
            "mathutils",
            "depsgraph",
            "bpy.ops only when required",
        ],
        "uiAutomation": False,
    }
