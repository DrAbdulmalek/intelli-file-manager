"""اختبارات P0 لحاجز الحساسية: منع قراءة محتوى الملفات الطبية والأسرار (IFM-003 ملاحظة P0)."""
from __future__ import annotations

from pathlib import Path

from src.core.classifier import SmartFileClassifier
from src.core.config import Config
from src.core.sensitive_guard import (
    LEVEL_NON_SENSITIVE,
    LEVEL_PRIVATE,
    LEVEL_SECURITY_SECRETS,
    LEVEL_SENSITIVE_MEDICAL,
    classify_sensitivity,
    content_read_allowed,
    external_send_allowed,
    redact_path,
)


def test_secrets_detected():
    assert classify_sensitivity("/app/.env") == LEVEL_SECURITY_SECRETS
    assert classify_sensitivity("/home/u/.ssh/id_rsa") == LEVEL_SECURITY_SECRETS
    assert classify_sensitivity("/backups/vault.kdbx") == LEVEL_SECURITY_SECRETS
    assert classify_sensitivity("/app/config/api_key.json") == LEVEL_SECURITY_SECRETS


def test_medical_detected_arabic_and_english():
    assert classify_sensitivity("/data/MRI_scan_001.dcm") == LEVEL_SENSITIVE_MEDICAL
    assert classify_sensitivity("/data/patient_report.txt") == LEVEL_SENSITIVE_MEDICAL
    assert classify_sensitivity("/ scans/رنين_مغناطيسي_مريض_2.pdf") == LEVEL_SENSITIVE_MEDICAL
    assert classify_sensitivity("/data/تحاليل_الدم.xlsx") == LEVEL_SENSITIVE_MEDICAL


def test_private_and_normal_levels():
    assert classify_sensitivity("/docs/عقد_إيجار.pdf") == LEVEL_PRIVATE
    assert classify_sensitivity("/books/orthopaedic_book.pdf") == LEVEL_NON_SENSITIVE


def test_content_and_send_gates():
    assert not content_read_allowed(LEVEL_SECURITY_SECRETS)
    assert not content_read_allowed(LEVEL_SENSITIVE_MEDICAL)
    assert content_read_allowed(LEVEL_NON_SENSITIVE)
    assert not external_send_allowed(LEVEL_SENSITIVE_MEDICAL)
    assert external_send_allowed(LEVEL_NON_SENSITIVE)


def test_redact_path_hides_home(tmp_path):
    p = tmp_path / "sub" / "file.txt"
    out = redact_path(str(p), home=str(tmp_path))
    assert out.startswith("~") and tmp_path.as_posix() not in out


def test_barrier_blocks_medical_content_read(tmp_path):
    """حاجز ما قبل الاستخراج: ملف باسم مريض لا يُقرأ محتاه حتى لو كان نصاً مقروءاً."""
    config = Config(database_path=str(tmp_path / "intellifile"))
    clf = SmartFileClassifier(config)

    sensitive = tmp_path / "patient_report.txt"
    sensitive.write_text("قلب القلب قلبية cardiac", encoding="utf-8")
    result = clf.classify_file_medical(str(sensitive))

    assert result["category"] == "sensitive_review_required"
    assert result["review_required"] is True
    assert result["sensitivity"] == LEVEL_SENSITIVE_MEDICAL
    assert result.get("source") == "sensitive_guard"


def test_barrier_does_not_block_normal_files(tmp_path):
    """ملف عادي بمحتوى طبي يُصنف كالمعتاد — الحاجز لا يعمّي كل شيء."""
    config = Config(database_path=str(tmp_path / "intellifile"))
    clf = SmartFileClassifier(config)

    normal = tmp_path / "cardiology_notes.txt"
    normal.write_text("قلب وقلبية cardiac anatomy", encoding="utf-8")
    result = clf.classify_file_medical(str(normal))

    assert result["category"] == "cardiology"
    assert result.get("review_required") is not True


def test_barrier_blocks_secrets_even_plain_named(tmp_path):
    """مفتاح باسم مشفّر الامتداد محجوب من قراءة المحتوى أيضاً."""
    config = Config(database_path=str(tmp_path / "intellifile"))
    clf = SmartFileClassifier(config)

    secret = tmp_path / "server.key"
    secret.write_text("-----BEGIN PRIVATE KEY-----\nMIIB\n-----END-----")
    result = clf.classify_file_medical(str(secret))

    assert result["sensitivity"] == LEVEL_SECURITY_SECRETS
    assert result["category"] == "sensitive_review_required"
