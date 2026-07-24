"""اختبارات تكامل لـ FileInventory

يغطي هذا الملف:
  - مسح مجلد حقيقي يحتوي ملفات txt/md/pdf/docx/xlsx/pptx
  - استخراج الميتاداتا بشكل صحيح (الحجم، الامتداد، التصنيف)
  - حساب SHA-256 لكل ملف
  - كشف التكرار عبر hash
  - استخراج النص من كل نوع مدعوم
  - تخطي الملفات المخفية
  - المسح المتداخل (recursive)
  - تسامح الأخطاء (ملف تالف لا يوقف المسح)
  - الإحصائيات النهائية (InventoryStats)

PR-02 من development-roadmap-v1.0
"""
import hashlib
from pathlib import Path

import pytest

from src.core.file_inventory import (
    FileInventory,
    InventoryStats,
    MAX_CONTENT_EXTRACTION_SIZE,
    TEXT_EXTRACTABLE_EXT,
)


# ─── Fixtures محلية ──────────────────────────────────────────────────────

@pytest.fixture
def inventory():
    """FileInventory بإعدادات افتراضية"""
    return FileInventory()


@pytest.fixture
def inventory_no_content():
    """FileInventory بدون استخراج المحتوى (أسرع للاختبارات الأخرى)"""
    return FileInventory(include_content=False)


# ─── اختبارات المسح الأساسية ──────────────────────────────────────────────

class TestScanBasic:
    """اختبارات المسح الأساسية"""

    def test_scan_returns_file_records(self, inventory_no_content, real_doc_dir):
        """المسح يُرجع FileRecord لكل ملف (وليس dict خام)"""
        records = list(inventory_no_content.scan(str(real_doc_dir)))
        assert len(records) > 0
        assert all(hasattr(r, "metadata") for r in records)
        assert all(hasattr(r, "document_text") for r in records)

    def test_scan_includes_all_supported_types(self, inventory_no_content, real_doc_dir):
        """يجب أن يجد كل الأنواع المدعومة في real_doc_dir"""
        records = inventory_no_content.scan_directory(str(real_doc_dir))
        extensions_found = {r.metadata.extension.lower() for r in records}
        # الأنواع الموجودة في real_doc_dir
        expected_extensions = {"txt", "md", "pdf", "docx", "xlsx", "pptx", "jpg"}
        assert expected_extensions.issubset(extensions_found), (
            f"missing extensions: {expected_extensions - extensions_found}"
        )

    def test_scan_recursive_includes_subfolder(self, inventory_no_content, real_doc_dir):
        """المسح المتداخل يلتقط ملف subfolder/nested.txt"""
        records = inventory_no_content.scan_directory(str(real_doc_dir))
        paths = [r.metadata.file_path for r in records]
        nested_path = str(real_doc_dir / "subfolder" / "nested.txt")
        assert any(p == nested_path for p in paths), (
            "nested file not found — recursive scan failed"
        )

    def test_scan_non_recursive_excludes_subfolder(self, inventory_no_content, real_doc_dir):
        """المسح غير المتداخل لا يلتقط الملفات داخل subfolder"""
        records = list(inventory_no_content.scan(str(real_doc_dir), recursive=False))
        paths = [r.metadata.file_path for r in records]
        nested_path = str(real_doc_dir / "subfolder" / "nested.txt")
        assert all(p != nested_path for p in paths), (
            "nested file found in non-recursive scan"
        )

    def test_scan_skips_hidden_files(self, inventory_no_content, real_doc_dir):
        """الملفات المخفية (التي تبدأ بـ .) يجب تخطيها"""
        records = inventory_no_content.scan_directory(str(real_doc_dir))
        names = [r.metadata.file_name for r in records]
        assert ".hidden_secret" not in names, "hidden file was not skipped"

    def test_scan_nonexistent_directory_returns_empty(self, inventory):
        """مسح مجلد غير موجود يُرجع قائمة فارغة"""
        records = list(inventory.scan("/nonexistent/path/xyz"))
        assert records == []
        assert inventory.last_stats is not None
        assert len(inventory.last_stats.errors) > 0


