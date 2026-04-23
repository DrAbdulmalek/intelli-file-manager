"""اختبارات وحدة EmergentCategoryEngine - محرك التصنيف الدينامي

يغطي هذا الملف الاختبارات التالية:
  - تحليل المجلد واكتشاف هيكله
  - توليد هيكل تصنيف مقترح
  - تجميع الامتدادات في تصنيفات
"""
from pathlib import Path

import pytest

from src.core.emergent_category import EmergentCategoryEngine


class TestAnalyzeDirectory:
    """اختبار دالة تحليل المجلد"""

    def test_analyze_directory(self, tmp_dir):
        """يتحقق من تحليل مجلد يحتوي ملفات متنوعة

        يجب أن يُرجع:
          - total_files: عدد الملفات
          - total_size: الحجم الكلي
          - extension_distribution: توزيع الامتدادات
          - proposed_structure: الهيكل المقترح
          - savings: تقدير الوفورات
        """
        engine = EmergentCategoryEngine()
        result = engine.analyze_directory(str(tmp_dir))

        assert "error" not in result
        assert "total_files" in result
        assert "total_size" in result
        assert "extension_distribution" in result
        assert "proposed_structure" in result
        assert "savings" in result
        assert result["directory"] == str(tmp_dir)
        assert result["total_files"] > 0
        assert result["total_size"] > 0

    def test_analyze_directory_nonexistent(self):
        """يتحقق من أن تحليل مجلد غير موجود يُرجع خطأ"""
        engine = EmergentCategoryEngine()
        result = engine.analyze_directory("/nonexistent/dir/path")

        assert "error" in result
        assert "غير موجود" in result["error"]

    def test_analyze_directory_empty(self, tmp_path):
        """يتحقق من تحليل مجلد فارغ"""
        engine = EmergentCategoryEngine()
        result = engine.analyze_directory(str(tmp_path))

        assert result["total_files"] == 0
        assert result["total_size"] == 0
        assert result["extension_distribution"] == {}

    def test_analyze_directory_counts_hidden_correctly(self, tmp_path):
        """يتحقق من أن الملفات المخفية لا تُحسب"""
        (tmp_path / "visible.txt").write_text("ظاهر")
        (tmp_path / ".hidden").write_text("مخفي")

        engine = EmergentCategoryEngine()
        result = engine.analyze_directory(str(tmp_path))

        assert result["total_files"] == 1
        assert ".hidden" not in result["extension_distribution"]

    def test_analyze_directory_extension_distribution(self, tmp_dir):
        """يتحقق من دقة توزيع الامتدادات في النتائج"""
        engine = EmergentCategoryEngine()
        result = engine.analyze_directory(str(tmp_dir))

        dist = result["extension_distribution"]
        # يجب أن يوجد على الأقل .pdf و .py و .txt
        assert ".pdf" in dist
        assert ".py" in dist
        assert ".txt" in dist
        # كل قيمة يجب أن تكون رقماً موجباً
        for ext, count in dist.items():
            assert count > 0


class TestGenerateHierarchy:
    """اختبار دالة توليد هيكل التصنيف"""

    def test_generate_hierarchy_with_stats(self):
        """يتحقق من توليد هيكل من إحصائيات صالحة

        يختبر:
          - وجود مفتاح 'categories'
          - أن كل تصنيف يحتوي files_count و extensions و total_size
          - ترتيب التصنيفات حسب عدد الملفات (الأكبر أولاً)
        """
        engine = EmergentCategoryEngine()
        stats = {
            "extension_distribution": {
                ".pdf": 5,
                ".docx": 3,
                ".py": 4,
                ".js": 2,
                ".jpg": 1,
                ".mp3": 1,
                ".unknown": 2,
            }
        }

        result = engine.generate_hierarchy(stats)

        assert "categories" in result
        categories = result["categories"]

        # يجب أن يكون هناك عدة تصنيفات
        assert len(categories) > 0

        # كل تصنيف يجب أن يحتوي الحقول المطلوبة
        for cat_name, cat_info in categories.items():
            assert "files_count" in cat_info
            assert "extensions" in cat_info
            assert "total_size" in cat_info
            assert isinstance(cat_info["extensions"], list)

        # الترتيب حسب عدد الملفات (تنازلي)
        counts = [info["files_count"] for info in categories.values()]
        assert counts == sorted(counts, reverse=True)

    def test_generate_hierarchy_empty_stats(self):
        """يتحقق من أن إحصائيات فارغة تُرجع هيكلاً يحتوي قائمة فارغة"""
        engine = EmergentCategoryEngine()

        result = engine.generate_hierarchy({"extension_distribution": {}})

        assert "categories" in result
        assert len(result["categories"]) == 0

    def test_generate_hierarchy_none_stats(self):
        """يتحقق من أن None يُرجع قاموساً فارغاً"""
        engine = EmergentCategoryEngine()

        result = engine.generate_hierarchy(None)

        assert result == {}

    def test_generate_hierarchy_only_unknown_extensions(self):
        """يتحقق من أن الامتدادات غير المعروفة تُصنّف تحت 'أخرى'"""
        engine = EmergentCategoryEngine()
        stats = {
            "extension_distribution": {
                ".abc": 3,
                ".xyz": 2,
                ".custom": 1,
            }
        }

        result = engine.generate_hierarchy(stats)

        assert "أخرى" in result["categories"]
        other = result["categories"]["أخرى"]
        assert other["files_count"] == 6
        assert len(other["extensions"]) == 3


