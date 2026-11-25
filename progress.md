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
