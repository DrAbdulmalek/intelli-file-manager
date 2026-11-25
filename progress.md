# Progress — intelli-file-manager

> سجل تراكمي للجلسات — الأحدث في الأعلى، مدخل لكل جلسة.
> اللقطة الحالية لآخر جلسة تعيش في `session-handoff.md` (تُستبدل، لا تُضاف).

## 2026-11-25 — المرحلة F: إكمال بوابات الـHarness (فرع feat/harness-phase-f)

- **F004 (done)**: بوابة OCR التعاقدية — وحدة `src/core/ocr_gateway.py` (نقطة
  الاستيراد الوحيدة، وكيل ديناميكي PEP 562 يحفظ سلوك الرقع في الاختبارات) فوق
  التنفيذ المركزي `src/core/ocr_service.py`؛ نزع الاستيراد المباشر لـpytesseract
  من `enhanced_multimodal.py` واستبداله بـ`any_engine_available()`؛ توحيد
  المستهلكين (multimodal_processor, classifier) عبر البوابة؛ بوابة
  `gate:ocr-imports-gateway` في verify.sh + اختبار مرآة في test_ocr_gateway.py.
  إثبات: مخالفة مزروعة مؤقتًا → البوابة حمراء؛ بعد التنظيف → خضراء.
- **F003 (done)**: `scripts/hooks/pre-push` + `scripts/install_hooks.sh`
  (idempotent، لا يستبدل hooks الغيراء؛ init.sh يبقى قراءة-فقط وفق عقده)؛
  سطر التركيب في أوامر AGENTS.md السريعة. الاختبار اليدوي الموثق: دفع إلى
  مستودع عارٍ محلي مع ملف سرّ مفبرك في الفهرس → مرفوض (EXIT=1، «البوابة
  حمراء — قاعدة صفرية 3»)؛ بعد تنظيف الفهرس → الدفع ينجح (EXIT=0).
- **F005 (done)**: `Config.light_mode` (افتراضي False، يُحفظ ويُحمَّل) —
  hybrid_search يعمل BM25 فقط (`engine: bm25_only_light`)؛ rag_engine يجيب
  استخلاصيًا من المقاطع المسترجعة بلا Ollama؛ ai_engine يعطل LLM صراحةً؛
  FileCopilot يقبل `light_mode` ويمرره لمحركيه مع تراجع فوري للمحتوى
  المسترجع. التراجع بلا حزمة ollama مثبت بالاختبارات.
- **F002 (blocked)**: يحتاج `MEM0_API_KEY` من المالك (بيئة) — لا وكيل ينجزه نيابةً عنه.
- **REPO_POLICY**: تعديل جدول الوكلاء بقرار المالك 2026-11-25 (إيقاف Mistral؛
  Z.ai المنفّذ الوحيد) — اعتماد الدمج يبقى للمالك وحده عبر PR.
- **تحقق**: `pytest tests/unit -q` → 794 passed, 1 skipped (EXIT=0) ·
  `./scripts/verify.sh` → خضراء بما فيها gate:ocr-imports-gateway ·
  `bash -n` للسكريبتات الجديدة ✓ · الالتزامات: `34e9844` / `9c76923` / `a1c5737`.
- **الخطوة التالية**: مراجعة المالك لـPR المرحلة F ولـPR #95؛ توفير
  `MEM0_API_KEY` لفتح F002؛ بعد دمج القضية #93 يعاد توليد التقرير بالقواعد المعدلة (§7).

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
