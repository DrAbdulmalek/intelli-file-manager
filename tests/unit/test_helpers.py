"""اختبارات وحدة helpers - الوظائف المساعدة

يغطي هذا الملف الاختبارات التالية:
  - تنسيق حجم الملف بوحدات مختلفة
  - الحصول على أيقونة الملف
  - حساب hash للملف
  - التحقق من أمان المسار
  - تنظيف اسم الملف
"""
import os
from pathlib import Path

import pytest

from src.utils.helpers import (
    format_size,
    get_file_icon,
    compute_file_hash,
    is_path_safe,
    sanitize_filename,
)


class TestFormatSize:
    """اختبار دالة تنسيق حجم الملف"""

    def test_format_size_zero_bytes(self):
        """يتحقق من تنسيق الصفر بايت"""
        result = format_size(0)
        assert result == "0 بايت"

    def test_format_size_bytes(self):
        """يتحقق من تنسيق الحجم بالبايت (أقل من 1 كيلوبايت)"""
        result = format_size(500)
        assert "بايت" in result
        assert "500.0" in result

    def test_format_size_kilobytes(self):
        """يتحقق من تنسيق الحجم بالكيلوبايت"""
        result = format_size(1024)
        assert "كيلوبايت" in result
        assert "1.0" in result

    def test_format_size_megabytes(self):
        """يتحقق من تنسيق الحجم بالميغابايت"""
        result = format_size(1024 * 1024)  # 1 MB
        assert "ميغابايت" in result
        assert "1.0" in result

    def test_format_size_gigabytes(self):
        """يتحقق من تنسيق الحجم بالغيغابايت"""
        result = format_size(1024 * 1024 * 1024)  # 1 GB
        assert "غيغابايت" in result
        assert "1.0" in result

    def test_format_size_terabytes(self):
        """يتحقق من تنسيق الحجم بالتيرابايت"""
        result = format_size(1024 * 1024 * 1024 * 1024)  # 1 TB
        assert "تيرابايت" in result
        assert "1.0" in result

    def test_format_size_fractional(self):
        """يتحقق من تنسيق الحجم الكسري (1.5 ميغابايت)"""
        result = format_size(int(1.5 * 1024 * 1024))
        assert "ميغابايت" in result
        assert "1.5" in result

    def test_format_size_large_file(self):
        """يتحقق من تنسيق حجم كبير (5.7 غيغابايت)"""
        result = format_size(int(5.7 * 1024 * 1024 * 1024))
        assert "غيغابايت" in result
        assert "5.7" in result

    def test_format_size_various_units(self):
        """يتحقق من تنسيق مجموعة متنوعة من الأحجام والتحول بين الوحدات

        يختبر الانتقال التدريجي بين الوحدات:
          - 512 بايت -> بايت
          - 1536 بايت -> 1.5 كيلوبايت
          - 2.5 ميغابايت
          - 3.2 غيغابايت
        """
        # أقل من كيلوبايت
        assert "بايت" in format_size(512)

        # بين كيلوبايت وميغابايت
        assert "كيلوبايت" in format_size(1536)
        assert "1.5" in format_size(1536)

        # بين ميغابايت وغيغابايت
        assert "ميغابايت" in format_size(int(2.5 * 1024 * 1024))

        # بين غيغابايت وتيرابايت
        assert "غيغابايت" in format_size(int(3.2 * 1024 * 1024 * 1024))

    def test_format_size_one_byte(self):
        """يتحقق من تنسيق بايت واحد"""
        result = format_size(1)
        assert "1.0" in result
        assert "بايت" in result


