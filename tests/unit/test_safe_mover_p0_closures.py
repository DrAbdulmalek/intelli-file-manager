# -*- coding: utf-8 -*-
"""اختبارات إغلاق عيوب جولة DeepSeek 7 و11 (2026-11-20) في safe_mover وundo_log.

العيوب المغطاة:
  1. IsADirectoryError كان يُبتلع صامتاً بـexcept OSError: pass في
     _atomic_move و_atomic_copy (IsADirectoryError صنف فرعي من OSError).
  2. فجوة TOCTOU في فرع EXDEV و_atomic_copy: os.replace(tmp, dst)
     يستبدل صامتاً إن ظهرت الوجهة بين الفحص والكتابة — الآن os.link
     (يرفض ذرياً)، والفشل مغلق إذا لم يدعم النظام النشر دون استبدال.
  3. فشل src.unlink بعد ربط/نسخ ناجح كان يترك حالة «كلاهما موجود» غير
     موثقة — الآن يُزال أثر العملية ويرفع خطأ صريح.
  4. دمج sidecar عند التراجع عن نقل كان يحذف sidecar الشاغل صامتاً
     (dst_sidecar.unlink()) — الآن لاحقة عبر SafeMover (لاحقة لا استبدال).
  5. _rollback_copy يحذف النسخة المنشأة مباشرة (استثناء معتمد موثق) —
     لكن مع حارس checksum: إن عُدّل الملف بعد نسخه يُرفض التراجع.
"""
import errno
import os
import pathlib

import pytest

from src.core import safe_mover as sm
from src.core.rule_schemas import ActionType, UndoEntry
from src.core.safe_mover import SafeMover, _atomic_copy, _atomic_move, compute_sha256
from src.core.undo_log import UndoLog


# ─── 1) رفض المجلد يُرفع فعلاً (لا ابتلاع) ─────────────────────────────────

def test_atomic_copy_refuses_directory(tmp_path):
    """النسخ فوق مجلد موجود يرفع IsADirectoryError قبل أي عمل — لا ابتلاع."""
    src = tmp_path / "file.txt"
    src.write_text("DATA")
    target_dir = tmp_path / "existing_dir"
    target_dir.mkdir()

    with pytest.raises(IsADirectoryError):
        _atomic_copy(src, target_dir)


def test_atomic_move_refuses_directory(tmp_path):
    """النقل فوق مجلد موجود يرفع IsADirectoryError قبل أي عمل — لا ابتلاع."""
    src = tmp_path / "file.txt"
    src.write_text("DATA")
    target_dir = tmp_path / "existing_dir"
    target_dir.mkdir()

    with pytest.raises(IsADirectoryError):
        _atomic_move(src, target_dir)


# ─── 2) سباق ما بعد الفحص: ظهور الوجهة لا يعني استبدالها ──────────────────

def test_atomic_copy_rejects_dst_created_mid_flight(tmp_path, monkeypatch):
    """إن ظهرت الوجهة بين الفحص والكتابة (سباق) — يُرفض بدل الاستبدال الصامت."""
    src = tmp_path / "src.txt"
    src.write_text("SRC-CONTENT")
    dst = tmp_path / "dst.txt"
    real_link = os.link

    def racing_link(path1, path2, *args, **kwargs):
        # يحاكي سباقاً: عملية أخرى أنشأت الوجهة لحظة الربط
        pathlib.Path(path2).write_text("RACE-OCCUPANT")
        return real_link(path1, path2, *args, **kwargs)

    monkeypatch.setattr(os, "link", racing_link)

    with pytest.raises(FileExistsError):
        _atomic_copy(src, dst)

    assert dst.read_text() == "RACE-OCCUPANT"  # الشاغل سليم — لا استبدال
    assert not list(tmp_path.glob(".ifm_tmp_*"))  # المؤقت نُظّف


