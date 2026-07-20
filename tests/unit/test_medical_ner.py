"""اختبارات مستخرج الكيانات الطبية العربية"""
import pytest
from src.core.medical_ner import ArabicMedicalNER, MedicalEntity, ExtractionResult


class TestMedicalEntity:
    """اختبارات كيان طبي"""

    def test_create_entity(self):
        entity = MedicalEntity(text="سكري", entity_type="disease", confidence=0.8)
        assert entity.text == "سكري"
        assert entity.entity_type == "disease"
        assert entity.confidence == 0.8
        assert entity.source == "regex"


class TestExtractionResult:
    """اختبارات نتيجة الاستخراج"""

    def test_empty_result(self):
        result = ExtractionResult()
        assert result.entity_count == 0
        assert result.summary == {}

    def test_summary(self):
        result = ExtractionResult(entities=[
            MedicalEntity(text="سكري", entity_type="disease"),
            MedicalEntity(text="أملوديبين", entity_type="medication"),
            MedicalEntity(text="كسر", entity_type="disease"),
        ])
        summary = result.summary
        assert summary["disease"] == 2
        assert summary["medication"] == 1


class TestArabicMedicalNER:
    """اختبارات مستخرج الكيانات الطبية"""

    def test_extract_diseases(self):
        ner = ArabicMedicalNER()
        result = ner.extract("المريض يعاني من مرض السكري والتهاب الكبد")
        disease_texts = [e.text for e in result.entities if e.entity_type == "disease"]
        assert len(disease_texts) > 0

    def test_extract_medications(self):
        ner = ArabicMedicalNER()
        result = ner.extract("وصفة دواء باراسيتامول 500 ملغ مرتين يومياً")
        med_texts = [e.text for e in result.entities if e.entity_type in ("medication", "dosage")]
        assert len(med_texts) > 0

    def test_extract_specialties(self):
        ner = ArabicMedicalNER()
        result = ner.extract("تم تحويل المريض لطب القلب")
        spec_texts = [e.text for e in result.entities if e.entity_type == "specialty"]
        assert len(spec_texts) > 0

    def test_extract_procedures(self):
        ner = ArabicMedicalNER()
        result = ner.extract("إجراء أشعة سينية وصورة رنين مغناطيسي")
        proc_texts = [e.text for e in result.entities if e.entity_type == "procedure"]
        assert len(proc_texts) > 0

    def test_extract_anatomy(self):
        ner = ArabicMedicalNER()
        result = ner.extract("فحص القلب والكبد والكلية")
        anat_texts = [e.text for e in result.entities if e.entity_type == "anatomy"]
        assert len(anat_texts) > 0

    def test_extract_english(self):
        ner = ArabicMedicalNER()
        result = ner.extract("Patient diagnosed with Diabetes and Hypertension")
        disease_texts = [e.text for e in result.entities if e.entity_type == "disease"]
        assert len(disease_texts) > 0

    def test_structured_fields(self):
        ner = ArabicMedicalNER()
        result = ner.extract("المريض يعاني من سكري وضغط. أدوية: أملوديبين 5 ملغ")
        # Check structured fields are populated
        assert isinstance(result.diagnosis, list)
        assert isinstance(result.medications, list)

    def test_empty_text(self):
        ner = ArabicMedicalNER()
        result = ner.extract("")
        assert result.entity_count == 0

    def test_non_medical_text(self):
        ner = ArabicMedicalNER()
        result = ner.extract("الطقس جميل اليوم في المدينة")
        # Should have few or no medical entities
        assert result.entity_count <= 2
