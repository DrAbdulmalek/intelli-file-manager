# -*- coding: utf-8 -*-
"""اختبارات تكامل التفضيلات مع المصنف الحقيقي (§9D)

المصنف الحقيقي SmartFileClassifier + ملفات اصطناعية فقط. تغطي: بقاء
سلوك المصنف، التعطل الآمن، عدم توفر المخزن، التعارضات، منع أي عملية
ملف تلقائية، ومسار الموافقة الصريحة.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core.classifier import SmartFileClassifier
from src.core.classifier_preferences import PreferenceAwareClassifier
from src.core.preference_engine import PreferenceEngine
from src.core.preference_store import PreferenceStore

BASE_FIELDS = ("name", "path", "extension", "category", "confidence",
               "content_type", "size", "modified")


@pytest.fixture
def classifier() -> SmartFileClassifier:
    return SmartFileClassifier()


@pytest.fixture
def sample_file(tmp_path) -> Path:
    """ملف اصطناعي بامتداد غير معروف (بلا محتوى حساس)."""
    f = tmp_path / "artifact.xyz"
    f.write_text("synthetic payload for classification test\n" * 4)
    return f


def _make_engine(tmp_path) -> PreferenceEngine:
    return PreferenceEngine(PreferenceStore(tmp_path / "prefs.json"))


def _learn_png_rule(engine: PreferenceEngine):
    for i in range(3):
        engine.record_correction(
            metadata={"name": f"pic{i}", "extension": ".xyz"},
            original_category="أخرى", corrected_category="صور",
            session_id=f"s{i}", file_fingerprint=f"f{i}")


# ─── بقاء سلوك المصنف الأساسي ───────────────────────────────────────────────

def test_base_classifier_behavior_fully_preserved(classifier, sample_file):
    wrapper = PreferenceAwareClassifier(classifier, engine=None)
    base = classifier.classify_file(str(sample_file))
    wrapped = wrapper.classify_file(str(sample_file))
    for field in BASE_FIELDS:
        assert wrapped[field] == base[field], f"حقل {field} تغيّر!"
    # الغلاف لم يعدّل قاموس المصنف الأساسي نفسه
    assert "preference" not in base


def test_disabled_engine_yields_traditional_result(classifier, sample_file):
    wrapper = PreferenceAwareClassifier(classifier, engine=None)
    result = wrapper.classify_file(str(sample_file))
    assert result["preference"]["active"] is False
    assert result["suggested_category"] is None
    assert result["category"] == result["original_category"]


def test_store_unavailable_degrades_safely(classifier, sample_file, tmp_path):
    """مخزن تالف → تحذير واضح + تصنيف تقليدي سليم + لا حفظ."""
    bad = tmp_path / "prefs.json"
    bad.write_text("{definitely corrupted", encoding="utf-8")
    wrapper = PreferenceAwareClassifier(classifier, store_path=str(bad))
    assert wrapper.engine is not None  # أُنشئ لكنه read-only
    result = wrapper.classify_file(str(sample_file))
    assert result["preference"]["active"] is False
    assert result["preference"]["errors"]
    assert result["category"] == result["original_category"]
    # الملف التالف لم يُلمس
    assert bad.read_text(encoding="utf-8") == "{definitely corrupted"


def test_engine_error_does_not_break_classification(classifier, sample_file):
    """محرك يرمي استثناء في predict → تجاهُل آمن والتصنيف يعمل."""
    class ExplodingEngine:
        active = True
        def status_report(self):
            return {"active": True, "errors": []}
        def predict(self, *a, **kw):
            raise RuntimeError("boom")
        def get_rule(self, rid):
            return None

    wrapper = PreferenceAwareClassifier(classifier, engine=ExplodingEngine())
    result = wrapper.classify_file(str(sample_file))
    assert result["preference"]["active"] is True
    assert result["suggested_category"] is None
    assert "boom" in (result["preference"].get("warning") or "")


# ─── الاقتراح الحي ──────────────────────────────────────────────────────────

def test_learned_rule_suggests_and_explains(classifier, sample_file, tmp_path):
    engine = _make_engine(tmp_path)
    _learn_png_rule(engine)
    wrapper = PreferenceAwareClassifier(classifier, engine=engine)
    result = wrapper.classify_file(str(sample_file))
    assert result["original_category"] == result["category"]  # المصنف لم يتغير
    assert result["suggested_category"] == "صور"
    layer = result["preference"]
    assert layer["active"] is True
    assert layer["rule_status"] == "stable"
    assert layer["independent_confirmations"] == 3
    assert layer["conflicts"] == []
    explanation = wrapper.explain(result)
    assert explanation["suggested_category"] == "صور"
    assert explanation["conflict"] is False
    assert explanation["preferences_active"] is True
    assert "موافقة" in explanation["note"]


def test_conflicting_rules_surfaced_not_resolved_silently(classifier, sample_file, tmp_path):
    engine = _make_engine(tmp_path)
    _learn_png_rule(engine)  # .xyz → صور (stable)
    engine.record_correction(
        metadata={"name": "other", "extension": ".xyz"},
        original_category="أخرى", corrected_category="فيديو",
        session_id="sX", file_fingerprint="fX")
    wrapper = PreferenceAwareClassifier(classifier, engine=engine)
    result = wrapper.classify_file(str(sample_file))
    layer = result["preference"]
    assert layer["active"] is True
    assert layer["suggested_category"] in ("صور", "فيديو")  # حسم حتمي داخل المحرك
    assert len(layer["conflicts"]) == 1  # التعارض مكشوف للمستخدم
    assert wrapper.explain(result)["conflict"] is True


def test_no_suggestion_when_destination_equals_original(classifier, tmp_path):
    f = tmp_path / "doc.txt"
    f.write_text("plain synthetic text\n")
    engine = _make_engine(tmp_path)
    engine.record_correction(
        metadata={"name": "doc", "extension": ".txt"},
        original_category="مستندات", corrected_category="مستندات",
        session_id="s1", file_fingerprint="f1")  # noop أصلاً
    # قاعدة صريحة .txt → مستندات (نفس التصنيف الأصلي)
    engine.store.add_rule({
        "rule_id": "r-equal", "created_at": "2026-11-20T00:00:00+00:00",
        "updated_at": "2026-11-20T00:00:00+00:00", "status": "stable",
        "match": {"kind": "extension", "value": ".txt", "case_insensitive": True},
        "scope": {"kind": "global", "value": None},
        "destination": {"category": "مستندات"},
        "confidence": {"independent_sessions": 3, "total_confirmations": 3,
                       "score": 0.9},
        "source": {"origin": "user_correction", "feedback_ids": []},
        "history": [],
    })
    wrapper = PreferenceAwareClassifier(classifier, engine=engine)
    result = wrapper.classify_file(str(f))
    assert result["suggested_category"] is None  # لا إعادة اقتراح نفس الشيء


# ─── لا عمليات ملف تلقائية إطلاقًا ─────────────────────────────────────────

def test_no_automatic_file_operations(classifier, tmp_path):
    """بوجود اقتراح جاهز: الملف لا يتحرك ولا يُنسخ ولا يُحذف."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    sample = data_dir / "artifact.xyz"
    sample.write_text("synthetic payload\n" * 4)
    store_dir = tmp_path / "store"
    engine = _make_engine(store_dir)
    _learn_png_rule(engine)
    wrapper = PreferenceAwareClassifier(classifier, engine=engine)
    result = wrapper.classify_file(str(sample))
    assert result["suggested_category"] == "صور"
    assert sample.exists()                       # ما زال في مكانه
    assert list(data_dir.iterdir()) == [sample]  # لا ملفات جديدة
    assert wrapper.base is classifier                 # الغلاف لا يملك أدوات نقل
    assert not hasattr(wrapper, "move_file")
    assert not hasattr(wrapper, "delete_file")


