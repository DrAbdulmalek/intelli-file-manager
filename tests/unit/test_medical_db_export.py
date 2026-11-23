# -*- coding: utf-8 -*-
"""اختبارات P1 المُقوّاة: export_deidentified + حقن الفشل + تنظيف المؤقت.

بيانات اصطناعية عامة فقط — لا مريض حقيقي.
"""
from __future__ import annotations

import os
import sqlite3

import pytest

from src.core import medical_db as mdb_mod
from src.core.medical_db import ExportError, MedicalDB


@pytest.fixture()
def clinic(tmp_path):
    db = MedicalDB(tmp_path / "clinic.db").init()
    pid = db.add_patient(name="مريض اصطناعي", age="40", sex="m",
                         notes="ملاحظة اصطناعية للاختبار")
    db.add_record(pid, "2026-01-01", "report",
                  source_path="/confidential/identity-report.pdf",
                  sha256="a" * 64,
                  summary="ملخص اصطناعي عام",
                  findings={"hemoglobin": "13"})
    plain = tmp_path / "plain.txt"
    plain.write_text("عادي", encoding="utf-8")
    db.register_file(str(plain))
    # الحالة الأساسية تُلتقط بعد كل الإعداد — التصدير يجب ألا يغيّر شيئاً
    yield db, tmp_path, (tmp_path / "clinic.db").read_bytes()
    db.close()


def _parts(tmp_path):
    return list(tmp_path.glob(".ifm_export_*.part"))


def _log_count(db):
    return db._conn.execute("SELECT COUNT(*) c FROM processing_log").fetchone()["c"]


# ─── Finding 1: سلامة المصدر الفعلية ─────────────────────────────────────

def test_export_success_source_untouched(clinic):
    db, tmp_path, before = clinic
    logs_before = _log_count(db)
    out = tmp_path / "publish.db"
    res = db.export_deidentified(out)
    assert out.exists()
    assert res["free_text_policy"] == "verbatim"
    assert res["logged_in_source_db"] is False
    # الحالة الفعلية بالبايت لا ادعاء التوثيق
    assert (tmp_path / "clinic.db").read_bytes() == before
    assert _log_count(db) == logs_before


def test_exported_db_valid_and_openable(clinic):
    db, tmp_path, _ = clinic
    out = tmp_path / "publish.db"
    db.export_deidentified(out)
    con = sqlite3.connect(str(out))
    con.row_factory = sqlite3.Row
    n = con.execute("SELECT COUNT(*) c FROM patients").fetchone()["c"]
    assert n == 1
    for row in con.execute("SELECT name, age, sex, notes FROM patients"):
        assert row["name"] is None and row["age"] is None
        assert row["sex"] is None and row["notes"] is None
    for row in con.execute("SELECT source_path, sha256, summary, findings FROM records"):
        assert row["source_path"] is None and row["sha256"] is None
        assert row["summary"] == "ملخص اصطناعي عام"
        assert "hemoglobin" in (row["findings"] or "")
    assert con.execute("SELECT COUNT(*) c FROM files").fetchone()["c"] == 0
    con.close()


# ─── Finding 2: تنظيف الملف المؤقت في كل المسارات ────────────────────────

def test_no_part_files_after_success(clinic):
    db, tmp_path, _ = clinic
    db.export_deidentified(tmp_path / "publish.db")
    assert _parts(tmp_path) == []


def test_mkstemp_failure_cleans(clinic, monkeypatch):
    db, tmp_path, _ = clinic
    def boom(*a, **k):
        raise OSError("حقن فشل mkstemp")
    monkeypatch.setattr(mdb_mod.tempfile, "mkstemp", boom)
    with pytest.raises(ExportError, match="المؤقتة"):
        db.export_deidentified(tmp_path / "out.db")
    assert not (tmp_path / "out.db").exists()
    assert _parts(tmp_path) == []


def test_writer_failure_cleans(clinic, monkeypatch):
    db, tmp_path, before = clinic
    logs_before = _log_count(db)
    def boom(self, tmp_file):
        raise RuntimeError("حقن فشل كتابة النسخة")
    monkeypatch.setattr(MedicalDB, "_write_deidentified_copy", boom)
    with pytest.raises(RuntimeError, match="حقن فشل"):
        db.export_deidentified(tmp_path / "out.db")
    assert not (tmp_path / "out.db").exists()
    assert _parts(tmp_path) == []
    assert (tmp_path / "clinic.db").read_bytes() == before
    assert _log_count(db) == logs_before


def test_fsync_failure_cleans(clinic, monkeypatch):
    db, tmp_path, _ = clinic
    def boom(fd):
        raise OSError("حقن فشل fsync")
    monkeypatch.setattr(mdb_mod.os, "fsync", boom)
    with pytest.raises(OSError, match="fsync"):
        db.export_deidentified(tmp_path / "out.db")
    # لم يُنشر شيء — لا وجهة ولا مؤقت متبقٍ
    assert not (tmp_path / "out.db").exists()
    assert _parts(tmp_path) == []


def test_publish_race_failure_cleans(clinic, monkeypatch):
    db, tmp_path, _ = clinic
    def boom(src, dst):
        raise FileExistsError("حقن سباق نشر")
    monkeypatch.setattr(mdb_mod.os, "link", boom)
    with pytest.raises(ExportError, match="سباق"):
        db.export_deidentified(tmp_path / "out.db")
    assert not (tmp_path / "out.db").exists()
    assert _parts(tmp_path) == []


def test_preexisting_dest_untouched(clinic):
    db, tmp_path, _ = clinic
    out = tmp_path / "publish.db"
    out.write_bytes(b"PRECIOUS EXISTING DATA")
    with pytest.raises(ExportError, match="No-Clobber"):
        db.export_deidentified(out)
    assert out.read_bytes() == b"PRECIOUS EXISTING DATA"
    assert _parts(tmp_path) == []


def test_overwrite_explicit_only(clinic):
    db, tmp_path, _ = clinic
    out = tmp_path / "publish.db"
    out.write_bytes(b"OLD")
    db.export_deidentified(out, overwrite=True)
    assert out.read_bytes()[:16] == b"SQLite format 3\x00"
    assert _parts(tmp_path) == []


# ─── حظر تطابق المصدر/الوجهة ─────────────────────────────────────────────

def test_reject_source_equals_dest(clinic, tmp_path):
    db, _, _ = clinic
    with pytest.raises(ExportError, match="يطابق"):
        db.export_deidentified(tmp_path / "clinic.db")


def test_reject_symlink_to_source(clinic, tmp_path):
    db, _, _ = clinic
    link = tmp_path / "link.db"
    os.symlink(tmp_path / "clinic.db", link)
    with pytest.raises(ExportError):
        db.export_deidentified(link)
    assert (tmp_path / "clinic.db").exists()


def test_reject_relative_path_equivalent_to_source(clinic, tmp_path, monkeypatch):
    db, _, _ = clinic
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ExportError):
        db.export_deidentified("clinic.db")