def test_atomic_move_exdev_rejects_dst_created_mid_flight(tmp_path, monkeypatch):
    """فرع EXDEV: بعد النسخ للمؤقت، ظهور الوجهة يُرفض ذرياً (لا os.replace صامت)."""
    src = tmp_path / "src.txt"
    src.write_text("SRC-CONTENT")
    dst = tmp_path / "dst.txt"
    real_link = os.link
    calls = {"n": 0}

    def fake_link(path1, path2, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            # المسار الأساسي: EXDEV لإجبار الفرع العابر للأجهزة
            raise OSError(errno.EXDEV, "cross-device link not permitted")
        # ربط المؤقت إلى الوجهة: يحاكي سباقاً — الشاغل ظهر لحظة الربط
        pathlib.Path(path2).write_text("RACE-OCCUPANT")
        return real_link(path1, path2, *args, **kwargs)

    monkeypatch.setattr(sm, "_renameat2_available", False)
    monkeypatch.setattr(os, "link", fake_link)

    with pytest.raises(FileExistsError):
        _atomic_move(src, dst)

    assert dst.read_text() == "RACE-OCCUPANT"  # الشاغل سليم
    assert src.read_text() == "SRC-CONTENT"  # المصدر لم يُمس
    assert not list(tmp_path.glob(".ifm_tmp_*"))


# ─── 3) فشل حذف المصدر بعد نجاح الربط: لا حالة «كلاهما موجود» ─────────────

def test_move_reports_failure_when_source_unlink_fails(tmp_path, monkeypatch):
    """فشل unlink للمصدر بعد ربط ناجح: يُزال الرابط، المصدر سليم، فشل صريح."""
    src = tmp_path / "src.txt"
    src.write_text("PRECIOUS")
    dst = tmp_path / "dst.txt"
    real_unlink = pathlib.Path.unlink

    def failing_unlink(self, *args, **kwargs):
        if str(self) == str(src):
            raise OSError(errno.EACCES, "Permission denied")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "unlink", failing_unlink)

    mover = SafeMover(verify_checksum=False)
    result = mover.move(str(src), str(dst))

    assert not result.success
    assert "فشل حذف المصدر" in (result.error or "")
    assert src.exists() and src.read_text() == "PRECIOUS"
    assert not dst.exists()  # الرابط أُزيل — لا حالة «كلاهما موجود»


# ─── 4) دمج sidecar عند التراجع: لاحقة لا حذف الشاغل ──────────────────────

def _sidecar_for(p):
    return p.parent / f".ifm_meta_{p.name}.json"


def test_rollback_move_sidecar_merge_preserves_existing_sidecar(tmp_path):
    """شاغل sidecar في وجهة التراجع يبقى سليمًا — المرتد يأخذ لاحقة (DeepSeek 11).

    الكود القديم كان يفعل dst_sidecar.unlink() — حذف صامت لبيانات الشاغل.
    """
    docs = tmp_path / "documents"
    downloads = tmp_path / "downloads"
    docs.mkdir()
    downloads.mkdir()

    orig = downloads / "report.txt"
    moved = docs / "report.txt"
    moved.write_text("CONTENT")
    _sidecar_for(moved).write_text('{"tags": ["restored"]}')

    # شاغل sidecar في مسار التراجع (سيرجع الملف إلى downloads/report.txt)
    occupant_sidecar = _sidecar_for(orig)
    occupant_sidecar.write_text('{"tags": ["occupant-data"]}')

    log = UndoLog()
    log.append(UndoEntry(
        action_type=ActionType.MOVE.value,
        file_path=str(orig),
        file_path_after=str(moved),
        success=True,
    ))

    rolled = log.rollback_last()
    assert rolled is not None and rolled.success

    # شاغل الـsidecar سليم — لم يُحذف
    assert occupant_sidecar.exists()
    assert "occupant-data" in occupant_sidecar.read_text()
    # sidecar المرتد موجود باللاحقة (لا استبدال ولا فقد)
    restored_sidecars = list(downloads.glob(".ifm_meta_report*.json"))
    assert len(restored_sidecars) == 2
    assert any("restored" in sc.read_text() for sc in restored_sidecars)


# ─── 5) _rollback_copy: استثناء معتمد + حارس checksum ─────────────────────