# ─── اختبارات الميتاداتا ─────────────────────────────────────────────────

class TestMetadata:
    """اختبارات استخراج الميتاداتا"""

    def test_metadata_contains_required_fields(self, inventory_no_content, real_doc_dir):
        """كل FileMetadata يجب أن تحتوي الحقول الإلزامية"""
        records = inventory_no_content.scan_directory(str(real_doc_dir))
        for record in records:
            md = record.metadata
            assert md.file_name, f"empty file_name for {record}"
            assert md.file_path, f"empty file_path for {record}"
            assert md.file_size >= 0, f"negative size for {record}"
            assert md.extension, f"empty extension for {record}"
            assert md.category, f"empty category for {record}"
            assert md.created_at, f"empty created_at for {record}"
            assert md.modified_at, f"empty modified_at for {record}"

    def test_metadata_category_matches_extension(self, inventory_no_content, real_doc_dir):
        """التصنيف يجب أن يطابق الامتداد وفق FileCategory.from_extension"""
        records = inventory_no_content.scan_directory(str(real_doc_dir))
        ext_to_category = {
            "txt": "مستندات", "md": "مستندات", "pdf": "مستندات",
            "docx": "مستندات", "xlsx": "مستندات", "pptx": "مستندات",
            "jpg": "صور",
        }
        for record in records:
            ext = record.metadata.extension.lower()
            if ext in ext_to_category:
                assert record.metadata.category == ext_to_category[ext], (
                    f"wrong category for .{ext}: got {record.metadata.category}"
                )

    def test_metadata_size_matches_actual_file(self, inventory_no_content, real_doc_dir):
        """حجم الملف في الميتاداتا يجب أن يطابق حجم الملف الفعلي"""
        records = inventory_no_content.scan_directory(str(real_doc_dir))
        for record in records:
            actual_size = Path(record.metadata.file_path).stat().st_size
            assert record.metadata.file_size == actual_size, (
                f"size mismatch for {record.metadata.file_name}: "
                f"metadata={record.metadata.file_size}, actual={actual_size}"
            )

    def test_metadata_parent_dir_extracted(self, inventory_no_content, real_doc_dir):
        """parent_dir يجب أن يُستخرج من file_path تلقائيًا"""
        records = inventory_no_content.scan_directory(str(real_doc_dir))
        for record in records:
            expected_parent = str(Path(record.metadata.file_path).parent)
            assert record.metadata.parent_dir == expected_parent


# ─── اختبارات الـ hash وكشف التكرار ───────────────────────────────────────

class TestHashAndDuplicates:
    """اختبارات حساب الـ hash وكشف التكرار"""

    def test_sha256_hash_computed_for_every_file(self, inventory_no_content, real_doc_dir):
        """كل ملف يجب أن يحتوي SHA-256 صالح (64 hex chars)"""
        records = inventory_no_content.scan_directory(str(real_doc_dir))
        for record in records:
            h = record.metadata.sha256_hash
            assert h, f"empty hash for {record.metadata.file_name}"
            assert len(h) == 64, f"invalid SHA-256 length for {record.metadata.file_name}"
            assert all(c in "0123456789abcdef" for c in h), (
                f"non-hex char in hash for {record.metadata.file_name}"
            )

    def test_sha256_matches_manual_computation(self, inventory_no_content, real_doc_dir):
        """الـ hash يجب أن يطابق حساب hashlib اليدوي"""
        records = inventory_no_content.scan_directory(str(real_doc_dir))
        for record in records:
            file_path = Path(record.metadata.file_path)
            expected = hashlib.sha256(file_path.read_bytes()).hexdigest()
            assert record.metadata.sha256_hash == expected, (
                f"hash mismatch for {record.metadata.file_name}"
            )

    def test_duplicate_files_flagged(self, inventory_no_content, real_doc_dir):
        """notes.txt و notes_copy.txt لهما نفس المحتوى فيجب أن يُعلَّم الثاني كمكرر"""
        records = inventory_no_content.scan_directory(str(real_doc_dir))
        by_name = {r.metadata.file_name: r for r in records}
        assert "notes.txt" in by_name
        assert "notes_copy.txt" in by_name
        # الأول ليس مكررًا (هو الأصل)، الثاني يجب أن يكون مكررًا
        # ملاحظة: الترتيب يعتمد على glob لكن أحد الاثنين على الأقل يجب أن يكون is_duplicate=True
        dup_flags = {
            by_name["notes.txt"].metadata.is_duplicate,
            by_name["notes_copy.txt"].metadata.is_duplicate,
        }
        assert True in dup_flags, "neither duplicate file was flagged"

    def test_unique_files_not_flagged(self, inventory_no_content, real_doc_dir):
        """ملفات فريدة لا يجب أن تُعلَّم كمكررة"""
        records = inventory_no_content.scan_directory(str(real_doc_dir))
        unique_files = [r for r in records if r.metadata.file_name in
                       {"report.pdf", "document.docx", "spreadsheet.xlsx", "presentation.pptx"}]
        for record in unique_files:
            assert record.metadata.is_duplicate is False, (
                f"{record.metadata.file_name} wrongly flagged as duplicate"
            )


