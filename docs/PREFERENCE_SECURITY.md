# Security Documentation — تعلم التفضيلات والملاحظات

> مراجعة أمنية لميزات المهمة: PreferenceStore / PreferenceEngine /
> FeedbackEngine / AlphaCode Adapter / لوحة الواجهة.

## نموذج التهديد وأساسيات

| التهديد | الحاجز | الاختبار المثبت |
|---|---|---|
| كتابة فوق تفضيلات من عملية فاشلة | كتابة ذرّية tmp+os.replace | `test_atomic_replacement_no_tmp_leftovers` |
| تلف البيانات بين كتّاب متزامنين | flock + قراءة طازجة تحت القفل | `test_concurrent_writes_all_survive` |
| حفظ فوق ملف تالف | SAFE READ-ONLY (رفض الحفظ والقواعد الجديدة) | `test_corrupted_json_enters_safe_read_only` |
| فقد أقسام/حقول غير معروفة عند الترحيل | ترحيل محافظ + إثبات الحفظ | `test_v1_migration_preserves_rules_and_unknown_sections` |
| استعادة نسخة احتياطية تالفة | تحقق sha256 + رفض موثَّق | `test_corrupted_backup_is_refused_and_decision_logged` |
| تعلم من رفض/تصحيح مؤقت | reject/temp_override لا ينشئان قاعدة | `test_reject_never_creates_rule` |
| رفع الثقة بتكرار غير مستقل | استقلالية = (جلسة، ملف) مختلفان؛ التكرار no-op | `test_duplicate_does_not_raise_independence` |
| نقل ملف تلقائي من التعلم | المحرك بلا استيراد SafeMover/FileHandler/subprocess + اختبارات بلا آثار ملفات | `test_no_automatic_file_operations`, `test_no_file_operation_side_effects` |
| تنفيذ أوامر من الـAdapter | فحص AST: لا subprocess/system/popen | `test_no_shell_execution_in_tools_or_server` |
| عميل غير موثق على الـAdapter | بوابة تهيئة MCP قبل أي أداة | `test_tools_rejected_before_initialize` |
| تسريب مسارات/أسماء/محتوى | تجزئة المسار + قائمة بيضاء للأدلة + سجل عمليات بلا payload | `test_sensitive_evidence_keys_stripped`, `test_ops_log_strips_payloads`, `test_raw_file_path_never_stored_verbatim` |
| تسريب بيانات طبية/شخصية | لا قراءة محتوى في أي مكون جديد؛ الحاجز الحساسي الموجود (`sensitive_barrier`) لم يُمس | الحزمة الكاملة تمر بنفس نتائج baseline |

## خصوصية البيانات

- المخزن وسجل الملاحظات **محليان 100%** (`~/.intellifile/`) — لا أي طلب
  شبكة في الكود الجديد (لا cloud fallback).
- ما يُخزَّن عن ملف: بصمة sha256 للمسار، الامتداد، نوع MIME، حِزمة الحجم
  (size bucket). لا يُخزَّن: المسار الخام، اسم الملف، المحتوى، أي نص مستخرج.
- بيانات المريض/الملفات الطبية: لا يفتحها أي مكون جديد إطلاقًا — التصنيف
  الحساسي يمر عبر `sensitive_barrier` القائم كما كان (بقي ساريًا).

## ما الذي يحتاج موافقة المستخدم؟

1. أي **نقل فعلي لملف** — عبر مسار الموافقة الحالي الموثق فقط
   (RuleEngine dry-run → execute / FileHandler عبر SafeMover)؛ الاقتراح
   لا ينفّذ شيئًا.
2. **تطبيق مرشح تعلم** — `apply_confirmed` لا يعمل إلا بعد مراجعة
   وتأكيد صريح (`confirm()` أو `user_confirmed=true` من الإنسان).
3. **حذف قاعدة** — حذف منطقي + حوار تأكيد في الواجهة، قابل للتراجع.

## التراجع والاستعادة

- تراجع عن آخر تعلم: `revert_last_update()` / زر اللوحة — من لقطة change_log.
- استعادة تفضيلات تالفة: `restore_backup()` (تحقق بصمة) أو استبدال يدوي
  بـ`preferences.json.bak`.
- تعطيل التعلم كليًا: نقل/حذف ملف `preferences.json` — التصنيف التقليدي
  يستمر كما كان (مثبت بالاختبارات).

## حدود معلومة (لا ادعاء)

- استهداف الروابط الرمزية للقواعد (`verify` لا يقارن أهداف الروابط) —
  لا علاقة له بالمكونات الجديدة (تخص tree_manifest) وموثق كاقتراح لاحق.
- لا تشفير-at-rest لمخزن التفضيلات (بياناته غير حساسة بطبيعتها: امتدادات
  ووجهات، بلا مسارات ولا محتوى) — أي تغيير مستقبلي يمر بمراجعة مستقلة.
