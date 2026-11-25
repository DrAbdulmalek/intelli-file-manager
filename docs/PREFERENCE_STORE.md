# Preference Store — مخزن تفضيلات التصنيف الآمن

> **الحالة:** مُنفَّذ ومختبر (19 اختبار وحدة) — جزء من مهمة
> «Preference Engine + Feedback Engine + AlphaCode Integration».

## ما هو؟

طبقة التخزين الوحيدة لقواعد تفضيلات التصنيف المكتسبة من تصحيحات
المستخدم. ملف JSON واحد (افتراضيًا `~/.intellifile/preferences.json`)
**مستقل تمامًا عن ملفات AlphaCode الشخصية** — التطبيق لا يقرأ ولا
يكتب `~/.alphacode_preferences/user_preference_profile.json`؛ أي تكامل
مستقبلي يمر عبر `src/integrations/alphacode_preference_tools.py` (Adapter).

## المخطط (schema_version = 2)

```json
{
  "schema_version": 2,
  "preferences": {"rules": [ { ...قاعدة... } ]},
  "change_log": [ {"ts", "action", "details", "before", "reverted"} ],
  "migrations_applied": [ {"from": 1, "to": 2, "at": "..."} ]
}
```

القاعدة (كل الحقول المعروفة، وأي حقول غير معروفة **تُحفظ كما هي**):

| الحقل | القيم |
|---|---|
| `status` | `provisional` → `stable` → (`disabled` ↔ `stable|provisional`)، `deleted` (منطقي) |
| `match` | `{kind: extension|mime|name_contains, value, case_insensitive}` |
| `scope` | `{kind: global|directory|file, value}` — أسبقية file > directory > global |
| `destination` | `{category}` (تصنيفات IntelliFile العربية) |
| `confidence` | `{independent_sessions, total_confirmations, score}` |
| `source` | `{origin: user_correction|alphacode|import, feedback_ids[]}` |

ويحتوي المستند نفسه اختياريًا على `category_catalog`: معرفات عشوائية من 32
محرفًا إلى أسماء فئات عرض محلية (بما فيها المخصصة). لا يُكرر Feedback JSONL
أسماء الفئات؛ يحتفظ بمعرفاتها فقط.

## ضمانات السلامة (P0)

1. **كتابة ذرّية:** ملف مؤقت في نفس المجلد + `os.replace` — لا حالة نصف مكتوبة أبدًا.
2. **قفل ملف (flock):** كل تعديل هو دورة «قراءة طازجة تحت القفل → تعديل → تحقق → كتابة» — لا فقد تحديث بين الكتّاب المتزامنين.
3. **نسخة احتياطية `.bak` + بصمة `.bak.sha256`** قبل كل كتابة تُغيّر ملفًا قائمًا.
4. **الاستعادة تتحقق من البصمة أولًا؛** نسخة تالفة → رفض + توثيق القرار في `.restore.log.jsonl` المحلي.
5. **SAFE READ-ONLY:** فشل التحميل/التحقق/الإصدار غير المعروف → لا حفظ فوق الملف الأصلي، لا إنشاء قواعد، لا تحويل الفشل إلى مستند فارغ قابل للحفظ. التصنيف التقليدي يستمر.
6. **ترحيل غير مدمِر:** v1→v2 يحفظ الأقسام والحقول غير المعروفة؛ الإصدار غير المدعوم يُرفض دون لمس الملف.
7. **سجل تغييرات** (سقف 500 إدخال) مع لقطة «قبل» لكل تعديل → `revert_last_change()` يستعيد أي فعل `rule_*` (تحديث/تأكيد/ترقية/تعطيل/حذف).

## الاستخدام

```python
from src.core.preference_store import PreferenceStore
from src.core.preference_engine import PreferenceEngine

store = PreferenceStore("~/.intellifile/preferences.json")
engine = PreferenceEngine(store)
if not engine.active:
    print(engine.status_report()["warning"])  # حالة تحذير واضحة
```

**كيفية استعادة التفضيلات:** انسخ `preferences.json.bak` فوق
`preferences.json` يدويًا، أو استدعِ `store.restore_backup()` (يتحقق من
البصمة). **كيفية تعطيل التعلم:** احذف/انقل ملف `preferences.json` أو
استخدم `disable_rule` — بلا مخزن يعمل المصنف التقليدي حرفيًا كما كان.
