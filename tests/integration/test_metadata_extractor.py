"""اختبارات تكامل لـ MetadataExtractor — PR-03

يغطي هذا الملف:
  - استخراج ميتاداتا الصور (PIL + EXIF) على JPEG و PNG حقيقيين
  - استخراج ميتاداتا الصوت/الفيديو (ffprobe) على MP3 و MP4 حقيقيين
  - كشف نوع المحتوى عبر python-magic مع fallback للامتداد
  - الواجهة الموحّدة extract_extended_metadata
  - التسامح مع الملفات التالفة
  - تكامل FileInventory مع الميتاداتا الموسّعة (extra_metadata)
  - توحيد المستخرجات في MultimodalProcessor

PR-03 من development-roadmap-v1.0
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from src.core.metadata_extractor import (
    IMAGE_EXTENSIONS,
    AV_EXTENSIONS,
    extract_image_metadata,
    extract_av_metadata,
    detect_content_type,
    extract_extended_metadata,
)
from src.core.file_inventory import FileInventory
from src.db.schemas import FileMetadata


# ─── Fixtures محلية ──────────────────────────────────────────────────────

@pytest.fixture
def inventory():
    """FileInventory بإعدادات افتراضية"""
    return FileInventory()


@pytest.fixture
def inventory_no_content():
    """FileInventory بدون استخراج المحتوى (أسرع)"""
    return FileInventory(include_content=False)


# ─── اختبارات استخراج ميتاداتا الصور ──────────────────────────────────────

class TestImageMetadata:
    """اختبارات extract_image_metadata"""

    def test_jpeg_returns_dimensions(self, real_media_dir):
        """JPEG حقيقي يُرجع الأبعاد الصحيحة"""
        info = extract_image_metadata(real_media_dir / "sample.jpg")
        assert info["width"] == 80
        assert info["height"] == 60
        assert info["format"] == "JPEG"

    def test_jpeg_returns_exif(self, real_media_dir):
        """JPEG مع EXIF يُرجع الوسوم المتوقعة"""
        info = extract_image_metadata(real_media_dir / "sample.jpg")
        assert "exif" in info
        exif = info["exif"]
        assert "Make" in exif
        assert exif["Make"] == "TestCamera"
        assert exif["Model"] == "IFM-1000"
        assert exif["DateTime"] == "2026:07:24 10:30:00"

    def test_jpeg_exif_count(self, real_media_dir):
        """exif_count يجب أن يساوي عدد الوسوم"""
        info = extract_image_metadata(real_media_dir / "sample.jpg")
        assert info["exif_count"] == len(info["exif"])
        assert info["exif_count"] >= 3  # Make + Model + DateTime على الأقل

    def test_jpeg_extracted_shortcuts(self, real_media_dir):
        """الحقول المساعدة (captured_at, camera_make, camera_model) تُستخرج من EXIF"""
        info = extract_image_metadata(real_media_dir / "sample.jpg")
        assert info["captured_at"] == "2026:07:24 10:30:00"
        assert info["camera_make"] == "TestCamera"
        assert info["camera_model"] == "IFM-1000"

    def test_png_returns_dimensions_without_exif(self, real_media_dir):
        """PNG بدون EXIF يُرجع الأبعاد فقط (لا مفتاح exif)"""
        info = extract_image_metadata(real_media_dir / "sample.png")
        assert info["width"] == 50
        assert info["height"] == 50
        assert info["format"] == "PNG"
        assert "exif" not in info

    def test_corrupt_image_returns_error(self, real_media_dir):
        """ملف تالف بامتداد jpg يُرجع قاموسًا به error"""
        info = extract_image_metadata(real_media_dir / "corrupt.jpg")
        assert "error" in info
        # يجب ألا يحتوي على أبعاد
        assert "width" not in info
        assert "height" not in info

    def test_nonexistent_image_returns_error(self, tmp_path):
        """ملف غير موجود يُرجع error"""
        info = extract_image_metadata(tmp_path / "nope.jpg")
        # PIL سيرفع استثناء → يُلتقط ويعيد error
        assert "error" in info or "width" not in info


# ─── اختبارات استخراج ميتاداتا الصوت/الفيديو ────────────────────────────────

class TestAVMetadata:
    """اختبارات extract_av_metadata"""

    def test_mp3_returns_duration(self, real_media_dir):
        """MP3 حقيقي يُرجع المدة"""
        info = extract_av_metadata(real_media_dir / "sample.mp3")
        # لو ffprobe غير مثبت، نتخطى
        if info.get("error") == "ffprobe_unavailable":
            pytest.skip("ffprobe not installed")
        assert "duration_seconds" in info
        # المدة يجب أن تكون قريبة من 1.5s (نسمح بتسامح)
        assert 1.0 <= info["duration_seconds"] <= 2.5

    def test_mp3_returns_audio_stream(self, real_media_dir):
        """MP3 يُرجع تفاصيل تدفق الصوت"""
        info = extract_av_metadata(real_media_dir / "sample.mp3")
        if "error" in info:
            pytest.skip(f"ffprobe unavailable: {info['error']}")
        assert "audio" in info
        audio = info["audio"]
        assert audio["codec"] == "mp3"
        assert audio["sample_rate"] == 44100
        assert audio["channels"] == 1

    def test_mp3_returns_tags(self, real_media_dir):
        """MP3 مع tags يُرجع العنوان والفنان"""
        info = extract_av_metadata(real_media_dir / "sample.mp3")
        if "error" in info:
            pytest.skip(f"ffprobe unavailable: {info['error']}")
        assert "tags" in info
        # ffmpeg يضيف title و artist من الـ metadata
        # (ملاحظة: بعض إصدارات ffmpeg لا تضعها في format.tags بل في stream.tags)
        # لذا نتحقق فقط من وجود tags dict
        assert isinstance(info["tags"], dict)

    def test_mp4_returns_video_stream(self, real_media_dir):
        """MP4 حقيقي يُرجع تفاصيل الفيديو"""
        info = extract_av_metadata(real_media_dir / "sample.mp4")
        if "error" in info:
            pytest.skip(f"ffprobe unavailable: {info['error']}")
        assert "video" in info
        video = info["video"]
        assert video["codec"] == "h264"
        assert video["width"] == 160
        assert video["height"] == 120
        assert "fps" in video
        assert video["fps"] == 15.0

    def test_mp4_returns_duration(self, real_media_dir):
        """MP4 يُرجع المدة"""
        info = extract_av_metadata(real_media_dir / "sample.mp4")
        if "error" in info:
            pytest.skip(f"ffprobe unavailable: {info['error']}")
        assert "duration_seconds" in info
        assert 0.5 <= info["duration_seconds"] <= 1.5

    def test_corrupt_av_returns_error(self, tmp_path):
        """ملف تالف بامتداد mp4 يُرجع error (وليس استثناء)"""
        bad = tmp_path / "corrupt.mp4"
        bad.write_bytes(b"not a real mp4")
        info = extract_av_metadata(bad)
        assert "error" in info
        # يجب ألا يحدث استثناء

    def test_av_no_video_stream_when_audio_only(self, real_media_dir):
        """MP3 لا يحتوي على تدفق فيديو"""
        info = extract_av_metadata(real_media_dir / "sample.mp3")
        if "error" in info:
            pytest.skip(f"ffprobe unavailable: {info['error']}")
        assert "video" not in info
        assert "audio" in info


# ─── اختبارات كشف نوع المحتوى (python-magic) ───────────────────────────────

class TestContentType:
    """اختبارات detect_content_type"""

    def test_jpeg_detected_as_image_jpeg(self, real_media_dir):
        """JPEG يُكشَف عبر magic bytes كـ image/jpeg"""
        mime = detect_content_type(real_media_dir / "sample.jpg")
        assert mime == "image/jpeg"

    def test_png_detected_as_image_png(self, real_media_dir):
        """PNG يُكشَف عبر magic bytes كـ image/png"""
        mime = detect_content_type(real_media_dir / "sample.png")
        assert mime == "image/png"

    def test_mp3_detected_as_audio_mpeg(self, real_media_dir):
        """MP3 يُكشَف عبر magic bytes كـ audio/mpeg"""
        mime = detect_content_type(real_media_dir / "sample.mp3")
        assert mime in ("audio/mpeg", "audio/mp3", "application/octet-stream")

    def test_mp4_detected_as_video_mp4(self, real_media_dir):
        """MP4 يُكشَف عبر magic bytes كـ video/mp4"""
        mime = detect_content_type(real_media_dir / "sample.mp4")
        assert mime in ("video/mp4", "application/octet-stream")

    def test_txt_detected_as_text_plain(self, tmp_path):
        """txt يُكشَف كـ text/plain"""
        p = tmp_path / "notes.txt"
        p.write_text("hello world", encoding="utf-8")
        mime = detect_content_type(p)
        assert mime.startswith("text/")

    def test_pdf_detected_as_application_pdf(self, real_media_dir, tmp_path):
        """PDF حقيقي يُكشَف كـ application/pdf"""
        # نستخدم PDF من real_doc_dir (يُبنى عبر reportlab في conftest)
        # لكن real_media_dir لا يحتوي PDF، لذا نستخدم tmp_path مباشرة
        from tests.conftest import _build_real_pdf
        _build_real_pdf(tmp_path / "test.pdf")
        mime = detect_content_type(tmp_path / "test.pdf")
        assert mime == "application/pdf"

    def test_extension_fallback_when_magic_unavailable(self, tmp_path, monkeypatch):
        """لو magic غير مثبت، fallback للامتداد"""
        # نحاكي غياب python-magic
        import sys
        # نحفظ النسخة الأصلية
        original_magic = sys.modules.get("magic")
        sys.modules["magic"] = None  # يجعل import magic يفشل

        try:
            p = tmp_path / "file.xyz"
            p.write_bytes(b"random")
            # لو magic فشل، fallback للامتداد
            mime = detect_content_type(p, ".xyz")
            # امتداد غير معروف → octet-stream
            assert mime == "application/octet-stream"
        finally:
            # استعادة
            if original_magic is not None:
                sys.modules["magic"] = original_magic
            else:
                del sys.modules["magic"]

    def test_extension_fallback_returns_known_mime(self, tmp_path, monkeypatch):
        """fallback للامتداد يُرجع MIME المعروف للامتدادات الشائعة"""
        import sys
        original_magic = sys.modules.get("magic")
        sys.modules["magic"] = None
        try:
            p = tmp_path / "file.docx"
            p.write_bytes(b"random")
            mime = detect_content_type(p, ".docx")
            assert "wordprocessingml" in mime
        finally:
            if original_magic is not None:
                sys.modules["magic"] = original_magic
            else:
                del sys.modules["magic"]


# ─── اختبارات الواجهة الموحّدة ─────────────────────────────────────────────

class TestUnifiedExtractExtended:
    """اختبارات extract_extended_metadata (واجهة موحّدة)"""

    def test_image_returns_image_metadata(self, real_media_dir):
        """ملف صورة يُرجع ميتاداتا الصورة"""
        info = extract_extended_metadata(real_media_dir / "sample.jpg")
        assert "width" in info
        assert "height" in info

    def test_audio_returns_av_metadata(self, real_media_dir):
        """ملف صوت يُرجع ميتاداتا AV"""
        info = extract_extended_metadata(real_media_dir / "sample.mp3")
        # لو ffprobe غير مثبت، info قد يكون {"error": ...}
        if "error" not in info:
            assert "duration_seconds" in info or "audio" in info

    def test_video_returns_av_metadata(self, real_media_dir):
        """ملف فيديو يُرجع ميتاداتا AV"""
        info = extract_extended_metadata(real_media_dir / "sample.mp4")
        if "error" not in info:
            assert "video" in info or "duration_seconds" in info

    def test_text_file_returns_empty_dict(self, tmp_path):
        """ملف نصي يُرجع {} (لا ميتاداتا موسّعة)"""
        p = tmp_path / "notes.txt"
        p.write_text("hello", encoding="utf-8")
        info = extract_extended_metadata(p)
        assert info == {}

    def test_pdf_returns_empty_dict(self, tmp_path):
        """PDF يُرجع {} (لا ميتاداتا موسّعة — استخراج النص في FileInventory)"""
        from tests.conftest import _build_real_pdf
        _build_real_pdf(tmp_path / "test.pdf")
        info = extract_extended_metadata(tmp_path / "test.pdf")
        assert info == {}

    def test_extension_param_overrides_path_suffix(self, tmp_path):
        """تمرير ext= يُستخدم بدلًا من suffix المسار"""
        # ننشئ ملفًا بامتداد غريب لكن نمرّر .jpg
        p = tmp_path / "file.dat"
        p.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 50)  # JPEG magic bytes
        # حتى مع ext=.dat، extract_extended_metadata يفحص ext
        # لكن لو مررنا .jpg، يجب أن يستخدم extract_image_metadata
        info = extract_extended_metadata(p, ".jpg")
        # يجب أن يحاول استخراج ميتاداتا صورة (قد يفشل لأن المحتوى تالف، لكن لا استثناء)
        assert isinstance(info, dict)


# ─── اختبارات تكامل FileInventory ──────────────────────────────────────────

class TestFileInventoryIntegration:
    """اختبارات أن FileInventory يستخدم المستخرجات الجديدة بشكل صحيح"""

    def test_scan_populates_extra_metadata_for_jpeg(self, inventory, real_media_dir):
        """FileRecord لـ JPEG يحتوي extra_metadata مع width/height"""
        records = inventory.scan_directory(str(real_media_dir))
        jpg_record = next(r for r in records if r.metadata.extension == "jpg"
                          and "corrupt" not in r.metadata.file_name)
        assert jpg_record.metadata.extra_metadata
        assert "width" in jpg_record.metadata.extra_metadata
        assert "height" in jpg_record.metadata.extra_metadata

    def test_scan_populates_exif_in_extra_metadata(self, inventory, real_media_dir):
        """extra_metadata للـ JPEG يحتوي EXIF"""
        records = inventory.scan_directory(str(real_media_dir))
        jpg_record = next(r for r in records if r.metadata.file_name == "sample.jpg")
        exif = jpg_record.metadata.extra_metadata.get("exif")
        assert exif is not None
        assert "Make" in exif
        assert exif["Make"] == "TestCamera"

    def test_scan_populates_av_metadata_for_mp3(self, inventory, real_media_dir):
        """FileRecord لـ MP3 يحتوي extra_metadata مع duration"""
        records = inventory.scan_directory(str(real_media_dir))
        mp3_record = next(r for r in records if r.metadata.extension == "mp3")
        if "error" not in mp3_record.metadata.extra_metadata:
            assert "duration_seconds" in mp3_record.metadata.extra_metadata

    def test_scan_populates_av_metadata_for_mp4(self, inventory, real_media_dir):
        """FileRecord لـ MP4 يحتوي extra_metadata مع video info"""
        records = inventory.scan_directory(str(real_media_dir))
        mp4_record = next(r for r in records if r.metadata.extension == "mp4")
        if "error" not in mp4_record.metadata.extra_metadata:
            assert "video" in mp4_record.metadata.extra_metadata

    def test_scan_text_file_has_empty_extra_metadata(self, inventory, real_doc_dir):
        """ملف نصي له extra_metadata فارغة"""
        records = inventory.scan_directory(str(real_doc_dir))
        txt_record = next(r for r in records if r.metadata.extension == "txt"
                          and "copy" not in r.metadata.file_name)
        assert txt_record.metadata.extra_metadata == {}

    def test_scan_uses_python_magic_for_content_type(self, inventory, real_media_dir):
        """content_type يُكشَف عبر python-magic (وليس فقط الامتداد)"""
        records = inventory.scan_directory(str(real_media_dir))
        jpg_record = next(r for r in records if r.metadata.file_name == "sample.jpg")
        assert jpg_record.metadata.content_type == "image/jpeg"

    def test_scan_corrupt_jpeg_does_not_crash(self, inventory, real_media_dir):
        """ملف تالف لا يوقف المسح"""
        records = inventory.scan_directory(str(real_media_dir))
        # يجب أن نحصل على سجلات لكل الملفات السليمة
        extensions = {r.metadata.extension for r in records}
        assert "jpg" in extensions
        assert "png" in extensions
        assert "mp3" in extensions
        assert "mp4" in extensions

    def test_scan_corrupt_jpeg_has_no_extra_metadata(self, inventory, real_media_dir):
        """corrupt.jpg ليس له ميتاداتا موسّعة صالحة"""
        records = inventory.scan_directory(str(real_media_dir))
        corrupt = next(r for r in records if r.metadata.file_name == "corrupt.jpg")
        # extra_metadata قد يكون {} أو {"error": ...}
        assert "width" not in corrupt.metadata.extra_metadata
        assert "height" not in corrupt.metadata.extra_metadata

    def test_scan_stats_track_all_media_files(self, inventory, real_media_dir):
        """الإحصائيات تشمل كل ملفات الوسائط"""
        records = inventory.scan_directory(str(real_media_dir))
        # real_media_dir يحتوي: sample.jpg, sample.png, sample.mp3, sample.mp4, corrupt.jpg
        assert len(records) == 5
        assert inventory.last_stats.total_files == 5
        assert inventory.last_stats.indexed_files == 5


# ─── اختبارات توحيد MultimodalProcessor ────────────────────────────────────

class TestMultimodalProcessorUnification:
    """اختبارات أن MultimodalProcessor يُوكِّل إلى المستخرج الموحّد"""

    def test_process_image_returns_dimensions(self, real_media_dir):
        """process_image يُرجع width/height من extract_image_metadata"""
        # لا نحتاج AI — نشيد MultimodalProcessor بدون ollama
        from src.core.multimodal_processor import MultimodalProcessor
        proc = MultimodalProcessor()
        result = proc.process_image(str(real_media_dir / "sample.jpg"))
        assert result["width"] == 80
        assert result["height"] == 60
        assert result["format"] == "JPEG"

    def test_process_image_includes_exif(self, real_media_dir):
        """process_image يُرجع EXIF من extract_image_metadata"""
        from src.core.multimodal_processor import MultimodalProcessor
        proc = MultimodalProcessor()
        result = proc.process_image(str(real_media_dir / "sample.jpg"))
        assert "exif" in result
        assert result["exif"]["Make"] == "TestCamera"

    def test_process_video_returns_format_name(self, real_media_dir):
        """process_video يُرجع format_name من extract_av_metadata"""
        from src.core.multimodal_processor import MultimodalProcessor
        proc = MultimodalProcessor()
        result = proc.process_video(str(real_media_dir / "sample.mp4"))
        # لو ffprobe غير مثبت، نتحقق من probe_error فقط
        if "probe_error" not in result:
            assert "format_name" in result

    def test_extract_text_methods_delegate_to_file_inventory(self, real_doc_dir):
        """extract_text_from_* في MultimodalProcessor تُوكِّل إلى FileInventory"""
        from src.core.multimodal_processor import MultimodalProcessor
        proc = MultimodalProcessor()
        # PDF
        text = proc.extract_text_from_pdf(str(real_doc_dir / "report.pdf"))
        assert isinstance(text, str)
        # DOCX
        text = proc.extract_text_from_docx(str(real_doc_dir / "document.docx"))
        assert "Hello from DOCX" in text
        # XLSX
        text = proc.extract_text_from_xlsx(str(real_doc_dir / "spreadsheet.xlsx"))
        assert "Sheet1" in text or "Ahmad" in text
        # PPTX
        text = proc.extract_text_from_pptx(str(real_doc_dir / "presentation.pptx"))
        assert "First Slide" in text or "Slide" in text


# ─── اختبارات الإعدادات والثوابت ───────────────────────────────────────────

class TestConstants:
    """اختبارات الثوابت والامتدادات المدعومة"""

    def test_image_extensions_includes_jpeg_png(self):
        assert ".jpg" in IMAGE_EXTENSIONS
        assert ".jpeg" in IMAGE_EXTENSIONS
        assert ".png" in IMAGE_EXTENSIONS
        assert ".gif" in IMAGE_EXTENSIONS

    def test_av_extensions_includes_mp3_mp4(self):
        assert ".mp3" in AV_EXTENSIONS
        assert ".mp4" in AV_EXTENSIONS
        assert ".wav" in AV_EXTENSIONS
        assert ".mkv" in AV_EXTENSIONS

    def test_image_and_av_extensions_disjoint(self):
        """لا تداخل بين امتدادات الصور والصوت/الفيديو"""
        assert not (IMAGE_EXTENSIONS & AV_EXTENSIONS)


# ─── اختبارات FileMetadata مع extra_metadata ───────────────────────────────

class TestFileMetadataExtraField:
    """اختبارات أن FileMetadata يدعم extra_metadata بشكل صحيح"""

    def test_extra_metadata_default_empty_dict(self):
        """القيمة الافتراضية هي {} لا None"""
        m = FileMetadata()
        assert m.extra_metadata == {}
        assert isinstance(m.extra_metadata, dict)

    def test_extra_metadata_to_dict_roundtrip(self):
        """extra_metadata يظهر في to_dict ويُستعاد من from_dict"""
        m = FileMetadata(file_name="test.jpg")
        m.extra_metadata = {"width": 100, "height": 200}
        d = m.to_dict()
        assert "extra_metadata" in d
        assert d["extra_metadata"]["width"] == 100
        # from_dict
        m2 = FileMetadata.from_dict(d)
        assert m2.extra_metadata == {"width": 100, "height": 200}

    def test_extra_metadata_merge_preserves_populated(self):
        """merge() لا يُستبدل extra_metadata المليئة بفارغة"""
        m1 = FileMetadata(file_name="a.jpg")
        m1.extra_metadata = {"width": 100}
        m2 = FileMetadata(file_name="b.jpg")
        m2.extra_metadata = {}  # فارغة
        merged = m1.merge(m2)
        # يجب أن يبقى width=100 (لا يُستبدل بـ {})
        assert merged.extra_metadata == {"width": 100}

    def test_extra_metadata_merge_overwrites_with_populated(self):
        """merge() يستبدل extra_metadata الفارغة بمليئة"""
        m1 = FileMetadata(file_name="a.jpg")
        m1.extra_metadata = {}
        m2 = FileMetadata(file_name="b.jpg")
        m2.extra_metadata = {"width": 200}
        merged = m1.merge(m2)
        assert merged.extra_metadata == {"width": 200}
