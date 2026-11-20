# تصميم محرك Observability والتحسين المستمر — مقترح معماري

> **الحالة:** تصميم مقترح للمراجعة، **ليس** وصفاً لملفات موجودة. الموجود فعلياً اليوم:
> `src/db/observability/` (أساس SQLite+JSONL بـ5 سلوكيات — انظر `docs/OBSERVABILITY.md`)
> و`src/core/tree_manifest.py`. كل ما في هذا المستند تحت «البنية المقترحة» يحتاج مرحلة
> تنفيذ معتمدة منفصلة وفق البند 19-20 من `docs/ALPHACODE_PROTOCOL_v2.0.md`.

## الفكرة الأساسية: اللوغ محرك تطوير، لا سجل تشغيل

كل خطأ يقع أثناء تشغيل AlphaCode الحقيقي يتحول إلى أصل دائم في IntelliFile:

```
خطأ التشغيل الحقيقي  →  ENGINEERING_FINDING  →  REGRESSION TEST  →  CI يمنع التكرار
     (محلي، خارج Git)        (منقّح، قابل للمشاركة)      (fixtures اصطناعية)      (قياس قبل/بعد)
```

## البنية المقترحة

```
intellifile/
├── src/
│   ├── core/
│   │   ├── path_policy.py          # موجود
│   │   ├── safe_mover.py           # موجود (ملفّي فقط)
│   │   ├── tree_manifest.py        # موجود
│   │   └── ...
│   ├── db/observability/           # موجود (انظر docs/OBSERVABILITY.md)
│   └── observability/              # مقترح — امتداد فوق الأساس الموجود
│       ├── session_logger.py
│       ├── discovery_metrics.py
│       ├── classification_metrics.py
│       ├── duplicate_metrics.py
│       ├── performance_monitor.py
│       ├── error_analyzer.py
│       ├── engineering_findings.py
│       ├── feedback_store.py
│       └── report_generator.py
│
├── LOGS/                           # محلي فقط — خارج Git (موجود كسياسة)
│   ├── operational/                # سجلات تفصيلية بمسارات حقيقية
│   ├── engineering/                # منقّحة: File IDs، مسارات منقّحة
│   ├── performance/
│   └── feedback/
│
├── reports/
│   ├── session_reports/
│   ├── regression_reports/
│   └── improvement_reports/
│
└── tests/
    └── observability/              # اختبارات المحرك نفسه
```

## فصل المحتوى على GitHub — سياسة إلزامية

| النوع | المحتوى | الوجهة |
|---|---|---|
| Operational Logs | مسارات وأسماء حقيقية، إحصاءات تفصيلية | محلي فقط (`LOGS/`، خارج Git) |
| Engineering Findings | منقّح: File IDs، error codes، خطوات إعادة إنتاج ببيانات اصطناعية | قابل للرفع بعد التنقيح |
| Regression Tests | اختبارات من الـfindings بملفات اختبار اصطناعية | GitHub عبر PR |

بهذا تستفيد تجارب الجهاز الحقيقية في تطوير المشروع دون رفع أي بيانات شخصية أو طبية.

## خريطة أنواع اللوغات (بند 15 من البروتوكول) على الأساس الموجود

| لوغ البروتوكول | الموجود اليوم في `src/db/observability/` | الفجوة المقترح تغطيتها |
|---|---|---|
| A. SESSION_LOG | `start_run/finish_run` (run_id, session_id, component, status, duration) | إكمال حقول agent_version وfilesystem وexecution_mode |
| B. DISCOVERY_LOG | جزئي (input/output summaries) | سجل لكل ملف: mime/signature/discovery_method/exclusion_reason |
| C. CLASSIFICATION_LOG | لا يوجد | جديد: predictions + confidence + evidence + model |
| D. RELATIONSHIP_LOG | لا يوجد | جديد: groups + hash_match + relationship_type |
| E. ORGANIZATION_PLAN_LOG | لا يوجد | جديد: plan entries + collision/sensitivity status |
| F. EXECUTION_LOG | ActionLog/UndoLog موجودان لعمليات SafeMover | ربط approval_reference + pre/post hash |
| G. ERROR_LOG | جزئي (error_summary في runs) | errno + reproducibility + redaction موحد |
| H. PERFORMANCE_LOG | لا يوجد | جديد: عدادات زمنية/ذاكرة/cache |
| I. USER_FEEDBACK_LOG | جزئي (notes) | ربط correction بالتصنيف الأصلي وبالثقة قبل/بعد |
| J. ENGINEERING_FINDINGS_LOG | improvement queue موجود (بسيط) | ترقية بحقول finding كاملة + حالات النضج |

**ملاحظة صريحة:** هذا الجدول يصف الفجوة، ولا يوحي بأن الحقول المقترحة موجودة في الكود الحالي.

## تحويل الأخطاء إلى اختبارات — الخريطة المرجعية

| ما يحدث أثناء التشغيل | الاختبار الذي يمنع تكراره في IntelliFile |
|---|---|
| تصنيف ملف PDF عربي في فئة خاطئة | حالة اختبار لتصنيف المستندات العربية |
| الخلط بين مجلد وملف نهائي | اختبار مسارات الوجهة (final_destination_path يشير للملف) |
| عدم اكتشاف نسخة مكررة | اختبار Duplicate Detection (حجم ← sha256) |
| خطأ بسبب مسافة في اسم الملف | اختبار Path Handling (مسافات/رموز/شرطة أول الاسم) |
| تجاهل مجلد مخفي مستثنى | اختبار Path Policy |
| نقل ملف إلى وجهة موجودة | اختبار Collision Safety (STOP+LOG+REPORT) |
| اختلاف SHA-256 بعد النقل | اختبار Data Integrity (tree_manifest verify) |
| فشل التراجع | اختبار Undo/Recovery |
| استهلاك ذاكرة مرتفع مع ملفات ضخمة | اختبار أداء وذاكرة |

كل اختبار يأخذ fixtures اصطناعية (أسماء عربية بأشكال Unicode مختلفة، ملفات بأحجام مضبوطة، symlinks وهمية) — لا بيانات حقيقية من جهاز المستخدم أبداً.

## دورة الحياة لكل Finding

`NEW → INVESTIGATING → REPRODUCED → CONFIRMED → PROPOSED → FIXED → TESTED → VERIFIED` (أو `DEFERRED/BLOCKED`)، مع: Finding ID، Related Session ID، Related Test ID، Before Metric، Expected After، Actual After، Validation Status.

لا يُقبل إغلاق finding دون اختبار regression يثبت الإصلاح، ولا ادعاء تحسن دون قياس قبلي وبعدي.

## خطوات التبنّي المقترحة (تتطلب موافقة صريحة لكل خطوة)

1. تنفيذ المهمة الأولى (READ_ONLY_DIAGNOSTICS) وجمع الـfindings الحقيقية.
2. استخراج أول دفعة findings موثقة من تجارب WD السابقة (الموثقة في `docs/LOCAL_AGENT_FILE_OPERATIONS.md`).
3. بناء محرك Observability على فرع مستقل — ترقية `improvement queue` الحالي وليس استبداله.
4. تحويل النتائج القابلة لإعادة الإنتاج إلى اختبارات regression بfixtures اصطناعية.
5. قياس الأداء قبل/بعد كل تحسين وتوثيقه في `reports/improvement_reports/`.
6. مراجعة أمنية + CI قبل أي دمج.
