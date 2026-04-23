<div align="center">

# 🏗️ وثائق البنية المعمارية
## IntelliFile - تطبيق تصنيف الملفات الذكي

**Architecture Documentation**

</div>

---

## 📑 فهرس المحتويات

1. [نظرة عامة على البنية | Architecture Overview](#1--نظرة-عامة-على-البنية--architecture-overview)
2. [البنية الثلاثية الطبقات | Three-Tier Architecture](#2--البنية-الثلاثية-الطبقات--three-tier-architecture)
3. [تبعيات الوحدات | Module Dependencies](#3--تبعيات-الوحدات--module-dependencies)
4. [مخططات تدفق البيانات | Data Flow Diagrams](#4--مخططات-تدفق-البيانات--data-flow-diagrams)
5. [تكامل الذكاء الاصطناعي | AI Integration](#5--تكامل-الذكاء-الاصطناعي--ai-integration)
6. [خط أنابيب تصنيف الملفات | File Classification Pipeline](#6--خط-أنابيب-تصنيف-الملفات--file-classification-pipeline)
7. [مخطط قاعدة البيانات | Database Schema](#7--مخطط-قاعدة-البيانات--database-schema)

---

## 1. 🏛️ نظرة عامة على البنية | Architecture Overview

يعتمد IntelliFile على بنية ثلاثية الطبقات (3-tier) مصممة لتحقيق الفصل بين المسؤوليات وقابلية التوسع العالية. البنية تدعم تشغيل واجهة سطح المكتب (PySide6) وواجهة الويب (Next.js) بالتوازي، مع مشاركة نفس محرك الذكاء الاصطناعي والمنطق الأساسي.

```
┌─────────────────────────────────────────────────────────────────┐
│                        طبقة العرض (UI)                        │
│  ┌──────────────────────┐    ┌──────────────────────────────┐  │
│  │   واجهة سطح المكتب   │    │       واجهة الويب          │  │
│  │   (PySide6 / Qt)     │    │  (Next.js + shadcn/ui)     │  │
│  └──────────┬───────────┘    └──────────────┬───────────────┘  │
└─────────────┼───────────────────────────────┼─────────────────┘
              │                               │
              ▼                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     طبقة المنطق الأساسي                        │
│  ┌────────────┐ ┌──────────────┐ ┌───────────────────────────┐ │
│  │FileManager │ │  Organizer   │ │   DuplicateDetector       │ │
│  └────────────┘ └──────────────┘ └───────────────────────────┘ │
│  ┌────────────┐ ┌──────────────┐ ┌───────────────────────────┐ │
│  │FileTypeDet.│ │ CategoryMiner│ │   VoiceControl            │ │
│  └────────────┘ └──────────────┘ └───────────────────────────┘ │
└─────────────┬───────────────────────────────┬─────────────────┘
              │                               │
              ▼                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    طبقة محرك الذكاء الاصطناعي                  │
│  ┌──────────┐ ┌──────────────┐ ┌──────────┐ ┌───────────────┐ │
│  │ Ollama   │ │  Magika      │ │sentence- │ │  ChromaDB     │ │
│  │ (LLM)    │ │ (Type Det.)  │ │transform.│ │ (Vector DB)   │ │
│  └──────────┘ └──────────────┘ └──────────┘ └───────────────┘ │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    وكلاء الملفات الذكية                      │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │ │
│  │  │ Classify │ │ Search   │ │ Organize │ │   RAG Agent  │  │ │
│  │  │  Agent   │ │  Agent   │ │  Agent   │ │              │  │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 🧩 البنية الثلاثية الطبقات | Three-Tier Architecture

### الطبقة الأولى: طبقة العرض (Presentation Layer)

تتولى هذه الطبقة تفاعل المستخدم مع النظام وتتكون من واجهتين:

#### واجهة سطح المكتب (PySide6)
```
src/gui/
├── main_window.py          # النافذة الرئيسية - QMainWindow
├── file_view.py            # عرض الملفات - QTreeView + QListView
├── settings_dialog.py      # نافذة الإعدادات - QDialog
├── chat_panel.py           # لوحة المحادثة مع AI
├── search_panel.py         # لوحة البحث الدلالي
├── dashboard_panel.py      # لوحة المعلومات والإحصائيات
└── components/
    ├── file_card.py        # بطاقة الملف - QWidget مخصص
    ├── category_badge.py   # شارة التصنيف
    ├── progress_widget.py  # شريط التقدم
    └── voice_button.py     # زر التحكم الصوتي
```

**المميزات:**
- دعم كامل للعربية (RTL) عبر Qt's layout mirroring
- وضع مظلم/فاتح قابل للتبديل
- رسوم متحركة سلسة عبر QPropertyAnimation
- دعم السحب والإفلات (Drag & Drop)

#### واجهة الويب (Next.js)
```
web/src/
├── app/
│   ├── layout.tsx          # التخطيط الرئيسي (dir="rtl")
│   ├── page.tsx            # الصفحة الرئيسية (SPA)
│   ├── globals.css         # الأنماط العامة
│   └── api/
│       └── route.ts        # نقطة نهاية API
├── components/ui/          # مكونات shadcn/ui (47 مكون)
├── hooks/                  # React Hooks مخصصة
└── lib/
    └── utils.ts            # دوال مساعدة (cn, etc.)
```

**المميزات:**
- تصميم متجاوب (Responsive) لجميع أحجام الشاشات
- رسوم متحركة عبر Framer Motion
- مكونات shadcn/ui بأسلوب new-york
- رسوم بيانية تفاعلية عبر Recharts

---

### الطبقة الثانية: طبقة المنطق الأساسي (Core Logic Layer)

تتضمن الوحدات الأساسية لمعالجة الملفات وإدارتها:

```
src/core/
├── file_manager.py         # إدارة عمليات الملفات (CRUD)
├── organizer.py            # المنظم التنبؤي للملفات
├── duplicate_detector.py   # كشف الملفات المكررة
├── file_type_detect.py     # كشف نوع الملف (Magika wrapper)
└── category_mining.py      # اكتشاف التصنيفات الجديدة
```

#### وصف الوحدات:

| الوحدة | المسؤولية | التقنيات |
|--------|-----------|----------|
| `file_manager.py` | عمليات القراءة والكتابة والنقل والحذف | Python os/shutil/pathlib |
| `organizer.py` | ترتيب الملفات بناءً على التصنيف والأنماط | خوارزميات التجميع (Clustering) |
| `duplicate_detector.py` | مقارنة الملفات وكشف المتطابقة | Hashing + Semantic similarity |
| `file_type_detect.py` | تحديد نوع الملف الحقيقي | Google Magika |
| `category_mining.py` | اكتشاف فئات جديدة تلقائياً | Association Rules + NLP |

---

### الطبقة الثالثة: طبقة محرك الذكاء الاصطناعي (AI Engine Layer)

```
src/ai/
├── classifier.py           # مصنف الملفات الرئيسي
├── embeddings.py           # إنشاء التضمينات الدلالية
├── rag_engine.py           # محرك RAG
├── voice_control.py        # التحكم الصوتي
├── agents/
│   ├── base_agent.py       # الفئة الأساسية للوكلاء
│   ├── classify_agent.py   # وكيل التصنيف
│   ├── search_agent.py     # وكيل البحث
│   ├── organize_agent.py   # وكيل التنظيم
│   └── rag_agent.py        # وكيل RAG
└── models/
    └── custom_models.py    # نماذج مخصصة
```

---

## 3. 🔗 تبعيات الوحدات | Module Dependencies

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
            │  │  db/    │ │ ai/agents/      │
            │  │ChromaDB │ │ ai/classifier   │
            │  └─────────┘ │ ai/embeddings   │
            │              │ ai/rag_engine   │
            │              │ ai/voice_ctrl   │
            │              └────────┬────────┘
            │                       │
            │        ┌──────────────┼──────────────┐
            │        ▼              ▼              ▼
            │   ┌─────────┐   ┌─────────┐   ┌─────────┐
            │   │ Ollama  │   │ Magika  │   │sentence-│
            │   │ (LLM)   │   │         │   │transform│
            │   └─────────┘   └─────────┘   └─────────┘
            │
            ▼
       ┌─────────┐
       │ PySide6 │
       │  (Qt)   │
       └─────────┘
```

### تبعيات خارجية:

```
intellifile/
├── Python ≥ 3.9
│   ├── PySide6 ≥ 6.8         # واجهة المستخدم الرسومية
│   ├── ollama                # عميل API لـ Ollama
│   ├── magika                # كشف نوع الملف (Google)
│   ├── sentence-transformers # التضمينات الدلالية
│   ├── chromadb              # قاعدة بيانات المتجهات
│   ├── numpy                 # عمليات المصفوفات
│   ├── scipy                 # خوارزميات المسافة
│   ├── speech-recognition    # التعرف على الكلام
│   ├── pyttsx3               # تحويل النص إلى كلام
│   └── watchdog              # مراقبة تغييرات الملفات
│
└── Node.js ≥ 18              # واجهة الويب
    ├── next ≥ 16             # إطار عمل الويب
    ├── react ≥ 19            # مكتبة UI
    ├── typescript ≥ 5        # لغة مكتوبة
    ├── tailwindcss ≥ 4       # تصميم CSS
    ├── shadcn/ui             # مكونات UI
    ├── framer-motion         # رسوم متحركة
    ├── recharts              # رسوم بيانية
    └── lucide-react          # أيقونات
```

---

## 4. 📊 مخططات تدفق البيانات | Data Flow Diagrams

### تدفق تصنيف الملف | File Classification Flow

```
[ملف جديد] ─────► [قراءة الملف] ─────► [كشف النوع (Magika)]
                                              │
                                              ▼
                                       [استخراج المحتوى]
                                       ┌────────┴────────┐
                                       ▼                 ▼
                                  [نص]             [وسائط]
                                   │                   │
                                   ▼                   ▼
                            [تضمينات دلالية]    [تحليل وسائط]
                            (sentence-transf.)   (VLM/Ollama)
                                   │                   │
                                   └────────┬──────────┘
                                            ▼
                                    [البحث في ChromaDB]
                                            │
                                    ┌───────┴───────┐
                                    ▼               ▼
                               [وجد تطابق]    [لا يوجد]
                                    │               │
                                    ▼               ▼
                              [تطبيق التصنيف]  [تصنيف AI]
                              [الموجود]        (Ollama LLM)
                                    │               │
                                    └───────┬───────┘
                                            ▼
                                    [حفظ في ChromaDB]
                                            │
                                            ▼
                                    [تحديث الواجهة]
```

### تدفق البحث الدلالي | Semantic Search Flow

```
[استعلام المستخدم] ─────► [تحويل إلى تضمين]
                           (sentence-transformers)
                                  │
                                  ▼
                          [البحث في ChromaDB]
                          (cosine similarity)
                                  │
                                  ▼
                       ┌──── إعادة النتائج ────┐
                       ▼                         ▼
               [نتائج عالية الدقة]       [نتائج منخفضة الدقة]
                       │                         │
                       ▼                         ▼
               [عرض فوري]               [توسيع البحث]
                                        (LLM re-ranking)
                                              │
                                              ▼
                                        [عرض النتائج]
```

### تدفق RAG | RAG Pipeline Flow

```
[سؤال المستخدم] ─────► [تضمين السؤال] ─────► [بحث المتجهات]
                           (embeddings)        (ChromaDB)
                                                    │
                                                    ▼
                                           [استرجاع المستندات]
                                                    │
                                           ┌────────┴────────┐
                                           ▼                 ▼
                                     [سياق عالي]      [سياق منخفض]
                                     (score > 0.8)    (score < 0.8)
                                           │                 │
                                           ▼                 ▼
                                     [بناء الـPrompt]   [استبعاد]
                                           │
                                           ▼
                                    [إرسال إلى Ollama]
                                    (LLM + Context)
                                           │
                                           ▼
                                    [توليد الإجابة]
                                           │
                                           ▼
                                    [عرض للمستخدم]
```

### تدفق التحكم الصوتي | Voice Control Flow

```
[ميكروفون] ─────► [تسجيل صوتي] ─────► [التعرف على الكلام]
                   (pyaudio)            (speech-recognition)
                                              │
                                              ▼
                                      [نص عربي خام]
                                              │
                                              ▼
                                      [معالجة NLP]
                                      (تنظيف + تطبيع)
                                              │
                                              ▼
                                      [استخراج القصد]
                                      (Intent Detection)
                                              │
                                    ┌─────────┼─────────┐
                                    ▼         ▼         ▼
                              [تصنيف]    [بحث]    [تنظيم]
                                    │         │         │
                                    ▼         ▼         ▼
                              [تنفيذ]   [تنفيذ]   [تنفيذ]
                                    │         │         │
                                    └─────────┼─────────┘
                                              ▼
                                    [تحويل النص إلى كلام]
                                      (pyttsx3)
                                              │
                                              ▼
                                    [إرجاع الصوت]
```

---

## 5. 🤖 تكامل الذكاء الاصطناعي | AI Integration

### Ollama (نماذج اللغة المحلية)

**الدور:** تصنيف الملفات، توليد الإجابات (RAG)، فهم الأوامر الطبيعية

```python
# تكوين Ollama
OLLAMA_CONFIG = {
    "base_url": "http://localhost:11434",
    "models": {
        "classifier": "llama3.2",           # تصنيف الملفات
        "embeddings": "nomic-embed-text",   # التضمينات الدلالية
        "vision": "llava",                  # تحليل الصور
        "rag": "llama3.2",                  # توليد الإجابات
    },
    "parameters": {
        "temperature": 0.3,                 # دقة عالية للتصنيف
        "num_predict": 256,                 # طول الاستجابة
        "top_p": 0.9,                       # تنويع معقول
    }
}
```

**مثال على تصنيف ملف:**
```python
import ollama

def classify_file(file_content: str, file_type: str) -> str:
    """تصنيف ملف باستخدام Ollama"""
    response = ollama.chat(
        model='llama3.2',
        messages=[{
            'role': 'user',
            'content': f'''صنّف هذا الملف إلى أحد الفئات التالية:
            مستندات، صور، فيديو، صوت، أرشيفات، برمجة، أنظمة، خطوط، أخرى

            نوع الملف: {file_type}
            المحتوى: {file_content[:500]}
            
            أجب فقط باسم الفئة.'''
        }]
    )
    return response['message']['content'].strip()
```

### Google Magika (كشف نوع الملف)

**الدور:** تحديد النوع الحقيقي للملف بناءً على محتواه (ليس الامتداد فقط)

```python
# تكامل Magika
from magika import Magika

magika = Magika()

def detect_file_type(file_path: str) -> dict:
    """كشف نوع الملف باستخدام Magika"""
    result = magika.predict_path(file_path)
    return {
        "mime_type": result.output.mime_type,
        "extension": result.output.extension,
        "group": result.output.group,
        "confidence": result.output.score,
        "description": result.output.description,
    }
```

**الأنواع المدعومة (100+ نوع):**
- المستندات: PDF, DOCX, XLSX, PPTX, TXT, MD
- الصور: JPG, PNG, GIF, SVG, WEBP, BMP
- الفيديو: MP4, AVI, MKV, MOV, WEBM
- الصوت: MP3, WAV, OGG, FLAC, AAC
- الأرشيفات: ZIP, RAR, 7Z, TAR, GZ
- البرمجة: PY, JS, TS, HTML, CSS, JSON, YAML
- الأنظمة: EXE, DLL, SO, DEB, RPM

### sentence-transformers (التضمينات الدلالية)

**الدور:** تحويل النصوص إلى متجهات رقمية للبحث الدلالي والمقارنة

```python
# تكوين sentence-transformers
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')

def generate_embedding(text: str) -> list[float]:
    """إنشاء تضمين دلالي للنص"""
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding.tolist()

def compute_similarity(text1: str, text2: str) -> float:
    """حساب التشابه بين نصين"""
    emb1 = model.encode(text1)
    emb2 = model.encode(text2)
    # cosine similarity
    similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
    return float(similarity)
```

**النموذج المستخدم:**
- `paraphrase-multilingual-MiniLM-L12-v2` — يدعم 50+ لغة بما فيها العربية
- أبعاد التضمين: 384
- حجم النموذج: ~420MB

---

## 6. 🔄 خط أنابيب تصنيف الملفات | File Classification Pipeline

### المراحل:

```
┌─────────────────────────────────────────────────────────────┐
│              خط أنابيب تصنيف الملفات                         │
│              File Classification Pipeline                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  المرحلة 1: الكشف الأولي                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  📥 استقبال الملف                                     │   │
│  │  → التحقق من وجود الملف                               │   │
│  │  → قراءة البيانات الوصفية (metadata)                 │   │
│  │  → حساب التجزئة (SHA-256)                            │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                          ▼                                   │
│  المرحلة 2: كشف النوع                                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  🏷️ كشف نوع الملف (Magika)                           │   │
│  │  → تحليل البايتات السحرية (magic bytes)              │   │
│  │  → مقارنة مع 100+ توقيع معروف                        │   │
│  │  → إرجاع MIME type + confidence score               │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                          ▼                                   │
│  المرحلة 3: استخراج المحتوى                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  📄 استخراج المحتوى القابل للقراءة                    │   │
│  │  → نصوص: قراءة مباشرة                               │   │
│  │  → PDF: PyMuPDF / pdfplumber                        │   │
│  │  → DOCX: python-docx                                │   │
│  │  → XLSX: openpyxl                                   │   │
│  │  → صور: OCR (Tesseract)                             │   │
│  │  → صوت: Whisper (transcription)                     │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                          ▼                                   │
│  المرحلة 4: التضمين الدلالي                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  🧠 إنشاء التضمينات (sentence-transformers)          │   │
│  │  → تحويل المحتوى إلى متجه 384 بُعد                  │   │
│  │  → تضمين اسم الملف + المحتوى + النوع                │   │
│  │  → تطبيع المتجه (L2 normalization)                  │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                          ▼                                   │
│  المرحلة 5: التصنيف                                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  🤖 تصنيف الملف (Ollama LLM)                         │   │
│  │  → بناء prompt مخصص                                 │   │
│  │  → إرسال المحتوى + النوع + السياق                   │   │
│  │  → استقبال التصنيف مع مستوى الثقة                    │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                          ▼                                   │
│  المرحلة 6: التحقق والتخزين                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  💾 تخزين النتائج (ChromaDB)                        │   │
│  │  → البحث عن ملفات مشابهة                            │   │
│  │  → حفظ التضمين + البيانات الوصفية                   │   │
│  │  → تحديث الفهرس                                     │   │
│  │  → إرجاع التصنيف النهائي                            │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### كود خط الأابيب:

```python
from pathlib import Path
from magika import Magika
from sentence_transformers import SentenceTransformer
import chromadb
import ollama

class FileClassificationPipeline:
    """خط أنابيب تصنيف الملفات الكامل"""

    CATEGORIES = [
        'مستندات', 'صور', 'فيديو', 'صوت',
        'أرشيفات', 'برمجة', 'أنظمة', 'خطوط', 'أخرى'
    ]

    def __init__(self):
        self.magika = Magika()
        self.encoder = SentenceTransformer(
            'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
        )
        self.chroma = chromadb.PersistentClient(path='./chroma_db')
        self.collection = self.chroma.get_or_create_collection('files')

    def classify(self, file_path: str) -> dict:
        """تصنيف ملف واحد - المراحل الست"""
        path = Path(file_path)

        # المرحلة 1: البيانات الوصفية
        metadata = self._extract_metadata(path)

        # المرحلة 2: كشف النوع
        file_type = self._detect_type(path)

        # المرحلة 3: استخراج المحتوى
        content = self._extract_content(path, file_type)

        # المرحلة 4: التضمين
        embedding = self._create_embedding(path.name, content, file_type)

        # المرحلة 5: التصنيف بالذكاء الاصطناعي
        category, confidence = self._ai_classify(
            path.name, content, file_type
        )

        # المرحلة 6: التخزين
        self._store_result(path, metadata, file_type, embedding, category)

        return {
            'file': str(path),
            'type': file_type,
            'category': category,
            'confidence': confidence,
            'embedding': embedding[:10],  # أول 10 أبعاد
        }
```

---

## 7. 💾 مخطط قاعدة البيانات | Database Schema

### ChromaDB Collection: `files`

يستخدم IntelliFile قاعدة بيانات **ChromaDB** لتخزين التضمينات الدلالية والبيانات الوصفية للملفات.

```
┌─────────────────────────────────────────────────────────────┐
│                  Collection: "files"                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    ID (String)                       │   │
│  │  التنسيق: "file:{sha256_hash}"                      │   │
│  │  مثال: "file:a1b2c3d4e5f6..."                       │   │
│  │  فريد لكل ملف                                       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Embedding (Float[384])                  │   │
│  │  النموذج: paraphrase-multilingual-MiniLM-L12-v2     │   │
│  │  الأبعاد: 384                                        │   │
│  │  المسافة: cosine                                    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Document (String)                       │   │
│  │  محتوى الملف المستخرج (نصي)                          │   │
│  │  أو وصف بصري للملفات غير النصية                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Metadata (Dictionary)                   │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │                                                     │   │
│  │  ┌───────────────┬──────────────┬────────────────┐  │   │
│  │  │    الحقل       │    النوع      │   الوصف         │  │   │
│  │  ├───────────────┼──────────────┼────────────────┤  │   │
│  │  │ file_name     │ str          │ اسم الملف       │  │   │
│  │  │ file_path     │ str          │ مسار الملف      │  │   │
│  │  │ file_size     │ int          │ حجم الملف(ببايت)│  │   │
│  │  │ extension     │ str          │ امتداد الملف    │  │   │
│  │  │ mime_type     │ str          │ نوع MIME        │  │   │
│  │  │ magika_group  │ str          │ مجموعة Magika   │  │   │
│  │  │ category      │ str          │ التصنيف النهائي  │  │   │
│  │  │ confidence    │ float        │ مستوى الثقة      │  │   │
│  │  │ is_protected  │ bool         │ محمي أم لا      │  │   │
│  │  │ is_duplicate  │ bool         │ مكرر أم لا      │  │   │
│  │  │ sha256_hash   │ str          │ تجزئة SHA-256   │  │   │
│  │  │ created_at    │ str (ISO)    │ تاريخ الإنشاء   │  │   │
│  │  │ modified_at   │ str (ISO)    │ تاريخ التعديل    │  │   │
│  │  │ classified_at │ str (ISO)    │ تاريخ التصنيف   │  │   │
│  │  │ tags          │ str (JSON)   │ وسوم إضافية     │  │   │
│  │  │ parent_dir    │ str          │ المجلد الأصلي    │  │   │
│  │  └───────────────┴──────────────┴────────────────┘  │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### مثال على سجل في ChromaDB:

```json
{
  "id": "file:a1b2c3d4e5f67890abcdef1234567890",
  "embedding": [0.0123, -0.0456, 0.0789, "... (384 dimensions)"],
  "document": "تقرير مبيعات الربع الأول 2024 - يتضمن إحصائيات...",
  "metadata": {
    "file_name": "تقرير_المبيعات_2024.pdf",
    "file_path": "/home/user/Documents/تقرير_المبيعات_2024.pdf",
    "file_size": 2456789,
    "extension": ".pdf",
    "mime_type": "application/pdf",
    "magika_group": "document",
    "category": "مستندات",
    "confidence": 0.96,
    "is_protected": false,
    "is_duplicate": false,
    "sha256_hash": "a1b2c3d4e5f67890abcdef1234567890",
    "created_at": "2024-03-15T10:30:00Z",
    "modified_at": "2024-03-15T10:30:00Z",
    "classified_at": "2024-03-15T10:35:22Z",
    "tags": "[\"تقارير\", \"مبيعات\", \"2024\"]",
    "parent_dir": "/home/user/Documents"
  }
}
```

### عمليات البحث المدعومة:

| العملية | الوصف | المسافة المستخدمة |
|---------|-------|------------------|
| بحث دلالي | البحث عن ملفات مشابهة لنص معين | Cosine Similarity |
| بحث بالفئة | تصفية الملفات حسب التصنيف | Metadata Filter |
| بحث بالتاريخ | تصفية حسب نطاق زمني | Metadata Filter |
| بحث بالامتداد | تصفية حسب نوع الملف | Metadata Filter |
| كشف المكررات | البحث عن ملفات متطابقة | L2 Distance |

### أمر البحث عبر ChromaDB:

```python
# بحث دلالي
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=10,
    where={"category": "مستندات"},
    where_document={"$contains": "تقرير"}
)

# البحث عن المكررات
duplicates = collection.query(
    query_embeddings=[file_embedding],
    n_results=5,
    where={"$and": [
        {"sha256_hash": {"$ne": current_hash}},
        {"file_size": {"$gte": min_size}}
    ]}
)
```

---

## 📈 تحسينات مستقبلية | Future Improvements

| التحسين | الوصف | الأولوية |
|---------|-------|---------|
| 分布式 ChromaDB | توزيع قاعدة البيانات عبر عدة عقد | عالية |
| نموذج تصنيف مخصص | تدريب نموذج خاص على بيانات المستخدم | عالية |
| معالجة دفعات | تصنيف آلاف الملفات بالتوازي | متوسطة |
| API REST كامل | واجهة برمجة تطبيقات شاملة | متوسطة |
| دعم Docker | حاويات للتشغيل السهل | منخفضة |
| إضافات VS Code | تكامل مع محرر الأكواد | منخفضة |

---

<div align="center">

**وثائق البنية المعمارية - IntelliFile v1.0**

**Architecture Documentation - IntelliFile v1.0**

آخر تحديث: 2025

</div>
