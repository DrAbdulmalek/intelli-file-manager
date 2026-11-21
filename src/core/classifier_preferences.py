# -*- coding: utf-8 -*-
"""طبقة تكامل التفضيلات مع المصنف — الاقتراح منفصل عن التنفيذ (P1)

تدفق موثق (متطلب المهمة §6):

    File Metadata → Existing Classifier → Preference Engine →
    Conflict Resolution → Explanation → User Approval Interface

ضمانات:
  - المصنف القديم **لا يُعدَّل إطلاقًا**؛ هذه الطبقة غلاف (wrapper) يستدعيه.
  - المحرك معطل/غير متوفر/فاشل → النتيجة الأساسية كما هي حرفيًا مع
    ``preference.active=False`` وتحذير واضح، ويستمر التصنيف التقليدي الآمن.
  - الاقتراح حقل نصي في النتيجة — لا نقل، لا حذف، لا استدعاء SafeMover
    أو FileHandler من هنا. أي نقل يمر عبر مسار الموافقة الحالي الموثق.
  - لا يُقرأ محتوى الملف هنا: الميتاداتا فقط (التصنيف الحساسي محكوم
    بالحاجز الحساسي داخل المصنف الأساسي كما هو).
"""
from __future__ import annotations

import copy
import logging
from typing import Any, Dict, Optional

from .preference_engine import PreferenceEngine
from .preference_store import PreferenceStore
from .feedback_engine import fingerprint_path

logger = logging.getLogger(__name__)


class PreferenceAwareClassifier:
    """غلاف حول مصنف قائم يضيف طبقة اقتراح التفضيلات دون تغيير سلوكه."""

    def __init__(self, base_classifier, engine: Optional[PreferenceEngine] = None,
                 store_path: Optional[str] = None):
        """
        Args:
            base_classifier: كائن يوفر ``classify_file(filepath) -> dict``
                (مثل SmartFileClassifier) — يبقى المصدر الوحيد للتصنيف.
            engine: محرك تفضيلات جاهز (اختياري).
            store_path: مسار مخزن تفضيلات لإنشاء محرك تلقائيًا إن لم يُمرر
                محرك. فشل الإنشاء/التحميل → المحرك معطل وليس استثناء.
        """
        self.base = base_classifier
        if engine is not None:
            self.engine = engine
        elif store_path is not None:
            self.engine = self._build_engine(store_path)
        else:
            self.engine = None

    @staticmethod
    def _build_engine(store_path: str) -> Optional[PreferenceEngine]:
        try:
            return PreferenceEngine(PreferenceStore(store_path))
        except Exception as exc:  # noqa: BLE001 — فشل التفضيلات لا يكسر التصنيف
            logger.warning("تفضيلات التصنيف غير متاحة (%s) — التصنيف التقليدي يعمل", exc)
            return None

    # ─── التصنيف ───────────────────────────────────────────────────────────

    def classify_file(self, filepath: str, *, context_directory: Optional[str] = None) -> dict:
        """يصنف عبر المصنف الأساسي ثم يضيف الاقتراح إن وُجد.

        مخرجات المصنف الأساسي تُنقل **كما هي** (نسخة عميقة) — حقول
        التصنيف الأصلي لا تتغير، والاقتراح حقول إضافية منفصلة.
        """
        base_result = self.base.classify_file(filepath)
        result = copy.deepcopy(base_result)
        if "error" in result:
            return result  # أخطاء المصنف الأساسي تمر كما هي

        preference_layer = self._preference_layer(filepath, result,
                                                  context_directory)
        result["original_category"] = result["category"]
        result["suggested_category"] = preference_layer.get("suggested_category")
        result["preference"] = preference_layer
        return result

    def _preference_layer(self, filepath: str, base_result: Dict[str, Any],
                          context_directory: Optional[str]) -> Dict[str, Any]:
        if self.engine is None:
            return {
                "active": False,
                "suggested_category": None,
                "reason": "محرك التفضيلات معطل (لم يُهيأ) — التصنيف التقليدي فقط",
            }
        status = self.engine.status_report()
        if not status.get("active"):
            return {
                "active": False,
                "suggested_category": None,
                "reason": "المخزن غير سليم — SAFE READ-ONLY، لا تفضيلات ولا حفظ",
                "errors": status.get("errors", []),
                "warning": status.get("warning"),
            }
        try:
            suggestion = self.engine.predict(
                {
                    "name": base_result.get("name", ""),
                    "extension": base_result.get("extension", ""),
                    "mime_type": base_result.get("content_type", ""),
                    "category": base_result.get("category", ""),
                },
                current_path=context_directory,
                file_fingerprint=fingerprint_path(filepath),
            )
        except Exception as exc:  # noqa: BLE001 — فشل التنبؤ لا يكسر التصنيف
            logger.warning("فشل تنبؤ التفضيلات (%s) — نتجاهل الاقتراح", exc)
            return {
                "active": True,
                "suggested_category": None,
                "reason": "فشل التنبؤ — تجاهُل آمن",
                "warning": str(exc)[:200],
            }
        if suggestion is None:
            return {
                "active": True,
                "suggested_category": None,
                "reason": "لا تفضيل مطابق — نتيجة المصنف الأساسي معتمدة",
            }
        return {
            "active": True,
            "suggested_category": suggestion.category,
            "rule_id": suggestion.rule_id,
            "rule_status": suggestion.rule_status,
            "confidence_score": suggestion.confidence_score,
            "independent_confirmations": suggestion.independent_confirmations,
            "conflicts": list(suggestion.conflicts),
            "source": suggestion.source,
            "reason": suggestion.reason,
        }

    # ─── الشرح ─────────────────────────────────────────────────────────────

    def explain(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """شرح كامل لنتيجة التصنيف المُفضَّلة (للواجهة/الـAdapter)."""
        layer = result.get("preference", {})
        explanation = {
            "original_category": result.get("original_category", result.get("category")),
            "suggested_category": layer.get("suggested_category"),
            "reason": layer.get("reason", ""),
            "confidence_score": layer.get("confidence_score"),
            "independent_confirmations": layer.get("independent_confirmations"),
            "rule_id": layer.get("rule_id"),
            "conflict": bool(layer.get("conflicts")),
            "preference_source": layer.get("source"),
            "preferences_active": bool(layer.get("active")),
            "note": "لا تنفيذ تلقائي — أي نقل يحتاج موافقة صريحة عبر المسار المعتمد",
        }
        if layer.get("rule_id") and self.engine is not None:
            suggestion = self.engine.get_rule(layer["rule_id"])
            if suggestion:
                explanation["rule_status"] = suggestion.get("status")
        return explanation
