# قاعدة البيانات الطبية المحلية — دليل العيادة

**قرار المالك (2026-11-22):** التعامل مع بيانات العيادة الخاصة ومعالجتها محلياً مسموح. النشر العام لاحقاً سيتم بعد إزالة بيانات المرضى الشخصية — والتصميم هنا يخدم المسارَين من اليوم الأول.

## 1. الوضع المحلي في الحاجز الأمني (`INTELLIFILE_MEDICAL_MODE`)

الحاجز الأمني (`src/core/sensitive_barrier.py`) يفصل الآن بين نوعين من المحتوى المحمي:

| الفئة | أمثلة | وضع strict (الافتراضي) | وضع local (وضع العيادة) |
|---|---|---|---|
| **أسرار واعتماديات** | `.env`، `id_rsa`، `credentials.json`، `.ssh/`، `.aws/`، `vault.kdbx` | محجوب | **محجوب — بلا استثناء** |
| **محتوى طبي** | مجلدات `patients/` و`عيادة/` و`mri/`، امتدادات `.dcm/.nii`، دليمة DICOM | محجوب | **مفتوح للقراءة والمعالجة محلياً** |

التفعيل:

```bash
# لجلسة واحدة
INTELLIFILE_MEDICAL_MODE=local python main.py

# أو من داخل التطبيق/الاختبارات
from src.core.sensitive_barrier import set_medical_mode, medical_mode
set_medical_mode("local")   # أو "strict" للعودة
```

**ثوابت لا يتغيرها أي وضع:**

1. الأسرار والاعتماديات ومجلدات النظام (`.ssh`, `.aws`, `secrets/`, `keys/`...) محجوبة عن القراءة دائماً.
2. **الإرسال الخارجي محكوم بالحكم الصارم دائماً** (`external_send_allowed` يستدعي `is_sensitive_strict`): أي محتوى طبي لا يغادر الجهاز — رفعه إلى HuggingFace أو أي خدمة سحابية يحتاج خروج الملف من "وضع العيادة" صراحةً بقرار موثق.
3. `classify_sensitivity` يكشف المحتوى الطبي دائماً للعرض والتسجيل (حقل `medical_content`) ويُبلغ عن قابلية القراءة في الوضع الحالي (`readable_in_current_mode`) — الكشف للعرض لا يتأثر بالوضع، القراءة فقط هي التي تُفتح.

## 2. قاعدة البيانات (`src/core/medical_db.py`)

SQLite عبر مكتبة stdlib فقط — بلا اعتمادات جديدة، والملف يبقى محلياً.

| الجدول | الغرض | ملاحظات الخصوصية |
|---|---|---|
| `patients` | المرضى: معرّف مستعار `P-0001` + اسم/عمر/جنس/ملاحظات | كل الحقول الشخصية **اختيارية** — بلاها يبقى المريض مستعاراً خالصاً |
| `records` | السجلات: تاريخ، نوع (`imaging/lab/report/visit/prescription/other`)، مسار المصدر، بصمة SHA-256، ملخص، نتائج JSON | المسار اختياري |
| `files` | فهرس الملفات: مسار، بصمة، تصنيف الحاجز (`medical/secret/plain`)، علم القراءة | البصمة تُحسب **فقط** للملفات المسموح قراءتها في الوضع الحالي |
| `processing_log` | سجل كل عملية على القاعدة | — |

**قاعدة البصمة:** ملف سرّ أو ملف طبي في وضع strict → يُسجَّل حجمه ووقته وتصنيفه **بلا قراءة محتوى وبلا بصمة**. في وضع local، الملفات الطبية تُبصم وتُفهرس طبيعياً.

### أمثلة CLI

```bash
python scripts/clinic_db.py init --db clinic.db
python scripts/clinic_db.py add-patient --db clinic.db --name "..." --age 34 --sex m
python scripts/clinic_db.py add-record --db clinic.db --patient P-0001 --date 2026-11-22 \
    --type report --summary "تقرير أشعة صدر" --findings '{"impression":"طبيعي"}'
INTELLIFILE_MEDICAL_MODE=local python scripts/clinic_db.py register-file \
    --db clinic.db --path "/scans/patients/IMG_0001.jpg" --patient P-0001
python scripts/clinic_db.py list-records --db clinic.db --patient P-0001
python scripts/clinic_db.py search --db clinic.db --query "الصدر"
python scripts/clinic_db.py stats --db clinic.db
```

## 3. التصدير المجرّد للنشر (`export-deidentified`)

عند الرغبة في النشر العام لاحقاً:

```bash
python scripts/clinic_db.py export-deidentified --db clinic.db --out publish.db
```

النسخة الناتجة **تحذف**: الأسماء والأعمار والجنس والملاحظات من المرضى، ومسارات الملفات وبصماتها من السجلات، وجدول `files` بالكامل (المسارات قد تحمل هوية المريض). و**تبقي**: المعرّف المستعار، تاريخ السجل، نوعه، الملخص، والنتائج المنظمة — وهي ما يفيد التطوير والبحث الطبي.

## 4. المسرد الطبي (`data/medical_glossary.csv`)

الملف الآن ملتزم في المستودع (بذرة +800 زوج عربي↔إنجليزي مصطلح طبي قياسي، تشمل الأزواج التي تعتمدها اختبارات الاقتراح والتصحيح لتحرير OCR). صيغة الملف: CSV برأس `en,ar[,confidence]`، والتحميل موسع ثنائي الاتجاه عبر `GlossaryService`. التوسعة: أضف أسطراً مباشرة أو وجّه `INTELLIFILE_GLOSSARY_PATH` إلى مسرد أضخم دون تغيير الكود. الاختبارات الستة المحجورة سابقاً خرجت من الحجر بإلزام هذا الملف — انظر `tests/KNOWN_FAILURES.md`.

## 5. خلاصة الضمانات

- الأسرار: محجوبة عن القراءة والبصمة والتصدير في **كل** الأوضاع.
- المحتوى الطبي: يُقرأ ويُعالج **على هذا الجهاز فقط**؛ الإرسال الخارجي محكوم بالحكم الصارم بغضّ النظر عن الوضع.
- النشر العام: مسار جاهز (`export-deidentified`) يجرّد الهوية من الجذور، لا مجرد وعد مستقبلي.
