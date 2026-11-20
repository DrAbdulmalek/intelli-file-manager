#!/usr/bin/env python3
"""CLI: ``snapshot ROOT OUT [--hash]`` قبل النقل، ``verify MANIFEST NEW_ROOT`` بعده.

رموز الخروج: 0 سليم، 1 فقد/اختلاف، 2 لقطة غير مكتملة أو خطأ استخدام.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.tree_manifest import ManifestError, snapshot, verify


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot")
    s.add_argument("root"); s.add_argument("out"); s.add_argument("--hash", action="store_true")
    v = sub.add_parser("verify")
    v.add_argument("manifest"); v.add_argument("new_root")
    v.add_argument("--hash", action="store_true"); v.add_argument("--strict", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "snapshot":
            print(json.dumps(snapshot(a.root, a.out, hash_files=a.hash), ensure_ascii=False))
            return 0
        rep = verify(a.manifest, a.new_root, check_hash=a.hash, strict=a.strict)
    except (ManifestError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    brief = {k: (len(val) if isinstance(val, list) else val) for k, val in rep.items()}
    print(json.dumps(brief, ensure_ascii=False))
    for key in ("missing", "type_changed", "size_changed", "hash_changed", "unreadable"):
        for item in rep[key][:20]:
            print(f"  {key}: {item}", file=sys.stderr)
    if not rep["complete"]:
        return 2
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
