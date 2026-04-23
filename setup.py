from setuptools import setup, find_packages

setup(
    name="intellifile",
    version="1.0.0",
    description="تطبيق تصنيف الملفات الذكي - Smart File Classifier",
    author="Dr. Abdulmalek",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "pyside6>=6.6.0",
        "magika>=0.5.0",
        "networkx>=3.1",
        "Pillow>=10.0.0",
        "watchdog>=3.0.0",
        "apscheduler>=3.10.0",
    ],
    entry_points={
        "console_scripts": [
            "intellifile=src.main:main",
        ],
    },
)