def test_suggestion_is_not_execution_even_after_learning(classifier, sample_file, tmp_path):
    """حتى بعد تسجيل تصحيح: لا تنفيذ — النقل عبر بوابة الموافقة فقط."""
    engine = _make_engine(tmp_path)
    wrapper = PreferenceAwareClassifier(classifier, engine=engine)
    first = wrapper.classify_file(str(sample_file))
    assert first["suggested_category"] is None  # بلا تعلم سابق
    # المستخدم يصحح عبر محرك الملاحظات/التفضيلات مباشرة (ليس من الغلاف)
    engine.record_correction(
        metadata={"name": sample_file.name, "extension": ".xyz"},
        original_category=first["category"], corrected_category="صور",
        session_id="ui-session", file_fingerprint="fp-ui")
    second = wrapper.classify_file(str(sample_file))
    assert second["suggested_category"] == "صور"
    assert sample_file.exists() and sample_file.stat().st_mtime >= 0
    # لا استيراد/استدعاء SafeMover أو FileHandler أو subprocess في وحدة الغلاف
    import inspect
    import src.core.classifier_preferences as mod
    source = inspect.getsource(mod)
    assert "from .safe_mover" not in source
    assert "from .file_handler" not in source
    assert "import safe_mover" not in source
    assert "subprocess" not in source
