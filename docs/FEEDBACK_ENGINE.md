# Feedback & Preference Engine — حلقة التعلم من تصحيحات المستخدم

> **الحالة:** مُنفَّذ ومختبر (26 + 17 اختبار وحدة + 9 تكامل مع المصنف الحقيقي).

## الدورة الموثقة (§5 من المهمة)

```
User Action → Feedback Capture → Feedback Classification →
Source Attribution → Duplicate Detection → Rule Candidate
Generation → User Review → Explicit Confirmation →
Preference Engine Update
```

## أنواع الملاحظة وماذا تفعل

| user_action | هل تُنشئ قاعدة؟ | ملاحظة |
|---|---|---|
| `accept` | تأكيد للقاعدة المسؤولة فقط | قبول بلا قاعدة = لا شيء نتعلمه |
| `reject` | **لا أبدًا** | تسجل في سجل الملاحظات فقط |
| `correct` | مرشح للمراجعة | يُطبَّق فقط بعد `confirm()` ثم `apply_confirmed()` |
| `set_destination` | مرشح للمراجعة | تغيير وجهة الملف |
| `file_exception` | مرشح بنطاق `file` | استثناء لهذا الملف فقط |
| `temp_override` | **لا أبدًا** | تصحيح مؤقت — لا قاعدة أبدية |
| `general_preference` | مرشح بنطاق `global` | تفضيل عام |

## قواعد التعلم الثابتة

1. **كل قاعدة تبدأ `provisional`.**
2. **الترقية إلى `stable` = 3 جلسات مستقلة** (جلسة مختلفة + ملف مختلف).
   التكرار على نفس الملف/الجلسة لا يرفع الاستقلالية إطلاقًا — بل يبقى
   no-op كاملًا في المحرك (لا مجموع تأكيدات ولا استقلالية).
3. **مصدر كل تصحيح مسجَّل** (`origin` + `feedback_ids[]`).
4. **التعارضات تُكشف بالاتجاهين** (نفس مفتاح المطابقة، وجهات مختلفة) وتُعرض
   مع الاقتراح — لا تُحلّ تلقائيًا؛ المستخدم يرى `conflicts` ويقرر.
5. **حسم التوازي حتمي:** نطاق (file>directory>global) ← تأكيدات مستقلة أكثر ←
   score أعلى ← `rule_id` قاموسيًا.
6. **no-op prediction:** إن كانت وجهة القاعدة تساوي تصنيف المصنف الحالي
   فلا اقتراح (اتساق applied مع suggestion).
7. **لا تطبيق تلقائي على الملفات:** `predict()` لا يستدعي SafeMover/FileHandler
   ولا ينفّذ أي عملية — الاقتراح نص للموافقة البشرية فقط.

## سجل الملاحظات (منفصل عن سجل القواعد)

- ملف JSONL مستقل (`feedback_log.jsonl`) **append-only**: السطر الأصلي لا
  يُعاد كتابته أبدًا؛ تحديثات الحالة (`review_update`) تُلحق كسطور جديدة
  والأحدث يفوز.
- كل سجل يحمل: `feedback_id`, `timestamp`, `source_session`,
  `file_fingerprint`, `original_prediction`, `user_action`,
  `corrected_value`, `source_rule_id`, `application_version`, `evidence`,
  `review_status` (`pending_review|confirmed|applied|dismissed`).
- **بصمة الملف = sha256 للمسار** لا المسار نفسه — لا مسارات ولا أسماء
  ولا محتوى تُخزَّن.
- **الأدلة بقائمة بيضاء:** `sanitize_evidence` يحتفظ بـ
  `extension/mime_type/size_bucket/is_dir` فقط؛ أي `path/name/content/text`
  يُسقط قبل الكتابة. لا يُسجل محتوى الملفات الطبية أو الشخصية أبدًا.

## التكامل مع المصنف (لا يكسر السلوك القديم)

```python
from src.core.classifier_preferences import PreferenceAwareClassifier
wrapper = PreferenceAwareClassifier(SmartFileClassifier(), store_path=...)
result = wrapper.classify_file(path)
# result["category"]      ← من المصنف القديم كما هو
# result["suggested_category"] ← من التفضيلات (أو None)
# result["preference"]["active"] ← False عند تعطل أي شيء + تحذير
```

- المحرك معطل/المخزن تالف/التنبؤ رمى استثناء → النتيجة الأساسية كما هي
  حرفيًا، تصنيف تقليدي آمن مستمر، ولا حفظ جديد.
- المصنف الأساسي (`src/core/classifier.py` و`src/ai/classifier.py`)
  **لم يُعدّل** — طبقة الغلاف فقط، لذلك التوافق الخلفي مثبت بالاختبار.
