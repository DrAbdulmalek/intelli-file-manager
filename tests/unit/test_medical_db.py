# -*- coding: utf-8 -*-
"""اختبارات قاعدة البيانات الطبية المحلية + مسار التصدير المجرّد للنشر."""
from __future__ import annotations

import json

import pytest

from src.core.medical_db import MedicalDB
from src.core import sensitive_barrier as sb


@pytest.fixture(autouse=True)
def _strict_default():
    sb.set_medical_mode("strict")
    yield
    sb.set_medical_mode("strict")


@pytest.fixture
def db(tmp_path):
    d = MedicalDB(tmp_path / "clinic.db").init()
    yield d
    d.close()


def test_init_creates_schema(db):
    tables = {
        r["name"]
        for r in db._conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"patients", "records", "files", "processing_log"} <= tables


def test_patient_ids_auto_increment(db):
    p1 = db.add_patient(name="أحمد")
    p2 = db.add_patient()  # بلا اسم — معرّف مستعار خالص
    assert p1 == "P-0001" and p2 == "P-0002"
    assert db.get_patient(p2)["name"] is None


def test_record_validation(db):
    pid = db.add_patient()
    with pytest.raises(ValueError):
        db.add_record(pid, "2026-11-22", "wrong-type")
    with pytest.raises(ValueError):
        db.add_record(pid, "22-11-2026", "visit")  # صيغة تاريخ غير ISO
    with pytest.raises(ValueError):
        db.add_record("P-9999", "2026-11-22", "visit")  # مريض غير موجود


def test_add_and_search_records(db):
    pid = db.add_patient(name="سارة")
    db.add_record(pid, "2026-11-01", "lab", summary="صورة دم كاملة",
                  findings={"hb": "13.2"})
    db.add_record(pid, "2026-11-20", "imaging", summary="أشعة صدر",
                  findings={"impression": "طبيعي"})
    assert len(db.list_records(pid)) == 2
    assert len(db.list_records(pid, "imaging")) == 1
    hits = db.search_records("صدر")
    assert len(hits) == 1 and hits[0]["record_type"] == "imaging"
    assert json.loads(hits[0]["findings"])["impression"] == "طبيعي"


def test_register_file_sha_rules(tmp_path):
    scan = tmp_path / "patients" / "IMG_0001.jpg"
    scan.parent.mkdir()
    scan.write_bytes(b"image-bytes-here")
    env = tmp_path / ".env"
    env.write_text("API_KEY=secret")
    db = MedicalDB(tmp_path / "c.db").init()
    try:
        sb.set_medical_mode("strict")
        info = db.register_file(scan)
        # صارم: ملف طبي غير مقروء → بلا بصمة، وتصنيفه طبي
        assert info["sha256"] is None
        assert info["classification"] == "medical"
        assert info["readable_in_current_mode"] is False
        info = db.register_file(env)
        # السرّ: بلا قراءة محتوى في أي وضع
        assert info["sha256"] is None
        assert info["classification"] == "secret"
        sb.set_medical_mode("local")
        info = db.register_file(scan)
        # وضع العيادة: القراءة مسموحة → البصمة تُحسب
        assert info["sha256"]
        assert info["classification"] == "medical"
    finally:
        db.close()


def test_register_plain_file_has_sha(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("hello")
    db = MedicalDB(tmp_path / "c.db").init()
    try:
        info = db.register_file(f)
        assert info["sha256"] is not None
        assert info["classification"] == "plain"
    finally:
        db.close()


def test_deidentify_export_strips_personal(db, tmp_path):
    pid = db.add_patient(name="محمد", age="44", sex="m", notes="ملاحظة خاصة")
    db.add_record(pid, "2026-11-20", "visit",
                  source_path="/private/محمد/report.pdf", summary="متابعة دورية")
    out = tmp_path / "publish.db"
    res = db.export_deidentified(out)
    assert res["records"] == 1
    with MedicalDB(out) as pub:
        pat = pub.get_patient(pid)
        assert pat["name"] is None
        assert pat["age"] is None
        assert pat["sex"] is None
        assert pat["notes"] is None
        recs = pub.list_records()
        assert recs[0]["source_path"] is None
        assert recs[0]["sha256"] is None
        assert recs[0]["summary"] == "متابعة دورية"
        assert pub.list_files() == []  # جدول الملفات لا يُصدَّر إطلاقاً


def test_stats_and_log(db):
    db.add_patient()
    db.add_record("P-0001", "2026-11-22", "visit", summary="زيارة أولى")
    st = db.stats()
    assert st["patients"] == 1
    assert st["records"] == 1
    assert st["log_entries"] >= 3  # init + add_patient + add_record
