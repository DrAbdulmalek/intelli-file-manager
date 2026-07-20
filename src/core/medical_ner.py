"""مستخرج الكيانات الطبية العربية (Arabic Medical NER)

Extracts medical entities from Arabic text:
  - Diseases / Diagnoses (أمراض / تشخيصات)
  - Medications (أدوية)
  - Dosages (جرعات)
  - Medical specialties (تخصصات طبية)
  - Patient demographics (بيانات المريض)
  - Procedures (إجراءات طبية)
  - Anatomy (تشريح)

Uses regex-based extraction with optional LLM enhancement via Ollama.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class MedicalEntity:
    """كيان طبي مستخرج من النص"""
    text: str
    entity_type: str  # disease, medication, dosage, specialty, procedure, anatomy, demographic
    start: int = -1
    end: int = -1
    confidence: float = 0.0
    normalized: str = ""
    source: str = "regex"  # regex | llm | field_extractor


@dataclass
class ExtractionResult:
    """نتيجة استخراج الكيانات من نص طبي"""
    entities: list[MedicalEntity] = field(default_factory=list)
    patient_name: str = ""
    patient_id: str = ""
    date: str = ""
    doctor_name: str = ""
    diagnosis: list[str] = field(default_factory=list)
    medications: list[str] = field(default_factory=list)
    procedures: list[str] = field(default_factory=list)
    raw_text: str = ""

    @property
    def entity_count(self) -> int:
        return len(self.entities)

    @property
    def summary(self) -> dict[str, int]:
        """ملخص بعدد الكيانات حسب النوع"""
        counts: dict[str, int] = {}
        for e in self.entities:
            counts[e.entity_type] = counts.get(e.entity_type, 0) + 1
        return counts


# ---------------------------------------------------------------------------
# Regex patterns for Arabic medical entities
# ---------------------------------------------------------------------------

# Diseases / Diagnoses — common Arabic medical terms
_DISEASE_PATTERNS = [
    re.compile(r"(?:مرض|إصابة بـ|التهاب|متلازمة|سرطان|ورم|كسر|ضيق|قصور|فشل|تليف|نزيف|تجلط|انسداد)\s+[\u0600-\u06FF\s]{2,30}", re.IGNORECASE),
    re.compile(r"(?:سكري|ضغط|ربو|صرع|التهاب المفاصل|التهاب الكبد|فشل كلوي|فشل قلبي|جلطة|سكتة دماغية|ذات الرئة)", re.IGNORECASE),
    re.compile(r"(?:Diabetes|Hypertension|Asthma|Epilepsy|Hepatitis|Pneumonia|Fracture|Tumor|Cancer|Cirrhosis)\s*[a-zA-Z]*", re.IGNORECASE),
]

# Medications — Arabic + common drug patterns
_MEDICATION_PATTERNS = [
    re.compile(r"(?:دواء|علاج|حبوب|كبسولات|حقنة|مرهم|قطرات|شراب|أمبول)\s+[\u0600-\u06FF\s]{2,25}", re.IGNORECASE),
    re.compile(r"(?:أموكسيسيلين|أزيثرومايسين|ميتفورمين|أملوديبين|أوميبرازول|باراسيتامول|إيبوبروفين|أسبرين|وارفارين|إنوسبريل)", re.IGNORECASE),
    re.compile(r"\b\d+\s*(?:ملغ|ملجم|ملليجرام|mg|milligram)", re.IGNORECASE),
]

# Dosages
_DOSAGE_PATTERNS = [
    re.compile(r"\b\d+[\.\d]*\s*(?:ملغ|ملجم|ملليجرام|mg|g|ml|مل|ملل|وحدة|IU|ميكروجرام|ميكروغرام|mcg)\b", re.IGNORECASE),
    re.compile(r"(?:مرة|مرتين|ثلاث مرات)\s+(?:يومياً|أسبوعياً|شهرياً|يومي|أسبوعي)", re.IGNORECASE),
    re.compile(r"\b\d+\s*(?:×|ضرب|مرات)\s*\d+", re.IGNORECASE),
]

# Medical specialties
_SPECIALTY_PATTERNS = [
    re.compile(r"(?:طب|قسم|عيادة|وحدة)\s+(?:ال(?:قلب|عظام|أعصاب|أطفال|نساء|جلدية|عين|أنف|أسنان|بولية|صدرية|غدد|مخ|أوعية|جراحة))", re.IGNORECASE),
    re.compile(r"(?:Cardiology|Orthopedics|Neurology|Pediatrics|Dermatology|Ophthalmology|Urology|Oncology|Radiology|Pathology)", re.IGNORECASE),
]

# Procedures
_PROCEDURE_PATTERNS = [
    re.compile(r"(?:عملية|إجراء|فحص|تحليل|أشعة|رنين|تصوير|خزعة|قسطرة|تنظير|جراحة| transplant|تخطيط)\s+[\u0600-\u06FF\s]{2,30}", re.IGNORECASE),
    re.compile(r"(?:MRI|CT scan|X-ray|ECG|EKG|EEG|Ultrasound|Biopsy|Endoscopy|Catheterization|Transplant)", re.IGNORECASE),
]

# Anatomy
_ANATOMY_PATTERNS = [
    re.compile(r"(?:القلب|الكبد|الكلية|الرئة|المعدة|الدماغ|العين|الأذن|الأنف|الحنجرة|العمود الفقري|المفصل|العظم|العضلة|الشريان|الوريد|الأمعاء|المثانة|البنكرياس|الطحال)", re.IGNORECASE),
    re.compile(r"(?:heart|liver|kidney|lung|brain|eye|spine|joint|bone|artery|vein|intestine|pancreas|spleen|stomach)", re.IGNORECASE),
]


class ArabicMedicalNER:
    """مستخرج الكيانات الطبية من النصوص العربية.

    Features:
      - Regex-based extraction for 7 entity types
      - Arabic text normalization for better matching
      - Optional LLM enhancement via Ollama (when available)
      - Integration with omni-medical-suite field_extractor
      - RTL-aware text processing
    """

    def __init__(self, ollama_url: str = "http://localhost:11434",
                 ai_model: str = "llama3.2"):
        self.ollama_url = ollama_url
        self.ai_model = ai_model
        self._field_extractor = None
        self._init_field_extractor()

    def _init_field_extractor(self):
        """Try to import field_extractor from omni-medical-suite."""
        try:
            from src.ocr.field_extractor import extract_fields, build_template_signature
            self._field_extractor = {
                "extract_fields": extract_fields,
                "build_template_signature": build_template_signature,
            }
            logger.info("تم تحميل field_extractor من omni-medical-suite")
        except ImportError:
            logger.debug("field_extractor غير متاح — استخدام regex فقط")

    def extract(self, text: str) -> ExtractionResult:
        """استخراج الكيانات الطبية من النص.

        Args:
            text: Arabic medical text to process

        Returns:
            ExtractionResult with all found entities and structured fields
        """
        result = ExtractionResult(raw_text=text)

        # 1. Try omni-medical-suite field_extractor for structured fields
        if self._field_extractor:
            try:
                fields = self._field_extractor["extract_fields"](text)
                if fields:
                    result.patient_name = getattr(fields, "patient_name", "")
                    result.patient_id = getattr(fields, "patient_id", "")
                    result.date = getattr(fields, "date", "")
                    result.doctor_name = getattr(fields, "doctor_name", "")
                    # Add field_extractor entities
                    for f_name in ["patient_name", "patient_id", "date", "doctor_name",
                                   "diagnosis", "medications"]:
                        val = getattr(fields, f_name, None)
                        if val:
                            if isinstance(val, list):
                                for v in val:
                                    result.entities.append(MedicalEntity(
                                        text=str(v),
                                        entity_type=f_name,
                                        confidence=0.9,
                                        source="field_extractor",
                                    ))
                            else:
                                result.entities.append(MedicalEntity(
                                    text=str(val),
                                    entity_type=f_name,
                                    confidence=0.9,
                                    source="field_extractor",
                                ))
            except Exception as exc:
                logger.debug(f"خطأ في field_extractor: {exc}")

        # 2. Regex-based extraction
        self._extract_diseases(text, result)
        self._extract_medications(text, result)
        self._extract_dosages(text, result)
        self._extract_specialties(text, result)
        self._extract_procedures(text, result)
        self._extract_anatomy(text, result)

        # Populate structured fields from regex results
        for entity in result.entities:
            if entity.source == "regex":
                if entity.entity_type == "disease" and entity.text not in result.diagnosis:
                    result.diagnosis.append(entity.text)
                elif entity.entity_type == "medication" and entity.text not in result.medications:
                    result.medications.append(entity.text)
                elif entity.entity_type == "procedure" and entity.text not in result.procedures:
                    result.procedures.append(entity.text)

        return result

    def extract_with_llm(self, text: str) -> ExtractionResult:
        """Extract entities using regex first, then enhance with LLM via Ollama."""
        result = self.extract(text)

        try:
            import ollama
            client = ollama.Client(host=self.ollama_url)
            prompt = f"""استخرج الكيانات الطبية من النص التالي وأعطها بصيغة JSON:
