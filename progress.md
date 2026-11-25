
- **تحديث (قرارات نهائية 2026-11-26 — Phase 5 جاهز)**:
  - **id=156 حُل**: B (toolkit) يفوز — label 'i'→'-' (تصحيح OCR)، x1 193→2224, x2 2385→2308 (تحسين إحداثيات)، verified 0→1. تعديل مقصود، ليس تلفاً.
  - **Metric 6 مُتحقق**: سلة_تحقق = 11,514 ملف — Suspected partial mp3_: 6,030 + jpg_: 5,412 + png_: 62 + jpeg_: 10. صفر تكرارات (وضع fast). 5 عينات مسارات فعلية.
  - **crops.db resolution**: D (investigate) → C (directed merge: B يفوز 24، id=156 يُحسم يدويًا). B (55,141) كأساس.
  - **س9**: نعم — 4 قواعد فرعية (screenshots/camera/music/voice) مفعّلة.
  - **س12-14**: نعم — لا توسيع دون مراجعة تقرير المرحلة السابقة. SHA-256 + أرقام مجمعة فقط.
  - **البوابة 1**: مغلقة (integrity ok · 55,124 · baseline ae79551386c765e5d79f3e0f2a12537887db95c5003ca76ca480f9f8bb9a8091).
  - **البند 4**: معتمد (1,552 ملف، أنماط v1).
  - **البنود السبعة**: معتمدة.
  - **الـdeep scan**: مكتمل (SHA-256=8a5316183d03ad090fe03490488db5b2bb357ca365c4772f3b82c30468326a93).
  - **Phase 5**: بدء trial batch (200-500 ملف) — UndoLog + SHA-256 before/after + copy→verify→delete + --sensitive v1 + --batch-size 500.


- **تحديث (قرارات نهائية 2026-11-26 — Phase 5 جاهز)**:
  - **id=156 حُل**: B (toolkit) يفوز — label 'i'→'-' (تصحيح OCR)، x1 193→2224, x2 2385→2308 (تحسين إحداثيات)، verified 0→1. تعديل مقصود، ليس تلفاً.
  - **Metric 6 مُتحقق**: سلة_ verifying = 11,514 ملف — Suspected partial mp3_: 6,030 + jpg_: 5,412 + png_: 62 + jpeg_: 10. صفر تكرارات (وضع fast). 5 عينات مسارات فعلية.
  - **crops.db resolution**: D (investigate) → C (directed merge: B يفوز 24، id=156 يُحسم يدويًا). B (55,141) كأساس.
  - **س9**: نعم — 4 قواعد فرعية (screenshots/camera/music/voice) مفعّلة (enabled: true).
  - **س12-14**: نعم — لا توسيع دون مراجعة تقرير المرحلة السابقة. SHA-256 + أرقام مجمعة فقط.
  - **البوابة 1**: مغلقة (integrity ok · 55,124 · baseline ae79551386c765e5d79f3e0f2a12537887db95c5003ca76ca480f9f8bb9a8091).
  - **البند 4**: معتمد (1,552 ملف، أنماط v1).
  - **البنود السبعة**: معتمدة.
  - **الـdeep scan**: مكتمل (SHA-256=8a5316183d03ad090fe03490488db5b2bb357ca365c4772f3b82c30468326a93).
  - **Phase 5**: بدء trial batch (200-500 ملف) — UndoLog + SHA-256 before/after + copy→verify→delete + --sensitive v1 + --batch-size 500.

# Progress — intelli-file-manager

> سجل تراكمي للجلسات — الأحدث في الأعلى، مدخل لكل جلسة.
> اللقطة الحالية لآخر جلسة تعيش في `session-handoff.md` (تُستبدل، لا تُضاف).

## 2026-11-25 — جلسة التحقق المستقلة + تسليم التنفيذ الوحيد (Z.ai)

- **ما أُنجز**: مراجعة مستقلة لـ`session-handoff.md` بالتحقق الحي من GitHub API
  ونشرها على القضية #93؛ فتح PR #95 (قناة البوابة 2) من
  `feat/archive-sort-unified-decision` إلى main؛ تشغيل البوابة على الرأس `f8f7500`؛
  إعادة توليد التسليم بـ`scripts/session_handoff.py` ببوابات فعلية (لا `--no-tests`).
  قرار المالك في هذه الجلسة: إيقاف Mistral واعتماد Z.ai المنفّذ الوحيد.
- **تحقق**: `python3 -m pytest tests/unit -q` → 788 passed, 1 skipped (EXIT=0) ·
  `./scripts/verify.sh` → البوابة خضراء.
- **تعطّل**: لا شيء.
- **الخطوة التالية**: إكمال المرحلة F (F003/F004/F005) على فرع مستقل عن PR #95؛
  F002 محتجز على تزويد المالك `MEM0_API_KEY` من البيئة.

