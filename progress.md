# Progress — intelli-file-manager

> سجل تراكمي للجلسات — الأحدث في الأعلى، مدخل لكل جلسة.
> اللقطة الحالية لآخر جلسة تعيش في `session-handoff.md` (تُستبدل، لا تُضاف).

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
