<div align="center">

# 🏗️ وثائق البنية المعمارية
## IntelliFile - تطبيق تصنيف الملفات الذكي

**Architecture Documentation**

</div>

---

## 1. 🏛️ نظرة عامة على البنية | Architecture Overview

يعتمد IntelliFile على بنية ثلاثية الطبقات (3-tier) مصممة لتحقيق الفصل بين المسؤوليات وقابلية التوسع العالية. البنية تدعم تشغيل واجهة سطح المكتب (PySide6) وواجهة الويب (Next.js) بالتوازي، مع مشاركة نفس محرك الذكاء الاصطناعي والمنطق الأساسي.

```
┌─────────────────────────────────────────────────────────────────┐
│                        طبقة العرض (UI)                        │
│  ┌──────────────────────┐    ┌──────────────────────────────┐  │
│  │   واجهة سطح المكتب   │    │       واجهة الويب          │  │
│  │   (PySide6 / Qt)     │    │  (Next.js + shadcn/ui)     │  │
│  │   src/gui/           │    │  web/src/                  │  │
│  └──────────┬───────────┘    └──────────────┬───────────────┘  │
└─────────────┼───────────────────────────────┼─────────────────┘
              │                               │
              ▼                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     طبقة المنطق الأساسي (src/core/)            │
│  ┌────────────┐ ┌──────────────┐ ┌───────────────────────────┐ │
│  │Classifier  │ │ FileHandler  │ │   AIEngine                │ │
│  └────────────┘ └──────────────┘ └───────────────────────────┘ │
│  ┌────────────┐ ┌──────────────┐ ┌───────────────────────────┐ │
│  │SemanticSrch│ │ RAGEngine    │ │   VoiceController         │ │
│  └────────────┘ └──────────────┘ └───────────────────────────┘ │
│  ┌────────────┐ ┌──────────────┐ ┌───────────────────────────┐ │
│  │FileAgent   │ │RelationMiner │ │   PredictiveOrganizer     │ │
│  └────────────┘ └──────────────┘ └───────────────────────────┘ │
└─────────────┬───────────────────────────────┬─────────────────┘
              │                               │
              ▼                               ▼
┌─────────────────────────────────────────────────────────────────┐
│               طبقة الذكاء الاصطناعي وقاعدة البيانات             │
│  ┌──────────┐ ┌──────────────┐ ┌─────────────────────────────┐ │
│  │  Ollama  │ │ sentence-    │ │      ChromaDB               │ │
│  │  (LLM)   │ │ transformers │ │    (Vector DB)              │ │
│  └──────────┘ └──────────────┘ └─────────────────────────────┘ │
│  ┌──────────┐ ┌──────────────────────────────────────────────┐ │
│  │  Magika  │ │  AIClassifier + EmbeddingEngine             │ │
│  │(Type Det)│ │  (src/ai/)                                 │ │
│  └──────────┘ └──────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 📁 هيكل المشروع الفعلي | Actual Project Structure

```
IntelliFile-app/
├── cli.py                          # نقطة دخخول CLI
├── setup.py                        # إعداد الحزمة
├── pyproject.toml                  # إعدادات البناء
├── pytest.ini                      # إعدادات الاختبارات
├── requirements.txt                # متطلبات Python
├── README.md                       # التوثيق الرئيسي
├── LICENSE                         # رخصة MIT
├── .gitignore                      # إعدادات Git
│
├── src/                            # الكود المصدري (Python)
│   ├── __init__.py
│   ├── main.py                     # نقطة الدخول الرئيسية (argparse)
│   │
│   ├── core/                       # المنطق الأساسي
│   │   ├── __init__.py             # تصدير جميع الفئات
│   │   ├── config.py               # Config dataclass + الفئات + خريطة الامتدادات
│   │   ├── classifier.py           # SmartFileClassifier (Magika + التصنيف بالامتداد)
│   │   ├── file_handler.py         # FileHandler (CRUD + تراجع + نسخ احتياطي)
│   │   ├── ai_engine.py            # AIEngine (تكامل Ollama)
│   │   ├── semantic_search.py      # SemanticSearchEngine (sentence-transformers)
│   │   ├── rag_engine.py           # RAGEngine (ChromaDB + Ollama)
│   │   ├── voice_controller.py     # VoiceController (SpeechRecognition + TTS)
│   │   ├── file_agent.py           # FileAgent (مسح دوري + كشف المكررات)
│   │   ├── multimodal_processor.py # MultimodalProcessor (صور/صوت/فيديو)
│   │   ├── relationship_miner.py   # RelationshipMiner (رسم بياني NetworkX)
│   │   ├── predictive_organizer.py # PredictiveOrganizer (تعلم أنماط المستخدم)
│   │   ├── emergent_category.py    # EmergentCategoryEngine (اكتشاف تلقائي)
│   │   ├── self_extending_assistant.py  # SelfExtendingAssistant (أدوات ديناميكية)
│   │   └── agent_cli.py            # AgentCLI (أوامر CLI)
│   │
│   ├── ai/                         # محرك الذكاء الاصطناعي
│   │   ├── __init__.py             # تصدير AIClassifier, EmbeddingEngine
│   │   ├── classifier.py           # AIClassifier (غلاف HTTP لـ Ollama)
│   │   ├── embeddings.py           # EmbeddingEngine (sentence-transformers)
│   │   └── agents/                 # وكلاء الذكاء الاصطناعي
│   │       ├── __init__.py
│   │       └── base_agent.py       # BaseAgent (فئة مجردة + قائمة مهام)
│   │
│   ├── db/                         # قاعدة البيانات
│   │   ├── __init__.py             # تصدير ChromaDBManager, FileMetadata, FileRecord
│   │   ├── schemas.py              # FileCategory, FileMetadata, FileRecord
│   │   └── chroma_db.py            # ChromaDBManager (CRUD + بحث + إحصائيات)
│   │
│   ├── gui/                        # واجهة سطح المكتب (PySide6)
│   │   ├── __init__.py
│   │   ├── main_window.py          # MainWindow (QMainWindow + ألواح)
│   │   └── components/__init__.py
│   │
│   └── utils/                      # أدوات مساعدة
│       ├── __init__.py
│       └── helpers.py              # format_size, get_file_icon, compute_file_hash
│
├── web/                            # واجهة الويب (Next.js 16)
│   ├── package.json
│   ├── next.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── postcss.config.mjs
│   ├── eslint.config.mjs
│   ├── components.json             # إعدادات shadcn/ui
│   └── src/
│       ├── app/
│       │   ├── layout.tsx          # التخطيط الرئيسي (RTL)
│       │   ├── page.tsx            # الصفحة الرئيسية (~100 سطر - تجميع المكونات)
│       │   ├── globals.css
│       │   └── api/route.ts
│       ├── components/
│       │   ├── types.ts            # أنواع TypeScript
│       │   ├── constants.tsx       # ثوابت التطبيق
│       │   ├── helpers.tsx         # دوال مساعدة
│       │   ├── Sidebar.tsx         # شريط التنقل
│       │   ├── FileManager.tsx     # مدير الملفات
│       │   ├── AICopilot.tsx       # لوحة المحادثة الذكية
│       │   ├── SearchPanel.tsx     # البحث الدلالي
│       │   ├── Dashboard.tsx       # لوحة المعلومات
│       │   ├── SettingsPanel.tsx   # الإعدادات
│       │   ├── FileActions.tsx     # قائمة السياق
│       │   ├── UploadDialog.tsx    # منطقة رفع الملفات
│       │   ├── StatsCards.tsx      # بطاقات الإحصائيات
│       │   └── ui/                 # مكونات shadcn/ui (50+ ملف)
│       ├── hooks/
│       └── lib/utils.ts
│
├── tests/                          # جناح الاختبارات
│   ├── conftest.py                 # Fixtures مشتركة
│   ├── unit/
│   │   ├── test_config.py          # 30 اختبار
│   │   ├── test_classifier.py      # 23 اختبار
│   │   ├── test_file_handler.py    # 21 اختبار
│   │   ├── test_helpers.py         # 33 اختبار
│   │   ├── test_voice_controller.py # 24 اختبار
│   │   └── test_emergent_category.py # 22 اختبار
│   └── integration/
│       ├── test_classification_pipeline.py # 7 اختبارات
│       └── test_cli.py             # 13 اختبار
│
└── docs/
    └── architecture.md             # هذا الملف