class TestGetFileIcon:
    """اختبار دالة الحصول على أيقونة الملف"""

    def test_get_file_icon_pdf(self):
        """يتحقق من أيقونة ملف PDF"""
        assert get_file_icon(".pdf") == "📄"

    def test_get_file_icon_images(self):
        """يتحقق من أيقونات ملفات الصور المتعددة"""
        assert get_file_icon(".jpg") == "🖼️"
        assert get_file_icon(".jpeg") == "🖼️"
        assert get_file_icon(".png") == "🖼️"
        assert get_file_icon(".gif") == "🖼️"
        assert get_file_icon(".svg") == "🖼️"

    def test_get_file_icon_video(self):
        """يتحقق من أيقونات ملفات الفيديو"""
        assert get_file_icon(".mp4") == "🎬"
        assert get_file_icon(".avi") == "🎬"
        assert get_file_icon(".mkv") == "🎬"

    def test_get_file_icon_audio(self):
        """يتحقق من أيقونات ملفات الصوت"""
        assert get_file_icon(".mp3") == "🎵"
        assert get_file_icon(".wav") == "🎵"
        assert get_file_icon(".flac") == "🎵"

    def test_get_file_icon_code(self):
        """يتحقق من أيقونات ملفات البرمجة"""
        assert get_file_icon(".py") == "🐍"
        assert get_file_icon(".js") == "⚡"
        assert get_file_icon(".ts") == "⚡"
        assert get_file_icon(".html") == "🌐"
        assert get_file_icon(".css") == "🎨"

    def test_get_file_icon_archive(self):
        """يتحقق من أيقونات ملفات الأرشيفات"""
        assert get_file_icon(".zip") == "📦"
        assert get_file_icon(".rar") == "📦"
        assert get_file_icon(".7z") == "📦"

    def test_get_file_icon_unknown(self):
        """يتحقق من أن الامتداد غير المعروف يُرجع أيقونة المجلد الافتراضية"""
        assert get_file_icon(".xyz123") == "📁"
        assert get_file_icon("") == "📁"
        assert get_file_icon("no_extension") == "📁"

    def test_get_file_icon_case_insensitive(self):
        """يتحقق من أن الدالة تتجاهل حالة الأحرف"""
        assert get_file_icon(".PDF") == "📄"
        assert get_file_icon(".Jpg") == "🖼️"
        assert get_file_icon(".MP3") == "🎵"
        assert get_file_icon(".ZIP") == "📦"


class TestComputeFileHash:
    """اختبار دالة حساب hash للملف"""

    def test_compute_file_hash_sha256(self, tmp_path):
        """يتحقق من حساب SHA-256 بشكل صحيح"""
        test_file = tmp_path / "hash_test.txt"
        test_file.write_text("محتوى تجريبي للهاش", encoding="utf-8")

        hash_result = compute_file_hash(str(test_file), "sha256")

        assert isinstance(hash_result, str)
        assert len(hash_result) == 64  # SHA-256 hex = 64 حرف

    def test_compute_file_hash_md5(self, tmp_path):
        """يتحقق من حساب MD5 بشكل صحيح"""
        test_file = tmp_path / "hash_md5.txt"
        test_file.write_text("test content", encoding="utf-8")

        hash_result = compute_file_hash(str(test_file), "md5")

        assert isinstance(hash_result, str)
        assert len(hash_result) == 32  # MD5 hex = 32 حرف

    def test_compute_file_hash_deterministic(self, tmp_path):
        """يتحقق من أن حساب الهاش يعطي نفس النتيجة دائماً لنفس الملف"""
        test_file = tmp_path / "deterministic.txt"
        test_file.write_bytes(b"same content")

        hash1 = compute_file_hash(str(test_file))
        hash2 = compute_file_hash(str(test_file))

        assert hash1 == hash2

    def test_compute_file_hash_different_files(self, tmp_path):
        """يتحقق من أن ملفات مختلفة تعطي قيم هاش مختلفة"""
        file1 = tmp_path / "file1.txt"
        file1.write_bytes(b"content 1")

        file2 = tmp_path / "file2.txt"
        file2.write_bytes(b"content 2")

        hash1 = compute_file_hash(str(file1))
        hash2 = compute_file_hash(str(file2))

        assert hash1 != hash2

    def test_compute_file_hash_empty_file(self, tmp_path):
        """يتحقق من حساب هاش ملف فارغ"""
        empty_file = tmp_path / "empty.txt"
        empty_file.write_bytes(b"")

        hash_result = compute_file_hash(str(empty_file))

        assert isinstance(hash_result, str)
        assert len(hash_result) > 0
        # SHA-256 لملف فارغ
        import hashlib
        expected = hashlib.sha256(b"").hexdigest()
        assert hash_result == expected

    def test_compute_file_hash_large_file(self, tmp_path):
        """يتحقق من حساب هاش ملف كبير (يُقرأ على دفعات)"""
        large_file = tmp_path / "large.bin"
        # ملف 100 كيلوبايت
        large_file.write_bytes(b"A" * 100_000)

        hash_result = compute_file_hash(str(large_file))

        assert isinstance(hash_result, str)
        assert len(hash_result) == 64


