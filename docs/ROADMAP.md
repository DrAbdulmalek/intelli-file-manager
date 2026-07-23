# IntelliFile Manager — Roadmap | خارطة الطريق

<div align="center">

## خارطة تطور مدير الملفات الذكي المحلي
### Local-first AI File Manager Development Roadmap

</div>

---

## v2.1 (Current) — Foundation & Security | الأساس والأمان

### Core Engine | محرك الأساس
- **Smart File Classifier** — مصنف الملفات الذكي (Magika + content-based)
- **File Handler** — معالج الملفات (CRUD + تراجع + نسخ احتياطي)
- **AI Engine** — محرك الذكاء الاصطناعي (تكامل Ollama)
- **Hybrid Search** — محرك بحث هجين (BM25 + Semantic + RRF)
- **Smart Tagger** — نظام وسوم ذكي متعدد الطبقات
- **File Copilot** — مساعد ملفات ذكي (RAG)
- **Multimodal Processor** — معالجة الصور والصوت والفيديو والمستندات

### Security Hardening | تعزيز الأمان
- API يربط على 127.0.0.1 فقط افتراضياً
- مصادقة API Key اختيارية
- CORS محدود بـ localhost
- Path sandboxing لمنع traversal
- إزالة exec() من الكود
- .gitignore صحيح وشامل

### Repository Cleanup | تنظيف المستودع
- فصل حدود المستودع عن omni-medical-suite
- إزالة إشارات التكامل من التوثيق
- هوية واضحة: مدير ملفات محلي عام

---

## v2.2 (Planned) — Desktop Usability | قابلية استخدام سطح المكتب

### PySide6 Desktop GUI | واجهة سطح المكتب
- محسن اختيار المجلدات
- شريط تقدم المسح والفهرسة
- معاينات الملفات (PDF, صور, نص)
- تقارير الأخطاء
- حالة الفهرسة في الخلفية
- UX البحث المتقدم
- UX الوسوم
- الإجراءات الأخيرة / التراجع
- إعدادات للتبديل (بحث دلالي، ollama، مراقبة مجلدات)

### File Organization MVP | تنظيم الملفات الأساسي
- مخزون ملفات مفهرس
- استخراج بيانات وصفية شامل
- استخراج محتوى (pdf/docx/xlsx/pptx/text)
- فئات ذكية قابلة للتخصيص
- علامات يحددها المستخدم
- إجراءات قائمة على القواعد
- وضع dry-run آمن
- سجل undo/rollback
- اكتشاف الملفات المكررة والمتشابهة
- مراقبة المجلدات مع debounce

---

## v3.0 (Planned) — Local AI & Smart Features | الذكاء المحلي والميزات الذكية

### Enhanced Local Search | بحث محلي محسن
- بحث هجين خفيف (BM25 + semantic + RRF)
- دلالي اختياري (عند توفر embeddings)
- واجهة "لماذا تم تصنيف هذا الملف هنا؟"
- تفسير: قاعدة مطابقة، كلمات مفتاحية، تشابه دلالي

### File Copilot | مساعد الملفات المحلي
- RAG على مجموعات ملفات محلية
- أولوية للسرعة والثبات
- إجابات مبنية على محتوى الملفات الفعلي
- تلخيص ذكي

### Plugin Ecosystem | منظومة الإضافات
- سجل إضافات مركزي
- تثبيت بنقرة واحدة
- بيئة آمنة (sandbox) للإضافات
- واجهة برمجة إضافات محسنة v2
- إضافات موثقة ومعتمدة

---

## v4.0 (Planned) — Cross-Platform & Performance | عبر المنصات والأداء

- دعم Windows و macOS بالإضافة إلى Linux
- نماذج لغوية مدمجة بدون حاجة لـ Ollama
- عمليات ملفات باللغة الطبيعية
- تحليلات تنبؤية لأنماط الملفات
- تحسين الأداء للمجلدات الكبيرة
- معالجة مجمعة للملفات

---

## Contributing | المساهمة

هل لديك أفكار لميزات جديدة؟ نرحب بمساهماتك:

1. افتح [Feature Request](https://github.com/DrAbdulmalek/intelli-file-manager/issues)
2. ناقش الفكرة في [Discussions](https://github.com/DrAbdulmalek/intelli-file-manager/discussions)
3. قدّم PR مع تنفيذ الميزة المقترحة

---

<div align="center">

**خارطة الطريق تتطور مع المجتمع**
**The roadmap evolves with the community**

</div>