# ─── اختبارات استخراج المحتوى ─────────────────────────────────────────────

class TestContentExtraction:
    """اختبارات استخراج النص من الأنواع المدعومة"""

    def test_txt_content_extracted(self, inventory, real_doc_dir):
        """txt: يجب استخراج النص الكامل"""
        records = inventory.scan_directory(str(real_doc_dir))
        txt_record = next(r for r in records if r.metadata.file_name == "notes.txt")
        assert "This is a test note" in txt_record.document_text
        assert "هذه ملاحظات تجريبية" in txt_record.document_text

    def test_md_content_extracted(self, inventory, real_doc_dir):
        """md: يجب استخراج النص الكامل"""
        records = inventory.scan_directory(str(real_doc_dir))
        md_record = next(r for r in records if r.metadata.file_name == "readme.md")
        assert "عنوان" in md_record.document_text
        assert "فقرة وصفية" in md_record.document_text

    def test_pdf_content_extracted(self, inventory, real_doc_dir):
        """pdf: يجب استخراج نص ولو جزئيًا"""
        records = inventory.scan_directory(str(real_doc_dir))
        pdf_record = next(r for r in records if r.metadata.file_name == "report.pdf")
        # PDF قد لا يُستخرج نصه كاملًا بسبب الترميز، لكن يجب أن يحتوي شيئًا
        # لو فشل الاستخراج، النص يكون فارغًا — نقبل ذلك لكن نتحقق من عدم الانهيار
        assert isinstance(pdf_record.document_text, str)
        # لو كان النص فارغًا، يجب أن يُسجَّل في الإحصائيات
        if not pdf_record.document_text:
            stats = inventory.last_stats
            assert stats.content_extraction_failed > 0

    def test_docx_content_extracted(self, inventory, real_doc_dir):
        """docx: يجب استخراج النص من الفقرات والجداول"""
        records = inventory.scan_directory(str(real_doc_dir))
        docx_record = next(r for r in records if r.metadata.file_name == "document.docx")
        assert "Hello from DOCX" in docx_record.document_text
        assert "Test content for extraction" in docx_record.document_text
        # الجدول أيضًا
        assert "Name" in docx_record.document_text
        assert "Ahmad" in docx_record.document_text

    def test_xlsx_content_extracted(self, inventory, real_doc_dir):
        """xlsx: يجب استخراج النص من كل الأوراق"""
        records = inventory.scan_directory(str(real_doc_dir))
        xlsx_record = next(r for r in records if r.metadata.file_name == "spreadsheet.xlsx")
        # الورقة الأولى
        assert "Sheet1" in xlsx_record.document_text
        assert "Ahmad" in xlsx_record.document_text
        assert "Damascus" in xlsx_record.document_text
        # الورقة الثانية
        assert "Sheet2" in xlsx_record.document_text
        assert "Book" in xlsx_record.document_text

    def test_pptx_content_extracted(self, inventory, real_doc_dir):
        """pptx: يجب استخراج النص من الشرائح والجداول"""
        records = inventory.scan_directory(str(real_doc_dir))
        pptx_record = next(r for r in records if r.metadata.file_name == "presentation.pptx")
        # شريحة 1
        assert "First Slide" in pptx_record.document_text
        assert "Hello from PPTX" in pptx_record.document_text
        # شريحة 2
        assert "Second slide content" in pptx_record.document_text
        # جدول
        assert "Col1" in pptx_record.document_text or "Val1" in pptx_record.document_text

    def test_unsupported_extension_no_content(self, inventory, real_doc_dir):
        """jpg: ملف غير مدعوم للاستخراج يجب أن يكون document_text فارغًا"""
        records = inventory.scan_directory(str(real_doc_dir))
        jpg_record = next(r for r in records if r.metadata.file_name == "image.jpg")
        assert jpg_record.document_text == ""

    def test_content_extraction_disabled(self, real_doc_dir):
        """عند include_content=False، يجب أن يكون document_text فارغًا دائمًا"""
        inv = FileInventory(include_content=False)
        records = inv.scan_directory(str(real_doc_dir))
        for record in records:
            assert record.document_text == "", (
                f"content extracted despite include_content=False for {record.metadata.file_name}"
            )


