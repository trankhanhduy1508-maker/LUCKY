# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import ast
import time
from typing import Any

from .config import BPY_EXECUTION_BUDGET_SECONDS, MAX_BPY_BYTES
from .errors import PolicyError

_BANNED_NODES = (
    ast.Import,
    ast.ImportFrom,
    ast.Global,
    ast.Nonlocal,
    ast.Lambda,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.While,
    ast.For,
    ast.AsyncFor,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
    ast.Pow,
)

_BANNED_NAMES = {
    "__import__", "open", "eval", "exec", "compile", "globals", "locals",
    "input", "help", "breakpoint", "getattr", "setattr", "delattr", "vars", "dir",
}

_ALLOWED_BUILTINS = {
    "abs": abs,
    "bool": bool,
    "dict": dict,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "round": round,
    "set": set,
    "str": str,
    "tuple": tuple,
}

_ALLOWED_BPY_PREFIXES = (
    "bpy.context.scene",
    "bpy.context.collection",
    "bpy.context.view_layer",
    "bpy.data.objects",
    "bpy.data.meshes",
    "bpy.data.materials",
    "bpy.data.cameras",
    "bpy.data.lights",
    "bpy.data.collections",
)

_DENIED_MATH_CALLS = {"math.factorial", "math.comb", "math.perm"}
_BOUNDED_COUNT_KEYWORDS = {
    "segments", "x_segments", "y_segments", "cuts", "number", "steps", "count",
}
_MAX_AST_NODES = 512
_MAX_CALLS = 64
_MAX_NUMERIC_LITERAL = 1_000_000
_MAX_BOUNDED_COUNT = 4096


def _attribute_path(node: ast.AST) -> str | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        if current.attr.startswith("_"):
            return None
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return ".".join(reversed(parts))
    return None


def _root_name(node: ast.AST) -> str | None:
    path = _attribute_path(node)
    return path.split(".", 1)[0] if path else None


def _bpy_path_allowed(path: str) -> bool:
    if path == "bpy":
        return True
    return any(
        path == prefix
        or path.startswith(prefix + ".")
        or prefix.startswith(path + ".")
        for prefix in _ALLOWED_BPY_PREFIXES
    )


def _literal_number(node: ast.AST) -> float | None:
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    ):
        return float(node.value)
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, (ast.UAdd, ast.USub))
        and isinstance(node.operand, ast.Constant)
        and isinstance(node.operand.value, (int, float))
        and not isinstance(node.operand.value, bool)
    ):
        value = float(node.operand.value)
        return -value if isinstance(node.op, ast.USub) else value
    return None


def validate_bpy_source(source: str) -> ast.Module:
    if not isinstance(source, str) or not source.strip():
        raise PolicyError("empty bpy source")
    if len(source.encode("utf-8")) > MAX_BPY_BYTES:
        raise PolicyError("bpy source exceeds byte limit")
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as exc:
        raise PolicyError("invalid bpy syntax") from exc

    nodes = list(ast.walk(tree))
    if len(nodes) > _MAX_AST_NODES:
        raise PolicyError("bpy source exceeds AST node limit")

    call_count = 0
    for node in nodes:
        if isinstance(node, _BANNED_NODES):
            raise PolicyError(f"banned syntax: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id in _BANNED_NAMES:
            raise PolicyError(f"banned name: {node.id}")
        if isinstance(node, ast.Attribute):
            path = _attribute_path(node)
            if path is None:
                raise PolicyError("private or dynamic attribute access denied")
            if path.startswith("bpy.") and not _bpy_path_allowed(path):
                raise PolicyError(f"bpy path denied: {path}")
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str) and len(node.value) > 4096:
                raise PolicyError("string literal exceeds limit")
            if (
                isinstance(node.value, (int, float))
                and not isinstance(node.value, bool)
                and abs(float(node.value)) > _MAX_NUMERIC_LITERAL
            ):
                raise PolicyError("numeric literal exceeds limit")
        if isinstance(node, ast.Call):
            call_count += 1
            if call_count > _MAX_CALLS:
                raise PolicyError("too many calls")

            if isinstance(node.func, ast.Name):
                if node.func.id not in _ALLOWED_BUILTINS:
                    raise PolicyError(f"call denied: {node.func.id}")
                continue

            if not isinstance(node.func, ast.Attribute):
                raise PolicyError("dynamic call denied")

            path = _attribute_path(node.func)
            root = _root_name(node.func)
            if not path or root not in {"bpy", "bmesh", "mathutils", "math"}:
                raise PolicyError("call root denied")
            if root == "bpy" and not _bpy_path_allowed(path):
                raise PolicyError(f"bpy call denied: {path}")
            if path in _DENIED_MATH_CALLS:
                raise PolicyError(f"expensive math call denied: {path}")

            if root == "bmesh":
                for keyword in node.keywords:
                    if keyword.arg in _BOUNDED_COUNT_KEYWORDS:
                        value = _literal_number(keyword.value)
                        if value is None or value < 0 or value > _MAX_BOUNDED_COUNT:
                            raise PolicyError(f"bmesh {keyword.arg} exceeds limit")

    return tree


def execute_bounded(source: str, *, bpy, bmesh, mathutils, math) -> dict[str, Any]:
    tree = validate_bpy_source(source)
    namespace = {
        "__builtins__": _ALLOWED_BUILTINS,
        "bpy": bpy,
        "bmesh": bmesh,
        "mathutils": mathutils,
        "math": math,
    }
    started = time.monotonic()
    exec(compile(tree, "<cws-ai-bounded>", "exec"), namespace, namespace)
    elapsed = time.monotonic() - started
    if elapsed > BPY_EXECUTION_BUDGET_SECONDS:
        raise PolicyError("bpy execution exceeded budget")
    result = namespace.get("result")
    if isinstance(result, (str, int, float, bool, type(None), list, dict, tuple)):
        safe_result = result
    else:
        safe_result = repr(result)[:1000]
    return {"elapsedSeconds": elapsed, "result": safe_result}
