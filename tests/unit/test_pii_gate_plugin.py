"""اختبارات بوابة PII — كشف وحجب/إخفاء البيانات الشخصية قبل فهرسة OCR

تغطي: الكشف (عربي + إنجليزي وأرقام عربية-هندية)، الإخفاء بعناصر نائبة،
الوضعين block/mask، تسجيل القرار في ActionLog، وتسجيل الإضافة في
PluginManager/PluginContext.
"""
from __future__ import annotations

import pytest

from src.plugins.pii_gate import (
    KIND_EMAIL,
    KIND_MRN,
    KIND_NAME,
    KIND_NATIONAL_ID,
    KIND_PHONE,
    MODE_BLOCK,
    MODE_MASK,
    PiiGatePlugin,
    find_pii,
    gate_text_for_indexing,
    get_mode,
    inspect_text,
    mask_text,
    set_action_log,
    set_mode,
)
from src.plugins import PluginManager


@pytest.fixture(autouse=True)
def _reset_gate_state():
    """يعيد حالة البوابة الافتراضية قبل وبعد كل اختبار (عزل كامل)"""
    set_mode(MODE_MASK)
    set_action_log(None)
    yield
    set_mode(MODE_MASK)
    set_action_log(None)


# ─── اختبارات الكشف ─────────────────────────────────────────────────────────

def test_find_email():
    """البريد الإلكتروني يُكتشف بنوعه"""
    findings = find_pii("تواصل عبر ahmad.clinic@example.com للتفاصيل")
    kinds = [f.kind for f in findings]
    assert kinds == [KIND_EMAIL]


def test_find_saudi_phone_formats():
    """صيغ الهاتف السعودية الثلاث تُكتشف (0 / +966 / 00966)"""
    findings = find_pii("0501234567 ثم +966501234567 ثم 00966501234567")
    kinds = [f.kind for f in findings]
    assert kinds == [KIND_PHONE, KIND_PHONE, KIND_PHONE]
    # لا بقايا أرقام خارج المقاطع المكتشفة
    assert mask_text("0501234567 ثم +966501234567 ثم 00966501234567", findings) == \
        "[PII:phone] ثم [PII:phone] ثم [PII:phone]"


def test_find_international_phone():
    """الرقم الدولي المضغوط (+963...) يُكتشف"""
    findings = find_pii("هاتف العيادة +963944123456 للطوارئ")
    assert [f.kind for f in findings] == [KIND_PHONE]


def test_find_saudi_national_id_ascii_and_arabic_digits():
    """المعرّف الوطني (10 أرقام تبدأ بـ 1/2) بأرقام لاتينية وعربية-هندية"""
    findings = find_pii("الهوية: 1234567890 والإقامة: ٢٠٢٣٤٥٦٧٨٩")
    assert [f.kind for f in findings] == [KIND_NATIONAL_ID, KIND_NATIONAL_ID]


def test_find_mrn_english_and_arabic_labels():
    """رقم الملف الطبي MRN بالتسمية الإنجليزية والعربية"""
    findings = find_pii("MRN: 448812 والرقم الطبي: ٤٤٣٢١")
    assert [f.kind for f in findings] == [KIND_MRN, KIND_MRN]


def test_find_arabic_name_labels():
    """الأسماء العربية المُسمّاة (المريض/الاسم/د.) تُكتشف"""
    findings = find_pii("المريض: أحمد بن محمد العلي حضر اليوم")
    assert len(findings) == 1
    assert findings[0].kind == KIND_NAME
    # الاسم المكتشف فقط يُخفى — بقي "حضر اليوم" خارج المقطع
    masked = mask_text("المريض: أحمد بن محمد العلي حضر اليوم", findings)
    assert masked == "المريض: [PII:name] حضر اليوم"


def test_find_english_name_label():
    """الأسماء الإنجليزية بتسمية Patient Name تُكتشف"""
    findings = find_pii("Patient Name: John Smith was discharged")
    assert [f.kind for f in findings] == [KIND_NAME]


def test_find_pii_does_not_store_raw_text():
    """الـ findings تحمل إحداثيات فقط — لا نسخة من النص الأصلي"""
    findings = find_pii("MRN: 448812")
    for f in findings:
        assert f.start >= 0 and f.end > f.start
        assert "448812" not in repr(f)


def test_clean_text_has_no_findings():
    """النص النظيف بلا بيانات شخصية يعود بلا نتائج"""
    assert find_pii("تقرير طبيعي بلا بيانات شخصية") == []
    assert find_pii("plain clinical note without personal data") == []


def test_overlapping_matches_keep_higher_priority():
    """الأرقام المُسمّاة (MRN) تفوز على نمط المعرّف الوطني عند التداخل"""
    findings = find_pii("الرقم الطبي: 1023456789")
    assert [f.kind for f in findings] == [KIND_MRN]


# ─── اختبارات الإخفاء ────────────────────────────────────────────────────────

def test_mask_replaces_with_placeholders():
    """الإخفاء يستبدل المقاطع بعناصر نائبة [PII:kind] ويحفظ بقية النص"""
    text = "البريد: ahmad@example.com الهاتف 0501234567 مرفق"
    masked = mask_text(text, find_pii(text))
    assert masked == "البريد: [PII:email] الهاتف [PII:phone] مرفق"
    # لا نص شخصي أصلي في الناتج
    assert "ahmad@example.com" not in masked
    assert "0501234567" not in masked


def test_mask_multiple_findings_sorted():
    """عدة مقاطع مختلفة الأنواع تُخفى جميعها في استدعاء واحد"""
    text = "ahmad@example.com 1234567890"
    masked = mask_text(text, find_pii(text))
    assert "[PII:email]" in masked
    assert "[PII:national_id]" in masked
    assert "@" not in masked