الأمراض: قائمة
الأدوية: قائمة
الجرعات: قائمة
الإجراءات: قائمة
بيانات المريض: اسم، رقم، تاريخ

النص:
{text[:2000]}

أجب بصيغة JSON فقط."""

            response = client.chat(self.ai_model, messages=[
                {"role": "system", "content": "أنت مساعد طبي متخصص في استخراج الكيانات. أجب بصيغة JSON فقط."},
                {"role": "user", "content": prompt},
            ])
            content = response.get("message", {}).get("content", "")

            # Parse LLM response and add entities
            import json
            try:
                # Try to extract JSON from the response
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    llm_data = json.loads(json_match.group())
                    for key, values in llm_data.items():
                        if isinstance(values, list):
                            for v in values:
                                if isinstance(v, str) and v.strip():
                                    result.entities.append(MedicalEntity(
                                        text=v.strip(),
                                        entity_type=self._map_llm_key(key),
                                        confidence=0.7,
                                        source="llm",
                                    ))
            except json.JSONDecodeError:
                logger.debug("لم يتم تحليل استجابة LLM كـ JSON")

        except Exception as exc:
            logger.debug(f"LLM enhancement غير متاح: {exc}")

        return result

    def _map_llm_key(self, key: str) -> str:
        """Map LLM response keys to entity types."""
        mapping = {
            "الأمراض": "disease",
            "الأدوية": "medication",
            "الجرعات": "dosage",
            "الإجراءات": "procedure",
            "بيانات المريض": "demographic",
            "التخصصات": "specialty",
        }
        return mapping.get(key, "unknown")

    def _find_matches(self, text: str, patterns: list[re.Pattern],
                      entity_type: str, result: ExtractionResult):
        """Find regex matches and add them as entities."""
        for pattern in patterns:
            for match in pattern.finditer(text):
                entity_text = match.group().strip()
                if entity_text:
                    result.entities.append(MedicalEntity(
                        text=entity_text,
                        entity_type=entity_type,
                        start=match.start(),
                        end=match.end(),
                        confidence=0.6,
                        source="regex",
                    ))

    def _extract_diseases(self, text: str, result: ExtractionResult):
        self._find_matches(text, _DISEASE_PATTERNS, "disease", result)

    def _extract_medications(self, text: str, result: ExtractionResult):
        self._find_matches(text, _MEDICATION_PATTERNS, "medication", result)

    def _extract_dosages(self, text: str, result: ExtractionResult):
        self._find_matches(text, _DOSAGE_PATTERNS, "dosage", result)

    def _extract_specialties(self, text: str, result: ExtractionResult):
        self._find_matches(text, _SPECIALTY_PATTERNS, "specialty", result)

    def _extract_procedures(self, text: str, result: ExtractionResult):
        self._find_matches(text, _PROCEDURE_PATTERNS, "procedure", result)

    def _extract_anatomy(self, text: str, result: ExtractionResult):
        self._find_matches(text, _ANATOMY_PATTERNS, "anatomy", result)