## 2026-11-24 — فرز أرشيف My Passport (ناتج عمل AlphaCode)

- **ما أُنجز**: بناء مخرجات فرز الأرشيف على الفرع `feat/archive-sort-unified-decision`:
  - `rules/archive_sort_rules.yaml` — 12 قاعدة من القرار الموحد (7 وجهات، عتبة 500MB، إعفاء crops.db).
  - `scripts/archive_sort.py` — سكريبت قراءة فقط (مسح + dry-run HTML بفلاتر، `--fast` و`--max-depth`).
  - `archive_sort_alphacode/` — مجلد مخصص يجمع كل المخرجات مع إشارة "ناتج عمل AlphaCode"
    (README + WORKLOG.md + PLAN_REVIEW_AND_OPEN_ITEMS.md + نسخ السكريبت/القواعد).
  - تقارير محاكاة تجريبية على عينات (`dry_run_report_sample*.html`).
- **تحقق**: `pytest tests/unit -q` → 775 passed, 1 skipped (EXIT=0) ·
  `verify.sh --quick` → البوابة خضراء · تحميل القواعد 12 قاعدة · العينة تُنتج تقرير HTML (EXIT=0).
- **تعطّل**: المسح الكامل للقرص (1.6TB على fuseblk) أبطأ من المهلة؛ المعاينة العملية
  تتطلب تشغيل المالك للسكريبت محلياً (بلا --fast للمسح الكامل بكشف التكرار).
- **الخطوة التالية**: على المالك إجابة البنود المفتوحة السبعة + اعتماد الخطة، ثم تنفيذ
  المرحلة 1 (نسخ crops.db خارجياً) كبوابة أولى قبل أي نقل فعلي.
- **تحديث (رد المراجعة المستقلة)**: وثّق AlphaCode تأكيدات سلوك الأدوات من الكود
  (path_policy لا يستثني النظامي؛ move يحذف قبل التحقق؛ لا NFC؛ strict؛ is_duplicate)
  في `ALPHAcode_RESPONSE_TO_INDEPENDENT_REVIEW.md`، وأضاف مجلداً ثامناً `غير_مصنّف`
  للقواعد. التزام `2f39e37`.
- **تحديث (تنفيذ آمن في archive_sort.py 2026-11-25)**: أُضيف وضع التنفيذ الفعلي إلى `scripts/archive_sort.py` (الالتزام `c95fbf4`، مرفوع إلى GitHub):
  - copy→verify→delete (ليس move-then-verify) لحماية البيانات على fuseblk/NTFS
  - توحيد يونيكود NFC لأسماء الملفات والوجهات
  - معالجة الملفات المقفلة عبر إعادة المحاولة (EBUSY/EACCES/EAGAIN/EWOULDBlock)
  - أنماط حساسية افتراضية + قائمة إضافية من البند 4
  - --execute يتطلب --confirm-execute (ضمانة أمان — يُرفض بدونه)
  - --batch-size (افتراضي 500، نطاق 200–5000) مع سجل التراجع (UndoLog)
  - جميع الاختبارات passent (63/63)، dry-run يعمل على مجلد اختبار
- **البوابة 1 معلقة**: يحتاج المالك تنفيذ نسخ `crops.db` خارجياً + فحص سلامة + بصمات SHA-256 قبل أي نقل فعلي على القرص.
- **البند 4 معلقة**: يحتاج المالك إرسال قائمة الحساسيات (لا يمكن لأي وكيل إنجازها نيابةً عنه).

## 2026-10-05 — تبنّي Harness Engineering v2.0

- **ما أُنجز**: إضافة العقد (`AGENTS.md` مخصص لهذا المستودع) + البوابات
  (`init.sh`, `scripts/verify.sh`, `scripts/session-handoff.py`,
  `scripts/test_mem0_memory.py`) + ملفات الحالة (`feature_list.json`,
  `progress.md`, `session-handoff.md`) + الدليل (`docs/HARNESS.md`).
  كل شيء على فرع `feat/harness-engineering` — صفر تعديل على ملفات قائمة.
- **تحقق**: `bash -n init.sh` ✅ + `bash -n scripts/verify.sh` ✅ +
  `python3 -m py_compile scripts/session-handoff.py scripts/test_mem0_memory.py` ✅ +
  فحص أسرار: لا أسرار متتبعة ✅. (بوابات الاختبارات الكاملة تعمل عبر
  `./init.sh` وCI في بيئة كاملة.)
- **تعطّل**: لا شيء.
- **الخطوة التالية**: مراجعة المالك لهذا PR؛ ثم F004 (بوابة منع الاستيراد المباشر).
