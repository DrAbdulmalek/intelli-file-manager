> 💡 **Independent Side Product** — IntelliFile is a standalone AI-powered file manager for Manjaro Linux. It is **NOT** part of the [OmniMedical Suite](https://github.com/DrAbdulmalek/omni-medical-suite) medical OCR ecosystem.
>
> For medical document processing, see: [OmniMedical Suite](https://github.com/DrAbdulmalek/omni-medical-suite) · [Live Demo](https://huggingface.co/spaces/DrAbdulmalek/medical-handwriting-ocr)

<div align="center">

# ✨ IntelliFile
## تطبيق تصنيف الملفات الذكي
### Smart File Classification Application

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![PySide6](https://img.shields.io/badge/PySide6-GUI-orange.svg)](https://pyside.org)
[![Next.js](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org)
[![Manjaro](https://img.shields.io/badge/OS-Manjaro_Linux-35BF5C.svg)](https://manjaro.org)

<p align="center">
  <img src="https://img.shields.io/badge/الذكاء_الاصطناعي-AI_Powered-purple" alt="AI Powered" />
  <img src="https://img.shields.io/badge/العربية-RTL_Support-blue" alt="Arabic RTL" />
  <img src="https://img.shields.io/badge/الوضع_المظلم-Dark_Mode-1a1a2e" alt="Dark Mode" />
</p>

<p align="center">
  <strong>تطبيق متقدم لإدارة وتصنيف الملفات باستخدام الذكاء الاصطناعي</strong><br/>
  <em>A sophisticated AI-powered file management and classification application</em>
</p>

</div>

---

## 📖 فهرس المحتويات | Table of Contents

- [📋 الوصف | Description](#-الوصف--description)
- [✨ المميزات | Features](#-المميزات--features)
- [🛠️ التقنيات المستخدمة | Tech Stack](#️-التقنيات-المستخدمة--tech-stack)
- [📦 التثبيت | Installation](#-التثبيت--installation)
- [🚀 التشغيل | Usage](#-التشغيل--usage)
- [📁 هيكل المشروع | Project Structure](#-هيكل-المشروع--project-structure)
- [📸 لقطات الشاشة | Screenshots](#-لقطات-الشاشة--screenshots)
- [🤝 المساهمة | Contributing](#-المساهمة--contributing)
- [📜 الترخيص | License](#-الترخيص--license)

---

## 📋 الوصف | Description

### العربية

**IntelliFile** هو تطبيق ذكي متقدم لتصنيف وإدارة الملفات مصمم خصيصاً لنظام مانجارو لينكس. يجمع التطبيق بين قوة الذكاء الاصطناعي وسهولة الاستخدام لتوفير تجربة فريدة في إدارة الملفات.

يدعم التطبيق التصنيف التلقائي للملفات باستخدام نماذج الذكاء الاصطناعي المحلية عبر **Ollama**، والبحث الدلالي عبر **sentence-transformers**، والمعالجة متعددة الوسائط، والتحكم الصوتي باللغة العربية، بالإضافة إلى واجهة ويب حديثة مبنية بـ **Next.js**.

### English

**IntelliFile** is an advanced AI-powered file classification and management application designed specifically for Manjaro Linux. The application combines the power of artificial intelligence with ease of use to provide a unique file management experience.

The application supports automatic file classification using local AI models via **Ollama**, semantic search via **sentence-transformers**, multimodal processing, Arabic voice control, and a modern web interface built with **Next.js**.

---

## ✨ المميزات | Features

### 🔥 المميزات الأساسية | Core Features

| # | الميزة | الوصف |
|---|--------|-------|
| 1 | 🤖 **تصنيف بالذكاء الاصطناعي** | تصنيف تلقائي للملفات باستخدام نماذج محلية (Ollama) بدون اتصال بالإنترنت |
| 2 | 🎤 **تحكم صوتي** | تحكم كامل بالتطبيق عبر الأوامر الصوتية باللغة العربية |
| 3 | 🔍 **بحث دلالي** | بحث ذكي يفهم معنى الاستعلام وليس مجرد تطابق نصي (sentence-transformers + ChromaDB) |
| 4 | 📚 **RAG - توليد معزز بالاسترجاع** | استرجاع المعلومات من الملفات وتوليد إجابات ذكية |
| 5 | 🖼️ **معالجة متعددة الوسائط** | دعم الصور والصوت والفيديو والنصوص في خط أنابيب واحد |
| 6 | 🏷️ **كشف نوع الملف** | تحديد دقيق لنوع الملف باستخدام Google Magika (يدعم 100+ نوع) |
| 7 | 🗂️ **واجهة سطر أوامر للوكلاء** | أدوات CLI للتفاعل مع وكلاء الملفات الذكيين |
| 8 | 🔄 **كشف الملفات المكررة** | اكتشاف الملفات المتطابقة والمشابهة بناءً على التجزئة الدلالية |
| 9 | 🧠 **وكلاء ملفات مستقلين** | وكلاء ذكيون تعمل بشكل مستقل لتنظيم الملفات |
| 10 | 📊 **تنظيم تنبؤي** | ترتيب الملفات تلقائياً بناءً على أنماط الاستخدام |

### 🌟 مميزات متقدمة | Advanced Features

| # | الميزة | الوصف |
|---|--------|-------|
| 11 | 🔄 **تصنيفات ظاهرة** | اكتشاف فئات جديدة تلقائياً من أنماط الملفات |
| 12 | 🔗 **تنقيب العلاقات** | العثور على العلاقات المخفية بين الملفات |
| 13 | 🤖 **مساعد ذاتي التوسع** | مساعد ذكي يتعلم ويطور قدراته مع الاستخدام |
| 14 | 🎨 **تصميم عصري** | واجهة مستخدم حديثة مع وضع مظلم |
| 15 | 🌐 **دعم العربية RTL** | دعم كامل للغة العربية مع واجهة من اليمين لليسار |
| 16 | 🛡️ **حماية الملفات** | تشفير وحماية الملفات الحساسة بكلمات مرور |
| 17 | 📁 **إدارة الأرشيفات** | دعم كامل للملفات المضغوطة مع إدارة كلمات المرور |
| 18 | 📈 **لوحة معلومات تفاعلية** | رسوم بيانية وإحصائيات شاملة عن الملفات |
| 19 | ⚡ **أداء عالي** | معالجة سريعة للملفات الكبيرة مع تحسين الذاكرة |
| 20 | 🔌 **قابل للتوسعة** | بنية معيارية تدعم إضافة ميزات ومكونات جديدة |
| 21 | 📱 **واجهة ويب** | واجهة ويب كاملة مبنية بـ Next.js + shadcn/ui |
| 22 | 🔄 **مزامنة في الوقت الفعلي** | تحديث فوري لأي تغييرات في الملفات |
| 23 | 🧩 **نظام إضافات** | دعم الإضافات لتوسيع وظائف التطبيق |
| 24 | 📝 **سجل النشاط** | تتبع كامل لجميع العمليات والإجراءات |

---

## 🛠️ التقنيات المستخدمة | Tech Stack

### واجهة سطح المكتب | Desktop GUI
| التقنية | الإصدار | الغرض |
|---------|---------|-------|
| ![Python](https://img.shields.io/badge/Python-3.9+-3776AB) | 3.9+ | لغة البرمجة الرئيسية |
| ![PySide6](https://img.shields.io/badge/PySide6-6.8+-41CD52) | 6.8+ | إطار عمل واجهة المستخدم الرسومية |

### محرك الذكاء الاصطناعي | AI Engine
| التقنية | الغرض |
|---------|-------|
| ![Ollama](https://img.shields.io/badge/Ollama-Local_AI-000000) | تشغيل نماذج اللغة المحلية (LLM) |
| ![Magika](https://img.shields.io/badge/Magika-File_Type-4285F4) | كشف نوع الملف بدقة عالية |
| ![sentence-transformers](https://img.shields.io/badge/sentence--transformers-Embeddings-FF6F00) | تحويل النصوص إلى متجهات دلالية |
| ![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_DB-FFC107) | قاعدة بيانات المتجهات للبحث الدلالي |

### واجهة الويب | Web Interface
| التقنية | الإصدار | الغرض |
|---------|---------|-------|
| ![Next.js](https://img.shields.io/badge/Next.js-16-black) | 16 | إطار عمل الويب |
| ![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6) | 5 | لغة برمجة مكتوبة |
| ![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-4-06B6D4) | 4 | إطار عمل التصميم |
| ![shadcn/ui](https://img.shields.io/badge/shadcn/ui-Components-black) | latest | مكتبة مكونات UI |
| ![Framer Motion](https://img.shields.io/badge/Framer_Motion-Animations-0055FF) | latest | حركات وتحريكات |
| ![Recharts](https://img.shields.io/badge/Recharts-Charts-8884D8) | latest | رسوم بيانية |

---

## 📦 التثبيت | Installation

### المتطلبات المسبقة | Prerequisites

- نظام تشغيل **Manjaro Linux** (أو أي توزيعة لينكس أخرى)
- **Python** 3.9 أو أحدث
- **Node.js** 18 أو أحدث
- **Ollama** (للذكاء الاصطناعي المحلي)

### 🐧 تثبيت على مانجارو | Manjaro Installation

#### الطريقة 1: باستخدام pacman (موصى بها)

```bash
# 1. استنساخ المستودع
git clone https://github.com/DrAbdulmalek/IntelliFile-app.git
cd IntelliFile

# 2. تثبيت متطلبات النظام
sudo pacman -Syu python python-pip qt6-base

# 3. تثبيت Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 4. تشغيل نموذج الذكاء الاصطناعي
ollama pull llama3.2
ollama pull nomic-embed-text

# 5. إنشاء بيئة افتراضية وتثبيت المتطلبات
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 6. تشغيل التطبيق
python main.py
```

#### الطريقة 2: باستخدام Conda

```bash
# 1. إنشاء بيئة كوندا
conda create -n intellifile python=3.11 -y
conda activate intellifile

# 2. استنساخ المستودع
git clone https://github.com/DrAbdulmalek/IntelliFile-app.git
cd IntelliFile

# 3. تثبيت المتطلبات
pip install -r requirements.txt

# 4. تثبيت Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2

# 5. تشغيل التطبيق
python main.py
```

### 🌐 إعداد واجهة الويب | Web Interface Setup

```bash
# الانتقال إلى مجلد الويب
cd web

# تثبيت التبعيات
npm install

# تشغيل بيئة التطوير
npm run dev

# بناء للإنتاج
npm run build

# تشغيل نسخة الإنتاج
npm start
```

> 📌 **ملاحظة:** واجهة الويب تعمل على المنفذ `3000` افتراضياً. افتح المتصفح على `http://localhost:3000`

---

## 🚀 التشغيل | Usage

### واجهة سطح المكتب | Desktop GUI

```bash
# تشغيل التطبيق الرسومي
python main.py

# تشغيل مع واجهة التصحيح
python main.py --debug

# تشغيل مع ملف إعدادات مخصص
python main.py --config custom_config.json
```

### واجهة سطر الأوامر | CLI

```bash
# تصنيف مجلد كامل
python cli.py classify /path/to/folder

# البحث الدلالي
python cli.py search "تقارير المبيعات"

# كشف الملفات المكررة
python cli.py duplicates /path/to/folder

# تشغيل وكلاء الملفات
python cli.py agent --mode auto /path/to/folder

# كشف نوع الملف
python cli.py detect /path/to/file

# المساعدة
python cli.py --help
```

### التحكم الصوتي | Voice Control

```bash
# تفعيل التحكم الصوتي
python voice_control.py

# أمثلة الأوامر الصوتية:
# - "صنّف جميع الملفات"
# - "ابحث عن تقارير المبيعات"
# - "احذف الملفات المكررة"
# - "أنشئ مجلد جديد للمستندات"
```

### واجهة الويب | Web Interface

```bash
cd web
npm run dev
# افتح http://localhost:3000 في المتصفح
```

**الأقسام المتاحة في واجهة الويب:**

| القسم | الوصف |
|-------|-------|
| 📂 مدير الملفات | إدارة وتنظيم الملفات مع سحب وإفلات |
| 🤖 المساعد الذكي | محادثة مع AI Copilot لتنفيذ الأوامر |
| 🔍 البحث الدلالي | بحث ذكي في الملفات حسب المعنى |
| 📊 لوحة المعلومات | إحصائيات ورسوم بيانية تفاعلية |
| ⚙️ الإعدادات | تخصيص التطبيق والنماذج الذكية |

---

## 📁 هيكل المشروع | Project Structure

```
IntelliFile-app/
├── 📄 README.md                    # التوثيق الرئيسي
├── 📄 LICENSE                      # رخصة MIT
├── 📄 .gitignore                   # إعدادات Git
├── 📄 requirements.txt             # متطلبات Python
├── 📄 setup.py                     # إعداد الحزمة
├── 📄 pyproject.toml               # إعدادات البناء
├── 📄 pytest.ini                   # إعدادات الاختبارات
├── 📄 cli.py                       # نقطة دخخول CLI
│
├── 📂 src/                         # الكود المصدري (Python)
│   ├── 📄 main.py                  # نقطة الدخول الرئيسية
│   │
│   ├── 📂 core/                    # المنطق الأساسي (14 وحدة)
│   │   ├── 📄 config.py            # الإعدادات + الفئات + خريطة الامتدادات
│   │   ├── 📄 classifier.py        # مصنف الملفات الذكي (Magika + امتداد)
│   │   ├── 📄 file_handler.py      # إدارة الملفات (CRUD + تراجع + نسخ احتياطي)
│   │   ├── 📄 ai_engine.py         # محرك الذكاء الاصطناعي (Ollama)
│   │   ├── 📄 semantic_search.py   # البحث الدلالي (sentence-transformers)
│   │   ├── 📄 rag_engine.py        # محرك RAG (ChromaDB + Ollama)
│   │   ├── 📄 voice_controller.py  # التحكم الصوتي (Arabic)
│   │   ├── 📄 file_agent.py        # وكيل الملفات المستقل
│   │   ├── 📄 multimodal_processor.py # معالجة متعددة الوسائط
│   │   ├── 📄 relationship_miner.py  # تنقيب العلاقات (NetworkX)
│   │   ├── 📄 predictive_organizer.py # المنظم التنبؤي
│   │   ├── 📄 emergent_category.py # التصنيف الدينامي
│   │   ├── 📄 self_extending_assistant.py # المساعد المتوسع
│   │   └── 📄 agent_cli.py         # واجهة سطر الأوامر
│   │
│   ├── 📂 ai/                      # محرك الذكاء الاصطناعي
│   │   ├── 📄 classifier.py        # مصنف AI (Ollama HTTP API)
│   │   ├── 📄 embeddings.py        # التضمينات الدلالية
│   │   └── 📂 agents/              # وكلاء AI
│   │       └── 📄 base_agent.py    # الفئة الأساسية
│   │
│   ├── 📂 db/                      # قاعدة البيانات
│   │   ├── 📄 schemas.py           # FileMetadata + FileRecord
│   │   └── 📄 chroma_db.py         # مدير ChromaDB
│   │
│   ├── 📂 gui/                     # واجهة سطح المكتب (PySide6)
│   │   └── 📄 main_window.py       # النافذة الرئيسية
│   │
│   └── 📂 utils/                   # أدوات مساعدة
│       └── 📄 helpers.py           # دوال مساعدة
│
├── 📂 web/                         # واجهة الويب (Next.js)
│   ├── 📄 package.json             # تبعيات Node.js
│   ├── 📄 next.config.ts           # إعدادات Next.js
│   ├── 📄 tsconfig.json            # إعدادات TypeScript
│   ├── 📄 tailwind.config.ts       # إعدادات Tailwind CSS
│   ├── 📄 components.json          # إعدادات shadcn/ui
│   │
│   └── 📂 src/
│       ├── 📂 app/                 # مسارات التطبيق
│       │   ├── 📄 layout.tsx       # التخطيط الرئيسي
│       │   ├── 📄 page.tsx         # الصفحة الرئيسية
│       │   ├── 📄 globals.css      # الأنماط العامة
│       │   └── 📂 api/             # واجهات API
│       │       └── 📄 route.ts     # نقطة نهاية API
│       │
│       ├── 📂 components/          # مكونات React
│       │   ├── 📂 ui/              # مكونات shadcn/ui (50+ ملف)
│       │   ├── 📄 types.ts         # أنواع TypeScript
│       │   ├── 📄 constants.tsx    # ثوابت التطبيق
│       │   ├── 📄 helpers.tsx      # دوال مساعدة
│       │   ├── 📄 Sidebar.tsx      # شريط التنقل
│       │   ├── 📄 FileManager.tsx  # مدير الملفات
│       │   ├── 📄 AICopilot.tsx    # لوحة المحادثة الذكية
│       │   ├── 📄 SearchPanel.tsx  # البحث الدلالي
│       │   ├── 📄 Dashboard.tsx    # لوحة المعلومات
│       │   ├── 📄 SettingsPanel.tsx# الإعدادات
│       │   └── 📄 ...              # مكونات أخرى
│       │
│       ├── 📂 hooks/               # React Hooks
│       └── 📂 lib/                 # مكتبات مساعدة
│           └── 📄 utils.ts         # دوال مساعدة
│
├── 📂 docs/                        # التوثيق
│   └── 📄 architecture.md          # وثائق البنية
│
├── 📂 tests/                       # الاختبارات (173 اختبار)
│   ├── 📄 conftest.py              # Fixtures مشتركة
│   ├── 📂 unit/                    # اختبارات الوحدات (153)
│   └── 📂 integration/             # اختبارات التكامل (20)
│
└── 📄 pyproject.toml               # إعدادات البناء والاختبارات
```

---

## 📸 لقطات الشاشة | Screenshots

### واجهة الويب | Web Interface

| الشاشة | الوصف |
|--------|-------|
| ![File Manager](docs/screenshots/file-manager.png) | مدير الملفات - عرض شبكي وقائمة |
| ![AI Copilot](docs/screenshots/ai-copilot.png) | المساعد الذكي - محادثة AI |
| ![Semantic Search](docs/screenshots/search.png) | البحث الدلالي - نتائج ذكية |
| ![Dashboard](docs/screenshots/dashboard.png) | لوحة المعلومات - إحصائيات |
| ![Settings](docs/screenshots/settings.png) | الإعدادات - تخصيص التطبيق |

### واجهة سطح المكتب | Desktop GUI

| الشاشة | الوصف |
|--------|-------|
| ![Main Window](docs/screenshots/desktop-main.png) | النافذة الرئيسية |
| ![Classification](docs/screenshots/desktop-classify.png) | عملية التصنيف التلقائي |

> 📌 **ملاحظة:** لقطات الشاشة قيد الإعداد وستتم إضافتها قريباً.

---

## 🤝 المساهمة | Contributing

نرحب بمساهماتكم! يرجى اتباع الخطوات التالية:

### خطوات المساهمة | Contribution Steps

1. **Fork المستودع**
   ```bash
   git clone https://github.com/DrAbdulmalek/IntelliFile-app.git
   ```

2. **إنشاء فرع جديد**
   ```bash
   git checkout -b feature/اسم-الميزة
   ```

3. **تطبيق التغييرات**
   ```bash
   # إضافة الميزة أو الإصلاح
   git add .
   git commit -m "إضافة: وصف الميزة الجديدة"
   ```

4. **رفع التغييرات**
   ```bash
   git push origin feature/اسم-الميزة
   ```

5. **إنشاء Pull Request**
   - اشرح التغييرات بشكل واضح
   - أضف لقطات شاشة إن أمكن
   - تأكد من اجتياز جميع الاختبارات

### معايير الكود | Code Standards

- اتبع نمط **PEP 8** للكود Python
- اتبع معايير **ESLint** للكود TypeScript
- أضف تعليقات توثيقية لجميع الدوال والفئات
- اكتب اختبارات لجميع الميزات الجديدة
- تأكد من دعم اللغة العربية (RTL) في أي تغييرات على الواجهة

### هيكل الفروع | Branch Naming

| النوع | الصيغة | مثال |
|-------|--------|------|
| ميزة جديدة | `feature/اسم-الميزة` | `feature/voice-control` |
| إصلاح خطأ | `fix/وصف-الخطأ` | `fix/duplicate-detection` |
| تحسين | `improve/وصف-التحسين` | `improve/search-speed` |
| توثيق | `docs/وصف-التغيير` | `docs/api-reference` |

---

## 📜 الترخيص | License

هذا المشروع مرخص بموجب رخصة **MIT**. يمكنك الاطلاع على ملف [LICENSE](LICENSE) للتفاصيل الكاملة.

```
MIT License

Copyright (c) 2025 IntelliFile

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software...
```

---

## 🙏 الشكر والتقدير | Acknowledgments

- [Ollama](https://ollama.com) - محرك الذكاء الاصطناعي المحلي
- [Google Magika](https://github.com/google/magika) - كشف نوع الملف
- [sentence-transformers](https://www.sbert.net) - التضمينات الدلالية
- [ChromaDB](https://www.trychroma.com) - قاعدة بيانات المتجهات
- [PySide6](https://pyside.org) - إطار عمل واجهة المستخدم
- [Next.js](https://nextjs.org) - إطار عمل الويب
- [shadcn/ui](https://ui.shadcn.com) - مكونات واجهة المستخدم
- [Tailwind CSS](https://tailwindcss.com) - إطار عمل التصميم

---

<div align="center">

**صُنع بـ ❤️ لمجتمع مانجارو لينكس**

**Built with ❤️ for the Manjaro Linux community**

</div>


---

## Repository Status

| Field | Value |
|-------|-------|
| **Role** | Smart File Manager (Independent) |
| **Status** | Active Development |
| **Layer** | Independent Project |
| **Priority** | Low |
| **Domain** | File Management / Productivity (NOT Medical) |

## What This Is

IntelliFile is a **standalone AI-powered file classification application** for Manjaro Linux. It is **independent** from the medical OCR ecosystem and serves a different domain.

## Who Should Use This

- Manjaro/Linux users wanting **AI-powered file organization**
- Users needing **local AI processing** (no internet required via Ollama)
- Teams wanting **semantic search** across their file system
- Users preferring **voice-controlled** file management (Arabic)

## How This Differs from Medical OCR Projects

| Aspect | IntelliFile | Medical OCR Ecosystem |
|--------|------------|----------------------|
| Domain | General file management | Medical document processing |
| AI Focus | Classification, RAG, Search | OCR, correction, NLP |
| Platform | Manjaro Linux desktop | Web/Cloud/Docker |
| Integration | Standalone | Connected ecosystem |

## Related Repositories (Medical Ecosystem)

> IntelliFile is independent. For medical document processing, see:
> - [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite) — Main platform
> - [omni-medical-suite/apps/handwriting-demo/](https://github.com/DrAbdulmalek/omni-medical-suite/tree/main/apps/handwriting-demo) — Handwriting & clinical OCR

**License: MIT** — Dr. Abdulmalek Tamer Al-husseini
