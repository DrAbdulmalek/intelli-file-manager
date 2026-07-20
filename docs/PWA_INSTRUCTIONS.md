# تعليمات PWA — IntelliFile Manager

## ما هو PWA؟

Progressive Web App يتيح تشغيل التطبيق من المتصفح كتطبيق مستقل مع:
- تثبيت على الشاشة الرئيسية
- عمل بدون إنترنت (offline-first)
- إشعارات
- وصول لأجهزة الجهاز (كاميرا، ميكروفون)

## الإعداد

### 1. تشغيل خادم API (Backend)
```bash
cd intelli-file-manager

# تثبيت الاعتماديات
pip install -e ".[all]"

# تشغيل خادم FastAPI
uvicorn src.api.server:app --port 8421 --host 0.0.0.0
```

### 2. تشغيل واجهة الويب (Frontend)
```bash
cd intelli-file-manager/web

# تثبيت اعتماديات Node.js
npm install

# تشغيل خادم التطوير
npm run dev
# سيكون متاحاً على: http://localhost:3000
```

### 3. إنتاج (Production Build)
```bash
cd intelli-file-manager/web
npm run build

# خدمة الملفات الثابتة
npx serve out -p 3000
```

## تثبيت كـ PWA

### على Chrome (Android/Desktop):
1. افتح `http://localhost:3000`
2. اضغط على أيقونة التثبيت في شريط العنوان (⊕ أو ⬇)
3. أو: القائمة → "تثبيت التطبيق"
4. سيظهر التطبيق كأيقونة مستقلة

### على Safari (iOS):
1. افتح `http://localhost:3000`
2. اضغط زر المشاركة (⬆)
3. اختر "إضافة إلى الشاشة الرئيسية"
4. سيظهر كأيقونة على الشاشة الرئيسية

### على Firefox:
1. افتح `http://localhost:3000`
2. اضغط أيقونة التثبيت في شريط العنوان
3. أكد التثبيت

## ملفات PWA

| الملف | الوظيفة |
|-------|---------|
| `public/manifest.json` | بيانات التطبيق (الاسم، الأيقونات، الألوان، RTL) |
| `public/sw.js` | Service Worker للتخزين المؤقت والعمل بدون إنترنت |
| `web/src/app/layout.tsx` | Layout الرئيسي مع ربط manifest و Service Worker |
| `web/src/app/manifest.ts` | Next.js manifest route |

## ميزات العمل بدون إنترنت

Service Worker يستخدم استراتيجيتين:

1. **الملفات الثابتة** (cache-first):
   - HTML, CSS, JS, الصور
   - تُحمّل من الذاكرة المؤقتة أولاً
   - تحديث في الخلفية

2. **استدعاءات API** (network-first):
   - البحث، التصنيف، NER
   - يجرّب الشبكة أولاً
   - يرجع للذاكرة المؤقتة عند فشل الشبكة

## نشر PWA

### على Vercel (الأسهل):
```bash
cd intelli-file-manager/web
npx vercel
```

### على Netlify:
```bash
cd intelli-file-manager/web
npm run build
# ارفع مجلد out/ إلى Netlify
```

### على خادم خاص:
```bash
# استخدام Docker
docker build -t intellifile-web -f web/Dockerfile .
docker run -p 3000:3000 intellifile-web

# أو Nginx
server {
    listen 3000;
    server_name localhost;
    root /path/to/web/out;
    
    location /api/ {
        proxy_pass http://localhost:8421;
    }
}
```

## اختبار PWA

### Lighthouse Audit:
```bash
# في Chrome DevTools
# F12 → Lighthouse → Progressive Web App → Analyze

# أو عبر CLI
npx lighthouse http://localhost:3000 --only-categories=pwa
```

### اختبار Offline:
1. افتح DevTools → Application → Service Workers
2. فعّل "Offline" في Network tab
3. أعد تحميل الصفحة — يجب أن تعمل من الذاكرة المؤقتة

## التخصيص

### تغيير الأيقونات:
```bash
# ضع أيقوناتك في:
public/icons/icon-192.png
public/icons/icon-512.png

# أو أنشئها من أيقونة واحدة:
npx pwa-asset-generator public/icons/icon-512.png public/icons/
```

### تغيير الألوان:
عدّل `public/manifest.json`:
```json
{
  "background_color": "#1a1a2e",
  "theme_color": "#0f3460"
}
```
