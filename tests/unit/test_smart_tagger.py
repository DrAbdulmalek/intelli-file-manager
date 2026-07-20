"""اختبارات نظام الوسوم الذكي"""
import json
import pytest
from pathlib import Path
from src.core.smart_tagger import SmartTagger, Tag, FileTags


class TestTag:
    """اختبارات وسم واحد"""

    def test_simple_tag(self):
        tag = Tag("medical", "category")
        assert tag.name == "medical"
        assert tag.category == "category"
        assert tag.is_hierarchical is False

    def test_hierarchical_tag(self):
        tag = Tag("medical/cardiology/diagnosis", "medical")
        assert tag.is_hierarchical is True
        assert tag.levels == ["medical", "cardiology", "diagnosis"]

    def test_tag_to_dict(self):
        tag = Tag("test", "general", 0.8, "auto")
        d = tag.to_dict()
        assert d["name"] == "test"
        assert d["confidence"] == 0.8


class TestFileTags:
    """اختبارات وسوم ملف"""

    def test_add_tag(self):
        ft = FileTags(filepath="/test/file.pdf")
        ft.add_tag(Tag("document/pdf", "document-type"))
        assert len(ft.tags) == 1
        assert "document/pdf" in ft.all_tag_names

    def test_no_duplicate_tags(self):
        ft = FileTags(filepath="/test/file.pdf")
        ft.add_tag(Tag("document/pdf", "document-type"))
        ft.add_tag(Tag("document/pdf", "document-type"))
        assert len(ft.tags) == 1

    def test_remove_tag(self):
        ft = FileTags(filepath="/test/file.pdf")
        ft.add_tag(Tag("test", "general"))
        removed = ft.remove_tag("test")
        assert removed is True
        assert len(ft.tags) == 0

    def test_remove_nonexistent_tag(self):
        ft = FileTags(filepath="/test/file.pdf")
        removed = ft.remove_tag("nonexistent")
        assert removed is False

    def test_manual_auto_separation(self):
        ft = FileTags(filepath="/test/file.pdf")
        ft.add_tag(Tag("auto_tag", "general", 0.8, "auto"))
        ft.add_tag(Tag("manual_tag", "general", 1.0, "manual"))
        assert len(ft.auto_tags) == 1
        assert len(ft.manual_tags) == 1

    def test_to_dict_from_dict_roundtrip(self):
        ft = FileTags(filepath="/test/file.pdf")
        ft.add_tag(Tag("test", "general", 0.9, "auto"))
        d = ft.to_dict()
        ft2 = FileTags.from_dict(d)
        assert ft2.filepath == "/test/file.pdf"
        assert len(ft2.tags) == 1
        assert ft2.tags[0].name == "test"


class TestSmartTagger:
    """اختبارات نظام الوسوم الذكي"""

    def test_auto_tag_txt_file(self, tmp_path):
        # Create a text file with medical content
        txt = tmp_path / "تقرير طبي.txt"
        txt.write_text("المريض يعاني من تشخيص سكري. وصفة دواء باراسيتامول.", encoding="utf-8")

        tagger = SmartTagger()
        ft = tagger.auto_tag(str(txt))
        assert len(ft.tags) > 0
        # Should have document-type tag
        tag_names = ft.all_tag_names
        assert any("document" in t for t in tag_names)

    def test_auto_tag_with_medical_keywords(self, tmp_path):
        txt = tmp_path / "report.txt"
        txt.write_text("تقرير أشعة صدر. المريض يشتبه في التهاب رئوي.", encoding="utf-8")

        tagger = SmartTagger()
        ft = tagger.auto_tag(str(txt))
        tag_names = ft.all_tag_names
        # Should have medical-related tags
        assert any("medical" in t for t in tag_names)

    def test_sidecar_save_load(self, tmp_path):
        txt = tmp_path / "test.txt"
        txt.write_text("محتوى تجريبي", encoding="utf-8")

        tagger = SmartTagger(tags_dir=str(tmp_path / "tags"))
        ft = tagger.auto_tag(str(txt))
        tagger._save_sidecar(str(txt), ft)

        # Load sidecar
        sidecar = tmp_path / "tags" / (txt.name + ".json")
        assert sidecar.exists()
        with open(sidecar, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "tags" in data

    def test_add_manual_tag(self, tmp_path):
        txt = tmp_path / "test.txt"
        txt.write_text("test", encoding="utf-8")

        tagger = SmartTagger(tags_dir=str(tmp_path / "tags"))
        tagger.add_manual_tag(str(txt), "important", "priority")
        ft = tagger.get_tags(str(txt))
        assert "important" in ft.all_tag_names

    def test_batch_tag(self, tmp_path):
        files = []
        for i in range(3):
            f = tmp_path / f"file{i}.txt"
            f.write_text(f"content {i}", encoding="utf-8")
            files.append(str(f))

        tagger = SmartTagger(tags_dir=str(tmp_path / "tags"))
        count = tagger.batch_tag(files, "project-x", "project")
        assert count == 3
