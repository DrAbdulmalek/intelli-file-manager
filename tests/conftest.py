"""إعدادات مشتركة للاختبارات -fixtures وmocks"""
import sys
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# تأكد من أن مسار المشروع الجذر في sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import Config, CATEGORIES, EXTENSION_MAP


# ─── Fixture: مجلد مؤقت مع ملفات عيّنة ────────────────────────────────────
@pytest.fixture
def tmp_dir(tmp_path):
    """ينشئ مجلداً مؤقتاً يحتوي ملفات متنوعة للاختبار

    يحتوي على:
      - مستندات: report.pdf, notes.txt, data.csv
      - صور: photo.jpg, image.png
      - برمجة: script.py, app.js
      - أرشيفات: backup.zip
      - ملفات بامتدادات غير معروفة: file.xyz123
    """
    # ملفات المستندات
    (tmp_path / "report.pdf").write_bytes(b"%PDF-1.4 fake pdf content")
    (tmp_path / "notes.txt").write_text("هذه ملاحظات تجريبية", encoding="utf-8")
    (tmp_path / "data.csv").write_text("اسم,عمر\nأحمد,25\nسارة,30\n", encoding="utf-8")

    # صور
    (tmp_path / "photo.jpg").write_bytes(b"\xff\xd8\xff\xe0 JFIF fake jpeg")
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n fake png")

    # برمجة
    (tmp_path / "script.py").write_text("print('مرحباً بالعالم')\n", encoding="utf-8")
    (tmp_path / "app.js").write_text("console.log('hello');\n", encoding="utf-8")

    # أرشيفات
    (tmp_path / "backup.zip").write_bytes(b"PK\x03\x04 fake zip")

    # ملف بامتداد غير معروف
    (tmp_path / "file.xyz123").write_bytes(b"unknown content")

    # مجلد فرعي مع ملفات
    subdir = tmp_path / "مجلد_فرعي"
    subdir.mkdir()
    (subdir / "document.docx").write_bytes(b"PK fake docx")
    (subdir / "song.mp3").write_bytes(b"ID3 fake mp3")

    return tmp_path


# ─── Fixture: كائن Config بإعدادات اختبار ────────────────────────────────
@pytest.fixture
def sample_config(tmp_path):
    """ينشئ كائن Config بإعدادات اختبار

    يستخدم مسار قاعدة بيانات مؤقت ويضيف تصنيفاً مخصصاً للتجربة.
    """
    config = Config(
        database_path=str(tmp_path / "intellifile_test"),
        ai_model="gemma3",
        ollama_url="http://localhost:11434",
        language="ar",
        dark_mode=True,
        auto_classify=True,
        duplicate_detection=True,
        file_protection=True,
        voice_enabled=False,
    )
    # إضافة تصنيف مخصص للاختبار
    config.add_custom_category("اختبارات", [".xyz123", ".tdata"])
    return config


# ─── Fixture: ملفات عيّنة إضافية ─────────────────────────────────────────
@pytest.fixture
def sample_files(tmp_path):
    """ينشئ ملفات عيّنة متنوعة في المجلد المؤقت ويُرجع قاموساً بالمسارات

    يُرجع قاموساً يحتوي على:
      - pdf_file: مسار ملف PDF
      - txt_file: مسار ملف نصي
      - py_file: مسار ملف Python
      - jpg_file: مسار صورة JPEG
      - zip_file: مسار أرشيف ZIP
      - unknown_file: ملف بامتداد غير معروف
      - empty_file: ملف فارغ
      - nested_dir: مجلد فرعي
      - nested_file: ملف داخل المجلد الفرعي
    """
    pdf_file = tmp_path / "document.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 test content")

    txt_file = tmp_path / "readme.txt"
    txt_file.write_text("محتوى نصي للتجربة\n", encoding="utf-8")

    py_file = tmp_path / "main.py"
    py_file.write_text("def hello():\n    print('مرحباً')\n", encoding="utf-8")

    jpg_file = tmp_path / "avatar.jpg"
    jpg_file.write_bytes(b"\xff\xd8\xff\xe0 fake jpeg data")

    zip_file = tmp_path / "archive.zip"
    zip_file.write_bytes(b"PK\x03\x04 fake archive")

    unknown_file = tmp_path / "data.unknown_ext"
    unknown_file.write_bytes(b"unknown data content")

    empty_file = tmp_path / "empty.txt"
    empty_file.write_bytes(b"")

    nested_dir = tmp_path / "subfolder"
    nested_dir.mkdir()
    nested_file = nested_dir / "nested.py"
    nested_file.write_text("# ملف متداخل\npass\n", encoding="utf-8")

    return {
        "pdf_file": str(pdf_file),
        "txt_file": str(txt_file),
        "py_file": str(py_file),
        "jpg_file": str(jpg_file),
        "zip_file": str(zip_file),
        "unknown_file": str(unknown_file),
        "empty_file": str(empty_file),
        "nested_dir": str(nested_dir),
        "nested_file": str(nested_file),
        "tmp_path": str(tmp_path),
    }


