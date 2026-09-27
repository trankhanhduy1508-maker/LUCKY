# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import hashlib
import json

from .scene_snapshot import scene_summary


def scene_digest(snapshot: dict | None = None) -> str:
    value = snapshot or scene_summary()
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def diff_snapshots(before: dict, after: dict) -> dict:
    b = {obj["name"]: obj for obj in before.get("objects", [])}
    a = {obj["name"]: obj for obj in after.get("objects", [])}
    changed = []
    for name in sorted(set(a).intersection(b)):
        if a[name] != b[name]:
            changed.append(name)
    return {
        "objectCountBefore": len(b),
        "objectCountAfter": len(a),
        "created": sorted(set(a) - set(b)),
        "deleted": sorted(set(b) - set(a)),
        "changed": changed,
        "digestBefore": scene_digest(before),
        "digestAfter": scene_digest(after),
    }
