# تقييم مقترح DeepSeek: طبقة AlphaCode MCP + حلقة Feedback — 2026-11-20

**المصدر:** مقترح معماري من DeepSeek («لجعل AlphaCode يستخدم بروتوكولات intelli-file-manager وخوارزمياته مع دورة feedback») — ثلاثية المكونات: خادم MCP يعرّض بروتوكولات المستودع كأدوات + بروتوكول Feedback مُهيكل + ذاكرة تفضيلات محلية.

**الحكم الإجمالي:** مقترح **سليم المعمارية ومطبق** — المبدأ المحوري «قرارات الأمان خارج حلقة التعلم» (§7) يطابق عقود المستودع منذ PR #63/#66 بالضبط. نُفّذ كاملاً في `src/mcp_server/` مع **18 اختباراً دائماً** وبدون تبعيات خارجية، بعد 8 تصحيحات موثقة أدناه.

---

## 1) ما قُبل كما هو (المطابق للكود الفعلي)

| بند المقترح | التنفيذ |
|---|---|
| MCP server يعرّض بروتوكولات المستودع كأدوات | `src/mcp_server/server.py` — 8 أدوات فوق `src/core` الفعلية |
| `feedback_token` يربط الإشارة بالاستدعاء | `_meta.feedback_token` في كل أداة تغيير حالة + `store.events_for_token()` |
| ثلاث طبقات إشارات (ضمنية/صريحة/نتيجة) | `ALLOWED_SIGNALS` = negative / positive_implicit / positive_explicit / outcome |
| Frequency table + ترقية بعد 3 تكرارات | `preferences` في SQLite + `PROMOTION_THRESHOLD=3` → `kind='rule'` |
| وزن النجاح 1.5× | `SUCCESS_WEIGHT` (مستند اختبار قابليته أعلى 0.9 عند الاستخدام) |
| تقادم لمنع تراكم التفضيلات | `R = exp(-أيام/S)` ب Growth عند الاستخدام وأرضية 0.25 للقواعد الدائمة |
| Skill file يحمّل دون تضخيم prompt | `docs/alphacode-integration/SKILL.md` |
| «الأمان خارج التعلم» (§7) | حاجزان اختباريان: رفض `preferred_action='overwrite'` + الحاجز الحساسي غير المتأثر بالتفضيلات |

## 2) التصحيحات الثمانية على المقترح (قابلية التحقق بالكود)

1. **`classify_path` وُجه للوحدة الصحيحة:** المقترح نسبه إلى `path_policy` — في المستودع الفعلي `path_policy` تكرار/سرد ملفات؛ التصنيف في `sensitive_barrier.classify_sensitivity` (`is_sensitive, reason, extension, path_parts`). نُفّذ على الصحيح.
2. **حذف `overwrite` من `safe_move_file`:** مثال المقترح يمرر `overwrite: bool = False` — يناقض قسمه §7 نفسه وعقد المستودع (`OverwriteForbiddenError` محظور كلياً). الأداة لا تعرض المعامل، وأي تمرير له يُرفض صراحة برسالة توثيقية — اختبار `test_safe_move_file_rejects_overwrite_parameter_by_design`.
3. **`@mcp.hook("post_tool_call")` ليس بروتوكول MCP:** المقترح افترض Hooks API غير موجود في المواصفة. البديل المطبق: `feedback_token` + أداة `feedback_record` — الوكيل يسجل الإشارة بعد رد فعل المستخدم؛ يعمل مع أي عميل MCP دون امتدادات.
4. **بلا تبعيات خارجية:** المقترح افترض حزمة `mcp` (FastMCP). تنفيذ stdio JSON-RPC يدوي (`python -m src.mcp_server`) يعمل في CI وشجرة PR بلا شبكة — المواصفة المستخدمة: `initialize` → `tools/list` → `tools/call`، بروتوكول `2025-06-18`.
5. **FSRS-6 مبسّط بصدق:** المقترح سمّى «FSRS-6» — نُفّذ نموذج تقادم FSRS-مستوحى (`R = exp(-t/S)`، نمو S عند الاستخدام، أرضية للقواعد) موثق في `feedback.py` كـ«استبدال لاحق بمعاملات FSRS-6 الكاملة ممكن». لا ادعاء بتطبيق FSRS-6 الكامل بمعاملاته الـ21.
6. **أداة التراجع فوق المسار المُصلح:** `undo_last` تستخدم `UndoLog.rollback_last` (مسار SafeMover المُصلح في التزامات ما بعد `fe9e643` — لاحقة لا استبدال) لا `FileHandler.undo_last_action` (تاريخ في الذاكرة فقط).
7. **عهد الامتداد بلا نقطة:** `evaluate_rule` يبني `FileMetadata(extension=".jpg")` فلا تطابق قواعد المستودع — العهد الفعلي بلا نقطة (`file_inventory.py:249` — `ext.lstrip(".")`). مُطبق ومختبر.
8. **تصنيف شدة التصحيحات (DB/DBN/DBNM/DBYC):** أبقيناه مبسطاً — الشدة تُسجل في حقل `note` النصي، والترقية تُبنى على عدد التكرارات. لا نبتكر تاكسونومي شديد التفصيل قبل أن يثبت حاجته في الاستخدام الفعلي.

