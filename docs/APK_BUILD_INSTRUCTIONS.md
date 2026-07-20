# تعليمات بناء APK — IntelliFile Manager

## المتطلبات الأساسية

### على Linux (Ubuntu/Debian):
```bash
# تثبيت الاعتماديات النظامية
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip \
    build-essential git zip unzip openjdk-17-jdk \
    autoconf libtool pkg-config zlib1g-dev libncurses5-dev \
    libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev \
    libltdl-dev

# تثبيت Buildozer
pip install --user buildozer cython

# إضافة مسار pip للمستخدم
export PATH="$HOME/.local/bin:$PATH"
```

### على macOS:
```bash
brew install python@3.11
pip3 install buildozer cython
```

## بناء APK

### 1. استنساخ المستودع
```bash
git clone https://github.com/DrAbdulmalek/intelli-file-manager.git
cd intelli-file-manager
git checkout feat/omni-integration-v2
```

### 2. بناء APK (الطريقة المباشرة)
```bash
# البناء الأول سيستغرق 15-30 دقيقة (تحميل Android SDK/NDK)
buildozer android debug

# APK سيكون في:
ls -la bin/*.apk
```

### 3. بناء APK للإصدار (Release)
```bash
# إنشاء مفتاح التوقيع
keytool -genkey -v -keystore intellifile.keystore \
    -alias intellifile -keyalg RSA -keysize 2048 -validity 10000

# بناء APK موقّع
buildozer android release

# توقيع APK
jarsigner -verbose -sigalg SHA1withRSA -digestalg SHA1 \
    -keystore intellifile.keystore \
    bin/IntelliFile-2.0.0-release-unsigned.apk \
    intellifile
```

### 4. بناء عبر GitHub Actions (تلقائي)
```bash
# ادفع tag لإطلاق البناء
git tag v2.0.0
git push origin v2.0.0

# سيتم بناء APK تلقائياً ورفعه كـ artifact
# يمكن تنزيله من: Actions → Build Android APK → Artifacts
```

## تثبيت APK على الجهاز

```bash
# عبر ADB
adb install bin/IntelliFile-2.0.0-debug.apk

# أو انسخ الملف مباشرة للهاتف وثبّته
```

## بناء باستخدام Docker (بديل)

```bash
# استخدام صورة Buildozer Docker
docker pull kivy/buildozer

docker run --rm -v "$PWD":/home/user/hostcwd \
    kivy/buildozer android debug
```

## استكشاف الأخطاء

### مشكلة: "SDK not found"
```bash
buildozer android debug --verbose
# أو احذف وأعد البناء
rm -rf .buildozer/
buildozer android debug
```

### مشكلة: "NDK version mismatch"
```bash
# عدّل في buildozer.spec
android.ndk = 25b
```

### مشكلة: مساحة القرص
```bash
# البناء يحتاج ~10GB مساحة حرة
df -h .
# نظّف إن لزم
rm -rf .buildozer/android/platform/build
```

## المواصفات

| العنصر | القيمة |
|--------|--------|
| الحزمة | org.intellifile.intellifile |
| الحد الأدنى Android | 7.0 (API 24) |
| المستهدف Android | 13 (API 33) |
| البنية | arm64-v8a |
| Python | 3.11.6 |
| Kivy | 2.3.0 |
| حجم APK المتوقع | ~80-120 MB |