def _make_copy_entry(tmp_path, content="COPIED-CONTENT", record_checksum=True):
    """ينفّذ نسخاً فعلياً ويسجّل UndoEntry كما يفعل RuleEngine._exec_copy."""
    orig = tmp_path / "original.txt"
    orig.write_text("SOURCE")
    copied = tmp_path / "copy.txt"
    copied.write_text(content)
    entry = UndoEntry(
        action_type=ActionType.COPY.value,
        file_path=str(orig),
        file_path_after=str(copied),
        success=True,
        checksum_after=compute_sha256(copied) if record_checksum else None,
    )
    return copied, entry


def test_rollback_copy_deletes_unmodified_copy(tmp_path):
    """التراجع عن نسخة لم تُعدّل: تُحذف (استثناء الحذف المباشر المعتمد)."""
    copied, entry = _make_copy_entry(tmp_path)
    log = UndoLog()
    log.append(entry)

    log.rollback_last()

    assert not copied.exists()


def test_rollback_copy_refuses_modified_copy(tmp_path):
    """نسخة عُدّلت بعد إنشائها: التراجع يُرفض صراحة — تعديلات المستخدم محمية."""
    copied, entry = _make_copy_entry(tmp_path)
    copied.write_text("USER-EDITED-AFTER-COPY")  # تعديل لاحق للنسخ
    log = UndoLog()
    log.append(entry)

    # عقد rollback_last: الفشل يُرجع القيد مع success=False (لا استثناء)
    rolled = log.rollback_last()

    assert rolled is not None and not rolled.success
    assert "عُدّل الملف بعد إنشائه" in rolled.error_message
    # تعديلات المستخدم سليمة — لم تُحذف
    assert copied.exists()
    assert copied.read_text() == "USER-EDITED-AFTER-COPY"


def test_rollback_copy_unrecorded_checksum_still_deletes(tmp_path):
    """قيد قديم بلا checksum (سجلات قبل الإصلاح): السلوك الحذف يعمل كالسابق."""
    copied, entry = _make_copy_entry(tmp_path, record_checksum=False)
    log = UndoLog()
    log.append(entry)

    log.rollback_last()

    assert not copied.exists()



# ─── 6) لا fallback إلى os.replace عند غياب hard-link ─────────────────────

def test_atomic_copy_fails_closed_without_noreplace_primitive(tmp_path, monkeypatch):
    """غياب hard-link لا يجيز os.replace؛ المصدر والوجهة يبقيان سليمين."""
    src = tmp_path / "src.txt"
    src.write_text("SOURCE")
    dst = tmp_path / "dst.txt"

    def unsupported_link(*args, **kwargs):
        raise OSError(errno.EOPNOTSUPP, "hard links unsupported")

    def forbidden_replace(*args, **kwargs):
        raise AssertionError("os.replace must never be used as no-clobber fallback")

    monkeypatch.setattr(os, "link", unsupported_link)
    monkeypatch.setattr(os, "replace", forbidden_replace)

    with pytest.raises(OSError, match="تعذر النشر الذري دون استبدال"):
        _atomic_copy(src, dst)

    assert src.read_text() == "SOURCE"
    assert not dst.exists()
    assert not list(tmp_path.glob(".ifm_tmp_*"))


def test_atomic_move_exdev_fails_closed_without_noreplace_primitive(tmp_path, monkeypatch):
    """فرع EXDEV يفشل مغلقاً إذا تعذر hard-link؛ لا يستبدل الوجهة."""
    src = tmp_path / "src.txt"
    src.write_text("SOURCE")
    dst = tmp_path / "dst.txt"
    calls = {"count": 0}

    def unsupported_link(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError(errno.EXDEV, "cross-device")
        raise OSError(errno.EOPNOTSUPP, "hard links unsupported")

    def forbidden_replace(*args, **kwargs):
        raise AssertionError("os.replace must never be used as no-clobber fallback")

    monkeypatch.setattr(sm, "_renameat2_available", False)
    monkeypatch.setattr(os, "link", unsupported_link)
    monkeypatch.setattr(os, "replace", forbidden_replace)

    with pytest.raises(OSError, match="تعذر النشر الذري دون استبدال"):
        _atomic_move(src, dst)

    assert src.read_text() == "SOURCE"
    assert not dst.exists()
    assert not list(tmp_path.glob(".ifm_tmp_*"))