## 3) خريطة الأدوات الثماني (الواجهات الحقيقية المستخدمة)

| الأداة | التغليف فوق | ملاحظات |
|---|---|---|
| `classify_path` | `sensitive_barrier.classify_sensitivity` | قراءة أسماء/امتدادات فقط — لا محتوى |
| `safe_move_file` | `block_if_sensitive(src)` + `SafeMover.move` | حاجز الحساسية على المصدر قبل أي فعل؛ الوجهة لا تُحجب (النقل إلى موضع محمي وقائي) |
| `safe_copy_file` | `block_if_sensitive(src)` + `SafeMover.copy` | التضارب لاحقة عبر `_resolve_collision` |
| `evaluate_rule` | `Ruleset.from_yaml/from_dict` + `RuleEngine.dry_run` | محاكاة بلا تعديل؛ inline أو YAML |
| `undo_last` | `UndoLog(log_path).rollback_last` | عبر SafeMover — فشل صريح، لا استبدال |
| `query_action_log` | `ActionLog.list_entries(action_type, rule_name, success, limit)` | تصفية كاملة |
| `feedback_record` | `FeedbackStore.record` | يرفض الإشارات الممنوعة و`overwrite` |
| `preference_query` | `FeedbackStore.query(context)` | متقادة بـR، المهملة (<0.05) لا تُحقن |

## 4) إثبات التشغيل

```bash
python -m pytest tests/unit/test_mcp_feedback.py -v    # 18 ناجحاً
python -m pytest tests/unit -q                          # 327 passed, 1 skipped, 5 failed (glossary baseline), 333 collected
echo '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{}}' | python -m src.mcp_server
```

اختبار `test_stdio_end_to_end_initialize_and_list` يشغّل الخادم فعلياً كعملية فرعية ويتفاوض البروتوكول عبر stdin/stdout.

**إعادة تحقق طازجة (2026-11-20، بعد إغلاقات الجولة 12):** 18/18 ما زالت ناجحة، والطقم على هذا الفرع **336 passed, 1 skipped, 5 failed (glossary), 342 collected** (+9 اختبارات الجولة 12: no-op وحاجز hybrid)، والحواف الموثقة في §5 أعيد اختبارها فعلياً — `copy` على نفسه يفشل صراحة برسالة السباق بلا أي فقد ولا لاحقة، كما هو موثق.

## 5) حواف معروفة (موثقة لا مخفاة)

- **نسخ ملف على نفسه** (`src.resolve() == dst.resolve()`): يفشل صراحةً الآن بـ«الوجهة موجودة (سباق...)» — قبل إغلاقات الجولة 7 كان `os.replace` يستبدل نفسه بصمت. لا-op متعمد مثل `move()` ممكن لاحقاً إن طلبه الاستخدام.
- **التفضيلات تحسّن الاختيار فقط:** لا شيء في `src/mcp_server/` يستطيع تعطيل `block_if_sensitive` أو قبول overwrite — وحدات الأمان تسبق أي حقن تفضيل، والاختبارات تثبت ذلك (`test_safe_move_file_blocks_sensitive_source_before_any_action`).

## 6) خطوات ما بعد الدمج (من مقترح DeepSeek §9، معدلة على الواقع)

1. تسجيل الخادم في عميل الوكيل (انظر `MCP_SETUP.md`) مع `IFM_PREFERENCE_DB` على مسار المستخدم.
2. جولة استخدام حقيقية: 20 جلسة نقل/تصنيف/تراجع، قياس عدد التصحيحات قبل/بعد.
3. عند الحاجة: ترقية نموذج التقادم إلى FSRS-6 الكامل، وإضافة أدوات بحث (hybrid_search/semantic_search) بحاجزها الحساسي الجاهز. *(ملاحظة الجولة 12: متطلب الحاجز اكتمل — `hybrid_search._extract_text` أُغلق ثغرة انعدام حاجزه وأضيف `patients`/`المرضى` إلى الثوابت باختبارات `test_hybrid_search_barrier.py` — أدوات البحث فوق الطبقتين أصبحت آمنة للفهرسة متى طلبها الاستخدام.)*
