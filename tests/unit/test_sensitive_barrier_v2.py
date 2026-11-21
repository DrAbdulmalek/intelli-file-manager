# -*- coding: utf-8 -*-
"""اختبارات الحاجز المعزّز (مراجعة التصلّد الشامل).

يغطي:
  - قواعد ملفات الأسرار (.env، مفاتيح SSH، .pem/.p12/.pfx، .netrc، .kdbx،
    credentials.json، الشهادات) — إلزامية لا تعطّلها الإعدادات.
  - مؤشرات المسارات الطبية الجديدة (medical_records/clinical/radiology/
    prescriptions/laboratory/hospital_records).
  - تصنيف الروابط الرمزية (الرابط + الهدف) وopen_checked بـ O_NOFOLLOW.
  - إغلاق ثغرة skip_dirs التي كانت تُبطل كشف secrets/credentials في
    FileInventory.
  - التوثيق الثلاثي للمستويات: path/name vs header vs full-content.
"""
from __future__ import annotations

import io
import json
import os
import builtins
from pathlib import Path

import pytest

from src.core.sensitive_barrier import (
    SensitiveFileBlockedError,
    SymlinkBlockedError,
    block_if_sensitive,
    classify_sensitivity,
    is_sensitive_path,
    open_checked,
    verify_open_identity,
)

DICOM_PAYLOAD = b"\x00" * 128 + b"DICM" + b"x" * 64


# ─── 1. ملفات الأسرار بالاسم/الامتداد ───────────────────────────────────────

@pytest.mark.parametrize("path", [
    "/tmp/x/.env",
    "/tmp/x/.env.local",
    "/tmp/x/.netrc",
    "/tmp/x/credentials.json",
    "/tmp/x/secrets.yaml",
    "/tmp/x/id_rsa",
    "/tmp/x/id_ed25519",
    "/tmp/x/server.pem",
    "/tmp/x/cert.p12",
    "/tmp/x/key.pfx",
    "/tmp/x/vault.kdbx",
    "/tmp/x/host.key",
    "/tmp/x/keystore.jks",
])
def test_secret_files_are_sensitive(path):
    """ملفات الأسرار والاعتماديات حساسة دائماً بالاسم/الامتداد."""
    assert is_sensitive_path(path) is True


def test_public_key_blocked_too():
    """حتى المفاتيح العامة تُحظر احترازياً (عائلة المفاتيح كلها)."""
    assert is_sensitive_path("/tmp/x/id_rsa.pub") is True


def test_dotenv_inside_project_dir(tmp_path):
    p = tmp_path / ".env"
    p.write_text("API_KEY=secret-value")
    assert is_sensitive_path(str(p)) is True


# ─── 2. مؤشرات المسارات الطبية الجديدة ──────────────────────────────────────

@pytest.mark.parametrize("directory", [
    "medical_records",
    "clinical",
    "hospital_records",
    "radiology",
    "prescriptions",
    "laboratory",
])
def test_new_medical_path_indicators(tmp_path, directory):
    """مجلدات طبية جديدة تُحظر حتى لامتدادات عامة."""
    d = tmp_path / directory
    d.mkdir()
    f = d / "note.txt"
    f.write_text("محتوى")
    assert is_sensitive_path(str(f)) is True


def test_arabic_medical_path_indicators(tmp_path):
    d = tmp_path / "أشعة"
    d.mkdir()
    f = d / "scan.png"
    f.write_text("x")
    assert is_sensitive_path(str(f)) is True


# ─── 3. skip_dirs لا يعطّل القواعد الإلزامية ─────────────────────────────────

def test_skip_dirs_cannot_disable_sensitive_rules(tmp_path):
    """تمرير مجلد حساس ضمن skip_dirs لا يجعله غير حساس (الإغلاق الأساسي)."""
    d = tmp_path / "secrets"
    d.mkdir()
    f = d / "key.txt"
    f.write_text("k")
    # سابقاً: skip_dirs={"secrets"} كان يُبطل كشفه
    assert is_sensitive_path(str(f), skip_dirs={"secrets", "credentials"}) is True
    d2 = tmp_path / "patients"
    d2.mkdir()
    f2 = d2 / "x.txt"
    f2.write_text("x")
    assert is_sensitive_path(str(f2), skip_dirs={"patients"}) is True


def test_file_inventory_hashes_secret_dirs_no_more(tmp_path):
    """ثغرة مُثبتة سابقاً: FileInventory كانت تمرر skip_dirs فتُلغي كشف
    secrets/credentials → SHA وmagic يقرآن المحتوى. الآن: لا hash ولا magic."""
    from src.core.file_inventory import FileInventory

    sec = tmp_path / "secrets"
    sec.mkdir()
    (sec / "api_key.txt").write_text("super-secret-value")
    normal = tmp_path / "notes.txt"
    normal.write_text("عادي")

    opened: list[str] = []

    real_open = builtins.open

    def spy_open(file, *a, **kw):
        opened.append(str(file))
        return real_open(file, *a, **kw)

    inventory = FileInventory(include_content=True)
    import src.core.file_inventory as fi_module
    real_hash = FileInventory._compute_hash

    def guarded_hash(path):
        opened.append(f"hash:{path}")
        return real_hash(path)

    import unittest.mock as mock
    with mock.patch("builtins.open", side_effect=spy_open), \
         mock.patch.object(FileInventory, "_compute_hash", staticmethod(guarded_hash)):
        records = list(inventory.scan(str(tmp_path)))

    by_name = {Path(r.metadata.file_path).name: r for r in records}
    assert by_name["api_key.txt"].metadata.sha256_hash is None
    assert by_name["api_key.txt"].metadata.content_type is None
    # لا فتح للمحتوى: hash/content-type لم يعملا على الملف السري
    assert f"hash:{sec / 'api_key.txt'}" not in opened
    # الملف العادي يُفهرس طبيعياً
    assert by_name["notes.txt"].metadata.sha256_hash


