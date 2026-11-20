"""اختبارات حسّاس-بارير — حماية الملفات الحساسة قبل القراءة/OCR/الإرسال الخارجي."""
from __future__ import annotations

import tempfile
from pathlib import Path

from src.core.sensitive_barrier import (
    SensitiveFileBlockedError,
    block_if_sensitive,
    classify_sensitivity,
    is_sensitive_path,
    safe_extract_content,
    safe_ocr_image,
)


# ─── اختبارات الكشف ─────────────────────────────────────────────────────────

def test_is_sensitive_dicom():
    """ملف DICOM يُصنّف كحساس دائمًا"""
    assert is_sensitive_path("/tmp/scan.dcm") is True
    assert is_sensitive_path("/tmp/images/dicom/file.dcm") is True


def test_is_sensitive_nifti():
    """ملف NIfTI يُصنّف كحساس"""
    assert is_sensitive_path("/tmp/brain.nii") is True
    assert is_sensitive_path("/tmp/mri.nii.gz") is True


def test_is_sensitive_medical_folder():
    """ملف في مجلد طبي يُصنّف كحساس حتى لو كان امتدادًا عاديًا"""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "mri" / "report.txt"
        p.parent.mkdir(parents=True)
        p.write_text("تقرير طبي")
        assert is_sensitive_path(str(p)) is True


def test_is_sensitive_patient_filename():
    """اسم ملف يحتوي على 'patient' يُصنّف كحساس"""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "patient_report.pdf"
        p.write_text("محتوى عادي")
        assert is_sensitive_path(str(p)) is True


def test_is_not_sensitive_regular_file():
    """ملف عادي لا يُصنّف كحساس"""
    assert is_sensitive_path("/tmp/document.txt") is False
    assert is_sensitive_path("/tmp/image.png") is False
    assert is_sensitive_path("/tmp/code.py") is False


def test_is_sensitive_ssh_config_folder():
    """مجلدات .ssh و .config تُصنّف كحساسة"""
    assert is_sensitive_path("/home/user/.ssh/id_rsa") is True
    assert is_sensitive_path("/home/user/.config/app/settings.json") is True


def test_classify_sensitivity_returns_dict():
    """تصنيف الحساسية يُعيد قاموسًا بمفاتيح محددة"""
    result = classify_sensitivity("/tmp/document.txt")
    assert "is_sensitive" in result
    assert "reason" in result
    assert "extension" in result
    assert "path_parts" in result
    assert result["is_sensitive"] is False


def test_classify_sensitivity_dicom():
    """تصنيف DICOM يُعيد is_sensitive=True"""
    result = classify_sensitivity("/tmp/scan.dcm")
    assert result["is_sensitive"] is True
    assert "تصوير طبي" in result["reason"] or "دcom" in result["reason"]


# ─── اختبارات الحظر ─────────────────────────────────────────────────────────

def test_block_if_sensitive_raises():
    """block_if_sensitive يرفع استثناء للملفات الحساسة"""
    try:
        block_if_sensitive("/tmp/scan.dcm", operation="اختبار قراءة")
        assert False, "يجب أن يُرفع استثناء"
    except SensitiveFileBlockedError:
        pass


def test_block_if_sensitive_allows_regular():
    """block_if_sensitive لا يرفع استثناء للملفات العادية"""
    block_if_sensitive("/tmp/document.txt", operation="اختبار قراءة")  # يجب ألا يفشل


# ─── اختبارات التكامل ────────────────────────────────────────────────────────

def test_safe_extract_content_blocks_sensitive():
    """safe_extract_content يُعيد None للملفات الحساسة دون استدعاء الاستخراج"""
    def fake_extractor(fp):
        return "محتوى مُستخرج"

    result = safe_extract_content("/tmp/scan.dcm", fake_extractor)
    assert result is None  # لم يُستدع الاستخراج


def test_safe_extract_content_allows_regular():
    """safe_extract_content يستدعي الاستخراج للملفات العادية"""
    def fake_extractor(fp):
        return "محتوى عادي"

    result = safe_extract_content("/tmp/document.txt", fake_extractor)
    assert result == "محتوى عادي"


def test_safe_ocr_image_blocks_sensitive():
    """safe_ocr_image يُعيد None للصور الحساسة دون استدعاء OCR"""
    def fake_ocr(fp):
        return {"text": "نص من الصورة", "success": True}

    result = safe_ocr_image("/tmp/mri.jpg", fake_ocr)
    assert result is None


def test_safe_ocr_image_allows_regular():
    """safe_ocr_image ينفذ OCR للصور العادية"""
    def fake_ocr(fp):
        return {"text": "نص من الصورة", "success": True}

    result = safe_ocr_image("/tmp/photo.jpg", fake_ocr)
    assert result == {"text": "نص من الصورة", "success": True}


# ─── اختبارات الحدود (edge cases) ──────────────────────────────────────────

def test_sensitive_path_with_skip_dirs():
    """تجاوز مجلدات محددة في skip_dirs"""
    # .ssh عادة حساس، لكن لو أضفناه إلى skip_dirs لا يُتجاوز (إنه جزء من الحساسية)
    #这里的 skip_dirs يُستخدم لاستبعاد أجزاء من المسار من الحساسية، وليس للتخطي من المسح
    assert is_sensitive_path("/home/user/.ssh/id_rsa") is True


def test_medical_report_pdf_in_medical_folder():
    """ملف PDF في مجلد طبي يُصنّف كحساس"""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "clinics" / "report.pdf"
        p.parent.mkdir(parents=True)
        p.write_text("تقرير")
        assert is_sensitive_path(str(p)) is True


def test_medical_report_pdf_outside_medical_folder():
    """ملف PDF خارج مجلد طبي لا يُصنّف كحساس (للمراجعة اليدوية)"""
    assert is_sensitive_path("/tmp/document.pdf") is False


def test_chinese_medical_keywords():
    """كلمات طبية بالعربية في اسم الملف"""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "تقرير طبي.pdf"
        p.write_text("محتوى")
        assert is_sensitive_path(str(p)) is True
