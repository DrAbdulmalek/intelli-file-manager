# Contributing to IntelliFile Manager | المساهمة في مدير الملفات الذكي

شكراً لاهتمامك بالمساهمة في **IntelliFile Manager**! هذا الدليل يشرح كيف يمكنك المساهمة في تطوير المشروع.

Thank you for your interest in contributing to **IntelliFile Manager**! This guide explains how you can contribute to the project's development.

---

## Code of Conduct | ميثاق السلوك

### Pledge | التعهد

بالمشاركة في هذا المشروع، تتعهد بجعل التجربة خالية من التحرش لجميع المشاركين، بغض النظر عن العمر، الجنس، الهوية، التعبير الجندري، الإعاقة، المظهر الشخصي، الحجم، العرق، الأصل، أو الدين.

By participating in this project, you pledge to make the experience harassment-free for everyone, regardless of age, gender, identity, expression, disability, appearance, size, race, ethnicity, or religion.

### Standards | المعايير

**سلوكيات مرغوبة | Positive Behavior:**

- استخدام لغة ترحيبية وشاملة | Using welcoming and inclusive language
- احترام وجهات النظر المختلفة | Respecting differing viewpoints
- قبول النقد البناء | Gracefully accepting constructive criticism
- التركيز على ما هو أفضل للمجتمع | Focusing on what is best for the community
- إظهار التعاطف تجاه أعضاء المجتمع | Showing empathy towards community members

**سلوكيات غير مقبولة | Unacceptable Behavior:**

- استخدام لغة أو صور جنسية | Using sexualized language or imagery
- التحرش أو الإهانة | Trolling, insulting, or derogatory comments
- مضايقات عامة أو خاصة | Public or private harassment
- نشر معلومات خاصة بدون إذن | Publishing others' private information
- أي سلوك غير مهني | Any unprofessional conduct

### Enforcement | الإنفاذ

