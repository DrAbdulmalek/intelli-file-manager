from setuptools import setup, find_packages

setup(
    name="intellifile",
    version="1.0.0",
    description="تطبيق تصنيف الملفات الذكي - Smart File Classifier",
    author="Dr. Abdulmalek",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        # Core
        "pyside6>=6.6.0",
        "magika>=0.5.0",
        "httpx>=0.24.0",
        "watchdog>=3.0.0",
        "apscheduler>=3.10.0",
        "networkx>=3.1",
        "Pillow>=10.0.0",
        # AI / Machine Learning
        "ollama>=0.1.0",
        "chromadb>=0.4.0",
        "langchain>=0.2.0",
        "sentence-transformers>=2.2.0",
        "numpy>=1.24.0",
        "scipy>=1.10.0",
        # Document Processing
        "pdfplumber>=0.10.0",
        "python-docx>=1.0.0",
        "openpyxl>=3.1.2",
        "python-pptx>=0.6.21",
    ],
    extras_require={
        "voice": [
            "pyttsx3>=2.90",
            "SpeechRecognition>=3.10.0",
            "pyaudio>=0.2.12",
        ],
        "extras": [
            "python-magic>=0.4.27",
            "plotly>=5.18.0",
            "pandas>=2.0.0",
        ],
        "all": [
            "pyttsx3>=2.90",
            "SpeechRecognition>=3.10.0",
            "pyaudio>=0.2.12",
            "python-magic>=0.4.27",
            "plotly>=5.18.0",
            "pandas>=2.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "intellifile=src.main:main",
            "intellifile-cli=cli:main",
        ],
    },
)
