#!/usr/bin/env bash
# سكريبت الإعداد السريع لـ IntelliFile
# Quick Setup Script for IntelliFile

set -e

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║        🚀 IntelliFile - سكريبت الإعداد السريع            ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# التحقق من وجود Python
if ! command -v python3 &> /dev/null; then
    echo "❌ الخطأ: Python 3 غير مثبت"
    echo "يرجى تثبيت Python 3.9 أو أحدث"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✅ Python $PYTHON_VERSION detected"

# التحقق من وجود pip
if ! command -v pip3 &> /dev/null; then
    echo "❌ الخطأ: pip غير مثبت"
    exit 1
fi

echo ""
echo "📦 تثبيت المتطلبات..."
pip3 install -r requirements.txt

echo ""
echo "🔧 تثبيت التطبيق في وضع التطوير..."
pip3 install -e .

echo ""
echo "📁 إنشاء مجلدات البيانات..."
mkdir -p ~/.intellifile/vectors
mkdir -p ~/.intellifile/logs

echo ""
echo "✅ اكتمل التثبيت بنجاح!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📚 طرق التشغيل:"
echo ""
echo "  1️⃣  واجهة سطر الأوامر العادية:"
echo "     python main.py --help"
echo ""
echo "  2️⃣  واجهة سطر الأوامر التفاعلية:"
echo "     python cli.py"
echo ""
echo "  3️⃣  بعد التثبيت الكامل:"
echo "     intellifile --help"
echo "     intellifile-cli"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 أمثلة سريعة:"
echo ""
echo "  • مسح مجلد:     python main.py --scan ~/Documents"
echo "  • بحث دلالي:    python main.py --search \"تقرير المبيعات\""
echo "  • تصنيف ملف:    python main.py --classify file.pdf"
echo "  • محادثة ذكية:  python main.py --chat \"ما هو محتوى هذا الملف؟\""
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚠️ ملاحظات مهمة:"
echo ""
echo "  • تأكد من تشغيل Ollama قبل الاستخدام:"
echo "    ollama serve"
echo ""
echo "  • حمل نموذج llama3.2 إذا لم يكن محملاً:"
echo "    ollama pull llama3.2"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🎉 استمتع بـ IntelliFile!"
echo ""
