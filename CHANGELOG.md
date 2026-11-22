# Changelog

All notable changes to IntelliFile are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] — AlphaCode closed-loop integration (تكامل الحلقة المغلقة)

### أُضيف
- `docs/alphacode-integration.md`: بروتوكول الحلقة المغلقة AlphaCode ↔
  IntelliFile — الأدوار، تخطيط القرص، قضبان الأمان، والتشغيل السريع.
- `scripts/alphacode_sync.py`: رفع تلقائي لمخرجات AlphaCode إلى فرع أيتام
  `alphacode/artifacts` (بلا force push، بلا لمس main) بعد مسح حاجز
  الحساسية v2 وسقوف صارمة، ثم تسليم للابتلاع وإفراغ الـoutbox.
- `scripts/alphacode_ingest.py`: ابتلاع artifacts بأسماء غير قابلة
  للتغيير + manifest.jsonl append-only + تصنيف SmartFileClassifier +
  evidence في FeedbackEngine بحالة pending (لا تفعيل بلا تأكيد المستخدم)
  + لوحة summary.md.
- `scripts/alphacode_apply.py`: بوابة الموافقة الإلزامية — لا تعديل على
  شجرة المشروع إلا بموافقة موقّعة بتجزئة sha256 للـpatch (أو موافقة
  تفاعلية تُسجَّل)، فحص مسارات صارم، نسخة احتياطية، اختبارات بعد التطبيق،
  وتراجع تلقائي بايت-بايت عند الفشل مع --rollback يدوي.
- `tests/unit/test_alphacode_toolkit.py`: 14 اختباراً يغطي رفض الحاجز،
  دفعات الفرع الأيتام، أرشفة الابتلاع، وكل مسارات رفض البوابة والتراجع.

## [Unreleased] — Preference & Feedback Learning (مهمة التفضيلات)

### أُضيف
- `src/core/preference_store.py`: مخزن تفضيلات (schema v2) بكتابة ذرّية
  تحت flock، نسخة احتياطية موثقة بالبصمة، ترحيل v1→v2 لا يفقد الحقول
  غير المعروفة، وSAFE READ-ONLY عند أي فشل (لا حفظ فوق الملف الأصلي).
- `src/core/preference_engine.py`: قواعد تعلم provisional→stable عبر 3
  جلسات مستقلة، أسبقية نطاق file>directory>global، حسم توازٍ حتمي، كشف
  تعارضات، حذف منطقي قابل للتراجع، وشرح اقتراح كامل.
- `src/core/feedback_engine.py`: دورة ملاحظات مغلقة بسجل JSONL منفصل
  append-only، رفض/مؤقت لا يتعلمان، تكرار معلَّم بلا استقلالية، وأدلة
  بقائمة بيضاء (لا مسارات/أسماء/محتوى).
- `src/core/classifier_preferences.py`: غلاف الاقتراح فوق المصنف الحقيقي
  — سلوك المصنف القديم بلا أي تغيير، والاقتراح منفصل عن التنفيذ.
- `src/integrations/alphacode_preference_tools.py` + خمس أدوات تفضيلات
  جديدة على جسر MCP المحلي (get_suggestion/record_user_correction/
  explain_rule/list_applicable_rules/confirm_rule/disable_rule/
  enable_rule) — لا ملفات، لا shell، لا شبكة؛ التطبيق يتطلب
  user_confirmed=true صريحًا.
- لوحة `PreferencesPanel` في واجهة سطح المكتب: عرض جميع حقول الاقتراح
  وإدارة القواعد — أزرارها تعلم فقط ولا تنفذ أي عملية ملف.
- وضع `on_conflict="reject"` اختياري في SafeMover (رفض الوجهة الموجودة
  وفق سياسة المستخدم) — الافتراضي (لاحقة تلقائية) بلا تغيير للتوافق
  مع UndoLog.
- توثيق: PREFERENCE_STORE / FEEDBACK_ENGINE / ALPHACODE_ADAPTER /
  PREFERENCE_SECURITY + قسم في README.

### السلامة
- المصنف الأساسي وSafeMover وUndoLog والحواجز الحساسية القائمة لم تُكسر:
  الحزمة الكاملة بنفس نتائج main المزعومة (فشل glossary الستة معروف
  سلفًا بغياب data/).