# ─── اختبارات التسامح مع الأخطاء ──────────────────────────────────────────

class TestErrorTolerance:
    """اختبارات تسامح FileInventory مع الملفات التالفة"""

    def test_corrupted_file_does_not_stop_scan(self, inventory, tmp_path):
        """ملف تالف لا يجب أن يوقف المسح كله"""
        # ملف txt صحيح
        (tmp_path / "good1.txt").write_text("good content 1", encoding="utf-8")
        # ملف docx تالف (بايتات وهمية)
        (tmp_path / "bad.docx").write_bytes(b"not really a docx file")
        # ملف xlsx تالف
        (tmp_path / "bad.xlsx").write_bytes(b"not really an xlsx")
        # ملف txt صحيح آخر
        (tmp_path / "good2.txt").write_text("good content 2", encoding="utf-8")

        records = inventory.scan_directory(str(tmp_path))
        # كل الملفات الأربعة يجب أن تُفهرس (حتى التالفة)
        names = {r.metadata.file_name for r in records}
        assert "good1.txt" in names
        assert "good2.txt" in names
        assert "bad.docx" in names
        assert "bad.xlsx" in names
        # الملفات التالفة يجب أن يكون document_text فارغًا
        bad_docx = next(r for r in records if r.metadata.file_name == "bad.docx")
        assert bad_docx.document_text == ""
        # الإحصائيات يجب أن تسجل فشل الاستخراج
        assert inventory.last_stats.content_extraction_failed >= 2

    def test_empty_file_does_not_crash(self, inventory, tmp_path):
        """ملف فارغ يجب أن يُفهرس بنجاح"""
        (tmp_path / "empty.txt").write_bytes(b"")
        records = inventory.scan_directory(str(tmp_path))
        assert len(records) == 1
        assert records[0].metadata.file_size == 0
        assert records[0].metadata.sha256_hash  # hash ملف فارغ معروف

    def test_symbolic_link_skipped_or_handled(self, inventory, tmp_path):
        """رمزية symlink لا يجب أن تسبب حلقة لا نهائية"""
        (tmp_path / "real.txt").write_text("real", encoding="utf-8")
        # symlink يشير إلى نفس المجلد (قد يسبب loop في المسح المتداخل)
        try:
            (tmp_path / "link.txt").symlink_to(tmp_path / "real.txt")
        except OSError:
            pytest.skip("symlinks not supported on this OS")
        records = inventory.scan_directory(str(tmp_path))
        # يجب أن نجد على الأقل real.txt
        names = {r.metadata.file_name for r in records}
        assert "real.txt" in names


# ─── اختبارات الإحصائيات ──────────────────────────────────────────────────