class TestClusterExtensions:
    """اختبار دالة تجميع الامتدادات في تصنيفات"""

    def test_cluster_extensions_documents(self):
        """يتحقق من تجميع امتدادات المستندات معاً"""
        engine = EmergentCategoryEngine()
        extensions = {
            ".pdf": 5,
            ".docx": 3,
            ".txt": 2,
        }

        clusters = engine._cluster_extensions(extensions)

        assert "مستندات" in clusters
        assert ".pdf" in clusters["مستندات"]
        assert ".docx" in clusters["مستندات"]
        assert ".txt" in clusters["مستندات"]

    def test_cluster_extensions_images(self):
        """يتحقق من تجميع امتدادات الصور معاً"""
        engine = EmergentCategoryEngine()
        extensions = {
            ".jpg": 10,
            ".png": 5,
            ".gif": 2,
        }

        clusters = engine._cluster_extensions(extensions)

        assert "صور" in clusters
        assert len(clusters["صور"]) == 3

    def test_cluster_extensions_mixed(self):
        """يتحقق من تجميع امتدادات متنوعة في التصنيفات الصحيحة"""
        engine = EmergentCategoryEngine()
        extensions = {
            ".pdf": 2,
            ".py": 3,
            ".mp3": 1,
            ".jpg": 4,
            ".zip": 1,
            ".exe": 1,
            ".ttf": 1,
        }

        clusters = engine._cluster_extensions(extensions)

        assert "مستندات" in clusters
        assert "برمجة" in clusters
        assert "صوت" in clusters
        assert "صور" in clusters
        assert "أرشيفات" in clusters
        assert "أنظمة" in clusters
        assert "خطوط" in clusters

    def test_cluster_extensions_unknown_go_to_other(self):
        """يتحقق من أن الامتدادات غير المعروفة تذهب لـ 'أخرى'"""
        engine = EmergentCategoryEngine()
        extensions = {
            ".custom1": 1,
            ".custom2": 1,
            ".weird_ext": 1,
        }

        clusters = engine._cluster_extensions(extensions)

        assert "أخرى" in clusters
        assert len(clusters["أخرى"]) == 3

    def test_cluster_extensions_preserves_counts(self):
        """يتحقق من أن أعداد الملفات تُحفظ بشكل صحيح"""
        engine = EmergentCategoryEngine()
        extensions = {
            ".pdf": 5,
            ".docx": 3,
        }

        clusters = engine._cluster_extensions(extensions)

        assert clusters["مستندات"][".pdf"] == 5
        assert clusters["مستندات"][".docx"] == 3


class TestApplyStructure:
    """اختبار دالة تطبيق الهيكل المقترح"""

    def test_apply_structure_creates_folders(self, tmp_path):
        """يتحقق من إنشاء المجلدات من الهيكل المقترح"""
        engine = EmergentCategoryEngine()
        structure = {
            "categories": {
                "مستندات": {
                    "files_count": 10,
                    "extensions": [".pdf"],
                    "total_size": 10,
                },
                "صور": {
                    "files_count": 5,
                    "extensions": [".jpg"],
                    "total_size": 5,
                },
            }
        }

        created = engine.apply_structure(str(tmp_path), structure)

        assert len(created) == 2
        assert (tmp_path / "مستندات").is_dir()
        assert (tmp_path / "صور").is_dir()

    def test_apply_structure_idempotent(self, tmp_path):
        """يتحقق من أن التطبيق المتكرر لا يُنشئ مجلدات مكررة"""
        engine = EmergentCategoryEngine()
        structure = {
            "categories": {
                "برمجة": {
                    "files_count": 1,
                    "extensions": [".py"],
                    "total_size": 1,
                },
            }
        }

        first = engine.apply_structure(str(tmp_path), structure)
        second = engine.apply_structure(str(tmp_path), structure)

        assert len(first) == 1
        assert len(second) == 0


class TestSuggestReorganization:
    """اختبار دالة اقتراح إعادة التنظيم"""

    def test_suggest_reorganization(self, tmp_dir):
        """يتحقق من اقتراح إعادة التنظيم لمجلد يحتوي ملفات متنوعة

        يجب أن يحتوي على:
          - moves: قائمة الحركات المقترحة
          - كل حركة تحتوي file, from, to
        """
        engine = EmergentCategoryEngine()
        result = engine.suggest_reorganization(str(tmp_dir))

        assert "moves" in result
        assert isinstance(result["moves"], list)

        # كل حركة يجب أن تحتوي الحقول المطلوبة
        for move in result["moves"]:
            assert "file" in move
            assert "from" in move
            assert "to" in move