- 84 اختبارًا جديدًا (بيانات اصطناعية فقط) + انحدار safe_mover/undo_log/MCP
  كاملًا.

### حدود معلومة
- تكامل AlphaCode GUI الفعلي غير مثبت بعد — يتطلب تسجيل خادم MCP في
  إعدادات AlphaCode؛ الواجهة موثقة كـ«جاهزة للتكامل».
- اختبارات واجهة Qt لم تُشغَّل محليًا لغياب libEGL.so.1 (تتخطى آليًا
  كالاختبارات القائمة).
## [Unreleased] — security/comprehensive-sensitive-barrier-hardening

### أُصلح — الحاجز الموحّد للبيانات الحساسة (انظر docs/SENSITIVE_BARRIER.md)
- **قواعد إلزامية لا تعطّلها الإعدادات:** كان `skip_dirs` يُمرَّر إلى
  `is_sensitive_path` فيُبطل كشف `secrets`/`credentials` (ثغرة مثبتة في
  `FileInventory` كان hash+magic يقرآن محتوى ملف داخل مجلد أسرار). الآن
  القواعد إلزامية والمعامل متجاهَل، وأزيل `secrets`/`credentials` من
  استثناءات المسح ليظهر الحظر صراحة في الجرد بدل الاختفاء الصامت.
- **ملفات الأسرار والاعتماديات:** كشف جديد بالاسم الصارم (`.env` وأي اسم
  ينتهي بـ`.env`، `.netrc`، `credentials.json`، `secrets.yaml`، مفاتيح SSH
  الخاصة `id_rsa`/`id_ed25519`/...) وبالامتداد (`.pem`، `.p12`، `.pfx`،
  `.key`، `.kdbx`، `.jks`، الشهادات...).
- **مؤشرات طبية إضافية:** `medical_records`، `clinical`، `hospital_records`،
  `radiology`، `prescriptions`، `laboratory`، `lab_results` والأعرب المقابلة.
- **الروابط الرمزية:** تصنيف الرابط + الهدف (`realpath`) بما في ذلك
  المكوّنات الوسيطة؛ `open_checked()` يفتح بـ`O_NOFOLLOW` مع فحص ملف عادي
  عبر `fstat`؛ `verify_open_identity()` ضد بدل الملف بين الفحص والقراءة.
- **توثيق مستويات الكشف الثلاثة** (path/name مقابل header مقابل full-content):
  فحص header DICOM يقرأ 4 بايتات موثّقة — لم يُعد تعداماً "قراءة صفرية".
- **قارئات جديدة عبر الحاجز:** `AIEngine.summarize_file/extract_keywords`،
  `FileCopilot.summarize_file/index_files`، `SmartTagger._extract_content`،
  `MultimodalProcessor.process_image/audio/video` و`extract_text_from_*`،
  `metadata_extractor` الثلاثية (EXIF/ffprobe/magic — EXIF يُعامل حساساً)،
  `SmartFileClassifier.classify_file` (لا Magika على حساس) و`batch_classify`
  (iter_files بلا symlinks)، `HFExporter._crop_and_save`.
- **الفهرسة التكرارية:** `FileCopilot.index_files` يوسّع المجلدات عبر
  `iter_files` ويفحص كل ملف على حدة قبل RAG — لا يمر مجلد خام إلى أي محرك.
- **`FileInventory._iter_files`:** لا يسلّم روابط رمزية للقراءة (كانت
  `glob` تُخرج روابط ملفات وقراءة هدفها خارج الشجرة).

### أُصلح — API ومصادقة
- **مصادقة ناقصة:** `/api/tags/search`، `/api/tags/all`،
  `/api/copilot/conversations`، `/api/file/serve` كانت بلا `_auth` — مفتاح
  API مضبوط لا يحميها؛ أُضيفت المصادقة ومقارنة زمن-ثابت (`compare_digest`).
- **WebSocket `/api/copilot/ws`:** كان يقبل الاتصال بلا مفتاح (Origin ليس
  مصادقة وأي عميل غير متصفح لا يرسله) — الآن المفتاح **قبل** `accept()`؛
  ورسائل الخطأ لا تسرب محتوى.
