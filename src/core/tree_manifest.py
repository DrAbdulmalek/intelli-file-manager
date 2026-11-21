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
from pathlib import Path
from datetime import datetime, timezone

__all__ = ["ManifestError", "snapshot", "verify"]

_VERSION = 1
_CHUNK = 1024 * 1024


class ManifestError(ValueError):
    """لقطة تالفة أو غير مدعومة."""


def _sha256(path: str) -> str:
    """sha256 بفتح آمن O_NOFOLLOW — لا يتبع رابطاً رمزياً عند الفتح."""
    h = hashlib.sha256()
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is not None:
        flags |= nofollow
    fd = os.open(path, flags)
    try:
        with os.fdopen(fd, "rb", closefd=False) as fh:
            for block in iter(lambda: fh.read(_CHUNK), b""):
                h.update(block)
    finally:
        os.close(fd)
    return h.hexdigest()


def _stat_no_follow(path: str) -> os.stat_result:
    """lstat مساعد — يرفع OSError كما هو."""
    return os.lstat(path)


def _stat_snapshot_matches(st1: os.stat_result, st2: os.stat_result) -> bool:
    """هل الحجم وmtime_ns متطابقان — لكشف تبدل الملف أثناء الهاش."""
    return st1.st_size == st2.st_size and st1.st_mtime_ns == st2.st_mtime_ns


def _reject_symlink_root(root: str) -> None:
    """يرفض جذر شجرة يحتوي أي مكوّن رابط رمزي (يتطلب جذر حقيقياً).

    سياسة السلامة: اللقطة دليل على نقل شجرة *حقيقية*؛ جذر symlink قد يشير
    إلى شجرة أخرى بين اللقطة والتحقق فينتج نجاحاً كاذباً.
    """
    absolute = Path(os.path.abspath(root))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            return  # سيُرفض لاحقاً بـ strict=True في resolve
        except OSError as exc:
            raise ManifestError(f"تعذّر فحص مكوّن الجذر: {current}") from exc
        if stat.S_ISLNK(info.st_mode):
            raise ManifestError(
                f"الجذر (أو أحد مكوّناته) رابط رمزي والسياسة تتطلب جذرًا حقيقياً: {absolute}"
            )


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
    """يكتب لقطة JSONL لـ ``root`` ويُرجع ملخصاً (files/dirs/symlinks/bytes/errors).

    السلامة: الجذر (وكل مكوّناته) يجب أن يكون مجلداً حقيقياً — أي رابط رمزي
    في المسار يُرفض (انظر ``_reject_symlink_root``).
    """
    _reject_symlink_root(os.fspath(root))
    root_path = Path(root).resolve(strict=True)
    if not root_path.is_dir():
        raise ManifestError(f"الجذر ليس مجلداً: {root_path}")
    root_s = os.fspath(root_path)
    out_resolved = Path(out_path).resolve(strict=False)
    if out_resolved == root_path or root_path in out_resolved.parents:
        raise ManifestError("يجب أن يكون ملف اللقطة خارج جذر المسح")
    summary = {"files": 0, "dirs": 0, "symlinks": 0, "bytes": 0, "errors": 0}
    try:
        out = open(out_resolved, "x", encoding="utf-8")
    except FileExistsError as exc:
        raise ManifestError(f"ملف اللقطة موجود مسبقاً ولن يُستبدل: {out_resolved}") from exc
    with out:
        header = {"type": "header", "version": _VERSION, "root": root_s,
                  "created": datetime.now(timezone.utc).isoformat(), "hash": hash_files}
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
                        # كشف تبدل الملف أثناء حساب الهاش: إعادة stat بعد
                        # القراءة (os.stat صريح — DirEntry.stat يخزّن
                        # النتيجة مؤقتاً فتعود نفس القيمة دائماً).
                        # fail-closed: لا يُكتب سجل للملف إطلاقاً فيصبح
                        # "missing" عند verify → ok=False (لا نجاح كاذب)
                        st_after = os.stat(entry.path, follow_symlinks=False)
                        if not _stat_snapshot_matches(st, st_after):
                            summary["errors"] += 1
                            out.write(json.dumps(
                                {"type": "error", "p": rel,
                                 "e": "mutated during hashing (size/mtime changed)"},
                                ensure_ascii=False) + "\n")
                            continue
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
    * أهداف الروابط الرمزية تُقارن نصياً — تغيّر الهدف = ``target_changed``
      ويرفض سلامة النقل.
    * تبدّل الملف أثناء حساب الهاش (قبل/بعد stat) يُسجّل ``hash_changed``.
    * أخطاء القراءة وقت اللقطة تجعل ``complete`` خطأ: لا يُدّعى سلامة ما لم يُقرأ.
    * الجذر (وكل مكوّناته) يجب أن يكون حقيقياً — روابط رمزية تُرفض.
    """
    _reject_symlink_root(os.fspath(new_root))
    header, records, snap_errors = _load(manifest_path)
    if check_hash and not header.get("hash"):
        raise ManifestError("اللقطة بلا sha256؛ أعدها مع hash_files=True")
    root_s = os.fspath(new_root)
    report = {"missing": [], "type_changed": [], "size_changed": [], "hash_changed": [],
              "target_changed": [], "extra": [], "unreadable": [], "checked": 0}
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
        if kind == "l":
            # سلامة هدف الرابط الرمزي: تغيّر الهدف بلا تغيّر النوع كان ينتج
            # نجاحاً كاذباً — الآن يُقارن الهدف النصي صراحةً
            try:
                current_target = os.readlink(entry.path)
            except OSError as exc3:
                report["unreadable"].append({"p": rel, "e": str(exc3)})
                continue
            if current_target != rec.get("t", ""):
                report["target_changed"].append(
                    {"p": rel, "was": rec.get("t", ""), "now": current_target}
                )
        elif kind == "f":
            if st.st_size != rec["s"]:
                report["size_changed"].append(rel)
            elif check_hash:
                try:
                    h = _sha256(entry.path)
                    # كشف تبدل الملف أثناء الهاش: مقارنة stat قبل/بعد القراءة
                    # (os.stat صريح — DirEntry.stat مخزّن مؤقتاً)
                    st_after = os.stat(entry.path, follow_symlinks=False)
                    if not _stat_snapshot_matches(st, st_after):
                        report["hash_changed"].append(
                            {"p": rel, "e": "mutated during hashing"}
                        )
                    elif h != rec["h"]:
                        report["hash_changed"].append(rel)
                except OSError as exc3:
                    report["unreadable"].append({"p": rel, "e": str(exc3)})
    report["extra"] = sorted(set(current) - seen)
    report["snapshot_errors"] = len(snap_errors)
    report["complete"] = not snap_errors and not report["unreadable"]
    bad = (report["missing"] or report["type_changed"] or report["size_changed"]
           or report["hash_changed"] or report["target_changed"]
           or (strict and report["extra"]))
    report["ok"] = bool(report["complete"] and not bad)
    return report