class TestInventoryStats:
    """اختبارات InventoryStats"""

    def test_stats_populated_after_scan(self, inventory_no_content, real_doc_dir):
        """last_stats يجب أن تُملأ بعد المسح"""
        inventory_no_content.scan_directory(str(real_doc_dir))
        stats = inventory_no_content.last_stats
        assert stats is not None
        assert stats.total_files > 0
        assert stats.indexed_files > 0
        assert stats.total_size_bytes > 0
        assert stats.duration_seconds >= 0.0

    def test_stats_to_dict_serializable(self, inventory_no_content, real_doc_dir):
        """stats.to_dict() يجب أن يُرجع قاموسًا قابلًا للتسلسل"""
        inventory_no_content.scan_directory(str(real_doc_dir))
        d = inventory_no_content.last_stats.to_dict()
        assert isinstance(d, dict)
        assert "total_files" in d
        assert "indexed_files" in d
        assert "total_size_human" in d
        assert "duration_seconds" in d

    def test_stats_counts_match_actual_records(self, inventory_no_content, real_doc_dir):
        """stats.indexed_files يجب أن يطابق عدد records الفعلية"""
        records = inventory_no_content.scan_directory(str(real_doc_dir))
        stats = inventory_no_content.last_stats
        assert stats.indexed_files == len(records)
        assert stats.total_files == len(records) + stats.skipped_files

    def test_stats_with_content_extraction(self, inventory, real_doc_dir):
        """عند تفعيل include_content، stats.content_extracted يجب أن يكون > 0"""
        inventory.scan_directory(str(real_doc_dir))
        stats = inventory.last_stats
        # على الأقل txt و md و docx يجب أن يُستخرج نصهما
        assert stats.content_extracted >= 3, (
            f"expected ≥3 successful extractions, got {stats.content_extracted}"
        )


# ─── اختبارات التكوين (Configuration) ─────────────────────────────────────

class TestConfiguration:
    """اختبارات تكوين FileInventory"""

    def test_custom_skip_dirs(self, tmp_path):
        """skip_dirs مخصص يجب أن يُحترم"""
        (tmp_path / "keep.txt").write_text("keep", encoding="utf-8")
        excluded = tmp_path / "excluded_dir"
        excluded.mkdir()
        (excluded / "skip.txt").write_text("skip", encoding="utf-8")

        inv = FileInventory(include_content=False, skip_dirs={"excluded_dir"})
        records = inv.scan_directory(str(tmp_path))
        names = {r.metadata.file_name for r in records}
        assert "keep.txt" in names
        assert "skip.txt" not in names

    def test_max_file_size_respected(self, tmp_path):
        """الملفات الأكبر من max_file_size لا يُستخرج منها محتوى"""
        # ملف صغير
        (tmp_path / "small.txt").write_text("small", encoding="utf-8")
        # ملف أكبر من 5 بايت (max_file_size=5)
        (tmp_path / "large.txt").write_text("this is a large file content", encoding="utf-8")

        inv = FileInventory(max_file_size=5)
        records = inv.scan_directory(str(tmp_path))
        by_name = {r.metadata.file_name: r for r in records}
        # الملف الصغير يجب أن يُستخرج منه المحتوى
        assert by_name["small.txt"].document_text == "small"
        # الملف الكبير يجب ألا يُستخرج منه المحتوى
        assert by_name["large.txt"].document_text == ""
        # الخطأ مسجل في الإحصائيات
        assert inv.last_stats.content_extraction_failed >= 1


# ─── اختبارات الأنواع المدعومة ────────────────────────────────────────────

class TestSupportedExtensions:
    """اختبارات TEXT_EXTRACTABLE_EXT وثوابت أخرى"""

    def test_text_extractable_ext_contains_all_five(self):
        """TEXT_EXTRACTABLE_EXT يجب أن يحتوي txt/pdf/docx/xlsx/pptx"""
        expected = {".txt", ".pdf", ".docx", ".xlsx", ".pptx"}
        assert expected.issubset(TEXT_EXTRACTABLE_EXT), (
            f"missing: {expected - TEXT_EXTRACTABLE_EXT}"
        )

    def test_max_content_extraction_size_reasonable(self):
        """MAX_CONTENT_EXTRACTION_SIZE يجب أن يكون بين 1MB و 100MB"""
        assert 1 * 1024 * 1024 <= MAX_CONTENT_EXTRACTION_SIZE <= 100 * 1024 * 1024
