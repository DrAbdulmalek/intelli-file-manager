"""لقطة/تحقق للأشجار: دليل على أن نقل مجلد كامل لم يفقد شيئاً.

سبب الوجود: ``SafeMover`` ملفّي فقط (انظر docs/SAFE_MOVER_HARDENING.md) بينما نقل
الوكيل المحلي مجلدات بأحجام مئات الجيجابايت بأوامر ``mv`` خام وكتب في لوغه ✅ دون
أي دليل قابل للفحص. هنا:

* ``snapshot``  قبل النقل: يكتب JSONL (مسار نسبي، نوع، حجم، mtime، sha256 اختياري).
* ``verify``    بعد النقل: يقارن الموقع الجديد باللقطة ويُرجع تقريراً صريحاً.

لا يتبع الروابط الرمزية، ولا يتخطى المخفي (فحص السلامة يجب أن يرى كل شيء)،
ويسجّل ما تعذّر قراءته كـ ``error`` بدل إسقاطه بصمت.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
from datetime import UTC, datetime

__all__ = ["ManifestError", "snapshot", "verify"]

_VERSION = 1
_CHUNK = 1024 * 1024


class ManifestError(ValueError):
    """لقطة تالفة أو غير مدعومة."""


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(_CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def _walk(root: str):
    """يولّد (مسار_نسبي, entry|None, خطأ|None) بترتيب حتمي، دون اتباع الروابط."""
    stack = [""]
    while stack:
        rel_dir = stack.pop()
        abs_dir = os.path.join(root, rel_dir) if rel_dir else root
        try:
            with os.scandir(abs_dir) as it:
                entries = sorted(it, key=lambda e: e.name)
        except OSError as exc:
            yield rel_dir, None, exc
            continue
        subdirs = []
        for entry in entries:
            rel = f"{rel_dir}/{entry.name}" if rel_dir else entry.name
            yield rel, entry, None
            try:
                if entry.is_dir(follow_symlinks=False):
                    subdirs.append(rel)
            except OSError as exc:
                yield rel, None, exc
        stack.extend(reversed(subdirs))


def snapshot(root: str | os.PathLike[str], out_path: str | os.PathLike[str], *,
             hash_files: bool = False) -> dict:
    """يكتب لقطة JSONL لـ ``root`` ويُرجع ملخصاً (files/dirs/symlinks/bytes/errors)."""
    root_s = os.fspath(root)
    if not os.path.isdir(root_s):
        raise ManifestError(f"الجذر ليس مجلداً: {root_s}")
    summary = {"files": 0, "dirs": 0, "symlinks": 0, "bytes": 0, "errors": 0}
    with open(out_path, "w", encoding="utf-8") as out:
        header = {"type": "header", "version": _VERSION, "root": root_s,
                  "created": datetime.now(UTC).isoformat(), "hash": hash_files}
        out.write(json.dumps(header, ensure_ascii=False) + "\n")
        for rel, entry, exc in _walk(root_s):
            if exc is not None:
                summary["errors"] += 1
                out.write(json.dumps({"type": "error", "p": rel, "e": str(exc)},
                                     ensure_ascii=False) + "\n")
                continue
            try:
                st = entry.stat(follow_symlinks=False)
                mode = st.st_mode
                if stat.S_ISLNK(mode):
                    rec = {"p": rel, "k": "l", "t": os.readlink(entry.path)}
                    summary["symlinks"] += 1
                elif stat.S_ISDIR(mode):
                    rec = {"p": rel, "k": "d"}
                    summary["dirs"] += 1
                elif stat.S_ISREG(mode):
                    rec = {"p": rel, "k": "f", "s": st.st_size, "m": st.st_mtime_ns}
                    if hash_files:
                        rec["h"] = _sha256(entry.path)
                    summary["files"] += 1
                    summary["bytes"] += st.st_size
                else:
                    rec = {"p": rel, "k": "o"}   # FIFO/socket/device: تُسجَّل ولا تُقرأ
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            except OSError as exc2:
                summary["errors"] += 1
                out.write(json.dumps({"type": "error", "p": rel, "e": str(exc2)},
                                     ensure_ascii=False) + "\n")
    return summary


def _load(manifest_path: str | os.PathLike[str]):
    header, records, errors = None, {}, []
    with open(manifest_path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ManifestError(f"سطر تالف {n}: {exc}") from exc
            if obj.get("type") == "header":
                if obj.get("version") != _VERSION:
                    raise ManifestError(f"إصدار غير مدعوم: {obj.get('version')}")
                header = obj
            elif obj.get("type") == "error":
                errors.append(obj)
            else:
                records[obj["p"]] = obj
    if header is None:
        raise ManifestError("اللقطة بلا ترويسة")
    return header, records, errors


def verify(manifest_path: str | os.PathLike[str], new_root: str | os.PathLike[str], *,
           check_hash: bool = False, strict: bool = False) -> dict:
    """يقارن ``new_root`` باللقطة. ``ok`` صحيح فقط دون أي فقد/اختلاف.

    * ``strict``: الملفات الزائدة (غير الموجودة في اللقطة) تُعدّ فشلاً.
    * ``check_hash``: يقارن sha256 (يتطلب لقطة مأخوذة بـ hash_files=True).
    * أخطاء القراءة وقت اللقطة تجعل ``complete`` خطأ: لا يُدّعى سلامة ما لم يُقرأ.
    """
    header, records, snap_errors = _load(manifest_path)
    if check_hash and not header.get("hash"):
        raise ManifestError("اللقطة بلا sha256؛ أعدها مع hash_files=True")
    root_s = os.fspath(new_root)
    report = {"missing": [], "type_changed": [], "size_changed": [], "hash_changed": [],
              "extra": [], "unreadable": [], "checked": 0}
    seen = set()
    current = {}
    for rel, entry, exc in _walk(root_s) if os.path.isdir(root_s) else ():
        if exc is not None:
            report["unreadable"].append({"p": rel, "e": str(exc)})
            continue
        current[rel] = entry
    for rel, rec in records.items():
        entry = current.get(rel)
        if entry is None:
            report["missing"].append(rel)
            continue
        seen.add(rel)
        report["checked"] += 1
        try:
            st = entry.stat(follow_symlinks=False)
        except OSError as exc2:
            report["unreadable"].append({"p": rel, "e": str(exc2)})
            continue
        kind = ("l" if stat.S_ISLNK(st.st_mode) else "d" if stat.S_ISDIR(st.st_mode)
                else "f" if stat.S_ISREG(st.st_mode) else "o")
        if kind != rec["k"]:
            report["type_changed"].append(rel)
            continue
        if kind == "f":
            if st.st_size != rec["s"]:
                report["size_changed"].append(rel)
            elif check_hash:
                try:
                    if _sha256(entry.path) != rec["h"]:
                        report["hash_changed"].append(rel)
                except OSError as exc3:
                    report["unreadable"].append({"p": rel, "e": str(exc3)})
    report["extra"] = sorted(set(current) - seen)
    report["snapshot_errors"] = len(snap_errors)
    report["complete"] = not snap_errors and not report["unreadable"]
    bad = (report["missing"] or report["type_changed"] or report["size_changed"]
           or report["hash_changed"] or (strict and report["extra"]))
    report["ok"] = bool(report["complete"] and not bad)
    return report
