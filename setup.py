from setuptools import setup, find_packages

setup(
    name="intellifile",
    version="1.0.0",
    description="تطبيق تصنيف الملفات الذكي - Smart File Classifier",
    author="Dr. Abdulmalek",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        # واجهة المستخدم
        "pyside6>=6.6.0",
        
        # تحليل الملفات
        "magika>=0.5.0",
        "Pillow>=10.0.0",
        "python-magic>=0.4.27",
        
        # الذكاء الاصطناعي ومعالجة اللغة
        "ollama>=0.1.0",
        "chromadb>=0.4.0",
        "langchain>=0.2.0",
        "sentence-transformers>=2.2.0",
        "transformers>=4.30.0",
        "torch>=2.0.0",
        
        # الرسوم البيانية والعلاقات
        "networkx>=3.1",
        
        # المراقبة والجدولة
        "watchdog>=3.0.0",
        "apscheduler>=3.10.0",
        
        # أدوات مساعدة
        "pydantic>=2.0.0",
        "rich>=13.0.0",
        "click>=8.0.0",
    ],
    entry_points={
        "console_scripts": [
            "intellifile=main:main",
            "intellifile-cli=cli:main",
        ],
    },
)
