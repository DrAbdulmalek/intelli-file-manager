"""
نظام السجلات لـ IntelliFile
Logging System for IntelliFile
"""

import logging
from pathlib import Path
from datetime import datetime


def setup_logger(name: str = "intellifile", level: int = logging.INFO) -> logging.Logger:
    """
    إعداد وتكوين نظام السجلات
    
    Args:
        name: اسم السجل
        level: مستوى السجلات
        
    Returns:
        Logger: كائن السجل المهيأ
    """
    
    # إنشاء مجلد السجلات
    log_dir = Path.home() / ".intellifile" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # إنشاء ملف سجل بتاريخ اليوم
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir / f"intellifile_{today}.log"
    
    # تكوين السجل
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # منع إضافة معالجات متعددة
    if logger.handlers:
        return logger
    
    # تنسيق السجلات
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # معالج ملف للسجلات التفصيلية
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # معالج وحدة تحكم للسجلات العامة
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    
    # تنسيق أبسط للوحدة التحكم
    console_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger


# إنشاء سجل عام
logger = setup_logger()