- **تسريب توكن HuggingFace:** `/api/snippets/export-hf/push` كان يستقبل
  التوكن عبر Query Parameter (يتسرب إلى access logs) — الآن رأس
  `X-HF-Token` فقط، ولا يظهر التوكن في أي رسالة خطأ.
- **`_get_allowed_dirs`:** كان يلحق `Path.cwd()` دائماً فيتجاوز الصندوق عند
  ضبط `INTELLIFILE_ALLOWED_DIRS` صراحةً — الآن cwd يُلحق في الوضع الافتراضي
  فقط.
- **`/api/file/serve`:** حاجز حساسي قبل خدمة أي صورة عبر HTTP (403).
- **نقاط process المكسورة:** `/api/process/audio|video|document` كانت ترمي
  `AttributeError` و`/api/process/image` ترمي `TypeError` (`fix_scan`) —
  `EnhancedMultimodalProcessor` اكتملت منهجهما عبر توكيل محاجوز.

### أُزيل — أسلاك ميتة (NER)
- `/api/ner/extract` ومحرك `ner` من `/api/health`: وحدة
  `src/core/medical_ner.py` غير موجودة والـendpoint كان يعيد 500 دائماً؛
  `PRODUCT_IDENTITY.md` يستبعد مكونات NER من هذا المستودع. أُزيلت أيضاً
  وسوم NER الميتة من `smart_tagger`.

### أُصلح — CI fail-closed
- `python-ci.yml`: `pytest ... || echo "No tests found"` → تشغيل صارم مع
  حارس "اختبارات موجودة" (صفر اختبارات = فشل)، وflake8 (E9/F63/F7/F82)
  حاجب، وblack غير حاجب معلن.
- `ci-kimi-review.yml`: `|| true` على الاختبارات والـlint → حذفها؛ فحص
  ruff على الفئات الجسيمة حاجب؛ فحص إقلاع الـAPI حاجب؛ إصلاح 8×F821
  (استيرادات TYPE_CHECKING ناقصة).

### أُصلح — tree_manifest (سلامة اللقطات)
- **رفض جذر symlink** (وأي مكوّن وسيط) في `snapshot` و`verify`.
- **تغيّر هدف الرابط الرمزي** بين اللقطة والتحقق → `target_changed` و
  `ok=False` (كان ينتج نجاحاً كاذباً).
- **تبدل الملف أثناء حساب الهاش** → fail-closed (لا سجل غير موثوق؛
  re-check عبر `os.stat` الصريح — `DirEntry.stat` مخزّن مؤقتاً).
- فتح بـ`O_NOFOLLOW` عند حساب الهاش.

### تنظيف البنية
- إزالة `project_context.txt` (1.6MB مولّد) و`web/tsconfig.tsbuildinfo`
  (مخرجات بناء) من التتبع + `.gitignore`.
- إزالة `docs/ARCHITECTURE.md` (الخلاصة المكررة؛ التفصيلية
  `docs/architecture.md` هي المرجع، بلا أي مرجع للملف المحذوف).
- تفكيك ازدواج pytest بين `pytest.ini` (المصدر الوحيد، يشمل علامة desktop)
  و`pyproject.toml` + تكوين `[tool.ruff]` موحّد.
- إصدار موحّد: `src/__version__.py` (2.2.0.dev0) — يتطابق مع محتوى PR #72
  ليسهل دمجه لاحقاً؛ `server.py` (health/app/stats) تستورده.

### اختبارات جديدة
- `tests/unit/test_sensitive_barrier_v2.py` (42): أسرار، مؤشرات، symlink،
  O_NOFOLLOW، عجز skip_dirs، إنذارات كاذبة محفوظة.
- `tests/unit/test_reader_read_prevention.py` (27): قياس **عدم الفتح
  الفعلي** لكل قارئ (ميزانية 4 بايتات)، الفهرسة التكرارية، سيناريوهات
  الخلط، symlink root/target، التبدل أثناء الهاش.
- `tests/integration/test_api_auth_ws.py` (19): مصادقة endpoints، WS
  (بلا مفتاح/خاطئ/صحيح/Origin)، HF token، NER مُزال، file/serve، sandbox،
  process endpoints.

### معلوم
- numpy: لا تعارض فعلي في main (`numpy>=1.24.0` فقط، بلا قيد `<2`) —
  البند كانت مخالفته قد أُغلقت سابقاً.