```

---

## 3. 🧩 تبعيات الوحدات | Module Dependencies

```
                    ┌──────────────┐
                    │   main.py    │
                    │  (Entry Pt.) │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
       ┌──────────┐ ┌──────────┐ ┌──────────┐
       │   gui/   │ │  core/   │ │   ai/    │
       └────┬─────┘ └────┬─────┘ └────┬─────┘
            │            │            │
            │       ┌────┴────┐       │
            │       ▼         ▼       ▼
            │  ┌─────────┐ ┌─────────────────┐
            │  │   db/   │ │   core/config   │
            │  │ChromaDB │ │   core/utils    │
            │  └─────────┘ └─────────────────┘
            │
            ▼
       ┌─────────┐
       │ PySide6 │
       │  (Qt)   │
       └─────────┘
```

---

## 4. 📊 مخطط تدفق تصنيف الملفات | Classification Flow

```
[ملف جديد] ──► [قراءة البيانات الوصفية] ──► [كشف النوع (Magika)]
                                                    │
                                                    ▼
                                             [استخراج المحتوى]
                                              ┌────┴────┐
                                              ▼         ▼
                                           [نص]      [وسائط]
                                            │           │
                                            ▼           ▼
                                     [تضمينات دلالية] [تحليل]
                                     (sentence-trans.)  (Ollama)
                                            │           │
                                            └─────┬─────┘
                                                  ▼
                                         [تصنيف + تخزين]
                                          (ChromaDB)