يمكن الإبلاغ عن السلوك غير المقبول عبر [فتح issue](https://github.com/DrAbdulmalek/IntelliFile-app/issues) أو التواصل مباشرة مع المشرفين.

---

## How to Contribute | كيف تساهم

### 1. Fork and Clone | استنساخ المستودع

```bash
# 1. Fork المستودع على GitHub
# 2. استنساخ نسختك
git clone https://github.com/YOUR_USERNAME/IntelliFile-app.git
cd intelli-file-manager

# 3. إضافة المستودع الأصلي كـ upstream
git remote add upstream https://github.com/DrAbdulmalek/IntelliFile-app.git
```

### 2. Create a Branch | إنشاء فرع جديد

```bash
# تحديث الفرع الرئيسي
git checkout main
git pull upstream main

# إنشاء فرع جديد
git checkout -b feature/اسم-الميزة
# أو
git checkout -b fix/وصف-الإصلاح
# أو
git checkout -b docs/وصف-التوثيق
```

**قواعد تسمية الفروع | Branch Naming Convention:**

| النوع | الصيغة | مثال |
|-------|--------|------|
| ميزة جديدة | `feature/اسم-الميزة` | `feature/dicom-viewer` |
| إصلاح خطأ | `fix/وصف-الخطأ` | `fix/search-timeout` |
| تحسين | `improve/وصف-التحسين` | `improve/ner-accuracy` |
| توثيق | `docs/وصف-التغيير` | `docs/api-reference` |
| إضافة | `plugin/اسم-الإضافة` | `plugin/radiology-classifier` |

### 3. Make Changes | تطبيق التغييرات

- اتبع معايير الكود المذكورة أدناه
- أضف اختبارات لجميع الميزات الجديدة
- حدّث التوثيق عند الحاجة
- تأكد من اجتياز جميع الاختبارات

### 4. Commit | التثبيت

```bash
git add .
git commit -m "feat: إضافة عارض DICOM طبي"
```

### 5. Push and PR | الرفع وإنشاء طلب سحب

```bash
git push origin feature/اسم-الميزة
```

ثم افتح Pull Request على GitHub مع وصف واضح للتغييرات.

---

## Development Setup | إعداد بيئة التطوير

### Prerequisites | المتطلبات

- **Python** 3.10+ (يفضل 3.11 أو 3.12)
- **Node.js** 18+ (لواجهة الويب)
- **Git** 2.30+
- **Ollama** (للاختبارات التي تتطلب AI)

### Setup Steps | خطوات الإعداد

```bash
# 1. إنشاء بيئة افتراضية
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# 2. تثبيت المتطلبات
pip install -r requirements.txt

# 3. تثبيت أدوات التطوير
pip install pytest pytest-cov flake8 bandit mypy black isort

# 4. تثبيت Ollama وتحميل النماذج (اختياري للاختبارات الكاملة)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2
ollama pull nomic-embed-text

# 5. إعداد واجهة الويب
cd web && npm install && cd ..

# 6. التحقق من الإعداد
pytest -v  # يجب أن تجتاز 241 اختبار
```

---

## Testing Requirements | متطلبات الاختبارات

### All 241 Tests Must Pass | يجب اجتياز 241 اختبار

قبل تقديم أي Pull Request، **يجب** أن تجتاز جميع الاختبارات الـ 241. لا يتم قبول أي PR يفشل في أي اختبار.

Before submitting any Pull Request, **all 241 tests must pass**. No PR will be accepted if any test fails.

### Running Tests | تشغيل الاختبارات

```bash
# جميع الاختبارات
pytest

# اختبارات الوحدات فقط
pytest tests/unit/ -v

# اختبارات التكامل فقط
pytest tests/integration/ -v

# اختبار محدد
pytest tests/unit/test_medical_ner.py -v

# مع تغطية الكود (الحد الأدنى 80%)
pytest --cov=src tests/ --cov-report=term-missing

# اختبارات سريعة فقط (بدون AI)
pytest -m "not slow" -v
```

### Writing Tests | كتابة الاختبارات

- كل ميزة جديدة يجب أن تتضمن اختبارات
- استخدم `pytest` fixtures من `tests/conftest.py`
- اختبارات الوحدات في `tests/unit/`
- اختبارات التكامل في `tests/integration/`
- استخدم `unittest.mock` للمحركات الخارجية (Ollama, ChromaDB)
- حدد علامات الاختبار: `@pytest.mark.unit` أو `@pytest.mark.integration` أو `@pytest.mark.slow`

```python
# مثال على اختبار وحدة
import pytest
from unittest.mock import MagicMock, patch

class TestMyFeature:
    @pytest.mark.unit
    def test_classify_medical_document(self):
        """اختبار تصنيف مستند طبي"""
        result = classifier.classify("تقرير أشعة صدر")
        assert result["category"] == "medical"
        assert result["confidence"] > 0.5
```

---

## Commit Message Conventions | معايير رسائل التثبيت

نتبع [Conventional Commits](https://www.conventionalcommits.org/) مع مراعاة السياق العربي:

### Format | الصيغة

```
<type>(<scope>): <description>

[optional body in Arabic or English]

[optional footer]
```

### Types | الأنواع

| Type | الوصف | مثال |
|------|-------|-------|
| `feat` | ميزة جديدة | `feat(search): إضافة البحث الهجين BM25+Semantic` |
| `fix` | إصلاح خطأ | `fix(ner): إصلاح استخراج أسماء الأدوية المركبة` |
| `docs` | توثيق فقط | `docs(api): تحديث توثيق نقاط نهاية API` |
| `style` | تنسيق بدون تغيير كود | `style(core): تنسيق imports حسب isort` |
| `refactor` | إعادة هيكلة | `refactor(tagger): فصل منطق الوسوم التلقائية` |
| `test` | إضافة/تحديث اختبارات | `test(hybrid_search): إضافة اختبارات RRF fusion` |
| `chore` | مهام صيانة | `chore(deps): تحديث متطلبات Python` |
| `perf` | تحسين أداء | `perf(embeddings): تخزين مؤقت للمتجهات` |
| `i18n` | ترجمة ودعم لغات | `i18n(ar): إضافة مصطلحات طبية عربية جديدة` |
| `plugin` | إضافة أو تحديث إضافة | `plugin(medical): إضافة مصنف التخصصات الطبية` |

### Arabic Context | السياق العربي

- يمكن كتابة الوصف بالعربية أو الإنجليزية
- عند كتابة الوصف بالعربية، ابدأ بالفعل: `إضافة`، `إصلاح`، `تحديث`
- أسماء الملفات والمسارات بالإنجليزية دائماً
- أمثلة:

```
feat(ner): إضافة استخراج الكيانات الطبية العربية
fix(copilot): إصلاح بث WebSocket للمحادثات الطويلة
docs(readme): إضافة حالات الاستخدام الطبي العربي
i18n(ar): إضافة دعم RTL للوحة البحث
plugin(medical): إضافة مصنف التخصصات الطبية
```

---

## Pull Request Template | قالب طلب السحب

عند إنشاء Pull Request، يرجى ملء القالب التالي:

```markdown
## الوصف | Description

[وصف واضح ومختصر للتغييرات]

## نوع التغيير | Type of Change

- [ ] feat: ميزة جديدة
- [ ] fix: إصلاح خطأ
- [ ] docs: توثيق
- [ ] refactor: إعادة هيكلة
- [ ] test: اختبارات
- [ ] chore: صيانة
- [ ] i18n: ترجمة
- [ ] plugin: إضافة

## الاختبارات | Tests

- [ ] جميع اختبارات الـ 241 تجتاز
- [ ] تمت إضافة اختبارات جديدة للتغييرات
- [ ] تغطية الكود لا تقل عن 80%

## التوثيق | Documentation

- [ ] تم تحديث README.md عند الحاجة
- [ ] تم إضافة docstrings للدوال/الفئات الجديدة
- [ ] تم تحديث API docs عند إضافة/تغيير endpoints

## دعم العربية | Arabic Support

- [ ] التغييرات تدعم النص العربي
- [ ] واجهة المستخدم تدعم RTL
- [ ] تم اختبار المدخلات العربية

## لقطات شاشة | Screenshots

[أضف لقطات شاشة للتغييرات المرئية إن أمكن]
```

---

## Arabic RTL Coding Guidelines | إرشادات البرمجة العربية RTL

### General Principles | مبادئ عامة

1. **الترميز**: جميع الملفات يجب أن تستخدم ترميز UTF-8
2. **اتجاه النص**: استخدم `dir="rtl"` و `dir="ltr"` بشكل صريح عند الحاجة
3. **محاذاة**: لا تعتمد على المحاذاة لتحديد اتجاه النص
4. **اختبار ثنائي الاتجاه**: اختبر دائماً مع نص عربي وإنجليزي مختلط

### Python Guidelines | إرشادات Python

```python
# ✅ صحيح — دعم النص العربي في docstrings
def classify_medical(text: str) -> dict:
    """تصنيف النص الطبي | Classify medical text.
    
    يدعم النصوص العربية والإنجليزية.
    Supports Arabic and English text.
    
    Args:
        text: النص المراد تصنيفه | Text to classify
    
    Returns:
        dict: نتيجة التصنيف | Classification result
    """
    pass

# ✅ صحيح — استخدام Unicode بشكل صريح
ARABIC_MEDICAL_TERMS = {
    "تشخيص": "diagnosis",
    "علاج": "treatment",
    "دواء": "medication",
}

# ❌ خطأ — الاعتماد على اتجاه النص الضمني
# لا تفترض أن النص العربي دائماً RTL في معالجة البيانات
```

### React/TypeScript Guidelines | إرشادات React/TypeScript

```tsx
// ✅ صحيح — دعم RTL صريح
<div dir="rtl" className="text-right">
  <p>{arabicText}</p>
</div>

// ✅ صحيح — استخدام CSS logical properties
<div className="ms-4 pe-2">  {/* بدلاً من ml-4 pr-2 */}
  <p>{text}</p>
</div>

// ✅ صحيح — كشف اتجاه النص تلقائياً
function getTextDirection(text: string): "rtl" | "ltr" {
  const arabicPattern = /[\u0600-\u06FF]/;
  return arabicPattern.test(text) ? "rtl" : "ltr";
}

// ❌ خطأ — استخدام left/right مع النص العربي
<div className="text-left">  {/* سيبدو خطأ مع العربية */}
  <p>{arabicText}</p>
</div>
```

### API Guidelines | إرشادات API

```python
# ✅ صحيح — دعم العربية في استجابات API
@_app.post("/api/search")
async def search(req: SearchRequest):
    results = search_eng.search(req.query, top_k=req.top_k)
    return {
        "query": req.query,
        "results": results,
        "total": len(results),
        "direction": "rtl" if any("\u0600" <= c <= "\u06FF" for c in req.query) else "ltr"
    }

# ✅ صحيح — رسائل خطأ ثنائية اللغة
raise HTTPException(400, f"المسار غير موجود: {req.path} | Path not found: {req.path}")
```

### Testing Arabic Content | اختبار المحتوى العربي

```python
# ✅ صحيح — اختبار مع نص عربي
def test_arabic_medical_ner():
    text = "المريض أحمد محمد، تشخيص: التهاب رئوي حاد"
    result = ner.extract(text)
    assert result.patient_name == "أحمد محمد"
    assert "التهاب رئوي حاد" in result.diagnosis

# ✅ صحيح — اختبار النص المختلط
def test_mixed_language_search():
    results = engine.search("تقرير MRI للدماغ")
    assert len(results) > 0  # يجب أن يجد نتائج بالعربية والإنجليزية
```

---

## Code Style | معايير الكود

### Python

- **PEP 8** مع حد أقصى 120 حرفاً لكل سطر
- **Type hints** لجميع الدوال العامة
- **Docstrings** ثنائية اللغة (عربي + إنجليزي) للدوال العامة
- **Imports**: مرتبة حسب `isort` (stdlib → third-party → local)
- **Formatting**: `black` للتنسيق التلقائي

```bash
# فحص وتنسيق الكود
flake8 src/ --max-line-length=120
black src/ --line-length=120
isort src/
mypy src/ --ignore-missing-imports
```

### TypeScript

- اتبع إعدادات ESLint في `web/eslint.config.mjs`
- استخدم TypeScript strict mode
- أضف أنواع لجميع props و state

```bash
cd web
npx eslint src/
npx tsc --noEmit
```

---

## Questions? | أسئلة?

- افتح [Discussion](https://github.com/DrAbdulmalek/IntelliFile-app/discussions) للأسئلة العامة
- افتح [Issue](https://github.com/DrAbdulmalek/IntelliFile-app/issues) للأخطاء والميزات
- راجع [ROADMAP.md](docs/ROADMAP.md) لخطة التطوير

---

<div align="center">

**شكراً لمساهمتك في تطوير IntelliFile Manager!**
**Thank you for contributing to IntelliFile Manager!**

</div>
