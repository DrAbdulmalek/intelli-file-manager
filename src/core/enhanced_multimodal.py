# src/core/enhanced_multimodal.py
from __future__ import annotations
import logging
from pathlib import Path
from typing import Dict, Any

# استيراد المحرك المركزي الموحد
try:
    from ocr_core import OCRProcessor, OCRConfig
    OCR_CORE_AVAILABLE = True
except ImportError:
    OCR_CORE_AVAILABLE = False
    logging.warning("ocr-core غير مثبت. سيتم تعطيل ميزات OCR المتقدمة.")

logger = logging.getLogger(__name__)

class EnhancedMultimodalProcessor:
    def __init__(self, config: Dict[str, Any] | None = None):
        self.config = config or {}
        self.ocr_engine = None
        
        if OCR_CORE_AVAILABLE:
            # تهيئة المحرك المركزي مع الإعدادات الآمنة
            ocr_config = OCRConfig(
                languages=self.config.get("languages", ["ara", "eng"]),
                enable_preprocessing=self.config.get("enable_preprocessing", True),
                enable_post_correction=self.config.get("enable_post_correction", True)
            )
            self.ocr_engine = OCRProcessor(config=ocr_config)
            logger.info("تم تهيئة محرك ocr-core المركزي بنجاح")
        else:
            logger.warning("يعمل النظام في الوضع الخفيف (Lightweight Mode) بدون OCR متقدم")

    def process_image(self, filepath: str | Path) -> Dict[str, Any]:
        path = Path(filepath)
        result = {"path": str(path), "type": "image", "success": False}

        if not self.ocr_engine:
            result["error"] = "محرك OCR غير متاح. يرجى تثبيت ocr-core."
            return result

        try:
            # استدعاء واحد موحد وآمن للمحرك المركزي
            ocr_result = self.ocr_engine.process_file(path)
            
            result["extracted_text"] = ocr_result.text
            result["confidence"] = ocr_result.confidence
            result["engine_used"] = ocr_result.metadata.get("best_engine", "unknown")
            result["success"] = True
            
            # حارس أمان: المعالجة اللاحقة فقط إذا كانت الثقة مقبولة
            if ocr_result.confidence > 0.75:
                result["needs_review"] = False
            else:
                result["needs_review"] = True
                result["warning"] = "ثقة الاستخراج منخفضة، يُنصح بالمراجعة اليدوية"
                
        except Exception as e:
            logger.error(f"فشل معالجة الملف {path.name}: {e}")
            result["error"] = str(e)

        return result