- اختبارات مسارد طبي أساسية (6) فاشلة قبل التغييرات وبعدها بسبب غياب
  `data/medical_glossary.csv` عن المستودع (ليس من هذا الفرع).

---

## [Unreleased] — AlphaCode local MCP bridge

### أُصلح (مراجعة مستقلة 2026-11-21)
- **انهيار أول تشغيل**: `~/.intellifile` يُنشأ قبل `setup_logging` (كان `FileNotFoundError` على جهاز نظيف).
- **مصدر إصدار واحد** `src.__version__` (كانت: 2.0.0 / 1.0.0 / 2.1.0 / 2.2.0.dev0 في نقاط الدخول).
- **إزالة NER الميت** (`/api/ner/extract` كان يعيد 500 لأن الوحدة محذوفة) من الخادم والجوال وREADME وقائمة الفحص.
- **WebSocket `/api/copilot/ws`** يطبّق مفتاح API (ترويسة `X-API-Key` أو بروتوكول فرعي `ifm-key.<key>`)، ومقارنة المفتاح ثابتة الزمن.
- **CI حاجز فعلاً**: بلا `|| echo`/`|| true`؛ flake8 للأخطاء القاتلة حاجز (وأُصلحت 8 أسماء غير معرّفة)،
  والاختبارات التسعة المعروفة الفشل محجورة صراحة في `tests/KNOWN_FAILURES.md` بدل إخفائها.
- `data/medical_glossary.csv` كان يُتجاهل بـ `data/` فلم يُلتزم قط (الاستثناء مضاف؛ **الملف نفسه يجب أن تلتزم به أنت**).
- APK لا يُبنى على كل دفعة إلى main (وسوم/يدوي فقط)؛ `*.tsbuildinfo` يُتجاهل ورُفع من الفهرس.
- **الحاجز يحجب الأسرار بالاسم/الامتداد** (`.env`، `id_rsa`، `*.pem`، `*.p12`، `*.kdbx`…) في أي مجلد،
  لا في `.ssh` وحده؛ مطابقة تامة فلا يُحجب `tokenizer.py` ولا `id_rsa.pub` ولا `.env.example`.
- **الحاجز لا يفتح ما حُسم بالاسم/المسار**: كانت ترويسة DICOM تُقرأ قبل فحص الاسم، فيُفتح الملف
  الحساس أصلاً. صار فحص الترويسة آخر خطوة ولملفات بلا امتداد أو بصور عامة فقط (لا فتح لكل ملف في مسح ضخم).
- **قرّاء محتوى كانوا بلا حاجز**: `AIEngine.summarize_file/extract_keywords`،
  `MultimodalProcessor.extract_text_from_*` و`process_image`، `FileCopilot.summarize_file/index_files`.
- تنظيف 16 سطراً فيها شظايا حروف غريبة (صينية/روسية/هندية/إيطالية) في الشيفرة والوثائق والاختبارات.

### أُضيف
- جسر MCP محلي عبر stdio لربط AlphaCode بـ IntelliFile دون خادم شبكي أو اتصال خارجي.
- أدوات محدودة للوكيل: حالة الاتصال، جرد بيانات وصفية فقط، والتحقق التجريبي من خطة التنظيم.
- اجتياز موحد مُبلّغ للأخطاء ضمن Path Policy، مع عدم اتباع الروابط الرمزية أو عبور نقاط التركيب.
- اختبارات اصطناعية لحدود الجذر المسموح، والمسارات الحساسة، والروابط الرمزية، وحدود النتائج، وبروتوكول MCP.
- أداة `scripts/alphacode_mcp_probe.py` لاكتشاف تلميحات إعداد MCP محلياً بوضع قراءة فقط، دون تشغيل AlphaCode أو طباعة قيم الإعدادات والأسرار.

### حدود السلامة
- لا قراءة محتوى أو OCR/RAG، ولا نقل أو نسخ أو حذف أو إعادة تسمية أو Undo أو تنفيذ أوامر.
- لا تُفعّل عمليات الكتابة قبل إغلاق عيوب SafeMover وحاجز الحساسية بمراجعة واختبارات مستقلة.
- اتصال AlphaCode الفعلي غير مثبت بعد؛ يتطلب دعم MCP stdio في نسخة AlphaCode المحلية وتسجيل الخادم في إعداداتها.

---

