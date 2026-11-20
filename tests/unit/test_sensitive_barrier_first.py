# -*- coding: utf-8 -*-
"""اختبارات سلبية لبوابة الحاجز أولاً وتوحيد فشل SafeMover.

تنفيذ بنود المراحل 1/3/4/5 من خطة جلسة ChatGPT (2026-11-20):
- الملف الحساس لا يُفتح إطلاقاً أثناء الفهرسة — لا SHA ولا كشف نوع ولا ميتاداتا.
- المقاطعات (KeyboardInterrupt/SystemExit) تُعاد إطلاقها ولا تُبتلع في النتائج.
- فشل sidecar يعني فشل العملية كاملة مع تراجع — لا نجاح جزئي مضلل.
"""
import json
from pathlib import Path

import pytest

from src.core import file_inventory as fi_module
from src.core import safe_mover as sm_module
from src.core import ocr_service
from src.core.file_inventory import FileInventory
from src.core.safe_mover import SafeMover
from src.core.sensitive_barrier import SensitiveFileBlockedError


@pytest.fixture
def inventory(tmp_path):
    return FileInventory(include_content=True)


def test_inventory_never_opens_sensitive_file(tmp_path, inventory, monkeypatch):
    """الملف داخل مجلد 'patients' حساس — لا يُفتح حتى لحساب SHA-256."""
    patients = tmp_path / "patients"
    patients.mkdir()
    sensitive = patients / "report.txt"
    sensitive.write_text("بيانات طبية سرية", encoding="utf-8")
    normal = tmp_path / "normal.txt"
    normal.write_text("ملف عادي", encoding="utf-8")

    opened: list[str] = []

    real_hash = FileInventory._compute_hash
    real_detect = fi_module.detect_content_type
    real_meta = FileInventory._safe_extract_extended

    def guarded_hash(path):
        opened.append(f"hash:{path}")
        return real_hash(path)

    def guarded_detect(path, ext):
        opened.append(f"content_type:{path}")
        return real_detect(path, ext)

    def guarded_meta(path, ext):
        opened.append(f"metadata:{path}")
        return real_meta(path, ext)

    monkeypatch.setattr(FileInventory, "_compute_hash", staticmethod(guarded_hash))
    monkeypatch.setattr(fi_module, "detect_content_type", guarded_detect)
    monkeypatch.setattr(FileInventory, "_safe_extract_extended", staticmethod(guarded_meta))

    records = inventory.scan_directory(str(tmp_path))
    by_path = {Path(r.metadata.file_path): r for r in records}

    assert normal in by_path and by_path[normal].metadata.sha256_hash
    assert sensitive in by_path, "الملف الحساس يُفهرَس بالعناوين فقط"
    assert not by_path[sensitive].metadata.sha256_hash, "لا قراءة محتوى لملف حساس"
    assert not any(str(sensitive) in call for call in opened), opened


def test_inventory_blocks_content_of_sensitive_file(tmp_path, inventory):
    """محتوى الملف الحساس لا يدخل document_text حتى مع include_content=True."""
    patients = tmp_path / "patients"
    patients.mkdir()
    (patients / "notes.md").write_text("سر طبي", encoding="utf-8")

    records = inventory.scan_directory(str(tmp_path))
    assert len(records) == 1
    assert records[0].document_text == ""
    assert not records[0].metadata.sha256_hash, "لا قراءة محتوى — لا SHA للحساس"


def test_safe_mover_reraises_keyboard_interrupt(tmp_path, monkeypatch):
    """KeyboardInterrupt أثناء النقل يُعاد إطلاقه — لا يتحول إلى result فاشل صامت."""
    src = tmp_path / "a.txt"
    src.write_text("DATA")
    dst = tmp_path / "b.txt"

    def boom(src_p, dst_p):
        raise KeyboardInterrupt()

    monkeypatch.setattr(sm_module, "_atomic_move", boom)
    mover = SafeMover()
    with pytest.raises(KeyboardInterrupt):
        mover.move(str(src), str(dst))


def test_safe_mover_sidecar_failure_rolls_back(tmp_path, monkeypatch):
    """فشل نقل sidecar ⇒ فشل العملية كاملة + تراجع النقل الرئيسي — صفر فقد."""
    src = tmp_path / "doc.txt"
    src.write_text("DATA")
    sidecar = tmp_path / ".ifm_meta_doc.txt.json"
    sidecar.write_text(json.dumps({"tags": ["مهم"]}), encoding="utf-8")
    dst = tmp_path / "moved" / "doc.txt"
    dst.parent.mkdir()

    real_move = sm_module._atomic_move

    def failing_sidecar_move(src_p, dst_p):
        if ".ifm_meta" in str(dst_p):
            raise OSError(errno_stub := 13, "sidecar dst unwritable")
        return real_move(src_p, dst_p)

    monkeypatch.setattr(sm_module, "_atomic_move", failing_sidecar_move)
    mover = SafeMover()
    result = mover.move(str(src), str(dst))

    assert not result.success, "لا نجاح جزئي مضلل"
    assert "تم التراجع" in (result.error or "")
    assert src.exists(), "الملف الرئيسي عاد إلى مصدره"
    assert not dst.exists(), "لا نسخة مقطوعة في الوجهة"
    assert sidecar.exists(), "sidecar لم يُمس"
    assert src.read_text() == "DATA"


def test_copy_sidecar_failure_cleans_destination(tmp_path, monkeypatch):
    """فشل نسخ sidecar ⇒ فشل النسخ + حذف النسخة في الوجهة."""
    src = tmp_path / "doc.txt"
    src.write_text("DATA")
    (tmp_path / ".ifm_meta_doc.txt.json").write_text("{}", encoding="utf-8")
    dst = tmp_path / "copy" / "doc.txt"
    dst.parent.mkdir()

    real_copy = sm_module._atomic_copy

    def failing_sidecar_copy(src_p, dst_p):
        if ".ifm_meta" in str(dst_p):
            raise OSError(13, "sidecar dst unwritable")
        return real_copy(src_p, dst_p)

    monkeypatch.setattr(sm_module, "_atomic_copy", failing_sidecar_copy)
    mover = SafeMover()
    result = mover.copy(str(src), str(dst))

    assert not result.success
    assert "حذف النسخة" in (result.error or "")
    assert src.exists() and src.read_text() == "DATA"
    assert not dst.exists(), "النسخة الناقصة حُذفت"


def test_ocr_internal_guards_fire_on_sensitive_paths(tmp_path):
    """الحواجز الداخلية في OCR ترفع قبل أي فتح للملف حتى لاستدعاء مباشر."""
    sensitive = tmp_path / "patients" / "scan.png"
    sensitive.parent.mkdir()
    sensitive.write_bytes(b"\x89PNG\r\n\x1a\n")

    with pytest.raises(SensitiveFileBlockedError):
        ocr_service._legacy_pytesseract(str(sensitive))
    with pytest.raises(SensitiveFileBlockedError):
        ocr_service.enhance_image(str(sensitive))
