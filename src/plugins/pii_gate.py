"""بوابة PII — كشف وحجب/إخفاء البيانات الشخصية قبل فهرسة نص OCR في ChromaDB

هذه الإضافة (أولوية P3 من خارطة الطريق المدمجة) تعمل **قبل** وصول أي نص
مستخرج/OCR إلى قاعدة المعرفة المتجهية، فلا يتسرب أي محتوى شخصي حسّاس إلى
فهرس البحث الدلالي أو سياق النموذج اللغوي المحلي.

الوضعان المدعومون:
  - "block": حجب الفهرسة كليًا — لا يدخل أي جزء من النص إلى ChromaDB.
  - "mask":  الفهرسة مع الإخفاء — تستبدل كل مقطع شخصي بعنصر نائب مثل
    ``[PII:phone]`` قبل التضمين، فيبقى المعنى العام بلا تسريب.

أنماط الكشف (Regex خفيفة تعمل محليًا بلا أي اعتماديات خارجية — لا presidio):
  - البريد الإلكتروني، أرقام الهواتف (الصيغ السعودية +966/00966/05 مع
    الأرقام العربية-الهندية ٠-٩، وأرقام دولية عامة)، المعرّف الوطني
    بأسلوب السعودية (10 أرقام تبدأ بـ 1 أو 2 — تشمل الإقامة)، رقم الملف
    الطبي MRN، وأسماء بأسلوب التسمية (اسم المريض/السيد/د. — Name/Patient)
    عربيًا وإنجليزيًا.

آلية القرار والتسجيل:
  - القرار (حجب/إخفاء) يُسجَّل في ActionLog إن كان متاحًا للإضافة عبر
    ``set_action_log`` أو عبر ``context.action_log`` وقت التهيئة — من دون
    تعديل مخطط ActionLogEntry (الأعداد تُسجَّل في tags_added مثل "email=2").
  - الـ findings لا تحفظ النص الأصلي مطلقًا — الإحداثيات فقط، فلا نسخة
    ثانية من الـ PII في الذاكرة أو السجل.

نقطة الربط (سطر واحد) في ``RAGEngine.ingest_file`` (src/core/rag_engine.py)
بعد التسوية العربية وقبل التقسيم إلى مقاطع:

    from src.plugins.pii_gate import gate_text_for_indexing  # أعلى الملف
    text = gate_text_for_indexing(text, source=str(path))    # داخل ingest_file

النص الفارغ العائد يعني "محجوب" — و``ingest_file`` يعيد 0 تلقائيًا عند
النص الفارغ فلا تُفهرس شيئًا (لا حاجة لأي تعديل آخر في المحرك).

حدود موثّقة (لا تُخفى):
  - الكشف regex تقريبي وليس NER كاملًا: قد يفوّت أسماء بلا تسمية، وقد
    يولّد إنذارات كاذبة (أي رقم 10 أرقام يبدأ بـ 1/2 يُعدّ معرّفًا وطنيًا).
    البوابة تميل لجانب الخصوصية عند الشك.
  - الأرقام الدولية المتباعدة بمسافات ("+1 415 555 2671") لا تُلتقط بصيغتها
    المتباعدة — تُلتقط بصيغتها المضغوطة فقط.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

try:
    from . import IntelliFilePlugin, PluginContext
except ImportError:  # pragma: no cover — تحميل كوحدة عليا خارج الحزمة
    from src.plugins import IntelliFilePlugin, PluginContext

try:
    from ..core.action_log import ActionLog, ActionLogEntry
except ImportError:  # pragma: no cover — تحميل كوحدة عليا خارج الحزمة
    from src.core.action_log import ActionLog, ActionLogEntry

logger = logging.getLogger(__name__)


# ─── ثوابت ──────────────────────────────────────────────────────────────────

# الوضعان المدعومان
MODE_BLOCK = "block"
MODE_MASK = "mask"
_MODES = (MODE_BLOCK, MODE_MASK)

# متغير البيئة لاختيار الوضع (نمط مطابق لـ INTELLIFILE_MEDICAL_MODE)
ENV_PII_GATE_MODE = "INTELLIFILE_PII_GATE_MODE"

# الوضع الافتراضي: الإخفاء — يمنع التسريب ويحفظ فائدة البحث معًا.
# غيّره إلى "block" عبر INTELLIFILE_PII_GATE_MODE أو set_mode للحجب الكامل.
DEFAULT_MODE = MODE_MASK

# أنواع البيانات الشخصية المكتشفة (تظهر في العنصر النائب [PII:kind])
KIND_EMAIL = "email"
KIND_PHONE = "phone"
KIND_NATIONAL_ID = "national_id"
KIND_MRN = "mrn"
KIND_NAME = "name"

# مصدر القرار في ActionLog (حقل source حر — ثوابت الوحدة استرشادية)
SOURCE_PII_GATE = "pii_gate"


# ─── أنماط الكشف ────────────────────────────────────────────────────────────

# حروف عربية فقط (همزة ← ياء) لكلمات الأسماء
_AR_WORD = r"[\u0621-\u064A]{2,}"

# الأنماط بترتيب الأولوية: الأنواع المُسمّاة أولًا ثم الأرقام العامة.
# \d في Python يطابق الأرقام العربية-الهندية (٠-٩) أيضًا، والفئات [0٠]
# تعالج الأرقام الحرفية في بادئات الهواتف.
# الصيغة: (النوع, النمط المُجمَّع, رقم المجموعة المُعلَّمة — 0 = المطابقة كلها)
_PATTERNS: tuple[tuple[str, re.Pattern, int], ...] = (
    # رقم الملف الطبي — تسمية عربية أو إنجليزية ثم 3-12 رقمًا
    (
        KIND_MRN,
        re.compile(
            r"(?:MRN|Medical\s*Record\s*(?:Number|No\.?)"
            r"|رقم\s*الملف\s*الطبي|الرقم\s*الطبي|رقم\s*الملف"
            r"|ملف\s*رقم|رقم\s*المرجع)"
            r"\s*[:#\-]?\s*(\d{3,12})",
            re.IGNORECASE,
        ),
        1,
    ),
    # البريد الإلكتروني
    (
        KIND_EMAIL,
        re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
        0,
    ),
    # هواتف السعودية/الخليج: ‎+966 / 00966 / 0 ثم 5 ثم 8-9 أرقام
    # (الرقم القياسي 8 أرقام بعد الـ 5 — يُسمح برقم إضافي لضمان تغطية كاملة)
    (
        KIND_PHONE,
        re.compile(r"(?:(?:\+|00)[9٩][6٦][6٦]|[0٠])[5٥]\d{8,9}"),
        0,
    ),
    # رقم دولي عام مضغوط: + ورمز دولة ثم 7-12 رقمًا
    (
        KIND_PHONE,
        re.compile(r"\+\d{1,3}[\s\-]?\d{7,12}"),
        0,
    ),
    # المعرّف الوطني بأسلوب السعودية (10 أرقام تبدأ بـ 1 أو 2 — تشمل الإقامة)
    (
        KIND_NATIONAL_ID,
        re.compile(r"\b[1١2٢]\d{9}\b"),
        0,
    ),
    # أسماء عربية بتسمية: اسم المريض/الاسم/المريض/السيد/الدكتور/د. ثم 2-4 كلمات
    (
        KIND_NAME,
        re.compile(
            r"(?:اسم\s*المريض|الاسم|المريض|السيد|السيدة"
            r"|الأستاذ|الاستاذ|الدكتور|الدكتورة|أ\.د|د\.)"
            r"\s*[:\-]?\s+((?:" + _AR_WORD + r")(?:\s+" + _AR_WORD + r"){1,3})"
        ),
        1,
    ),
    # أسماء إنجليزية بتسمية: Patient Name/Name/Mr./Dr. ثم 2-4 كلمات بعلامة كبيرة
    # (حساس لحالة الأحرف عمدًا — كلمات الاسم بعلامة كبيرة لتقليل الإنذارات الكاذبة)
    (
        KIND_NAME,
        re.compile(
            r"(?:Patient\s*[Nn]ame|Full\s*[Nn]ame|Patient|Name|Mr\.|Mrs\.|Ms\.|Dr\.)"
            r"\s*[:\-]?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})"
        ),
        1,
    ),
)


# ─── نماذج البيانات ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PiiFinding:
    """مقطع شخصي مكتشف — إحداثيات فقط، بلا نص أصلي (منع التسريب المزدوج)"""
    kind: str
    start: int
    end: int


@dataclass
class PiiGateDecision:
    """قرار البوابة على نص واحد

    Attributes:
        mode: الوضع المطبَّق ("block" أو "mask").
        allowed: هل يُسمح بفهرسة text_for_index؟
        text_for_index: النص المسموح بفهرسته ("" عند الحجب، مُخفى عند mask).
        findings: المقاطع المكتشفة (إحداثيات فقط).
        counts: عدد المقاطع لكل نوع (للتسجيل والعرض).
    """
    mode: str
    allowed: bool
    text_for_index: str
    findings: list[PiiFinding] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def has_findings(self) -> bool:
        """هل وُجدت أي بيانات شخصية في النص؟"""
        return bool(self.findings)


# ─── الكشف والإخفاء ──────────────────────────────────────────────────────────

def find_pii(text: str) -> list[PiiFinding]:
    """يكشف المقاطع الشخصية في النص (عربي + إنجليزي)

    تعمل على النص الأصلي مباشرة (بدون تسوية) لتبقى الإحداثيات صالحة
    للإخفاء. الأنماط ذات الأولوية الأعلى تُطالَب بالمقاطع أولًا، وأي
    مطابقة متداخلة مع مقطع محجوز تُهمَل.

    Returns:
        قائمة PiiFinding مرتبة حسب موضع البداية.
    """
    if not text:
        return []

    claimed: set[int] = set()
    findings: list[PiiFinding] = []
    for kind, pattern, group in _PATTERNS:
        for match in pattern.finditer(text):
            start, end = match.span(group) if group else match.span(0)
            if start == end:
                continue
            span_positions = range(start, end)
            if any(pos in claimed for pos in span_positions):
                continue  # متداخل مع نمط أعلى أولوية — يُهمَل
            claimed.update(span_positions)
            findings.append(PiiFinding(kind=kind, start=start, end=end))

    findings.sort(key=lambda f: f.start)
    return findings


def mask_text(text: str, findings: list[PiiFinding]) -> str:
    """يستبدل المقاطع المكتشفة بعناصر نائمة مثل [PII:phone]

    الاستبدال من النهاية إلى البداية حتى تبقى إحداثيات المقاطع صالحة.

    Returns:
        النص بعد الإخفاء — بلا أي مقطع شخصي أصلي.
    """
    masked = text
    for finding in reversed(findings):
        placeholder = f"[PII:{finding.kind}]"
        masked = masked[:finding.start] + placeholder + masked[finding.end:]
    return masked


def _counts(findings: list[PiiFinding]) -> dict[str, int]:
    """يعدّ المقاطع لكل نوع (للتسجيل في ActionLog والعرض)"""
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.kind] = counts.get(finding.kind, 0) + 1
    return dict(sorted(counts.items()))


# ─── وضع البوابة والسجل (نمط مطابق لـ sensitive_barrier) ────────────────────

def _mode_from_env() -> str:
    """يقرأ وضع البوابة من متغير البيئة (الافتراضي: mask)"""
    mode = os.environ.get(ENV_PII_GATE_MODE, DEFAULT_MODE).strip().lower()
    if mode not in _MODES:
        logger.warning("وضع بوابة PII غير معروف: %r — استخدام %s", mode, DEFAULT_MODE)
        return DEFAULT_MODE
    return mode


_MODE: str = _mode_from_env()
_ACTION_LOG: Optional[ActionLog] = None


def get_mode() -> str:
    """الوضع الحالي لبوابة PII: block أو mask."""
    return _MODE


def set_mode(mode: str) -> None:
    """تغيير وضع البوابة وقت التشغيل (إعدادات التطبيق/الاختبارات).

    القيم: block | mask. القيم غير المعروفة تُرفض — لا وضع صامت.

    Raises:
        ValueError: إذا كان الوضع غير معروف.
    """
    global _MODE
    m = (mode or "").strip().lower()
    if m not in _MODES:
        raise ValueError(f"وضع غير معروف: {mode!r} — المتاح: {', '.join(_MODES)}")
    _MODE = m
    logger.info("وضع بوابة PII الآن: %s", _MODE)


def get_action_log() -> Optional[ActionLog]:
    """سجل الإجراءات المرتبط بالبوابة (None = لا تسجيل)."""
    return _ACTION_LOG


def set_action_log(action_log: Optional[ActionLog]) -> None:
    """يربط البوابة بسجل إجراءات موجود (من وحدة التحكم مثلًا) للتسجيل."""
    global _ACTION_LOG
    _ACTION_LOG = action_log


def _log_decision(
    log: Optional[ActionLog],
    decision: PiiGateDecision,
    source: str,
) -> None:
    """يسجّل قرار البوابة في ActionLog — لا يكسر الفهرسة عند فشل التسجيل

    القيد: بلا تعديل على مخطط ActionLogEntry — أعداد الأنواع تذهب إلى
    tags_added (مثل "email=2") وتظهر كوسوم في لوحة السجل.
    """
    if log is None:
        return
    if not decision.has_findings:
        return  # نص نظيف بلا بيانات شخصية — لا قرار يستحق التسجيل
    try:
        log.log(
            action_type=f"pii_gate:{decision.mode}",
            file_path=source,
            rule_name=SOURCE_PII_GATE,
            success=True,
            tags_added=[f"{kind}={count}" for kind, count in decision.counts.items()],
            source=SOURCE_PII_GATE,
        )
    except Exception as exc:
        logger.warning(f"فشل تسجيل قرار بوابة PII في سجل الإجراءات: {exc}")


# ─── الواجهة لمسار الفهرسة ───────────────────────────────────────────────────

def inspect_text(
    text: str,
    *,
    mode: Optional[str] = None,
) -> PiiGateDecision:
    """يفحص النص ويُرجع قرارًا كاملًا بلا تسجيل ولا تعديل حالة

    للاستخدام في الاستعلام/العرض. مسار الفهرسة يستدعي
    ``gate_text_for_indexing`` الذي يسجّل القرار في ActionLog.

    Args:
        text: النص المستخرج/OCR المراد فحصه.
        mode: تجاوز وضع البوابة لهذا الاستدعاء فقط (None = الوضع الحالي).

    Returns:
        PiiGateDecision يحمل الوضع والسماح والنص النهائي والمقاطع والأعداد.
    """
    effective_mode = (mode or _MODE).strip().lower()
    if effective_mode not in _MODES:
        raise ValueError(
            f"وضع غير معروف: {mode!r} — المتاح: {', '.join(_MODES)}"
        )

    findings = find_pii(text)
    if not findings:
        return PiiGateDecision(
            mode=effective_mode, allowed=True, text_for_index=text,
        )

    if effective_mode == MODE_BLOCK:
        return PiiGateDecision(
            mode=effective_mode, allowed=False, text_for_index="",
            findings=findings, counts=_counts(findings),
        )
    return PiiGateDecision(
        mode=effective_mode, allowed=True, text_for_index=mask_text(text, findings),
        findings=findings, counts=_counts(findings),
    )


def gate_text_for_indexing(
    text: str,
    source: str = "",
    *,
    mode: Optional[str] = None,
    action_log: Optional[ActionLog] = None,
) -> str:
    """بوابة الفهرسة — النص العائد هو ما يُضمَّن في ChromaDB فقط

    الاستخدام (سطر واحد داخل ``RAGEngine.ingest_file`` بعد التسوية العربية):

        text = gate_text_for_indexing(text, source=str(path))

    النص الفارغ العائد يعني "محجوب" — و``ingest_file`` يعيد 0 تلقائيًا
    عند النص الفارغ. القرار (مع أعداد الأنواع) يُسجَّل في ActionLog إن
    كان متاحًا عبر المعامل أو ``set_action_log`` — النصوص النظيفة بلا
    بيانات شخصية لا تُسجَّل ليبقى السجل مختصرًا.

    Args:
        text: النص المستخرج/OCR المراد فهرسته.
        source: مسار الملف المصدر (للتسجيل في ActionLog).
        mode: تجاوز الوضع لهذا الاستدعاء (None = الوضع الحالي).
        action_log: تجاوز السجل لهذا الاستدعاء (None = السجل المرتبط).

    Returns:
        النص المسموح بفهرسته ("" عند الحجب في وضع block).
    """
    if not text:
        return text

    decision = inspect_text(text, mode=mode)

    log = action_log if action_log is not None else _ACTION_LOG
    _log_decision(log, decision, source)

    if not decision.allowed:
        logger.info(
            f"بوابة PII: حجب فهرسة النص من {source or 'مصدر غير معروف'} "
            f"— الأنواع: {decision.counts or {}}"
        )
    elif decision.has_findings:
        logger.info(
            f"بوابة PII: إخفاء {sum(decision.counts.values())} مقطعًا "
            f"من {source or 'مصدر غير معروف'} — الأنواع: {decision.counts or {}}"
        )
    return decision.text_for_index


# ─── فئة الإضافة ─────────────────────────────────────────────────────────────

class PiiGatePlugin(IntelliFilePlugin):
    """إضافة بوابة PII — تُكتشف تلقائيًا من src/plugins/ بواسطة PluginManager"""

    name = "pii_gate"
    version = "1.0.0"
    description = (
        "بوابة PII: كشف وحجب/إخفاء البيانات الشخصية (عربي+إنجليزي) "
        "قبل فهرسة نص OCR في ChromaDB — أولوية P3"
    )

    def initialize(self, context: PluginContext) -> None:
        """يسجّل دوال البوابة في سياق الإضافات ويربط سجل الإجراءات إن وُجد

        يُسجَّل الكشاف كـ NER extractor (البوابة كشف تسميات بطبيعتها) و
        دالة الفهرسة كـ file processor (أقرب خطاف موجود في PluginContext).
        إن أُلحق سجل الإجراءات المشترك بالسياق لاحقًا (context.action_log)
        يلتقطه الكشاف تلقائيًا هنا.
        """
        self._context = context
        context.register_ner_extractor(self.name, find_pii)
        context.register_file_processor(self.name, gate_text_for_indexing)

        shared_log = getattr(context, "action_log", None)
        if shared_log is not None:
            set_action_log(shared_log)

        logger.info(
            f"بوابة PII جاهزة — الوضع: {get_mode()}، "
            f"التسجيل في ActionLog: {'نعم' if get_action_log() is not None else 'لا'}"
        )

    def shutdown(self) -> None:
        """التنظيف عند إلغاء تحميل الإضافة — يفك ربط السجل فقط"""
        set_action_log(None)
        logger.info("تم إيقاف بوابة PII")


__all__ = [
    "MODE_BLOCK",
    "MODE_MASK",
    "ENV_PII_GATE_MODE",
    "DEFAULT_MODE",
    "KIND_EMAIL",
    "KIND_PHONE",
    "KIND_NATIONAL_ID",
    "KIND_MRN",
    "KIND_NAME",
    "SOURCE_PII_GATE",
    "PiiFinding",
    "PiiGateDecision",
    "find_pii",
    "mask_text",
    "inspect_text",
    "gate_text_for_indexing",
    "get_mode",
    "set_mode",
    "get_action_log",
    "set_action_log",
    "PiiGatePlugin",
]