class TestIsPathSafe:
    """اختبار دالة التحقق من أمان المسار"""

    def test_is_path_safe_within_base(self, tmp_path):
        """يتحقق من أن المسار داخل القاعدة يُعتبر آمناً"""
        safe_path = tmp_path / "subfolder" / "file.txt"
        assert is_path_safe(str(tmp_path), str(safe_path)) is True

    def test_is_path_safe_same_path(self, tmp_path):
        """يتحقق من أن المسار نفسه يُعتبر آمناً"""
        assert is_path_safe(str(tmp_path), str(tmp_path)) is True

    def test_is_path_safe_traversal(self, tmp_path):
        """يتحقق من رفض path traversal (نقاط مزدوجة)

        يجب ألا يُسمح بالوصول لمجلدات خارج القاعدة عبر ../
        """
        if tmp_path.parent.parent.exists():
            dangerous = tmp_path / ".." / ".." / "etc" / "passwd"
            assert is_path_safe(str(tmp_path), str(dangerous)) is False

    def test_is_path_safe_absolute_outside(self, tmp_path):
        """يتحقق من رفض المسار المطلق خارج القاعدة"""
        assert is_path_safe(str(tmp_path), "/etc/passwd") is False

    def test_is_path_safe_nonexistent_target(self, tmp_path):
        """يتحقق من أن المسار غير الموجود داخل القاعدة يُعتبر آمناً"""
        nonexistent = tmp_path / "does_not_exist" / "file.txt"
        assert is_path_safe(str(tmp_path), str(nonexistent)) is True

    def test_is_path_safe_empty_paths(self):
        """يتحقق من أن المسارات الفارغة تُعامل بأمان"""
        # لا يجب أن يُطرح استثناء
        result = is_path_safe("", "")
        assert isinstance(result, bool)


class TestSanitizeFilename:
    """اختبار دالة تنظيف اسم الملف"""

    def test_sanitize_filename_dangerous_chars(self):
        """يتحقق من إزالة الأحرف الخطرة من اسم الملف

        الأحرف الخطرة: < > : " / \\ | ? * \\0
        يجب أن تُستبدل بشرطة سفلية _
        """
        assert sanitize_filename('file<name>.txt') == 'file_name_.txt'
        assert sanitize_filename('file>name>.txt') == 'file_name_.txt'
        assert sanitize_filename('file:name.txt') == 'file_name.txt'
        assert sanitize_filename('file"name.txt') == 'file_name.txt'
        assert sanitize_filename('file/name.txt') == 'file_name.txt'
        assert sanitize_filename('file\\name.txt') == 'file_name.txt'
        assert sanitize_filename('file|name.txt') == 'file_name.txt'
        assert sanitize_filename('file?name.txt') == 'file_name.txt'
        assert sanitize_filename('file*name.txt') == 'file_name.txt'

    def test_sanitize_filename_leading_dots(self):
        """يتحقق من إزالة النقاط والمسافات من البداية والنهاية"""
        assert sanitize_filename('..hidden') == 'hidden'
        assert sanitize_filename('  spaced  ') == 'spaced'
        assert sanitize_filename('. .test. .') == 'test'

    def test_sanitize_filename_clean_input(self):
        """يتحقق من أن الاسم النظيف لا يتغير"""
        assert sanitize_filename('document.pdf') == 'document.pdf'
        assert sanitize_filename('report_2024.xlsx') == 'report_2024.xlsx'

    def test_sanitize_filename_arabic(self):
        """يتحقق من أن الأسماء العربية النظيفة لا تتغير"""
        assert sanitize_filename('تقرير_المبيعات.pdf') == 'تقرير_المبيعات.pdf'
        assert sanitize_filename('ملخص الربع الأول.docx') == 'ملخص الربع الأول.docx'

    def test_sanitize_filename_combined_dangerous(self):
        """يتحقق من تنظيف اسم يحتوي عدة أحرف خطرة"""
        result = sanitize_filename('file<>:"/\\|?*test.txt')
        assert '<' not in result
        assert '>' not in result
        assert ':' not in result
        assert '"' not in result
        assert '/' not in result
        assert '\\' not in result
        assert '|' not in result
        assert '?' not in result
        assert '*' not in result
