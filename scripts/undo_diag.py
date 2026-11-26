#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""undo_diag.py — تشخيص سجل التراجع (UndoLog) دون كشف المحتوى.

يقرأ JSON لسجل التراجع ويطبع وصفًا بنيويًا فقط:
  - نوع البنية، عدد السجلات، أسماء الحقول فقط (لا قيم).
  - توزيع status/action/result (أعداد).
  - checksum: match/mismatch/missing (أعداد فقط).
  - أخطاء: عدّ فقط، لا نصوص.
  - لا يكتب أي ملفات (stdout فقط).

الاستخدام:
    python3 scripts/undo_diag.py _runs/backup_undo.json _runs/medi_undo.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter


def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def diagnose(path: str) -> dict:
    data = _load(path)
    result = {"path_label": path, "top_type": type(data).__name__}

    if isinstance(data, dict):
        result["top_keys"] = list(data.keys())
        entries = data.get("entries", [])
    elif isinstance(data, list):
        result["top_keys"] = None
        entries = data
    else:
        result["top_keys"] = None
        entries = []

    result["entry_count"] = len(entries)

    # أسماء الحقول فقط (من أول سجل).
    if entries and isinstance(entries[0], dict):
        result["field_names"] = list(entries[0].keys())
    else:
        result["field_names"] = []

    # توزيع action_type.
    actions = Counter(
        e.get("action_type", "?") for e in entries if isinstance(e, dict)
    )
    result["action_dist"] = dict(actions)

    # توزيع success (status).
    success = Counter(
        str(e.get("success", "?")) for e in entries if isinstance(e, dict)
    )
    result["success_dist"] = dict(success)

    # توزيع recovery_state (result).
    recovery = Counter(
        str(e.get("recovery_state", "")) for e in entries if isinstance(e, dict)
    )
    result["recovery_dist"] = dict(recovery)

    # checksum: match / mismatch / missing (أعداد فقط).
    match = mismatch = missing = 0
    for e in entries:
        if not isinstance(e, dict):
            continue
        before = e.get("checksum_before")
        after = e.get("checksum_after")
        if not before and not after:
            missing += 1
        elif before and after and before == after:
            match += 1
        else:
            mismatch += 1
    result["checksum"] = {
        "match": match,
        "mismatch": mismatch,
        "missing": missing,
    }

    # أخطاء: عدّ فقط (لا نصوص).
    err_count = sum(
        1
        for e in entries
        if isinstance(e, dict) and (e.get("error_message") or e.get("rollback_error_message"))
    )
    result["error_count"] = err_count

    return result


def main(argv):
    paths = argv[1:]
    if not paths:
        print("usage: undo_diag.py <undo.json> [...]", file=sys.stderr)
        return 2
    for p in paths:
        try:
            r = diagnose(p)
        except (OSError, json.JSONDecodeError) as e:
            print(f"=== {p} ===")
            print(f"  LOAD_ERROR: {type(e).__name__}")
            continue
        print(f"=== {r['path_label']} ===")
        print(f"  top_type: {r['top_type']}")
        print(f"  top_keys: {r['top_keys']}")
        print(f"  entry_count: {r['entry_count']}")
        print(f"  field_names: {r['field_names']}")
        print(f"  action_dist: {r['action_dist']}")
        print(f"  success_dist: {r['success_dist']}")
        print(f"  recovery_dist: {r['recovery_dist']}")
        print(
            f"  checksum: match={r['checksum']['match']} "
            f"mismatch={r['checksum']['mismatch']} "
            f"missing={r['checksum']['missing']}"
        )
        print(f"  error_count: {r['error_count']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))