```

---

## 5. 💾 مخطط قاعدة البيانات | Database Schema

### ChromaDB: Collection "files"

| الحقل | النوع | الوصف |
|-------|-------|-------|
| id | String | التنسيق: "file:{sha256_hash}" |
| embedding | Float[384] | التضمين الدلالي |
| document | String | المحتوى المستخرج |
| file_name | Metadata | اسم الملف |
| file_path | Metadata | مسار الملف |
| file_size | Metadata | الحجم بالبايت |
| extension | Metadata | الامتداد |
| category | Metadata | التصنيف |
| confidence | Metadata | مستوى الثقة |
| sha256_hash | Metadata | تجزئة SHA-256 |
| classified_at | Metadata | تاريخ التصنيف |

---

## 6. 🧪 بنية الاختبارات | Test Architecture

```
tests/
├── conftest.py                 # Fixtures مشتركة + Mocks
├── unit/                       # اختبارات الوحدات (153 اختبار)
│   ├── test_config.py          # إعدادات التطبيق
│   ├── test_classifier.py      # تصنيف الملفات
│   ├── test_file_handler.py    # عمليات الملفات
│   ├── test_helpers.py         # الدوال المساعدة
│   ├── test_voice_controller.py # التحكم الصوتي
│   └── test_emergent_category.py # التصنيف الدينامي
└── integration/                # اختبارات التكامل (20 اختبار)
    ├── test_classification_pipeline.py # خط أنابيب التصنيف
    └── test_cli.py             # واجهة سطر الأوامر
```

### تشغيل الاختبارات:
```bash
# جميع الاختبارات
pytest

# اختبارات الوحدات فقط
pytest tests/unit/

# اختبارات التكامل فقط
pytest tests/integration/

# مع تغطية الكود
pytest --cov=src tests/
```

---

<div align="center">

**وثائق البنية المعمارية - IntelliFile v1.0**

آخر تحديث: 2025

</div>