# ─── اختبارات الوضعين والبوابة ───────────────────────────────────────────────

def test_inspect_block_mode():
    """وضع block يمنع الفهرسة: allowed=False والنص الفهارس فارغ"""
    decision = inspect_text("MRN: 448812", mode=MODE_BLOCK)
    assert decision.allowed is False
    assert decision.text_for_index == ""
    assert decision.has_findings is True
    assert decision.counts == {KIND_MRN: 1}


def test_inspect_mask_mode():
    """وضع mask يسمح بالفهرسة مع نص مُخفى"""
    decision = inspect_text("MRN: 448812", mode=MODE_MASK)
    assert decision.allowed is True
    assert decision.text_for_index == "MRN: [PII:mrn]"
    assert "448812" not in decision.text_for_index


def test_inspect_clean_text_unchanged():
    """النص النظيف يعود كما هو في الوضعين دون أي تعديل"""
    text = "تقرير طبيعي بلا بيانات شخصية"
    for mode in (MODE_BLOCK, MODE_MASK):
        decision = inspect_text(text, mode=mode)
        assert decision.allowed is True
        assert decision.text_for_index == text
        assert decision.findings == []


def test_gate_returns_empty_on_block_mode():
    """gate_text_for_indexing يعيد نصًا فارغًا في وضع block — ingest_file يتوقف"""
    set_mode(MODE_BLOCK)
    assert gate_text_for_indexing("MRN: 448812", "report.txt") == ""


def test_gate_returns_masked_on_mask_mode():
    """gate_text_for_indexing يعيد النص المُخفى في الوضع الافتراضي (mask)"""
    assert get_mode() == MODE_MASK
    assert gate_text_for_indexing("MRN: 448812", "report.txt") == "MRN: [PII:mrn]"


def test_gate_clean_text_passthrough():
    """النص النظيف يمر عبر البوابة بلا تعديل"""
    text = "تقرير طبيعي بلا بيانات شخصية"
    assert gate_text_for_indexing(text, "notes.txt") == text


def test_gate_empty_text_passthrough():
    """النص الفارغ يمر كما هو (لا قرار ولا تسجيل)"""
    assert gate_text_for_indexing("", "empty.txt") == ""


def test_set_mode_rejects_unknown():
    """وضع غير معروف يُرفض باستثناء — لا وضع صامت"""
    with pytest.raises(ValueError):
        set_mode("yolo")
    # الوضع الحالي لم يتغير
    assert get_mode() == MODE_MASK


# ─── اختبارات التسجيل في ActionLog ──────────────────────────────────────────

def test_action_log_records_mask_decision():
    """قرار الإخفاء يُسجَّل في ActionLog بنوع الإجراء والوسوم والأعداد"""
    from src.core.action_log import ActionLog

    log = ActionLog()  # ذاكرة فقط — بلا ملف
    set_action_log(log)
    gate_text_for_indexing("البريد: ahmad@example.com", "doc/letter.txt")

    assert len(log) == 1
    entry = log.list_entries()[0]
    assert entry.action_type == "pii_gate:mask"
    assert entry.file_path == "doc/letter.txt"
    assert entry.rule_name == "pii_gate"
    assert entry.success is True
    assert f"{KIND_EMAIL}=1" in entry.tags_added


def test_action_log_records_block_decision():
    """قرار الحجب يُسجَّل في ActionLog في وضع block"""
    from src.core.action_log import ActionLog

    log = ActionLog()
    set_mode(MODE_BLOCK)
    gate_text_for_indexing(
        "MRN: 448812 الهوية 1234567890", "docs/report.txt", action_log=log
    )

    assert len(log) == 1
    entry = log.list_entries()[0]
    assert entry.action_type == "pii_gate:block"
    assert entry.file_path == "docs/report.txt"
    assert f"{KIND_MRN}=1" in entry.tags_added
    assert f"{KIND_NATIONAL_ID}=1" in entry.tags_added


def test_clean_text_is_not_logged():
    """النصوص النظيفة لا تُسجَّل — يبقى سجل الإجراءات مختصرًا"""
    from src.core.action_log import ActionLog

    log = ActionLog()
    gate_text_for_indexing("تقرير طبيعي", "notes.txt", action_log=log)
    assert len(log) == 0


def test_missing_action_log_does_not_crash():
    """غياب سجل الإجراءات لا يكسر البوابة — الفهرسة تستمر"""
    set_action_log(None)
    assert gate_text_for_indexing("MRN: 448812", "x.txt") == "MRN: [PII:mrn]"


# ─── اختبارات نظام الإضافات ─────────────────────────────────────────────────

def test_plugin_registers_into_context():
    """الإضافة تسجّل الكشاف ودالة الفهرسة في سياق الإضافات"""
    from src.plugins import PluginContext

    plugin = PiiGatePlugin()
    context = PluginContext()
    plugin.initialize(context)

    assert "pii_gate" in context.ner_extractors
    assert "pii_gate" in context.file_processors
    assert context.ner_extractors["pii_gate"] is find_pii
    assert context.file_processors["pii_gate"] is gate_text_for_indexing


def test_plugin_discovered_and_loaded_by_manager():
    """PluginManager يكتشف الإضافة من src/plugins/ ويحمّلها بنجاح"""
    manager = PluginManager()
    assert "pii_gate" in manager.discover_plugins()
    assert manager.load_plugin("pii_gate") is True
    assert "pii_gate" in manager.loaded_plugins
