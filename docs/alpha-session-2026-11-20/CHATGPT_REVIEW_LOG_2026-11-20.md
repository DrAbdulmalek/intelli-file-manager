# سجل مراجعة للمُراجع الخارجي (ChatGPT) — جلسة 2026-11-20

**الغرض:** يشرح هذا الملف لمراجع AI خارجي ما عُدّل في هذا المستودع يوم 2026-11-20، ومن أي مصدر، وما هي التعديلات التي تحتاج تدقيقاً مستقلاً قبل الدمج. كل رقم وSHA وأمر أدناه قابل لإعادة التشغيل على الفرع الحالي.

---

## 1) سياق الجلسة باختصار

1. عمل وكيل محلي (AlphaCode) على إصلاح عيوب P0 المكتشفة في المراجعة المستقلة (PR #64 يوثقها) داخل مستودع محلي — **دون رفع أي شيء إلى GitHub**.
2. جاء العمل إلى GitHub عبر ملفين مرفوعين: لقطة شجرة العمل (`Archive.zip` بلا `.git`) ثم **التاريخ الحقيقي** (`.git.zip` — فُحص بـ `git fsck` وسليم).
3. تحقق مستقل (Z.ai) أعاد إنتاج كل ادعاء بالتجربة، وجد ثغرات، أصلحها، ثم رفع الفرعين وفتح PRين متراكبين.
4. **سلسلة مراجعة DeepSeek الخارجية** (11 جولة موثقة): حكمها الحاسم الأول بُني على فروع محلية ستالة وسُحب رسمياً؛ ثم وصلت إلى **مراجعة كود فعلية** وجدت 3 عيوب حقيقية في `safe_mover.py` و3 مسارات متبقية في `undo_log.py` — كلها أُصلحت أو أُغلقت بقرار موثق (استثناء معتمد بحارس checksum). التفاصيل والأدلة في `DEEPSEEK_REVIEW_2026-11-20.md`.

## 2) خرائط الالتزامات — تاريخ AlphaCode الأصلي مقابل المرفوع

| التزام AlphaCode الأصلي (محلي) | التزام مكافئ على GitHub | المحتوى |
|---|---|---|
| — | `a8e6dd6` (main) | الأصل المشترك |
| `c29ab5a` (فرع path_policy المحلي) | **`c29ab5a` نفسه — مرفوع كما هو دون تعديل** | تحصين `path_policy` + إغلاق مسارات الالتفاف في `file_handler`/`rule_engine` |
| `2a50a95` | `f1c7f10` (إعادة تطبيق فوق `c29ab5a`) | SafeMover + حاجز الحساسية + تكامل ocr/inventory/classifier |
| `be77e5f` | `e727f4c` (إعادة تطبيق + **حل تعارض في `file_handler.py`**) | إصلاحات F1–F8 + التراجع الآمن |
| — | `9884a7b` (Z.ai) | إصلاحات ما بعد التحقق — انظر القسم 4 |
| — | `53e35eb` (Z.ai) | وثائق الجلسة في هذا المجلد |
| — | `aa17316` ثم `fe9e643` (Z.ai) | هذا السجل + برومبت التسليم + حالة المستودع + سكربت عيوب P0 التاريخي |
| — | ما بعد `fe9e643` (Z.ai) | إصلاح `undo_log.py` (جولة DeepSeek) + اختباراته + وثيقة `DEEPSEEK_REVIEW` |
| — | ما بعد `6d4eee8` (Z.ai) | إغلاقات الجولات 5-11: عيوب `safe_mover` الثلاثة + استثناء `_rollback_copy` الموثق بحارس checksum + لاحقة sidecar + 9 اختبارات — انظر `git log --oneline -3` للـSHAs |

**سبب الخلط الممكن:** وثائق الجلسة القديمة (`SESSION_HANDOVER_F1_F8_FIX_2026-11-20.md` في هذا المجلد) تستشهد بـSHAs المحلية (`2a50a95`, `be77e5f`) التي لم تعد موجودة على GitHub بعد إعادة الأرساء فوق `c29ab5a`. استخدم دائماً خرائط الجدول أعلاه. **وكذلك الفروع المحلية قد تكون على التزام قديم منفصل عن البعيد** — تحقق بـ`git rev-parse <branch> origin/<branch>` قبل أي فحص، والمرجع الوحيد هو `origin/<branch>` أو الـSHA (درس جولة DeepSeek: grep على شجرة محلية قديمة ولّد «انحداراً» وهمياً كاد يمنع الدمج).

## 3) الفروع والـPRs الحالية

| العنصر | الحالة |
|---|---|
| PR #65: `fix/p0-path-policy-bypass-only` → `main` | مفتوح، CI أخضر 4/4 (backend 3.10/3.11, frontend, test) |
| PR #66: `fix/p0-safe-mover-and-barrier` → `fix/p0-path-policy-bypass-only` | مفتوح، متراكب على #65، `mergeable_state: clean` |
| PR #63 (`feat/p0-safety-hardening`) | يُغلق بعد دمج #65/#66 — محتواه قُسم وأُعيد بناؤه فيهما |
| PR #62 و#64 | بلا تغيير (وثائق مراجعة) |

**وثائق إضافية في هذا المجلد:** `ALPHACODE_HANDOFF_PROMPT_2026-11-20.md` (برومبت التسليم الأصلي الذي نُفّذ على AlphaCode)، `intellifile_repo_state_2026-11-20.md` (ملخص حالة المستودع بعد الرفع)، و`DEEPSEEK_REVIEW_2026-11-20.md` (السلسلة الكاملة لجولات DeepSeek الـ11 وأدلة التحقق منها — سجل تاريخي، المرجع هو هذا القسم 5). سكربت إعادة إنتاج عيوب P0 الأصلية (إثباتات المراجعة المستقلة على شجرة PR #63) متاح في `scripts/verify_claude_findings.py` — وثيقة تاريخية تعمل ضد الشجرة القبل-الإصلاح فقط؛ التحقق على الشجرة الحالية بأوامر pytest أعلاه.

## 4) التعديلات فوق عمل AlphaCode — **هذا هو محور المراجعة**

الخمسة الأولى في التزام `9884a7b`، والسادس من جولة DeepSeek (التزامات ما بعد `fe9e643`)، والسابع والثامن من مراجعة كود DeepSeek للجولات 7 و11 (ما بعد `6d4eee8`):

**قاعدة وقائية (طلب DeepSeek في جولتها 8):** كل ادعاء إصلاح في هذا السجل يجب أن يُقابَل بـ`git show origin/<branch>:<path>` قبل الاعتماد عليه — الادعاء في الوثيقة وحده لا يكفي، والمرجع الستالة بلا `fetch` حديث ولّد «حكمين حاسمين» خاطئين في جولتَي 2 و8.

1. **فجوة في F1 — حاجز الحساسية:** `rag_engine.py` و`semantic_search.py` كانا يقرآن المحتوى دون حاجز رغم أن المراجعة المستقلة سمّتهما بالاسم. أُضيف `is_sensitive_path` كحارس أول في `_extract_text` لكليهما بنفس نمط AlphaCode في `ocr_service.py`.
2. **انحدار idempotent:** نقل ملف إلى نفس مساره كان يفشل برسالة «الوجهة موجودة بالفعل» مع الحارس الجديد ضد التضارب — الاختبار (`test_move_idempotent_to_same_path`, `test_move_to_same_path_idempotent`) ناجح على main. أُضيف حارس no-op في `safe_mover.move` بعد فحص وجود المصدر (يقارن `src.resolve() == dst.resolve()`).
3. **NameError كامن:** مسار undo للحذف النهائي في نسخة be77e5f يستدعي `shutil.copy2` دون أن يستورد الملف `shutil` — استُبدل بـ `self.safe_mover.move` (بوابة واحدة، بلا مسارات تخطي).
4. **حل تعارض الفرعين في `file_handler.py`** (التزام `e727f4c`): بُني على نسخة `c29ab5a` (الإغلاق الكامل عبر `self.safe_mover` + رفض الحذف النهائي دائماً) ودمج فيها إصلاح التراجع من be77e5f — صار التراجع كله عبر SafeMover: «اللاحقة لا الاستبدال»، وdelete_permanent استُعيد بلائقة أيضاً.
5. **مواءمة اختبارَي P1/P5** في `tests/unit/test_f1_f8_inversion.py`: كانا يفشلان فعلياً رغم ادعاء handover «12/12 ناجح» — توقعا «رفض النقل» بينما handover نفسه والمشروع كله يستخدمان دلالة «التضارب يأخذ لاحقة (_1) لا استبدالاً». **هذا قرار حكم قابل للتحدي** — إن كان مراجعك يرى أن الرفض أصرم، فالنقاش مطلوب قبل الدمج (لكن حظر `overwrite=True` كلياً يبقى ثابتاً في الحالتين عبر `OverwriteForbiddenError`).
6. **إغلاق مسار `_rollback_move`؛ `_rollback_copy` استثناء معتمد؛ دمج sidecar باللاحقة — `undo_log.py`** (جولتا DeepSeek 2 و11 — العنوان صُحح بصياغتها بعد أن كان «إغلاق آخر مسار تراجع مباشر»): `_rollback_move` كان يستخدم `shutil.move` مباشرة (استبدال صامت — صنف عيب U نفسه، ومسار قابل للوصول من واجهة سطح المكتب). صار التراجع عبر `SafeMover` (لاحقة لا استبدال، فشل صريح بـ`RuntimeError`)، حُذف `import shutil`، واختبارات دائمة في `tests/unit/test_undo_log_rollback.py` (3 اختبارات). المساران المتبقيان حُكما عليهما صراحة في الجولة 11: `_rollback_copy` يحذف النسخة المنشأة مباشرة — **استثناء معتمد موثق** في docstring الدالة (النسخة أُنشئت بهذه العملية نفسها؛ لا بيانات سابقة تُمس) مع **حارس checksum** يرفض الحذف إن عُدّل الملف بعد نسخه (حقل `checksum_after` جديد في `UndoEntry` تُعبئه `_exec_copy`)؛ ودمج sidecar في `_rollback_move` كان يحذف sidecar الشاغل صامتاً (`dst_sidecar.unlink()`) — حُذف الفرع كلياً وSafeMover يتضارب باللاحقة. ملاحظة: ملاحظة DeepSeek على `rule_engine.py` لم تصمد — أسطره المزعومة تعليقات توثيقية فقط عند الطرف؛ المسارات القديمة أغلقها `c29ab5a`.
7. **إغلاقات كود `safe_mover.py` من مراجعة DeepSeek للجولة 7** (3 عيوب وجدتها قراءة الكود نفسه، كلها أُصلحت باختبارات دائمة في `tests/unit/test_safe_mover_p0_closures.py` — 9 اختبارات):
   - **ابتلاع `IsADirectoryError`:** `try: if dst.is_dir(): raise IsADirectoryError(...) except OSError: pass` في `_atomic_move` و`_atomic_copy` — الخطأ الصريح كان يُلتقط فوراً لأنه صنف فرعي من `OSError`. الفحص داخل try فقط لفشل `is_dir()` نفسه، والـraise خارجها.
   - **فجوة TOCTOU:** `os.replace(tmp, dst)` في فرع EXDEV و`_atomic_copy` يستبدل صامتاً إن ظهرت الوجهة بين الفحص والكتابة. صار `os.link(tmp, dst)` (يرفض ذرياً بـ`FileExistsError`) مع fallback موثق بتحذير للأنظمة بلا hardlink.
   - **فشل `src.unlink()` بعد نجاح الربط/النسخ:** كان يترك «كلاهما موجود» غير موثقة — الآن يُزال أثر العملية (الرابط/النسخة — hardlink ونسخة كاملة = صفر فقد) ويرفع خطأ صريح.
8. **تصحيح أرقام البطاريات** (ملاحظة DeepSeek الجولة 5 التي ثبتت صحتها): بطارية عيوب P0 التاريخية هي **8/8** (A1, A2, P1–P5, U — تطابق تجارب التسليم الثمانية)، لا «10/10» كما كان مكتوباً سابقاً.

## 5) أوامر إعادة التحقق (على فرع `fix/p0-safe-mover-and-barrier`)

```bash
# الطقم الكامل — الأرقام الفعلية بصياغة صريحة بلا لبس (طلب DeepSeek، الجولة 5):
# 309 passed, 1 skipped, 5 failed (glossary), 315 collected
python -m pytest tests/unit -q

# التكامل — المتوقع في صندوق التحقق: 88 passed, 2 failed (watcher), 90 collected
python -m pytest tests/integration/test_safe_move_actionlog.py -q

# مراجعة الفروق — بادئة origin/ إلزامية (درس جولتا DeepSeek 3 و8:
# الفرع المحلي والمرجع غير المحدَّث بـfetch حديث ولّدا حكمين حاسمين خاطئين!)
git fetch origin --prune                                            # قبل كل فحص للبعيد
git diff a8e6dd6..c29ab5a                                        # PR #65 كاملاً (التزام واحد)
git diff origin/fix/p0-path-policy-bypass-only..origin/fix/p0-safe-mover-and-barrier   # PR #66

# نقاط المراجعة المهمة في safe_mover
grep -n "no-op" src/core/safe_mover.py         # حارس idempotent
grep -n "OverwriteForbiddenError" src/core/safe_mover.py   # حظر overwrite الكلي
grep -n "BaseException\|finally" src/core/safe_mover.py    # تنظيف الاستثناءات
grep -n "سباق ما بعد الفحص\|os.link" src/core/safe_mover.py  # إغلاق TOCTOU (الجولة 7)
grep -n "عُدّل الملف بعد إنشائه" src/core/undo_log.py        # حارس checksum للتراجع (الجولة 11)

# بطارية إعادة إنتاج عيوب P0 الأصلية — وثيقة تاريخية تعمل ضد شجرة PR #63
# قبل الإصلاح فقط؛ على الشجرة الحالية تخرج برسالة توجيه لأن العيوب مُصلَحة
python scripts/verify_claude_findings.py
```

**خط الأساس المرجعي (لا تُحسب إخفاقاته على هذه السلسلة) — الدائم منها 5 فقط:**
- 5 في `test_glossary_and_export.py` — مؤكدة على `origin/main` في بيئتين (صندوق التحقق وجهاز المالك، Python 3.13). **هذه وحدها خط الأساس الدائم.**
- 2 في `tests/integration/test_safe_move_actionlog.py` بالضبط: `TestWatcherActionLogIntegration::test_watcher_logs_to_action_log` و`::test_watcher_without_action_log_works` — **بيئة-معتمدة بدليل موثق (طلب DeepSeek، الجولة 5)، خارج خط الأساس الدائم**: تفشلان في صندوق التحقق (Linux kernel `5.10.134` حاوية Anolis، Python `3.12.16` — توقيت أحداث نظام الملفات) وتنجح 90/90 على جهاز المالك (Python `3.13.11`). عدد الاختبارات في الملف 90 على main وعلى الفرع سواء (`--collect-only` مؤكد — أعيد إثباته في الجولة 12) — لا تقليل تغطية. (تصحيح جولة 12: خط الأساس = 5 لا 7؛ الاثنان watcher ليسا منه)

**جدول البطاريات الموحد (تصحيح «10/10» — ملاحظة DeepSeek الصحيحة في الجولة 5):**

| البطارية | النتيجة | الموقع |
|---|---|---|
| تجارب عيوب P0 التاريخية (A1, A2, P1–P5, U) | 8/8 | `scripts/verify_claude_findings.py` على شجرة PR #63 فقط |
| اختبارات التراجع الدائمة | 3/3 | `tests/unit/test_undo_log_rollback.py` |
| اختبارات إغلاقات الجولات 7 و11 | 9/9 | `tests/unit/test_safe_mover_p0_closures.py` |

**أدلة الحواجز عند الطرف الحالي (أرقام أسطر قابلة للتشغيل):**
```
grep -n "no-op" src/core/safe_mover.py                    # 412-422 (+ حارس مكافئ 190)
grep -n "OverwriteForbiddenError" src/core/safe_mover.py  # 139/353/453 — حظر overwrite الكلي
grep -n "BaseException\|finally" src/core/safe_mover.py   # 278/311/483-498 — تنظيف استثناءات P4
grep -n "is_sensitive_path" src/core/rag_engine.py        # 278 — حاجز قبل القراءة
grep -n "is_sensitive_path" src/core/semantic_search.py   # 64 — حاجز قبل القراءة
grep -n "is_sensitive_path" src/core/ocr_service.py       # 123 — حاجز OCR (نمط AlphaCode الأصلي)
```

ملاحظة السكربت التاريخي: على الشجرة المصلحة يخرج `verify_claude_findings.py` بـ**exit=2** مع رسالة توجيه — لا تُفسر نتيجته على شجرة خاطئة كنجاح.

## 6) نقاط نُبقيت عمداً على القرار (ليست أخطاء)

1. **إعادة كتابة تاريخ main:** لوغ `wd_backup_organization.log` داخل تاريخ main (`2d502f5`) — الخطة جاهزة (`git filter-repo`) لكنها force push تتطلب موافقة المالك صراحة.
2. **وثائق العمليات محلية فقط:** كل ما يحيل إلى `/mnt/wd_backup/` (INDEX، SESSION_REPORT، ENGINEERING_FINDINGS، ملفات `wd_backup_*`) بقيت خارج git عمداً — بيانات حقيقية لا ترفع.
3. **PR #62 و#64:** وثائق مراجعة، بلا تغيير.

## 7) ماذا يُطلب من مراجعك تحديداً

1. تدقيق حل التعارض في `file_handler.py` (`e727f4c`): هل مزج إغلاق `c29ab5a` مع undo الجديد سليم؟ (لا مسارات shutil متبقية، التراجع كله عبر SafeMover)
2. الحكم على قرار دلالة P1/P5 (القسم 4-بند 5): لاحقة أم رفض؟ — ويُستحسن توثيقه في ADR/CHANGELOG كما اقترحت DeepSeek.
3. مراجعة حارس no-op: هل `src.resolve() == dst.resolve()` كافية؟ — ويُطلب إضافة اختبارات symlink/hardlink/same-inode (نقطة DeepSeek المقبولة).
4. مراجعة الحاجز في `rag_engine`/`semantic_search`: هل `is_sensitive_path` قبل القراءة كافية أم تحتاج `block_if_sensitive` الصارم؟ (نقطة DeepSeek المفتوحة)
5. تدقيق إصلاحات `undo_log.py` (القسم 4-بند 6): هل التمرير عبر SafeMover + استثناء `_rollback_copy` المعتمد بحارس checksum + لاحقة sidecar تغطي كل الحالات؟
6. مراجعة إغلاقات `safe_mover.py` الثلاثة (القسم 4-بند 7): هل fallback `os.replace` الموثق للأنظمة بلا hardlink مقبول بدل فشل كامل؟ وهل سياسة «إزالة الأثر + خطأ صريح» عند فشل unlink صائبة؟
7. تأكيد أن الإخفاقات خارج هذه السلسلة ليست انحدارات منها — **خط الأساس الدائم 5 glossary فقط**، والاثنان watcher بيئة-معتمدان بدليل موثق (صياغة مصححة في الجولة 12: لا تُجمعان مع خط الأساس).
8. القاعدة الوقائية أعلاه: كل ادعاء إصلاح يُقابَل بـ`git show origin/<branch>:<path>` — جرّبها على بنود القسم 4.

**خلاصة الجاهزية:** وحدة **309 passed, 1 skipped, 5 failed (glossary), 315 collected** ✓ (منها 3 undo + 9 إغلاقات جديدة)، تكامل 88/90 في بيئة الصندوق و90/90 على جهاز المالك (نفس الملف، بيئة-معتمد بدليل موثق)، بطاريات 8/8 و3/3 و9/9 ✓ (تصححت من «10/10»)، السلسلة 11-جولة مع DeepSeek وصلت مراجعة كود فعلية: عيوبها الثلاثة في `safe_mover` أُصلحت وبنودها الثلاثة في `undo_log` أُغلقت بقرار موثق (انظر `DEEPSEEK_REVIEW_2026-11-20.md` القسمان 8 و10)، CI أخضر على #65، فحص أمني نظيف (صفر توكنات/أسرار في الفروق) — الفرعان جاهزان للدمج بترتيب #65 ثم #66، والدمج مسؤولية المالك.