## [2.2.0-dev] — قصاصات التدريب + محرر OCR + المسارد الطبية

### أُضيف
- **نظام القصاصات التدريبية** (`src/db/snippet_db.py` + `/api/snippets/*`):
  SQLite مع سير عمل كامل (إنشاء/تحرير مربع/اعتماد/رفض/حذف) لإنتاج بيانات
  تدريب OCR بشرح بشري — تصحيح كلمة/سطر/فقرة.
- **محرر OCR الويب** (`web/` → صفحة `/edit-ocr`): محرر مربعات canvas
  (رسم/سحب/تحجيم بـ8 مقابض/حذف) + تلوين ثقة (أخضر/أصفر/أحمر/رمادي=غير
  معروفة) + تحرير نص RTL + اقتراحات المسرد الطبي — الأدوات المرجعية
  (labelme/dots-ocr-editor/ScribeArabic) دُرست بنيويًا فقط.
- **خدمة المسارد الطبية** (`src/core/glossary_service.py` +
  `/api/glossary/suggest`): 741 زوجًا طبيًا عربي-إنجليزي مدمجًا من مشروع
  `arabic-medical-glossary` (تنظيف من مسرد شامل + مصطلحات عالية الثقة)
  مع تطبيع عربي (تشكيل/همزات) وقابلية الاستبدال بمسرد 21k عبر
  `INTELLIFILE_GLOSSARY_PATH`.
- **تصدير HuggingFace** (`src/services/hf_exporter.py` +
  `scripts/export_training_data.py`): JSONL للقصاصات المعتمدة + رفع
  صريح يتطلب توكنًا صريحًا (لا اعتمادات ضمنية أبدًا).
- **وضع خفيف بلا LLM** (`INTELLIFILE_LIGHTWEIGHT=1`): يعطل Ollama/
  التضمينات الدلالية؛ بحث BM25 وتصنيف بالقواعد فقط.