# ─── 4. الروابط الرمزية ─────────────────────────────────────────────────────

def test_symlink_to_env_file_is_sensitive(tmp_path):
    """رابط رمزي 'بريء' يشير إلى .env → حساس (تصنيف الهدف)."""
    env = tmp_path / ".env"
    env.write_text("KEY=v")
    link = tmp_path / "innocent.txt"
    link.symlink_to(env)
    assert is_sensitive_path(str(link)) is True


def test_symlink_to_dicom_target_is_sensitive(tmp_path):
    """رابط يشير إلى DICOM بلا امتداد مميز → حساس (header الهدف، 4 بايتات)."""
    dicom = tmp_path / "img001"
    dicom.write_bytes(DICOM_PAYLOAD)
    link = tmp_path / "photo.jpg"
    link.symlink_to(dicom)
    assert is_sensitive_path(str(link)) is True


def test_symlink_to_patients_dir_target(tmp_path):
    """رابط يشير إلى مجلد مرضى → المسار المستهدف يحمل المؤشر → حساس."""
    target_dir = tmp_path / "patients"
    target_dir.mkdir()
    (target_dir / "report.txt").write_text("x")
    link = tmp_path / "photos"
    link.symlink_to(target_dir, target_is_directory=True)
    link_file = link / "a.txt"
    assert is_sensitive_path(str(link_file)) is True


def test_broken_symlink_name_indicator(tmp_path):
    """رابط مكسور باسم حساس → حساس بالاسم."""
    link = tmp_path / "id_rsa.bak"
    try:
        link.symlink_to(tmp_path / "nonexistent_target_xyz")
    except OSError:
        pytest.skip("symlink غير مدعوم في هذه البيئة")
    assert is_sensitive_path(str(link)) is True


def test_open_checked_rejects_symlink(tmp_path):
    """open_checked يرفض الرابط الرمزي حتى لو كان الهدف عادياً (جذر حقيقي)."""
    target = tmp_path / "real.txt"
    target.write_text("محتوى")
    link = tmp_path / "alias.txt"
    link.symlink_to(target)
    with pytest.raises(SymlinkBlockedError):
        open_checked(str(link), operation="اختبار")


def test_open_checked_rejects_sensitive(tmp_path):
    dicom = tmp_path / "scan.dcm"
    dicom.write_bytes(DICOM_PAYLOAD)
    with pytest.raises(SensitiveFileBlockedError):
        open_checked(str(dicom))


def test_open_checked_allows_regular_and_identity(tmp_path):
    """ملف عادي يُفتح، وverify_open_identity يطابق الهوية."""
    f = tmp_path / "note.txt"
    f.write_text("مرحبا")
    with open_checked(str(f), "r", operation="اختبار") as fh:
        data = fh.read()
        st = os.fstat(fh.fileno())
    assert "مرحبا" in data
    # فحص الهوية عبر كائن مفتوح حي
    with open_checked(str(f)) as fh2:
        assert verify_open_identity(fh2, os.stat(str(f))) is True


def test_open_checked_rejects_directory(tmp_path):
    """open_checked يرفض المجلد (غير ملف عادي) بـ fstat."""
    with pytest.raises(SensitiveFileBlockedError):
        open_checked(str(tmp_path))


def test_open_checked_text_mode(tmp_path):
    f = tmp_path / "doc.txt"
    f.write_text("نص عربي")
    with open_checked(str(f), "r") as fh:
        assert "نص عربي" in fh.read()


# ─── 5. DICOM بامتداد مضلل (header-based) ───────────────────────────────────

def test_dicom_with_pdf_extension_blocked(tmp_path):
    """DICOM خلف امتداد .pdf → الحاجز يكتشفه بدليمة 128 (قراءة 4 بايتات موثقة)."""
    p = tmp_path / "invoice.pdf"
    p.write_bytes(DICOM_PAYLOAD)
    assert is_sensitive_path(str(p)) is True
    cls = classify_sensitivity(str(p))
    assert cls["is_sensitive"] is True
    assert "header_dicom" in cls["detection_layers"]


def test_header_scan_fails_closed_on_symlink(tmp_path):
    """فحص header لا يتبع الروابط؛ التصنيف يمر عبر تصنيف الهدف."""
    dicom = tmp_path / "scan"
    dicom.write_bytes(DICOM_PAYLOAD)
    link = tmp_path / "photo.png"
    link.symlink_to(dicom)
    assert is_sensitive_path(str(link)) is True


# ─── 6. التوثيق: classify_sensitivity يفرّق بين المستويات ────────────────────

def test_classify_layers_path_name_only():
    cls = classify_sensitivity("/tmp/scan.dcm")
    assert cls["detection_layers"] == ["path_name"]


def test_classify_layers_for_plain_file():
    cls = classify_sensitivity("/tmp/document.txt")
    assert cls["is_sensitive"] is False
    assert cls["detection_layers"] == []


# ─── 7. إنذارات كاذبة محفوظة (regression) ───────────────────────────────────

@pytest.mark.parametrize("path", [
    "/tmp/Amrita.txt",        # تحتوي "mri" كسلسلة فرعية
    "/tmp/secretary.docx",    # تحتوي "secret" كسلسلة فرعية
    "/tmp/keyboard.png",      # تحتوي "key" كسلسلة فرعية
    "/tmp/document.txt",
    "/tmp/code.py",
])
def test_no_false_positives(path):
    assert is_sensitive_path(path) is False
