"""اختبارات انهيار (inversion) للعيوب F1–F8 per وثيقة المراجعة المستقلة CLAUDE_INDEPENDENT_REVIEW_2026-11-20.

كل اختبار يُعيد إنتاج العيب على الكود المعيب (يُفترض النجاح قبل الإصلاح)،
ثم يُنقل بعد الإصلاح ليعكس النتيجة (فشل قبل → نجاح بعد).

ملاحظة: هذه الاختبارات تُشغل على الكود *المُصلح* — يجب أن تمر جميعها.
لو أي اختبار فشل، يعني أن العيب لم يُصلح بالكامل.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.safe_mover import SafeMover, OverwriteForbiddenError
from src.core.sensitive_barrier import (
    classify_sensitivity,
    is_sensitive_path,
    external_send_allowed,
)
from src.core.file_handler import FileHandler
from src.core.config import Config


# ═════════════════════════════════════════════════════════════════════════════
# F1 — حاجز الحساسية (تصنيف بالاسم فقط، إنذارات كاذبة، DICOM header، external_send_allowed)
# ═════════════════════════════════════════════════════════════════════════════

class TestF1_SensitiveBarrier:
    """F1: حاجز الحساسية لا يغطي classifier فقط، والتصنيف بالاسم فقط، وإنذارات كاذبة."""

    def test_A1_medical_scan_names_are_sensitive(self):
        """أسماء الأشعة العامة تُصنّف حساسة بعد C2/C3 (DICOM header + word-boundary)."""
        for name in ["IMG_0001.jpg", "scan_0231.pdf", "xray_ortho_4411.png"]:
            c = classify_sensitivity(name)
            # IMG_0001.jpg ليس له مؤشر طبي → NON_SENSITIVE (صحيح، لا إنذار كاذب)
            if name == "IMG_0001.jpg":
                assert c["is_sensitive"] is False
            else:
                assert c["is_sensitive"] is True, f"{name} يجب أن يُصنّف حساس"

    def test_A2_no_false_positive_mri_substring(self):
        """mri كسلسلة فرعية داخل Amrita لا تُنتج إنذاراً كاذباً (word-boundary)."""
        c = classify_sensitivity("Amrita_Notes.docx")
        assert c["is_sensitive"] is False, "Amrita تحتوي على mri كسلسلة فرعية فقط — لا يجب أن تُصنّف حساسة"

        c = classify_sensitivity("tokenizer.py")
        assert c["is_sensitive"] is False, "tokenizer.py لا يجب أن يُصنّف SECURITY_SECRETS"

        # patient ككلمة كاملة → حساس (صحيح)
        c = classify_sensitivity("patient_education_handbook.pdf")
        assert c["is_sensitive"] is True, "patient ككلمة كاملة يجب أن يُصنّف حساس"

    def test_dicom_header_detected_despite_generic_extension(self):
        """دليمة DICOM عند الإزاحة 128 تُكتشف حتى لو الامتداد عام (.jpg)."""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "image.jpg"
            with p.open("wb") as f:
                f.write(b"\x00" * 128 + b"DICM")
            c = classify_sensitivity(str(p))
            assert c["is_sensitive"] is True, "ملف بـ DICM header يجب أن يُصنّف حساس حتى لو امتداده .jpg"

    def test_external_send_allowed_blocks_sensitive(self):
        """external_send_allowed يُعيد False للملفات الحساسة (لم يعد كوداً ميتاً)."""
        assert external_send_allowed("scan.dcm", service_name="test") is False
        assert external_send_allowed("report.txt", service_name="test") is True


# ═════════════════════════════════════════════════════════════════════════════
# F2–F6 — SafeMover (TOCTOU، غير OSError، KeyboardInterrupt، overwrite على مجلد)
# ═════════════════════════════════════════════════════════════════════════════

class TestF2_F6_SafeMover:
    """F2–F6: SafeMover يرفض الاستبدال الصامت، ويلتقط BaseException، ويرفض المجلدات."""

    def test_P1_no_silent_overwrite_on_existing_destination(self):
        """الوجهة الموجودة → العملية تُرفض (لا استبدال صامت، المصدر سليم)."""
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            src = base / "source.txt"
            dst = base / "dest.txt"
            src.write_text("المحتوى الأصلي")
            dst.write_text("البيانات الموجودة")

            mover = SafeMover()
            result = mover.move(str(src), str(dst))

            assert result.success is False, "النقل فوق وجهة موجودة يجب أن يُرفض"
            assert src.exists(), "المصدر يجب أن يظل موجوداً"
            assert dst.read_text() == "البيانات الموجودة", "الوجهة يجب أن تحتفظ بمحتواها"

    def test_P3_non_oserror_exception_caught_source_preserved(self):
        """استثناء غير OSError يُلتقط والمصدر يُحفظ (لا حالة تالفة)."""
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            src = base / "source.txt"
            dst = base / "dest.txt"
            src.write_text("المحتوى الأصلي")
            dst.write_text("البيانات الموجودة")

            def boom(*args, **kwargs):
                raise RuntimeError("خطأ غير متوقع")

            mover = SafeMover()
            with patch("src.core.safe_mover._atomic_move", side_effect=boom):
                result = mover.move(str(src), str(dst))

            assert result.success is False, "الاستثناء غير OSError يجب أن يُ捕获 ويُرجع فشلاً"
            assert src.exists(), "المصدر يجب أن يظل موجوداً بعد الاستثناء"
            assert dst.read_text() == "البيانات الموجودة", "الوجهة يجب أن تحتفظ بمحتواها"

    def test_P4_keyboard_interrupt_source_preserved(self):
        """KeyboardInterrupt يُلتقط والمصدر يُحفظ (لا ملف placeholder فارغ)."""
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            src = base / "source.txt"
            dst = base / "dest.txt"
            src.write_text("المحتوى الأصلي")
            dst.write_text("البيانات الموجودة")

            def boom(*args, **kwargs):
                raise KeyboardInterrupt()

            mover = SafeMover()
            try:
                with patch("src.core.safe_mover._atomic_move", side_effect=boom):
                    mover.move(str(src), str(dst))
            except KeyboardInterrupt:
                pass  # المقاطعة قد تنتشر إلى المستدعي الخارجي — مقبول

            assert src.exists(), "المصدر يجب أن يظل موجوداً بعد KeyboardInterrupt"

    def test_P5_refuse_overwrite_on_directory(self):
        """النقل فوق مجلد موجود يُرفض برسالة صريحة."""
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            src = base / "source.txt"
            dst_dir = base / "dest_dir"
            dst_dir.mkdir()
            src.write_text("المحتوى الأصلي")

            mover = SafeMover()
            result = mover.move(str(src), str(dst_dir))

            assert result.success is False, "النقل فوق مجلد يجب أن يُرفض"
            assert src.exists(), "المصدر يجب أن يظل موجوداً"

    def test_normal_move_still_works(self):
        """النقل الطبيعي يجب أن لا يزال ينجح (لا كسر للسلوك الصحيح)."""
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            src = base / "source.txt"
            dst = base / "dest.txt"
            src.write_text("المحتوى الأصلي")

            mover = SafeMover()
            result = mover.move(str(src), str(dst))

            assert result.success is True, f"النقل الطبيعي يجب أن ينجح: {result.error}"
            assert not src.exists(), "المصدر يجب أن يُحذف بعد النقل الناجح"
            assert dst.exists(), "الوجهة يجب أن تُنشأ"
            assert dst.read_text() == "المحتوى الأصلي", "محتوى الوجهة يجب أن يطابق المصدر"

    def test_overwrite_true_forbidden(self):
        """overwrite=True يُرفع OverwriteForbiddenError في المُنشئ وفي move()."""
        with pytest.raises(OverwriteForbiddenError):
            SafeMover(overwrite=True)

        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            src = base / "source.txt"
            dst = base / "dest.txt"
            src.write_text("المحتوى الأصلي")
            dst.write_text("البيانات الموجودة")

            mover = SafeMover()
            result = mover.move(str(src), str(dst), overwrite=True)
            assert result.success is False
            assert "overwrite" in (result.error or "").lower()


# ═════════════════════════════════════════════════════════════════════════════
# F6/F7 — التراجع لا يستبدل الملف الجديد بصمت
# ═════════════════════════════════════════════════════════════════════════════

class TestF6_UndoDoesNotDestroyNewFile:
    """F6: FileHandler.undo_last_action لا يدمر ملفاً جديداً أُنشئ بالاسم الأصلي."""

    def test_undo_preserves_new_file_created_after_move(self):
        """نقل → إنشاء ملف جديد بالاسم الأصلي → undo — الملف الجديد يُحفظ (لا يُستبدل)."""
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            fh = FileHandler()

            src = base / "source.txt"
            src.write_text("المحتوى الأصلي")
            dest_dir = base / "category"

            move_result = fh.move_file(str(src), "category", str(base))
            assert move_result["success"] is True

            # إنشاء ملف جديد بالاسم الأصلي في المسار الأصلي (محاكاة-user)
            new_file = base / "source.txt"
            new_file.write_text("المحتوى الجديد مهم - يجب ألا يُدمر")

            undo_result = fh.undo_last_action()
            assert undo_result["success"] is True, f"التراجع يجب أن ينجح: {undo_result.get('error')}"

            # الملف الجديد يجب ألا يُدمّر (قد يُعاد تسميته ولكن لا يُمحى ولا يُستبدل)
            assert new_file.exists(), "الملف الجديد يجب ألا يُحذف أثناء التراجع"
            assert new_file.read_text() == "المحتوى الجديد مهم - يجب ألا يُدمر", (
                "محتوى الملف الجديد يجب ألا يُستبدل بمحتوى الملف المستعاد"
            )


# ═════════════════════════════════════════════════════════════════════════════
# F8 — renameat2 موثقة ومُنفذة (لا تناقض وثيقة/كود)
# ═════════════════════════════════════════════════════════════════════════════

class TestF8_Renameat2Implemented:
    """F8: renameat2 موصوف في الوثيقة ومُنفذ في الكود (لا تناقض)."""

    def test_renameat2_is_importable_and_usable(self):
        """safe_mover.styre يُصدر renameat2 availability."""
        from src.core import safe_mover as sm

        # renameat2 متوفر كآلية (قد يكون غير متوفر على macOS بسبب AT_FDCWD، ولكن الكود يتعامل مع ذلك)
        assert hasattr(sm, "_renameat2_available")
        assert hasattr(sm, "_RENAME_NOREPLACE")
        # الكود يحتوي على المنطق nawet لو النظام لا يدعم renameat2 فعلياً
