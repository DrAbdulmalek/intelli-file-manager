"""إضافة طبية تجريبية — Sample Medical Plugin

Demonstrates how to create an IntelliFile plugin that adds:
  - A custom medical classifier
  - A custom tag generator for medical documents
"""

from __future__ import annotations

import logging
from . import IntelliFilePlugin, PluginContext

logger = logging.getLogger(__name__)

# Medical specialty classifier keywords
_SPECIALTY_MAP = {
    "قلب": "cardiology", "قلبية": "cardiology", "أشعة قلب": "cardiology",
    "عظام": "orthopedics", "كسر": "orthopedics", "مفصل": "orthopedics",
    "أعصاب": "neurology", "دماغ": "neurology", "صرع": "neurology",
    "أطفال": "pediatrics", "طفل": "pediatrics", "حديثي الولادة": "pediatrics",
    "نساء": "obstetrics", "حمل": "obstetrics", "ولادة": "obstetrics",
    "جلدية": "dermatology", "جلد": "dermatology",
    "عين": "ophthalmology", "بصر": "ophthalmology",
    "أنف": "ent", "أذن": "ent", "حنجرة": "ent",
    "بولية": "urology", "كلية": "urology", "مثانة": "urology",
    "صدرية": "pulmonology", "رئة": "pulmonology", "ربو": "pulmonology",
    "غدد": "endocrinology", "سكري": "endocrinology", "غدة": "endocrinology",
    "أورام": "oncology", "سرطان": "oncology", "ورم": "oncology",
}


class SampleMedicalPlugin(IntelliFilePlugin):
    """إضافة تصنيف طبي مخصصة"""
    
    name = "sample_medical"
    version = "1.0.0"
    description = "تصنيف طبي مخصص وتوليد وسوم طبية"
    
    def initialize(self, context: PluginContext) -> None:
        context.register_classifier("medical_specialty", self._classify_specialty)
        context.register_tag_generator("medical_specialty", self._generate_tags)
        logger.info("SampleMedicalPlugin initialized")
    
    def shutdown(self) -> None:
        logger.info("SampleMedicalPlugin shutdown")
    
    def _classify_specialty(self, text: str) -> dict:
        """Classify text into medical specialty."""
        scores = {}
        text_lower = text.lower()
        for keyword, specialty in _SPECIALTY_MAP.items():
            if keyword in text_lower:
                scores[specialty] = scores.get(specialty, 0) + 1
        
        if scores:
            best = max(scores, key=scores.get)
            return {"specialty": best, "scores": scores, "source": "medical_plugin"}
        return {"specialty": "unknown", "scores": {}, "source": "medical_plugin"}
    
    def _generate_tags(self, filepath: str, text: str) -> list[str]:
        """Generate medical tags for a file."""
        tags = []
        text_lower = text.lower()
        for keyword, specialty in _SPECIALTY_MAP.items():
            if keyword in text_lower:
                tags.append(f"medical/specialty/{specialty}")
        return list(set(tags))
