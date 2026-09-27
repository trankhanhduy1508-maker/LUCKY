from __future__ import annotations

import json
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cws_ai_p0
assert cws_ai_p0.SOURCE_COMMIT == "f351239f9cb291b6553a31b39414f3d1abbbfcbe"
import bpy

import cws_ai_p0.ai_control.config as ai_config
from cws_ai_p0.ai_control.audit import scene_digest
from cws_ai_p0.ai_control.batch_executor import execute_plan
from cws_ai_p0.ai_control.capabilities import capability_manifest
from cws_ai_p0.ai_control.checkpoint import save_blend_checkpoint
from cws_ai_p0.ai_control.errors import ExecutionError, PlanValidationError
from cws_ai_p0.ai_control.plan_validator import validate_plan
from cws_ai_p0.ai_control.scene_snapshot import scene_summary


def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


clear_scene()
assert ai_config.AI_ENABLED_DEFAULT is False

caps = capability_manifest()
assert caps["uiAutomation"] is False
assert "object.transform" in caps["ops"]
assert "checkpoint.restore" in caps["ops"]

summary = scene_summary()
assert summary["objectCount"] == 0
assert summary["blenderVersion"].startswith("5.2.")
print("CWS_AI_SCENE_SUMMARY_PASS", json.dumps(summary, sort_keys=True), flush=True)

tmp = Path(tempfile.mkdtemp(prefix="cws-ai-p0-"))
preview = tmp / "ai-preview.png"

plan = {
    "version": 1,
    "goal": "create a red product block, light it, and render one preview",
    "checkpoint": True,
    "commands": [
        {"op": "object.create", "name": "AI_Product", "primitive": "CUBE", "size": 2.0, "location": [0.0, 0.0, 0.0]},
        {"op": "object.transform", "target": "AI_Product", "location": [1.0, 2.0, 0.5], "scale": [1.2, 0.8, 0.6]},
        {"op": "material.edit", "target": "AI_Product", "material": "AI_Red", "base_color": [0.75, 0.08, 0.04, 1.0], "roughness": 0.35},
        {"op": "light.create", "name": "AI_Key", "light_type": "AREA", "location": [2.5, -2.5, 4.0], "energy": 900.0},
        {"op": "render.preview", "path": str(preview), "width": 64, "height": 64, "engine": "CYCLES", "samples": 1},
    ],
}

validated = validate_plan(plan, bpy.data.objects.keys())
assert len(validated["commands"]) == 5
print("CWS_AI_PLAN_VALIDATION_PASS", {"commands": len(validated["commands"])}, flush=True)

result = execute_plan(plan, checkpoint_dir=str(tmp))
obj = bpy.data.objects.get("AI_Product")
assert obj is not None
assert tuple(round(float(v), 3) for v in obj.location) == (1.0, 2.0, 0.5)
assert tuple(round(float(v), 3) for v in obj.scale) == (1.2, 0.8, 0.6)
assert preview.is_file() and preview.stat().st_size > 0
checkpoint_path = Path(result["checkpointPath"])
assert checkpoint_path.is_file() and checkpoint_path.stat().st_size > 0
assert "AI_Product" in result["audit"]["created"]
print("CWS_AI_BATCH_EXECUTION_PASS", {"created": result["audit"]["created"], "changed": result["audit"]["changed"], "checkpointBytes": checkpoint_path.stat().st_size}, flush=True)

before_bad = scene_digest()
try:
    execute_plan({"version": 1, "commands": [
        {"op": "object.transform", "target": "DOES_NOT_EXIST", "location": [9, 9, 9]},
        {"op": "object.delete", "target": "AI_Product"},
    ]})
    raise AssertionError("invalid plan unexpectedly executed")
except PlanValidationError:
    pass
assert before_bad == scene_digest()
assert bpy.data.objects.get("AI_Product") is not None
print("CWS_AI_INVALID_PLAN_NO_MUTATION_PASS", before_bad, flush=True)

before_runtime_failure = scene_digest()
try:
    execute_plan({"version": 1, "commands": [
        {"op": "object.create", "name": "AI_MustRollback", "primitive": "CUBE"},
        {"op": "python.execute_bounded", "code": "result = bpy.data.objects['CWS_OBJECT_THAT_DOES_NOT_EXIST'].name"},
    ]}, allow_bpy=True, checkpoint_dir=str(tmp))
    raise AssertionError("runtime failure plan unexpectedly completed")
except Exception:
    pass
assert bpy.data.objects.get("AI_MustRollback") is None
assert scene_digest() == before_runtime_failure
print("CWS_AI_RUNTIME_FAILURE_ROLLBACK_PASS", before_runtime_failure, flush=True)

obj = bpy.data.objects["AI_Product"]
original_location = tuple(float(v) for v in obj.location)
explicit_checkpoint = Path(save_blend_checkpoint(str(tmp), "restore-proof"))
assert explicit_checkpoint.is_file() and explicit_checkpoint.stat().st_size > 0

forged_checkpoint = tmp / "cws-forged.blend"
forged_checkpoint.write_bytes(explicit_checkpoint.read_bytes())
digest_before_forged = scene_digest()
try:
    execute_plan({"version": 1, "commands": [{"op": "checkpoint.restore", "path": str(forged_checkpoint)}]})
    raise AssertionError("untrusted checkpoint unexpectedly restored")
except ExecutionError:
    pass
assert scene_digest() == digest_before_forged
print("CWS_AI_UNTRUSTED_CHECKPOINT_REJECTED_PASS", str(forged_checkpoint), flush=True)

# open_mainfile during rollback invalidates prior RNA object references.
obj = bpy.data.objects["AI_Product"]
obj.location = (8.0, 8.0, 8.0)
assert tuple(float(v) for v in obj.location) != original_location
restore_result = execute_plan({"version": 1, "commands": [{"op": "checkpoint.restore", "path": str(explicit_checkpoint)}]})
obj = bpy.data.objects.get("AI_Product")
assert obj is not None
assert tuple(round(float(v), 6) for v in obj.location) == tuple(round(v, 6) for v in original_location)
assert restore_result["results"][0]["op"] == "checkpoint.restore"
print("CWS_AI_CHECKPOINT_RESTORE_PASS", {"blendBytes": explicit_checkpoint.stat().st_size, "location": original_location}, flush=True)

assert preview.stat().st_size > 0
print("CWS_AI_PREVIEW_PASS", {"path": str(preview), "bytes": preview.stat().st_size}, flush=True)
print("CWS_AI_ASSISTANT_CORE_RUNTIME_PASS", flush=True)
