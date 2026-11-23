# -*- coding: utf-8 -*-
"""اختبارات TOCTOU لـ register_file — تحقق هوية ثلاثي (مراجعة مستقلة Finding 7).

كل حالة تُحاكي عبر غلاف open_checked القابل للحقن: لا اختبار واحد يُفترض
أنه يثبت كل الحالات.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from src.core import medical_db as mdb
from src.core.medical_db import MedicalDB


class _Wrap:
    """غلاف ملف قابل للحقن: on_read (أثناء القراءة) و on_exit (بعد الإغلاق)."""
    def __init__(self, real, on_read=None, on_exit=None):
        self._real = real
        self._on_read = on_read
        self._on_exit = on_exit
        self._reads = 0
    def read(self, n):
        data = self._real.read(n)
        self._reads += 1
        if self._on_read and self._reads == 1:
            self._on_read()
        return data
    def seek(self, offset, whence=0):
        return self._real.seek(offset, whence)
    def fileno(self):
        return self._real.fileno()
    def __enter__(self):
        return self
    def __exit__(self, *a):
        try:
            self._real.close()
        finally:
            if self._on_exit:
                self._on_exit()


def _patch_open(monkeypatch, on_read=None, on_exit=None, open_target=None):
    def fake(path, mode, operation=None):
        target = str(open_target) if open_target is not None else str(path)
        return _Wrap(open(target, mode), on_read=on_read, on_exit=on_exit)
    monkeypatch.setattr(mdb, "open_checked", fake)


@pytest.fixture()
def clinic(tmp_path):
    db = MedicalDB(tmp_path / "c.db").init()
    yield db, tmp_path
    db.close()


def _registered_sha(db):
    rows = db.list_files()
    assert len(rows) == 1
    return rows[0]["sha256"]


def test_positive_control_hash_matches(clinic):
    db, tmp_path = clinic
    p = tmp_path / "plain.txt"
    p.write_text("محتوى سليم", encoding="utf-8")
    res = db.register_file(str(p))
    assert res["readable_in_current_mode"] is True
    expected = hashlib.sha256("محتوى سليم".encode("utf-8")).hexdigest()
    assert res["sha256"] == expected
    assert _registered_sha(db) == expected


def test_swapped_before_open_no_sha(clinic, monkeypatch):
    db, tmp_path = clinic
    p = tmp_path / "plain.txt"; p.write_text("الأصل", encoding="utf-8")
    decoy = tmp_path / "decoy.txt"; decoy.write_text("الذييل — مختلف", encoding="utf-8")
    _patch_open(monkeypatch, open_target=decoy)
    res = db.register_file(str(p))
    # الهوية المفتوحة لا تطابق المطلوب — لا بصمة تُخزَّن
    assert res["sha256"] is None
    assert _registered_sha(db) is None


def test_swapped_during_read_no_sha(clinic, monkeypatch):
    db, tmp_path = clinic
    p = tmp_path / "plain.txt"; p.write_text("x" * 500, encoding="utf-8")
    def swap():
        os.unlink(p)
        p.write_text("hijacked — محتوى مختلف كلياً", encoding="utf-8")
    _patch_open(monkeypatch, on_read=swap)
    res = db.register_file(str(p))
    assert res["sha256"] is None
    assert _registered_sha(db) is None


def test_content_mutated_same_inode_no_sha(clinic, monkeypatch):
    db, tmp_path = clinic
    p = tmp_path / "plain.txt"; p.write_text("y" * 300, encoding="utf-8")
    def mutate():
        fd = os.open(str(p), os.O_WRONLY)
        try:
            os.write(fd, b"zzz")
            os.ftruncate(fd, 3)
        finally:
            os.close(fd)
    _patch_open(monkeypatch, on_read=mutate)
    res = db.register_file(str(p))
    assert res["sha256"] is None
    assert _registered_sha(db) is None


def test_deleted_after_read_no_sha(clinic, monkeypatch):
    db, tmp_path = clinic
    p = tmp_path / "plain.txt"; p.write_text("حُذف بعد القراءة", encoding="utf-8")
    def gone():
        os.unlink(p)
    _patch_open(monkeypatch, on_exit=gone)
    res = db.register_file(str(p))
    assert res["sha256"] is None
    assert _registered_sha(db) is None


def test_path_becomes_symlink_after_read_no_sha(clinic, monkeypatch):
    db, tmp_path = clinic
    p = tmp_path / "plain.txt"; p.write_text("سليم", encoding="utf-8")
    decoy = tmp_path / "decoy2.txt"; decoy.write_text("مخالف", encoding="utf-8")
    def to_symlink():
        os.unlink(p)
        os.symlink(decoy, p)
    _patch_open(monkeypatch, on_exit=to_symlink)
    res = db.register_file(str(p))
    assert res["sha256"] is None
    assert _registered_sha(db) is None


# ─── F8: استكمال TOCTOU — تغيّر المحتوى مع ثبات الحجم/الـinode ──────────
# (المراجعة المستقلة F8: مقارنة mtime_ns/ctime_ns + lstat بعد القراءة)

def test_f8_same_size_content_swap_no_sha(clinic, monkeypatch):
    """تعديل المحتوى أثناء القراءة مع بقاء الحجم نفسه — يجب كشفه."""
    db, tmp_path = clinic
    p = tmp_path / "plain.txt"; p.write_text("a" * 500, encoding="utf-8")
    def same_size_swap():
        # كتابة محتوى مختلف تماماً بنفس الطول بالضبط
        fd = os.open(str(p), os.O_WRONLY)
        try:
            os.write(fd, b"Z" * 500)
        finally:
            os.close(fd)
    _patch_open(monkeypatch, on_read=same_size_swap)
    res = db.register_file(str(p))
    assert res["sha256"] is None
    assert _registered_sha(db) is None


def test_f8_mutate_then_restore_size_no_sha(clinic, monkeypatch):
    """تعديل المحتوى ثم إعادة الحجم الأصلي — الحجم يتطابق لكن الأوقات لا."""
    db, tmp_path = clinic
    p = tmp_path / "plain.txt"; p.write_text("b" * 400, encoding="utf-8")
    def mutate_and_restore_size():
        # الكتابة فوق البداية (محتوى مختلف) ثم إعادة الحجم الأصلي —
        # الحجم يتطابق لكن المحتوى والأوقات لا
        fd = os.open(str(p), os.O_WRONLY)
        try:
            os.write(fd, b"injected-junk" + b"x" * 437)  # 450 بايت
            os.ftruncate(fd, 400)  # إعادة الحجم الأصلي بمحتوى مختلف
        finally:
            os.close(fd)
    _patch_open(monkeypatch, on_read=mutate_and_restore_size)
    res = db.register_file(str(p))
    assert res["sha256"] is None
    assert _registered_sha(db) is None


def test_f8_mutate_with_mtime_restored_still_detected(clinic, monkeypatch):
    """إخفاء التعديل بإعادة ضبط mtime — ctime لا يمكن إعادة ضبطه فيُكشف."""
    db, tmp_path = clinic
    p = tmp_path / "plain.txt"; p.write_text("c" * 300, encoding="utf-8")
    old = p.stat()
    def stealth_mutate():
        fd = os.open(str(p), os.O_WRONLY)
        try:
            os.write(fd, b"Q" * 300)
            os.utime(str(p), ns=(old.st_atime_ns, old.st_mtime_ns))
        finally:
            os.close(fd)
    _patch_open(monkeypatch, on_read=stealth_mutate)
    res = db.register_file(str(p))
    assert res["sha256"] is None
    assert _registered_sha(db) is None


def test_f8_same_size_inode_swap_no_sha(clinic, monkeypatch):
    """استبدال الـinode بمحاكاة (unlink + إنشاء جديد بنفس الحجم)."""
    db, tmp_path = clinic
    p = tmp_path / "plain.txt"; p.write_text("d" * 250, encoding="utf-8")
    def swap_inode_same_size():
        os.unlink(p)
        p.write_text("E" * 250, encoding="utf-8")  # inode جديد، حجم مطابق
    _patch_open(monkeypatch, on_read=swap_inode_same_size)
    res = db.register_file(str(p))
    assert res["sha256"] is None
    assert _registered_sha(db) is None


def test_f8_symlink_to_same_target_after_read_no_sha(clinic, monkeypatch):
    """استبدال المسار برابط رمزي **إلى نفس الملف** — stat العادي كان
    سيمرّ (نفس dev/ino عبر التابع)؛ lstat يكشف الرابط ويرفض."""
    db, tmp_path = clinic
    p = tmp_path / "plain.txt"; p.write_text("سليم-نفس-الهدف", encoding="utf-8")
    real = tmp_path / "real.bin"
    def to_symlink_same_target():
        # ننقل الملف الحقيقي ونجعل الاسم الأصلي رابطاً رمزياً إليه —
        # نفس الـinode، نفس المحتوى: الحالة الأكثر ملتبسة
        os.rename(p, real)
        os.symlink(real, p)
    _patch_open(monkeypatch, on_exit=to_symlink_same_target)
    res = db.register_file(str(p))
    assert res["sha256"] is None
    assert _registered_sha(db) is None



def test_f8_replaced_after_initial_stat_before_hash_no_sha(clinic, monkeypatch):
    """استبدال الملف بعد stat الأول وقبل حساب البصمة لا يربط بصمة البديل ببيانات الأصل."""
    db, tmp_path = clinic
    p = tmp_path / "plain.txt"
    p.write_text("original-file", encoding="utf-8")
    real_classify = mdb.classify_sensitivity

    def replace_after_initial_stat(path):
        info = real_classify(path)
        replacement = tmp_path / "replacement.txt"
        replacement.write_text("replacement!", encoding="utf-8")
        os.replace(replacement, p)
        return info

    monkeypatch.setattr(mdb, "classify_sensitivity", replace_after_initial_stat)
    res = db.register_file(str(p))
    assert res["sha256"] is None
    assert _registered_sha(db) is None
    assert p.read_text(encoding="utf-8") == "replacement!"
