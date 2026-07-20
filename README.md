<div align="center">

# ✨ IntelliFile Manager
## مدير الملفات الذكي — Smart File Manager

### تطبيق متقدم لإدارة وتصنيف الملفات باستخدام الذكاء الاصطناعي
### An Advanced AI-Powered File Management & Classification System

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB.svg)](https://python.org)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![Tests: 241](https://img.shields.io/badge/Tests-241-passing-brightgreen.svg)]()
[![Manjaro](https://img.shields.io/badge/OS-Manjaro_Linux-35BF5C.svg)](https://manjaro.org)

<p align="center">
  <img src="https://img.shields.io/badge/الذكاء_الاصطناعي-AI_Powered-purple" alt="AI Powered" />
  <img src="https://img.shields.io/badge/البحث_الهجين-Hybrid_Search-blue" alt="Hybrid Search" />
  <img src="https://img.shields.io/badge/العربية-RTL_Support-FF6F00" alt="Arabic RTL" />
  <img src="https://img.shields.io/badge/الخصوصية-Offline_First-red" alt="Offline First" />
  <img src="https://img.shields.io/badge/NER_طبي-Medical_NER-e91e63" alt="Medical NER" />
</p>

</div>

---

## Table of Contents

- [Description | الوصف](#description--الوصف)
- [Features | المميزات](#features--المميزات)
- [Architecture | البنية المعمارية](#architecture--البنية-المعمارية)
- [Quick Start | البدء السريع](#quick-start--البدء-السريع)
- [API Endpoints | نقاط نهاية API](#api-endpoints--نقاط-نهاية-api)
- [Arabic Medical Use Cases | حالات الاستخدام الطبي](#arabic-medical-use-cases--حالات-الاستخدام-الطبي)
- [Development Guide | دليل التطوير](#development-guide--دليل-التطوير)
- [Plugin System | نظام الإضافات](#plugin-system--نظام-الإضافات)
- [Integration with omni-medical-suite | التكامل مع المنصة الطبية](#integration-with-omni-medical-suite--التكامل-مع-المنصة-الطبية)
- [License | الترخيص](#license--الترخيص)

---

## Description | الوصف

### العربية

**IntelliFile Manager** هو نظام متقدم لإدارة وتصنيف الملفات يعمل بالذكاء الاصطناعي، مصمم خصيصاً للأنظمة القائمة على لينكس (مانجارو وأرتش). يجمع التطبيق بين محرك بحث هجين (BM25 + دلالي + RRF)، ومعالجة متعددة الوسائط، ووسوم ذكية تلقائية، ومساعد ملفات ذكي (RAG)، واستخراج كيانات طبية مسمى (NER) باللغة العربية — كل ذلك مع دعم كامل للغة العربية من اليمين لليسار وخصوصية تامة عبر المعالجة المحلية بدون اتصال بالإنترنت.

يعمل النظام كخدمة API عبر FastAPI مع واجهة ويب حديثة مبنية بـ Next.js 16 و shadcn/ui، بالإضافة إلى واجهة سطح مكتب PySide6. جميع معالجات الذكاء الاصطناعي تعمل محلياً عبر Ollama وsentence-transformers لضمان الخصوصية الكاملة.

### English

**IntelliFile Manager** is an advanced AI-powered file management and classification system designed for Linux (Manjaro/Arch). It combines a hybrid search engine (BM25 + Semantic + RRF), multimodal processing, smart auto-tagging, a RAG-based File Copilot, and Arabic Medical Named Entity Recognition — all with full Arabic RTL support and offline-first privacy through local AI processing.

The system runs as a FastAPI service with a modern Next.js 16 + shadcn/ui web interface and an optional PySide6 desktop GUI. All AI processing runs locally via Ollama and sentence-transformers for complete privacy.

---

## Features | المميزات

### 🔍 Hybrid Search | البحث الهجين

محرك بحث هجين يجمع بين خوارزمية BM25 للبحث الكلمي والبحث الدلالي عبر المتجهات (sentence-transformers)، مع دمج النتائج باستخدام خوارزمية Reciprocal Rank Fusion (RRF). يدعم البحث باللغة العربية والإنجليزية مع فهم عميق لسياق الاستعلام.

- **BM25 Keyword Search**: بحث كلمي سريع ودقيق
- **Semantic Vector Search**: بحث دلالي يفهم المعنى والسياق
- **RRF Fusion**: دمج ذكي لنتائج المحركين مع ترجيح متوازن
- **Arabic Tokenization**: دعم تجزئة النص العربي معالجة خاصة

### 🖼️ Multimodal Processing | المعالجة متعددة الوسائط

معالجة شاملة لأنواع الملفات المختلفة في خط أنابيب موحد:

- **الصور**: استخراج النصوص (OCR)، تحسين الصور الممسوحة ضوئياً، وصف المحتوى
- **الصوت**: تحويل الكلام إلى نص (STT) باللغة العربية، تحليل المحتوى الصوتي
- **الفيديو**: استخراج الإطارات، تحليل المشاهد، إنشاء ملخصات
- **المستندات**: استخراج النصوص من PDF وDOCX وXLSX، تحليل البنية

### 🏷️ Smart Tagging | الوسوم الذكية

نظام وسوم ذكي متعدد الطبقات يولد وسوماً تلقائياً بناءً على:

- **وسوم المحتوى**: استخراج الكلمات المفتاحية والمواضيع
- **وسوم النوع**: تصنيف حسب نوع الملف وامتداده
- **وسوم مخصصة**: إضافة وسوم يدوية مع تصنيفات قابلة للتخصيص
- **وسوم مجمعة**: تطبيق وسوم على مجموعة ملفات دفعة واحدة
- **بحث الوسوم**: البحث عن الملفات بواسطة الوسوم

### 🤖 File Copilot | مساعد الملفات

مساعد ذكي يعتمد على تقنية RAG (Retrieval-Augmented Generation) للمحادثة مع ملفاتك:

- **محادثة ذكية**: أسئلة وأجوبة بناءً على محتوى ملفاتك
- **تلخيص تلقائي**: إنشاء ملخصات شاملة لأي ملف
- **فهرسة ذكية**: إضافة ملفات إلى قاعدة المعرفة
- **محادثات متعددة**: إدارة عدة محادثات بالتوازي
- **بث مباشر**: دعم WebSocket للردود المتدفقة في الوقت الفعلي

### 🏥 Medical NER | استخراج الكيانات الطبية

نظام متخصص لاستخراج الكيانات المسماة من النصوص الطبية العربية:

- **أسماء المرضى**: استخراج وتحديد هويات المرضى
- **التشخيصات**: تحديد التشخيصات والأمراض المذكورة
- **الأدوية**: استخراج أسماء الأدوية وجرعاتها
- **الإجراءات**: تحديد الإجراءات الطبية والعمليات
- **تحسين LLM**: خيار لاستخدام نماذج اللغة الكبيرة لتحسين الدقة

### 🌐 RTL Support | دعم العربية

دعم كامل للغة العربية في جميع مستويات التطبيق:

- **واجهة عربية**: واجهة مستخدم كاملة من اليمين لليسار
- **بحث عربي**: معالجة خاصة للنص العربي في البحث والتصنيف
- **وسوم عربية**: إنشاء وسوم باللغة العربية
- **أوامر صوتية**: تحكم صوتي باللغة العربية

### ⚡ Offline-First | أولوية العمل بدون اتصال

جميع عمليات الذكاء الاصطناعي تعمل محلياً بدون حاجة للإنترنت:

- **Ollama LLM**: نماذج لغوية محلية (llama3.2)
- **Local Embeddings**: تضمينات محلية (nomic-embed-text / all-MiniLM-L6-v2)
- **ChromaDB**: قاعدة بيانات متجهات محلية
- **Magika**: كشف نوع الملف محلياً (100+ نوع)

### 🔒 Privacy | الخصوصية

تصميم يركز على الخصوصية:

- **لا بيانات خارجية**: لا يتم إرسال أي بيانات لخوادم خارجية
- **معالجة محلية**: جميع العمليات تتم على جهازك
- **تشفير اختياري**: دعم تشفير الملفات الحساسة
- **تحكم كامل**: أنت تتحكم في جميع بياناتك

---

## Architecture | البنية المعمارية

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Presentation Layer                          │
│  ┌───────────────────────┐    ┌──────────────────────────────────┐  │
│  │  Desktop GUI (PySide6)│    │  Web UI (Next.js 16 + shadcn)  │  │
│  │  src/gui/             │    │  web/src/                       │  │
│  └───────────┬───────────┘    └──────────────┬───────────────────┘  │
└──────────────┼───────────────────────────────┼─────────────────────┘
               │                               │
               ▼                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        API Layer (FastAPI)                           │
│                    src/api/server.py — Port 8421                     │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌────────────┐ │
│  │ Classify│ │  Search  │ │   Tags   │ │ Copilot │ │    NER     │ │
│  │ /api/   │ │ /api/    │ │ /api/    │ │ /api/   │ │ /api/ner/  │ │
│  │ classify│ │ search   │ │ tags     │ │ copilot │ │ extract    │ │
│  └────┬────┘ └────┬─────┘ └────┬─────┘ └────┬────┘ └─────┬──────┘ │
└───────┼───────────┼────────────┼─────────────┼────────────┼────────┘
        │           │            │             │            │
        ▼           ▼            ▼             ▼            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       Core Engine Layer (src/core/)                  │
│  ┌───────────────┐ ┌──────────────┐ ┌─────────────────────────────┐ │
│  │ SmartFile     │ │ HybridSearch │ │ SmartTagger                 │ │
│  │ Classifier    │ │ Engine       │ │ (auto-tag + manual)         │ │
│  └───────────────┘ └──────────────┘ └─────────────────────────────┘ │
│  ┌───────────────┐ ┌──────────────┐ ┌─────────────────────────────┐ │
│  │ FileCopilot   │ │ Enhanced     │ │ ArabicMedicalNER            │ │
│  │ (RAG Chat)    │ │ Multimodal   │ │ (Arabic Medical Entities)   │ │
│  └───────────────┘ └──────────────┘ └─────────────────────────────┘ │
│  ┌───────────────┐ ┌──────────────┐ ┌─────────────────────────────┐ │
│  │ FileHandler   │ │ AIEngine     │ │ VoiceController             │ │
│  │ (CRUD+Undo)   │ │ (Ollama)     │ │ (Arabic STT/TTS)            │ │
│  └───────────────┘ └──────────────┘ └─────────────────────────────┘ │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    AI & Data Layer                                   │
│  ┌──────────┐ ┌──────────────────┐ ┌────────────────────────────┐  │
│  │  Ollama  │ │ sentence-        │ │      ChromaDB              │  │
│  │  (LLM)   │ │ transformers     │ │    (Vector Store)          │  │
│  │ Port 11434│ │ (Embeddings)    │ │                            │  │
│  └──────────┘ └──────────────────┘ └────────────────────────────┘  │
│  ┌──────────┐ ┌──────────────────────────────────────────────────┐ │
│  │  Magika  │ │  Plugin System (src/plugins/)                   │ │
│  │(Type Det)│ │  • IntelliFilePlugin base class                 │ │
│  └──────────┘ │  • PluginManager + PluginContext                │ │
│               │  • Auto-discovery from src/plugins/ + ~/.intellifile/ │
│               └──────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Quick Start | البدء السريع

### Prerequisites | المتطلبات المسبقة

- **Python** 3.10 أو أحدث
- **Node.js** 18 أو أحدث (لواجهة الويب)
- **Ollama** (للذكاء الاصطناعي المحلي)

### Installation | التثبيت

```bash
# 1. استنساخ المستودع
git clone https://github.com/DrAbdulmalek/IntelliFile-app.git
cd intelli-file-manager

# 2. إنشاء بيئة افتراضية
python -m venv venv
source venv/bin/activate

# 3. تثبيت متطلبات Python
pip install -r requirements.txt

# 4. تثبيت Ollama وتحميل النماذج
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2
ollama pull nomic-embed-text

# 5. تثبيت واجهة الويب (اختياري)
cd web && npm install && cd ..
```

### Running the API Server | تشغيل خادم API

```bash
# تشغيل خادم API على المنفذ 8421
uvicorn src.api.server:app --host 0.0.0.0 --port 8421 --reload

# أو باستخدام main.py
python main.py --api

# التوثيق التفاعلي
# Swagger UI: http://localhost:8421/api/docs
# ReDoc:      http://localhost:8421/api/redoc
```

### Running the Web Interface | تشغيل واجهة الويب

```bash
cd web
npm run dev
# افتح http://localhost:3000 في المتصفح
```

### Running Tests | تشغيل الاختبارات

```bash
# جميع الاختبارات (241 اختبار)
pytest

# اختبارات الوحدات فقط
pytest tests/unit/ -v

# اختبارات التكامل فقط
pytest tests/integration/ -v

# مع تغطية الكود
pytest --cov=src tests/ --cov-report=html

# اختبارات محددة
pytest tests/unit/test_hybrid_search.py -v
pytest tests/unit/test_medical_ner.py -v
pytest tests/unit/test_smart_tagger.py -v
pytest tests/unit/test_file_copilot.py -v
```

### CLI Usage | واجهة سطر الأوامر

```bash
# تصنيف مجلد
python cli.py classify /path/to/folder

# بحث هجين
python cli.py search "تقارير المبيعات الربعية"

# كشف نوع الملف
python cli.py detect /path/to/file

# تشغيل وكلاء الملفات
python cli.py agent --mode auto /path/to/folder
```

---

## API Endpoints | نقاط نهاية API

يقدم خادم API **22 نقطة نهاية** تغطي جميع وظائف النظام:

| # | Method | Endpoint | الوصف | Description |
|---|--------|----------|-------|-------------|
| 1 | `GET` | `/api/health` | فحص صحة النظام ومحركاته | Health check & engine status |
| 2 | `POST` | `/api/classify` | تصنيف ملف أو مجلد | Classify file or directory |
| 3 | `POST` | `/api/search` | بحث هجين (BM25+دلالي+RRF) | Hybrid search (BM25+Semantic+RRF) |
| 4 | `POST` | `/api/search/index` | فهرسة مجلد للبحث | Index directory for search |
| 5 | `POST` | `/api/tags/auto` | وسوم تلقائية لملف | Auto-tag a file |
| 6 | `POST` | `/api/tags/add` | إضافة وسم يدوي | Add manual tag |
| 7 | `POST` | `/api/tags/batch` | وسوم مجمعة لعدة ملفات | Batch tag multiple files |
| 8 | `DELETE` | `/api/tags/remove` | حذف وسم من ملف | Remove tag from file |
| 9 | `GET` | `/api/tags/search` | بحث عن ملفات بوسم | Search files by tag |
| 10 | `GET` | `/api/tags/all` | جميع الوسوم في مجلد | Get all tags in directory |
| 11 | `POST` | `/api/copilot/chat` | محادثة مع مساعد الملفات | Chat with File Copilot |
| 12 | `POST` | `/api/copilot/index` | فهرسة ملفات للمحادثة | Index files for Copilot |
| 13 | `GET` | `/api/copilot/conversations` | قائمة المحادثات | List conversations |
| 14 | `POST` | `/api/copilot/summarize` | تلخيص ملف | Summarize a file |
| 15 | `WS` | `/api/copilot/ws` | محادثة مباشرة (WebSocket) | Streaming Copilot chat |
| 16 | `POST` | `/api/process/image` | معالجة صورة | Process image (OCR, enhance) |
| 17 | `POST` | `/api/process/audio` | معالجة ملف صوتي | Process audio (STT) |
| 18 | `POST` | `/api/process/video` | معالجة فيديو | Process video (extract) |
| 19 | `POST` | `/api/process/document` | معالجة مستند | Process document (extract) |
| 20 | `POST` | `/api/process/upload` | رفع ومعالجة ملف | Upload & process file |
| 21 | `POST` | `/api/ner/extract` | استخراج كيانات طبية | Extract medical NER entities |
| 22 | `POST` | `/api/organize` | تنظيم ملفات تلقائياً | Auto-organize files |

### API Authentication

حالياً لا يتطلب API مصادقة (يعمل محلياً على `localhost`). للنشر الإنتاجي، يُنصح بإضافة middleware مصادقة.

### Example API Calls

```bash
# فحص صحة النظام
curl http://localhost:8421/api/health

# تصنيف ملف
curl -X POST http://localhost:8421/api/classify \
  -H "Content-Type: application/json" \
  -d '{"path": "/home/user/documents", "recursive": true}'

# بحث هجين
curl -X POST http://localhost:8421/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "تقارير طبية", "top_k": 10, "engine": "hybrid"}'

# استخراج كيانات طبية
curl -X POST http://localhost:8421/api/ner/extract \
  -H "Content-Type: application/json" \
  -d '{"text": "المريض أحمد محمد، تشخيص: التهاب رئوي حاد", "use_llm": false}'

# وسوم تلقائية
curl -X POST "http://localhost:8421/api/tags/auto?filepath=/home/user/report.pdf"

# محادثة مع مساعد الملفات
curl -X POST http://localhost:8421/api/copilot/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "لخص لي تقرير المبيعات"}'
```

---

## Arabic Medical Use Cases | حالات الاستخدام الطبي

### مستندات طبية | Medical Documents

IntelliFile Manager يقدم دعماً متخصصاً لإدارة المستندات الطبية العربية. يمكن للنظام تصنيف وتنظيم التقارير الطبية تلقائياً بناءً على محتواها، واستخراج الكيانات الطبية المهمة مثل أسماء المرضى والتشخيصات والأدوية الموصوفة.

**مثال عملي**: عند إضافة مجلد يحتوي على تقارير طبية، يقوم النظام تلقائياً بـ:
1. تصنيف كل تقرير حسب التخصص الطبي (قلب، عظام، أعصاب...)
2. استخراج الكيانات المسماة (اسم المريض، التشخيص، الأدوية)
3. إنشاء وسوم ذكية (طبي/تشخيص/التهاب_رئوي)
4. فهرسة المحتوى للبحث الدلالي

```bash
# استخراج كيانات من تقرير طبي
curl -X POST http://localhost:8421/api/ner/extract \
  -d '{"text": "المريض: خالد العمري، رقم الملف: MR-2024-1234. التشخيص: ارتفاع ضغط الدم المزمن. الأدوية: أملوديبين 5ملغ، لوسارتان 50ملغ"}'

# النتيجة:
# {
#   "patient_name": "خالد العمري",
#   "patient_id": "MR-2024-1234",
#   "diagnosis": ["ارتفاع ضغط الدم المزمن"],
#   "medications": ["أملوديبين 5ملغ", "لوسارتان 50ملغ"],
#   ...
# }
```

### تقارير طبية | Medical Reports

النظام يدعم معالجة التقارير الطبية بجميع أنواعها:

- **تقارير المختبر**: استخراج النتائج والقيم المرجعية
- **تقارير الأشعة**: ربط تقارير الأشعة بالصور المقابلة
- **تقارير العيادات**: تنظيم حسب التخصص والطبيب والتاريخ
- **وصفات الأدوية**: استخراج الأدوية والجرعات والتعليمات
- **خطابات الإحالة**: ربط الإحالات بالتقارير ذات الصلة

يتم كل ذلك مع الحفاظ على الخصوصية الكاملة — جميع العمليات تتم محلياً على جهازك بدون إرسال أي بيانات لخوادم خارجية.

### صور الأشعة | Radiology Images

دعم معالجة صور الأشعة والتصوير الطبي:

- **استخراج النصوص**: قراءة البيانات الوصفية من صور الأشعة (DICOM metadata)
- **تحسين الصور**: تحسين جودة الصور الممسوحة ضوئياً
- **الوصف الذكي**: إنشاء أوصاف تلقائية لمحتوى الصورة
- **الربط بالتقارير**: ربط صور الأشعة بتقاريرها الطبية المقابلة عبر نظام الوسوم والعلاقات

```bash
# معالجة صورة أشعة
curl -X POST "http://localhost:8421/api/process/image?filepath=/path/to/xray.png&fix_scan=true"

# الوسوم التلقائية ستشمل: medical/radiology, medical/specialty/cardiology
```

### تكامل مع المنصة الطبية | Medical Suite Integration

يمكن ربط IntelliFile Manager مع [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite) لإنشاء نظام متكامل لإدارة المستندات الطبية:

- **استيراد التقارير**: استقبال التقارير من نظام OCR الطبي
- **تصنيف تلقائي**: تصنيف المخرجات حسب النوع والأهمية
- **بحث موحد**: بحث في جميع المستندات من واجهة واحدة
- **تنبيهات ذكية**: إشعارات عند اكتشاف معلومات حرجة

---

## Development Guide | دليل التطوير

### Project Structure | هيكل المشروع

```
intelli-file-manager/
├── src/
│   ├── api/                    # FastAPI server (22 endpoints)
│   │   └── server.py
│   ├── core/                   # Core engines
│   │   ├── config.py           # Configuration & categories
│   │   ├── classifier.py       # Smart file classifier (Magika)
│   │   ├── hybrid_search.py    # BM25 + Semantic + RRF
│   │   ├── smart_tagger.py     # Auto + manual tagging
│   │   ├── file_copilot.py     # RAG-based chat assistant
│   │   ├── medical_ner.py      # Arabic medical NER
│   │   ├── enhanced_multimodal.py  # Image/Audio/Video/Doc processing
│   │   ├── file_handler.py     # CRUD + undo + backup
│   │   ├── ai_engine.py        # Ollama integration
│   │   ├── semantic_search.py  # Vector search
│   │   ├── rag_engine.py       # RAG engine (ChromaDB + Ollama)
│   │   ├── voice_controller.py # Arabic voice control
│   │   ├── relationship_miner.py   # File relationships
│   │   ├── predictive_organizer.py # Usage pattern learning
│   │   ├── emergent_category.py    # Dynamic categories
│   │   ├── self_extending_assistant.py # Self-learning assistant
│   │   ├── file_agent.py       # Autonomous file agents
│   │   └── agent_cli.py        # Agent CLI interface
│   ├── ai/                     # AI engine layer
│   │   ├── classifier.py       # Ollama HTTP classifier
│   │   ├── embeddings.py       # Embedding engine
│   │   └── agents/base_agent.py
│   ├── db/                     # Database layer
│   │   ├── schemas.py          # Pydantic schemas
│   │   └── chroma_db.py        # ChromaDB manager
│   ├── plugins/                # Plugin system (NEW)
│   │   ├── __init__.py         # IntelliFilePlugin, PluginManager
│   │   └── sample_medical_plugin.py
│   ├── gui/                    # PySide6 desktop GUI
│   └── utils/                  # Utilities
├── web/                        # Next.js 16 web interface
│   └── src/
│       ├── app/                # Next.js app router
│       ├── components/         # React components + shadcn/ui
│       ├── hooks/              # React hooks
│       └── lib/                # Utilities
├── tests/                      # 241 tests
│   ├── unit/                   # Unit tests
│   └── integration/            # Integration tests
├── docs/                       # Documentation
│   ├── architecture.md
│   └── ROADMAP.md
├── README.md
├── CONTRIBUTING.md
├── pyproject.toml
└── requirements.txt
```

### Development Setup | إعداد بيئة التطوير

```bash
# 1. استنساخ وإنشاء بيئة افتراضية
git clone https://github.com/DrAbdulmalek/IntelliFile-app.git
cd intelli-file-manager
python -m venv venv
source venv/bin/activate

# 2. تثبيت متطلبات التطوير
pip install -r requirements.txt
pip install pytest pytest-cov flake8 bandit mypy

# 3. تثبيت pre-commit hooks (اختياري)
pre-commit install

# 4. تشغيل الاختبارات
pytest -v

# 5. فحص جودة الكود
flake8 src/ --max-line-length=120
mypy src/ --ignore-missing-imports
```

### Code Style | معايير الكود

- **Python**: اتباع PEP 8 مع حد أقصى 120 حرفاً لكل سطر
- **TypeScript**: اتباع إعدادات ESLint الموجودة في `web/eslint.config.mjs`
- **Type Hints**: استخدام تعليقات النوع لجميع الدوال العامة
- **Docstrings**: توثيق جميع الدوال والفئات العامة بالعربية والإنجليزية
- **Arabic RTL**: ضمان دعم RTL في أي تغييرات على الواجهة

### Adding New Features | إضافة ميزات جديدة

1. إنشاء الوحدة في `src/core/` أو `src/plugins/`
2. إضافة نقاط نهاية API في `src/api/server.py`
3. كتابة اختبارات في `tests/unit/` أو `tests/integration/`
4. تحديث التوثيق

---

## Plugin System | نظام الإضافات

يتضمن IntelliFile Manager نظام إضافات مرن يسمح بتوسيع الوظائف بدون تعديل الكود الأساسي.

### Creating a Plugin | إنشاء إضافة

```python
from src.plugins import IntelliFilePlugin, PluginContext

class MyPlugin(IntelliFilePlugin):
    name = "my_plugin"
    version = "1.0.0"
    description = "وصف الإضافة"
    
    def initialize(self, context: PluginContext) -> None:
        context.register_classifier("my_classifier", self._classify)
        context.register_tag_generator("my_tags", self._generate_tags)
    
    def _classify(self, text: str) -> dict:
        return {"category": "custom", "confidence": 0.9}
    
    def _generate_tags(self, filepath: str, text: str) -> list[str]:
        return ["custom/tag1", "custom/tag2"]
```

### Plugin Discovery | اكتشاف الإضافات

الإضافات يتم اكتشافها تلقائياً من:

1. **`src/plugins/`** — إضافات مدمجة (built-in)
2. **`~/.intellifile/plugins/`** — إضافات المستخدم
3. **PYTHONPATH** — حزم باسم `intellifile_plugin`

### Plugin Registration Types | أنواع التسجيل

| النوع | الوصف |
|-------|-------|
| `register_classifier` | مصنف مخصص للملفات |
| `register_search_engine` | محرك بحث مخصص |
| `register_ner_extractor` | مستخرج كيانات مسماة مخصص |
| `register_tag_generator` | مولد وسوم مخصص |
| `register_file_processor` | معالج ملفات مخصص |

---

## Integration with omni-medical-suite | التكامل مع المنصة الطبية

IntelliFile Manager يمكن أن يعمل كجزء من منظومة [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite) لإدارة المستندات الطبية:

### Architecture Integration | بنية التكامل

```
┌──────────────────────────────┐
│     omni-medical-suite       │
│  (Medical OCR + NLP)         │
│  • Handwriting OCR           │
│  • Clinical Text Correction  │
│  • Medical NLP Pipeline      │
└──────────────┬───────────────┘
               │ REST API / File System
               ▼
┌──────────────────────────────┐
│   IntelliFile Manager        │
│  (File Management + AI)      │
│  • Smart Classification      │
│  • Hybrid Search             │
│  • Medical NER (Arabic)      │
│  • RAG Chat                  │
│  • Smart Tagging             │
└──────────────────────────────┘
```

### Integration Points | نقاط التكامل

| الوظيفة | omni-medical-suite | IntelliFile |
|---------|-------------------|-------------|
| OCR الطبي | ✅ معالجة الخط اليدوي | استقبال المخرجات |
| تصحيح النص | ✅ تصحيح النصوص الطبية | تخزين وفهرسة |
| NER طبي | أساسي | متقدم (عربي) |
| تصنيف الملفات | — | ✅ تلقائي |
| بحث دلالي | — | ✅ هجين |
| وسوم ذكية | — | ✅ متعددة الطبقات |
| محادثة RAG | — | ✅ مع الملفات |

### Configuration | الإعدادات

```python
# إعداد التكامل في config.py
OMNI_MEDICAL_SUITE_URL = os.getenv("OMNI_MEDICAL_URL", "http://localhost:7860")
INTELLIFILE_API_URL = os.getenv("INTELLIFILE_API_URL", "http://localhost:8421")
```

---

## Tech Stack | التقنيات المستخدمة

### Backend | الخلفية

| التقنية | الإصدار | الغرض |
|---------|---------|-------|
| Python | 3.10+ | لغة البرمجة الرئيسية |
| FastAPI | 0.115+ | إطار عمل API |
| Ollama | latest | نماذج اللغة المحلية (LLM) |
| sentence-transformers | latest | التضمينات الدلالية |
| ChromaDB | latest | قاعدة بيانات المتجهات |
| Magika | latest | كشف نوع الملف (100+ نوع) |
| PySide6 | 6.8+ | واجهة سطح المكتب |

### Frontend | الواجهة

| التقنية | الإصدار | الغرض |
|---------|---------|-------|
| Next.js | 16 | إطار عمل الويب |
| TypeScript | 5 | لغة مكتوبة |
| Tailwind CSS | 4 | إطار التصميم |
| shadcn/ui | latest | مكونات UI |
| Framer Motion | latest | التحريكات |
| Recharts | latest | الرسوم البيانية |

---

## Testing | الاختبارات

يتضمن المشروع **241 اختباراً** تغطي جميع الوحدات والتكامل:

| المجموعة | عدد الاختبارات | الوصف |
|----------|---------------|-------|
| `test_core` | 30+ | اختبارات الإعدادات |
| `test_classifier` | 23 | اختبارات المصنف |
| `test_file_handler` | 21 | اختبارات معالج الملفات |
| `test_helpers` | 33 | اختبارات الدوال المساعدة |
| `test_voice_controller` | 24 | اختبارات التحكم الصوتي |
| `test_emergent_category` | 22 | اختبارات التصنيف الديناميكي |
| `test_hybrid_search` | 20+ | اختبارات البحث الهجين |
| `test_medical_ner` | 20+ | اختبارات NER الطبي |
| `test_smart_tagger` | 20+ | اختبارات الوسوم الذكية |
| `test_file_copilot` | 20+ | اختبارات مساعد الملفات |
| Integration | 20+ | اختبارات التكامل |

---

## License | الترخيص

هذا المشروع مرخص بموجب رخصة **MIT**. يمكنك الاطلاع على ملف [LICENSE](LICENSE) للتفاصيل الكاملة.

```
MIT License

Copyright (c) 2025 IntelliFile - Dr. Abdulmalek Tamer Al-husseini

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

<div align="center">

**صُنع بـ ❤️ لمجتمع مانجارو لينكس والطب العربية**
**Built with ❤️ for the Manjaro Linux & Arabic Medical communities**

[Report Bug](https://github.com/DrAbdulmalek/IntelliFile-app/issues) · [Request Feature](https://github.com/DrAbdulmalek/IntelliFile-app/issues) · [Contribute](CONTRIBUTING.md) · [Roadmap](docs/ROADMAP.md)

</div>
