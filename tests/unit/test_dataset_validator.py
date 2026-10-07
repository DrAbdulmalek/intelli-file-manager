"""اختبارات بوابات الجودة."""
from PIL import Image
import pytest

from src.services.dataset_validator import DatasetValidator


@pytest.fixture
def blank_image(tmp_path):
    img = Image.new("RGB", (200, 100), "white")
    path = tmp_path / "blank.png"
    img.save(path)
    return str(path)


def test_validate_simple_pass(blank_image):
    snippets = [{"id": 1, "bbox": [10, 10, 50, 50], "text": "مرحبا",
                 "confidence": 0.9}]
    validator = DatasetValidator()
    result = validator.validate_all(snippets, blank_image)
    assert result.total == 1
    assert result.passed == 1
    assert result.failed == 0


def test_validate_out_of_bounds(blank_image):
    snippets = [{"id": 1, "bbox": [300, 10, 400, 50], "text": "خارج",
                 "confidence": 0.9}]
    validator = DatasetValidator()
    result = validator.validate_all(snippets, blank_image)
    assert result.failed == 1
    assert any(i.code == "OUT_OF_BOUNDS" for i in result.issues)


def test_validate_empty_text(blank_image):
    snippets = [{"id": 1, "bbox": [10, 10, 50, 50], "text": "",
                 "confidence": 0.9}]
    validator = DatasetValidator(require_all_text=True)
    result = validator.validate_all(snippets, blank_image)
    assert result.failed == 1
    assert any(i.code == "EMPTY_TEXT" for i in result.issues)


def test_validate_numerical_drift(blank_image):
    """تصحيح يغيّر الأرقام = خطأ حرج."""
    snippets = [{
        "id": 1, "bbox": [10, 10, 50, 50],
        "text": "جرعة ٥٠٠",
        "ocr_text": "جرعة 500",
        "confidence": 0.9,
    }]
    validator = DatasetValidator(check_digits_preservation=True)
    result = validator.validate_all(snippets, blank_image)
    # الأرقام تغيّرت حرفيًا (500 ≠ ٥٠٠)
    assert result.failed == 1
    assert any(i.code == "NUMERICAL_DRIFT" for i in result.issues)


def test_validate_medical_unit_drift(blank_image):
    """الوحدات الطبية محمية."""
    snippets = [{
        "id": 1, "bbox": [10, 10, 50, 50],
        "text": "باراسيتامول 500 gm",   # gm ≠ mg
        "ocr_text": "باراسيتامول 500 mg",
        "confidence": 0.9,
        "category": "medical",
    }]
    validator = DatasetValidator()
    result = validator.validate_all(snippets, blank_image)
    assert any(i.code == "UNIT_DRIFT" for i in result.issues)


def test_validate_invalid_bbox(blank_image):
    snippets = [{"id": 1, "bbox": [50, 50, 10, 10], "text": "معكوس",
                 "confidence": 0.9}]
    validator = DatasetValidator()
    result = validator.validate_all(snippets, blank_image)
    assert result.failed == 1
    assert any(i.code == "EMPTY_BBOX" for i in result.issues)


def test_validate_no_letters(blank_image):
    snippets = [{"id": 1, "bbox": [10, 10, 50, 50], "text": "123 !!!",
                 "confidence": 0.9}]
    validator = DatasetValidator()
    result = validator.validate_all(snippets, blank_image)
    # warning وليس error
    assert any(i.code == "NO_LETTERS" and i.severity == "warning"
               for i in result.issues)


def test_validate_unreadable_image():
    snippets = [{"id": 1, "bbox": [10, 10, 50, 50], "text": "نص",
                 "confidence": 0.9}]
    validator = DatasetValidator()
    result = validator.validate_all(snippets, "/nonexistent/image.png")
    assert result.failed >= 1
    assert any(i.code == "IMAGE_UNREADABLE" for i in result.issues)
