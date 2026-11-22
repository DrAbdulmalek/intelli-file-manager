# -*- coding: utf-8 -*-
"""وضع العيادة المحلية (INTELLIFILE_MEDICAL_MODE).

العقد (قرار المالك 2026-11-22):
  1. strict (الافتراضي): المحتوى الطبي محجوب عن القراءة كما في التصلّد.
  2. local (وضع العيادة): قراءة المحتوى الطبي ومعالجته محلياً مسموحة —
     الأسرار/الاعتماديات/مجلدات النظام محجوبة في كل الأوضاع بلا استثناء.
  3. الإرسال الخارجي محكوم دائماً بالحكم الصارم: المحتوى الطبي لا يغادر
     الجهاز مهما كان الوضع.
  4. classify_sensitivity يكشف المحتوى الطبي دائماً للعرض والتسجيل، ويُبلغ
     عن قابلية القراءة في الوضع الحالي.
"""
from __future__ import annotations

import pytest

from src.core import sensitive_barrier as sb


@pytest.fixture(autouse=True)
def _restore_strict():
    yield
    sb.set_medical_mode("strict")


PATIENT_SCAN = "/home/u/clinic/patients/IMG_0001.jpg"  # جزء مسار طبي: patients
ENV_FILE = "/home/u/proj/.env"  # سرّ — محجوب في كل الأوضاع


def test_default_mode_is_strict():
    sb.set_medical_mode("strict")
    assert sb.medical_mode() == "strict"
    assert sb.medical_reads_unlocked() is False


def test_strict_blocks_medical_paths():
    sb.set_medical_mode("strict")
    assert sb.is_sensitive_path(PATIENT_SCAN) is True
    assert sb.is_sensitive_strict(PATIENT_SCAN) is True


def test_local_unlocks_medical_reads():
    sb.set_medical_mode("local")
    assert sb.medical_reads_unlocked() is True
    assert sb.is_sensitive_path(PATIENT_SCAN) is False
    # الحكم الصارم يبقى متاحاً كما هو بغضّ النظر عن الوضع
    assert sb.is_sensitive_strict(PATIENT_SCAN) is True


def test_secrets_stay_blocked_in_local(tmp_path):
    sb.set_medical_mode("local")
    assert sb.is_sensitive_path(ENV_FILE) is True
    assert sb.is_secret_file(ENV_FILE) is True
    env = tmp_path / ".env"
    env.write_text("API_KEY=secret")
    with pytest.raises(sb.SensitiveFileBlockedError):
        sb.block_if_sensitive(str(env), operation="اختبار")


def test_system_dirs_stay_blocked_in_local():
    sb.set_medical_mode("local")
    assert sb.is_sensitive_path("/home/u/.ssh/id_rsa") is True
    assert sb.is_sensitive_path("/home/u/.aws/credentials") is True
    assert sb.is_sensitive_path("/home/u/.gnupg/privkeys") is True


def test_credential_names_stay_blocked_in_local():
    sb.set_medical_mode("local")
    assert sb.is_sensitive_path("/home/u/backups/credentials.json") is True
    assert sb.is_sensitive_path("/home/u/vault.kdbx") is True


def test_external_send_stays_strict(tmp_path):
    sb.set_medical_mode("local")
    scan = tmp_path / "patients" / "IMG_0001.jpg"
    scan.parent.mkdir()
    scan.write_bytes(b"\x00" * 140)
    env = tmp_path / ".env"
    env.write_text("API_KEY=secret")
    notes = tmp_path / "notes.txt"
    notes.write_text("hello")
    # المحتوى الطبي لا يغادر الجهاز حتى في وضع العيادة المحلية
    assert sb.external_send_allowed(scan, service_name="test") is False
    # والأسرار كذلك في كل الأوضاع
    assert sb.external_send_allowed(env, service_name="test") is False
    # والملف العادي يُسمح
    assert sb.external_send_allowed(notes, service_name="test") is True


def test_classify_reports_medical_even_in_local(tmp_path):
    scan = tmp_path / "patients" / "report.pdf"
    scan.parent.mkdir()
    scan.write_bytes(b"\x00" * 128 + b"DICM" + b"\x00" * 32)
    sb.set_medical_mode("local")
    info = sb.classify_sensitivity(scan)
    assert info["medical_content"] is True
    assert info["medical_mode"] == "local"
    assert info["readable_in_current_mode"] is True
    sb.set_medical_mode("strict")
    info = sb.classify_sensitivity(scan)
    assert info["is_sensitive"] is True
    assert info["medical_content"] is True
    assert info["readable_in_current_mode"] is False


def test_dicom_probe_skipped_in_local(tmp_path):
    # في الوضع المحلي لا مسح دليمة للكشف عن الحجب — الملف لا يُفتح أصلاً؛
    # وفي الصارم يُمسح المرشّح (صورة عامة) وتُكتشف الدليمة.
    jpg = tmp_path / "photo.jpg"
    jpg.write_bytes(b"\x00" * 128 + b"DICM" + b"\x00" * 32)
    sb.set_medical_mode("local")
    assert sb.is_sensitive_path(jpg) is False
    sb.set_medical_mode("strict")
    assert sb.is_sensitive_path(jpg) is True


def test_setter_rejects_unknown_mode():
    with pytest.raises(ValueError):
        sb.set_medical_mode("bogus")


def test_block_if_sensitive_follows_mode(tmp_path):
    scan = tmp_path / "patients" / "report.pdf"
    scan.parent.mkdir()
    scan.write_bytes(b"plain-report-bytes")
    sb.set_medical_mode("strict")
    with pytest.raises(sb.SensitiveFileBlockedError):
        sb.block_if_sensitive(str(scan), operation="اختبار صارم")
    sb.set_medical_mode("local")
    sb.block_if_sensitive(str(scan), operation="اختبار محلي")  # لا يرفع