# ─── Mock: ollama ──────────────────────────────────────────────────────────
@pytest.fixture
def mock_ollama():
    """يُحاكي مكتبة ollama بدون اتصال حقيقي بالخدمة

    يوفر كائن chat الاستجابات التالية:
      - وصف لمحتوى ملف
    """
    mock = MagicMock()
    mock.chat.return_value = "هذا ملف مستند نصي يحتوي على معلومات مهمة"
    mock.list.return_value = {"models": [{"name": "gemma3"}]}
    mock.show.return_value = {
        "details": {"parameter_size": "2B", "quantization_level": "Q4_0"}
    }
    return mock


# ─── Mock: chromadb ────────────────────────────────────────────────────────
@pytest.fixture
def mock_chromadb():
    """يُحاكي مكتبة chromadb بدون اتصال حقيقي بقاعدة البيانات

    يوفر:
      - PersistentClient: عميل وهمي
      - collection: مجموعة وهمية للبيانات
    """
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_collection.add.return_value = ["id1", "id2"]
    mock_collection.query.return_value = {
        "ids": [["id1"]],
        "documents": [["نص تجريبي"]],
        "metadatas": [[{"source": "test.txt"}]],
        "distances": [[0.1]],
    }
    mock_client.get_or_create_collection.return_value = mock_collection

    with patch("chromadb.PersistentClient", return_value=mock_client):
        yield {
            "client": mock_client,
            "collection": mock_collection,
        }


# ─── Mock: magika ──────────────────────────────────────────────────────────
@pytest.fixture
def mock_magika():
    """يُحاكي مكتبة magika للتصنيف بالمحتوى

    ينشئ كائن وهمي يدعم أسلوب identify_path الذي يُرجع
    كائناً يحتوي على خاصية output بنوع الملف.
    """
    mock_result = MagicMock()
    mock_result.output = "pdf"

    mock_magika_instance = MagicMock()
    mock_magika_instance.identify_path.return_value = mock_result

    with patch.dict("sys.modules", {"magika": MagicMock(Magika=lambda: mock_magika_instance)}):
        yield mock_magika_instance


# ─── Fixture: منع وحدات خارجية عن طريق التصحيح ──────────────────────────
@pytest.fixture(autouse=True)
def patch_external_modules():
    """يمنع تلقائياً تحميل الوحدات الخارجية التي قد لا تكون مثبتة

    يشمل: ollama, chromadb, magika, speech_recognition, pyttsx3
    """
    modules_to_mock = [
        "ollama",
        "chromadb",
        "magika",
        "speech_recognition",
        "pyttsx3",
    ]
    mocked = {}
    for mod in modules_to_mock:
        if mod not in sys.modules:
            mocked[mod] = MagicMock()
            sys.modules[mod] = mocked[mod]

    yield

    # تنظيف: إزالة فقط ما أضفناه
    for mod in modules_to_mock:
        if mod in mocked and mod in sys.modules:
            del sys.modules[mod]
