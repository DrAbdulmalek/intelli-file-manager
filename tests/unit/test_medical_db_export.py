# -*- coding: utf-8 -*-
"""اختبارات P1: export_deidentified الآمن الذري (No-Clobber، حظر تطابق المصدر/الوجهة).

بيانات اصطناعية عامة فقط — لا مريض حقيقي.
"""
from __future__ import annotations

import os
import sqlite3

import pytest

from src.core.medical_db import ExportError, MedicalDB


@pytest.fixture()
def clinic(tmp_path):
    db = MedicalDB(tmp_path / "clinic.db").init()
    pid = db.add_patient(name="مريض اصطناعي", age="40", sex="m",
                         notes="ملاحظة اصطناعية للاختبار")
    db.add_record(pid, "2026-01-01", "report",
                  source_path="/ confidential/identity-report.pdf",
                  sha256="a" * 64,
                  summary="ملخص اصطناعي عام",
                  findings={"hemoglobin": "13"})
    plain = tmp_path / "plain.txt"; plain.write_text("عادي", encoding="utf-8")
    db.register_file(str(plain))
    yield db
    db.close()


def test_export_success_and_source_untouched(clinic, tmp_path):
    src_bytes = (tmp_path / "clinic.db").read_bytes()
    out = tmp_path / "publish.db"
    res = clinic.export_deidentified(out)
    assert out.exists()
    assert res["free_text_policy"] == "verbatim"
    # قاعدة المصدر لم تتغير تماماً
    assert (tmp_path / "clinic.db").read_bytes() == src_bytes


def test_export_deidentification_content(clinic, tmp_path):
    out = tmp_path / "publish.db"
    clinic.export_deidentified(out)
    con = sqlite3.connect(str(out))
    con.row_factory = sqlite3.Row
    for row in con.execute("SELECT name, age, sex, notes FROM patients"):
        assert row["name"] is None and row["age"] is None
        assert row["sex"] is None and row["notes"] is None
    for row in con.execute("SELECT source_path, sha256, summary, findings FROM records"):
        assert row["source_path"] is None and row["sha256"] is None
        assert row["summary"] == "ملخص اصطناعي عام"   # نص حر: verbatim موثق
        assert "hemoglobin" in (row["findings"] or "")
    assert con.execute("SELECT COUNT(*) c FROM files").fetchone()["c"] == 0
    con.close()


def test_no_clobber_existing_dest_untouched(clinic, tmp_path):
    out = tmp_path / "publish.db"
    out.write_bytes(b"PRECIOUS EXISTING DATA")
    with pytest.raises(ExportError, match="No-Clobber"):
        clinic.export_deidentified(out)
    assert out.read_bytes() == b"PRECIOUS EXISTING DATA"


def test_overwrite_explicit_only(clinic, tmp_path):
    out = tmp_path / "publish.db"
    out.write_bytes(b"OLD")
    clinic.export_deidentified(out, overwrite=True)
    assert out.read_bytes()[:16] == b"SQLite format 3\x00"


def test_reject_source_equals_dest(tmp_path):
    db = MedicalDB(tmp_path / "same.db").init()
    try:
        with pytest.raises(ExportError, match="يطرابق|يطابق"):
            db.export_deidentified(tmp_path / "same.db")
    finally:
        db.close()


def test_reject_symlink_to_source(tmp_path):
    # الوجهة رابط رمزي يشير إلى قاعدة المصدر — يجب الرفض
    db = MedicalDB(tmp_path / "src.db").init()
    try:
        link = tmp_path / "link.db"
        os.symlink(tmp_path / "src.db", link)
        with pytest.raises(ExportError):
            db.export_deidentified(link)
        assert (tmp_path / "src.db").exists()
    finally:
        db.close()


def test_reject_relative_path_equivalent_to_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = MedicalDB(tmp_path / "rel.db").init()
    try:
        with pytest.raises(ExportError):
            db.export_deidentified("rel.db")   # مسار نسبي يطابق المصدر
    finally:
        db.close()