- **Rate limiting** على /api/* (نافذة منزلقة داخلية بلا تبعيات جديدة،
  قابل للضبط عبر INTELLIFILE_RATE_LIMIT/WINDOW).
- **نقطة `/api/file/serve`** لخدمة صور القصاصات داخل الـsandbox الحالي.
- ROADMAP.md خطة الإصدارات.
- اختبارات: 23 وحدة + 8 تكامل جديدة (snippet_db, glossary, exporter,
  snippets API, rate limit, lightweight, file-serve sandbox).

### أُضيف (أدوات الوكيل المحلي)
- `src/core/tree_manifest.py` + `scripts/tree_manifest.py`: لقطة قبل نقل شجرة وتحقق بعدها
  (يرى المخفي والمجلدات الفارغة، لا يتبع الروابط، يفشل عند الفقد أو عدم اكتمال القراءة).
- `docs/LOCAL_AGENT_FILE_OPERATIONS.md`: بروتوكول وبرومبت للوكيل المحلي مبنيان على أخطاء لوغ WD.
- `docs/ALPHACODE_PROTOCOL_v2.0.md`: البروتوكول الموحد للوكيل + التحسين المستمر — هدف مزدوج
  (تنظيم آمن + تغذية هندسية راجعة)، سياسة خدمات خارجية بمستويات بيانات (الطبي الحساس والأسرار
  لا تُرسل)، مراجعة قدرات إلزامية قبل التعديل، 10 أنواع لوغ، فصل OPERATIONAL/ENGINEERING،
  ومهمة أولى READ_ONLY_DIAGNOSTICS بلا أي نقل.
- `docs/OBSERVABILITY_ENGINE_DESIGN.md`: تصميم مقترح لمحرك التحسين المستمر — تحويل أخطاء
  التشغيل إلى اختبارات regression، وخريطة فجوات صريحة على أساس `src/db/observability/` الموجود.

### أُصلح
- **سياسة اجتياز موحّدة** (`src/core/path_policy.py`): المخفي يُحدَّد نسبةً إلى
  جذر المسح، وتُقلَّم المجلدات المخفية والمستثناة قبل النزول فيها، ولا تُتبع
  الروابط الرمزية للمجلدات أو الملفات. استُخدمت في المصنّف والوكيل ومدير الملفات
  والوسوم والبحث الهجين والدلالي ومحرك التصنيف الناشئ.
- **التصنيف الناشئ**: معالجة عدم تطابق مفتاح الإحصاء (`extensions` مقابل
  `extension_distribution`) الذي كان يمنع توليد التصنيفات المقترحة.
### ملاحظات
- ثقة 0.0 تعني "غير معروفة" (سياسة ocr-core) — لا تُختلق درجات أبدًا.
- الرفع إلى HuggingFace منفصل صريح عن التصدير المحلي.

## [Unreleased] — 2.2.0-dev

> The work below is merged to `main` but **not yet tagged `v2.2.0`**.
> The latest released tag is `v2.1.0`. The `2.2.0.dev0` version in
> `setup.py` reflects this pre-release state. Tag `v2.2.0` only after
> completing `docs/RELEASE_CHECKLIST_v2.2.0.md`.

### Desktop UX (Phase C Complete)

#### PR-09: Progress + Previews + Settings
- **Cancellable progress bars** — `ProgressManager` (multi-op) integrated with
  `IFMController.progress` + `operation_cancelled`. Covers indexing, dry-run,
  and rule execution.
- **File preview panel** — `FilePreviewPanel`:
  - Text preview for ~30 extensions (txt, md, csv, json, yaml, py, js, ...)
  - Image thumbnails for 10 extensions (jpg, png, gif, bmp, webp, svg, ...)
  - Full file metadata (name / path / size / MIME / mtime)
  - Smart truncation for files >100 KB
  - Auto-update on inventory row selection
- **Settings panel** — `SettingsPanel` with 11 persisted fields:
  - watch_folders_enabled, default_dry_run, confirm_destructive
  - semantic_search_enabled (optional — off by default)
  - dark_mode, rtl, auto_organize
  - thumbnail_size, max_text_preview_bytes
  - save_undo_log_on_exit, save_action_log_on_exit
- **Error reporter** — `ErrorReporter` (counter + last-50 log) in status bar
- **Recent actions widget** — last 20 actions in status bar

#### PR-10: Polish + Release Checklist + v2.2.0
- **Keyboard shortcuts** — `ShortcutManager` with 8 global shortcuts:
  - Ctrl+R (refresh), F5 (scan), Ctrl+Z (undo), Ctrl+F (search)
  - Ctrl+, (settings), Ctrl+P (preview), Ctrl+T (toggle theme), Esc (cancel)
- **Crash recovery** — `CrashRecovery`:
  - Session persistence (last directory, panel, theme)
  - Global exception hook with crash logs (rotated, last 10 kept)
  - SIGINT/SIGTERM graceful shutdown
  - Crash recovery dialog on restart
- **PyInstaller packaging spec** — `packaging/desktop.spec` (Linux-first)
- **Release checklist** — `docs/RELEASE_CHECKLIST_v2.2.0.md`
- **Version bump** — `2.1.0` → `2.2.0`
- **`--version` CLI flag** — `python -m src.desktop.app --version`

### Core MVP (Phase A Complete)
- Indexed file inventory with SHA-256 deduplication
- Metadata extraction (EXIF, ffprobe, python-magic)
- Rule engine with YAML rulesets + dry-run mode
- Undo/rollback log with full action reversal
- Duplicate detection (exact + near-duplicate via embeddings)
- Watch folders with debounce + safe batch processing
- Safe atomic move/copy with checksum verification
- Action log with JSON/HTML/CSV export

### Security & Identity
- Product identity reset: local-first desktop file manager
- Removed all omni-medical-suite coupling
- API key optional auth + localhost binding
- No medical/DICOM/SyncManager scope creep

---

## [2.1.0] — 2026-07-24

### Desktop UX Foundation (Phase C — PR-08)
- PySide6 main window with sidebar + central stack + status bar
- 7 panels: Inventory, Preview, Rules, ActionLog, UndoLog, Watcher, Settings
- RTL Arabic theme + dark mode toggle
- IFMController signal/slot integration

### Phase A — Core MVP (PR-01 through PR-07)
- PR-01: Removed DICOM/SyncManager (scope reset)
- PR-02: Indexed file inventory with SHA-256
- PR-03: Enhanced metadata + content extraction
- PR-05: Rule engine + dry-run + undo
- PR-06: Duplicate detection + watch folders
- PR-07: Safe move/copy + action log

---

## [2.0.0] — 2026-07-22

### Initial Product Identity Reset
- Established local-first desktop file manager scope
- Created PRODUCT_IDENTITY.md, REPO_POLICY.md, SECURITY_NOTES.md
- Removed all medical/DICOM/SyncManager scope creep

## Unreleased
- Session handoff is local-only by default, writes a private no-clobber file, and requires explicit flags for remote Mem0 upload/testing.

## Unreleased
- Verification secret scanning now reports file paths only and never prints matched secret values.

## Unreleased
- Moved marathon-ocr-core from base requirements to an opt-in, commit-pinned OCR integration requirements file.
- Hardened read-only organization preflight against hidden/system and nested mount traversal; manifest output now uses exclusive no-clobber publication and rejects symlinked parents.

## Unreleased
- Organization preflight now rejects symlinked source ancestors before walking directory trees.

## Unreleased
- Added a regression test for fail-closed manifest publication when atomic no-clobber linking is unavailable.
- Removed raw LOGS references and identifying operational details from the safe-organization preflight proposal.
- Redacted personal filesystem paths and detailed operational inventory data from the organization-lessons document.
- Redacted private log filenames and credential-incident details from the independent review document.
- SafeMover now fails closed when atomic no-clobber publication is unavailable and rejects symlink path components and non-regular sources; added regression tests for unsafe fallback and symlink cases.
- Hardened FileHandler scans to use the shared path policy; permit explicitly selected mount roots while pruning nested mounts; fail closed on mount-inspection errors; exclude .gnupg; and add hidden-tree/symlink regression coverage.
- Scan-root validation now rejects symlinked ancestor components, with regression coverage.


---

## [Unreleased] — P0 + P1 (2026-11-22) — branch feat/p0p1-ops-safety-readiness

### Added (P1)
- `UndoLog.rollback_batch(batch_id)`: تراجع عن دفعة كاملة بترتيب عكسي، عبر SafeMover فقط،
  مع فحص مبدئي (preflight) يقرأ `checksum_after` ويُجهض الدفعة **كاملة دون أي تعديل**
  عند اكتشاف ملف عُدّل بعد العملية الأصلية. السجلات تُحذف بعد نجاح عكسها فقط.
- `UndoEntry.batch_id` و `ActionLogEntry.batch_id` + `ActionLog.by_batch()` —
  توافق خلفي كامل: السجلات القديمة بلا batch_id تُحمَّل بقيمة الشريطة الفارغة.
- `ExportError` + إعادة كتابة `MedicalDB.export_deidentified()`: تصدير ذري
  (mkstemp + fsync + os.link no-clobber، أو os.replace فقط مع overwrite=True صريح)،
  No-Clobber افتراضياً، رفض تطابق المصدر/الوجهة بعد expanduser+resolve
  (يشمل الروابط الرمزية والمسارات النسبية)، تنظيف الملف المؤقت دائماً،
  و`free_text_policy="verbatim"` موثق: النصوص الحرة (summary/findings) تُنسخ
  نصياً بلا تنقية مدمرة — النشر العام يتطلب مراجعة بشرية.

### Changed (P1)
- `MedicalDB.register_file()`: حساب البصمة عبر `open_checked()` + إعادة التحقق
  `verify_open_identity()` بعد القراءة (مضاد TOCTOU) — عند تغيّر/استبدال الملف
  أثناء القراءة تُرفض البصمة كلياً ولا تُسجَّل باسم ملف آخر.

### Docs (P0)
- README: توحيد النطاق — IntelliFile Core عام + Medical Module اختيارية + جدول
  أوضاع الحاجز (strict/local؛ الأسرار والإرسال الخارجي محجوبان دائماً). حُسم تعارض
  «ليس أداة طبية» مع وجود وضع العيادة والقاعدة الطبية.

### Tests (سلبية، ليست Happy-Path فقط)
- `tests/unit/test_undo_batch_rollback.py`: تراجع دفعة، أجهض بالكامل دون تعديل عند تعارض،
  بقاء ملف المستخدم المعدَّل، توافق سجلاتقديمة بلا batch_id.
- `tests/unit/test_medical_db_export.py`: سلامة قاعدة المصدر بايت-بايت، تجرّد محتوى،
  No-Clobber يترك الوجهة الموجودة سليمة، overwrite صريح فقط، رفض نفس المسار
  وسيم-لينك المصدر والمسار النسبي المكافئ.


---

## [Unreleased] — PR #78 Remediation (2026-11-22) — مراجعة مستقلة: CI فاشل (1 failed/1051 passed على 3.10 و3.11)

### Fixed — التصدير (Findings 1، 2، 3)
- **F1**: إزالة `self.log("export_deidentified", ...)` من `export_deidentified` — كانت تكتب في
  `processing_log` داخل قاعدة المصدر فتخالف شرط عدم تعديل المصدر (سبب فشل CI الفعلي:
  `test_export_success_and_source_untouched`). التتبع الآن عبر القيمة المرجعة
  (`logged_in_source_db: False`) + توثيق استخدام ActionLog الخارجي. سجل العمليات العام وما عداه بلا تغيير.
- **F2**: تنظيف الملف المؤقت في كل المسارات بما فيها النجاح عبر `os.link` (كان الرابط المؤقت يبقى)؛
  أخطاء التنظيف تُسجَّل ولا تحجب نتيجة التصدير الأساسية؛ الوجهة المنشورة لا تُمس عند فشل التنظيف.
- **F3**: الكتابة مُستخرجة إلى `_write_deidentified_copy()` (قابلة لحقن الفشل)؛ fsync على واصف مستقل
  بعد إغلاق SQLite وقبل النشر؛ fsync مجلد جهدي — **لا تدّعية متانة بعد انقطاع الطاقة** (قيد موثق).
  ``mkstemp`` فاشل يتحول إلى ExportError.

### Fixed — rollback_batch (Findings 4، 5، 6)
- **F4**: فشل منتصف الدفعة لم يبق حالة جزئية: كل إجراء عُكس بالفعل يُعاد تطبيقه (استرداد تعويضي —
  Transactional Recovery) عبر SafeMover فقط، تُستعاد حالة ما قبل محاولة التراجع، **ولا يُحذف أي سجل**
  إلا بعد نجاح عكس الدفعة كلها.
- **F5**: دلالات غياب المستهدف — MOVE: أصل موجود + وجهة مفقودة = مكتمل مسبقاً (يُحتفظ بالسجل ويُذكر
  في `already_rolled_back`)؛ الوجهة والأصل مفقودان = أجهض fail-closed. COPY: نسخة مفقودة غير قابلة
  للتمييز عدلياً عن حذف خارجي = أجهض. لا حذف سجل عند غياب دليل كافٍ.
- **F6**: preflight لأنواع sidecar (tag/untag/set_category/delete_flag): شرط وجود الملف الأساسي؛
  حارس محتوى sidecar قيد موثق (لا checksum_after لهذه الأنواع).

### Fixed — register_file TOCTOU (Finding 7)
- تحقق ثلاثي في `_sha256_with_identity_check()`: fstat قبل القراءة، فstat بعد القراءة (استبدال/
  تغيّر حجم/محتوى)، stat المسار بعد الإغلاق (استبدال/نقل/رابط رمزي). أي فشل = لا بصمة تُخزَّن (fail-closed).

### Added — تكامل batch_id (المرحلة 4)
- `RuleEngine.execute(..., batch_id="")`: ختم موحّد في `_execute_single` يشمل كل UndoEntry المنبثقة
  عن الجلسة (بما فيها سجلات الفشل) — لم يعد الإبقاء على الحقل بلا وصول فعلي.
- `ActionLog.export_csv`: عمود batch_id؛ السجلات القديمة القيمة "" بلا تغيير معانٍ.

### Tests
- فحص الحالة الفعلية للمصدر (بايت + عدد processing_log) بدل ادعاء التوثيق.
- حقن فشل التصدير: mkstemp/كتابة/fsync/سباق نشر — تنظيف المؤقت وسلامة الوجهة والمصدر في كل حالة.
- فشل منتصف دفعة 5 إجراءات: تعويض كامل + بقاء السجلات + استرداد كامل بعد إزالة الحقن.
- دلالات MOVE/COPY المفقود + preflight sidecar + happy path للأنواع الدلالية.
- مصفوفة TOCTOU: 5 سيناريوهات + اختبار تحكم إيجابي للبصمة.
- ممنوع skip/xfail — لا تعديل اختبارات لإضعاف الحماية.