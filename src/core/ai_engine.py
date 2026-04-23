"""محرك الذكاء الاصطناعي - تكامل مع Ollama المحلي"""
import logging
from typing import Optional
from .config import Config

logger = logging.getLogger(__name__)


class AIEngine:
    """محرك الذكاء الاصطناعي المحلي باستخدام Ollama"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self._ollama = None

    def _get_ollama(self):
        """تهيئة Ollama إذا لم يتم بعد"""
        if self._ollama is None:
            try:
                import ollama
                self._ollama = ollama.Client(host=self.config.ollama_url)
            except ImportError:
                logger.error("مكتبة ollama غير مثبتة")
                return None
            except Exception as e:
                logger.error(f"خطأ في الاتصال بـ Ollama: {e}")
                return None
        return self._ollama

    def is_ollama_running(self) -> bool:
        """التحقق من أن Ollama يعمل"""
        try:
            import requests
            resp = requests.get(f"{self.config.ollama_url}/api/tags", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list:
        """قائمة النماذج المتاحة"""
        client = self._get_ollama()
        if not client:
            return []
        try:
            models = client.list()
            return [m.model for m in models] if models else []
        except Exception as e:
            logger.error(f"خطأ في عرض النماذج: {e}")
            return []

    def summarize_file(self, filepath: str) -> str:
        """تلخيص محتوى ملف"""
        client = self._get_ollama()
        if not client:
            return "خطأ: Ollama غير متاح"

        try:
            # قراءة محتوى الملف
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()[:4000]

            prompt = f"لخّص المحتوى التالي باختصار (3-5 جمل):\n\n{content}"
            response = client.chat(self.config.ai_model, messages=[
                {"role": "system", "content": "أنت مساعد ذكي. أجب بالعربية."},
                {"role": "user", "content": prompt}
            ])
            return response["message"]["content"]
        except Exception as e:
            logger.error(f"خطأ في التلخيص: {e}")
            return f"خطأ: {e}"

    def suggest_category(self, filepath: str, filename: str) -> str:
        """اقتراح تصنيف للملف"""
        client = self._get_ollama()
        if not client:
            return "أخرى"

        categories = ", ".join(self.config.categories)
        prompt = (
            f"بناءً على اسم الملف '{filename}'، اختر التصنيف الأنسب من: {categories}\n"
            f"أجب فقط باسم التصنيف بدون أي شرح."
        )
        try:
            response = client.chat(self.config.ai_model, messages=[
                {"role": "system", "content": "أنت مصنف ملفات ذكي. أجب بالعربية."},
                {"role": "user", "content": prompt}
            ])
            suggestion = response["message"]["content"].strip()
            # التحقق من أن الاقتراح ضمن الفئات
            for cat in self.config.categories:
                if cat in suggestion:
                    return cat
            return "أخرى"
        except Exception as e:
            logger.error(f"خطأ في اقتراح التصنيف: {e}")
            return "أخرى"

    def chat(self, message: str, context: str = "") -> str:
        """محادثة مع المساعد الذكي"""
        client = self._get_ollama()
        if not client:
            return "خطأ: Ollama غير متاح. تأكد من تشغيله بالأمر: ollama serve"

        system_msg = "أنت مساعد IntelliFile الذكي. أجب بالعربية. ساعد المستخدم في إدارة الملفات."
        if context:
            system_msg += f"\nسياق الملفات:\n{context}"

        try:
            response = client.chat(self.config.ai_model, messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": message}
            ])
            return response["message"]["content"]
        except Exception as e:
            logger.error(f"خطأ في المحادثة: {e}")
            return f"خطأ: {e}"

    def extract_keywords(self, filepath: str) -> list:
        """استخراج كلمات مفتاحية من ملف"""
        client = self._get_ollama()
        if not client:
            return []

        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()[:2000]

            response = client.chat(self.config.ai_model, messages=[
                {"role": "system", "content": "أنت محلل نصوص. أجب بقائمة كلمات مفتاحية مفصولة بفواصل."},
                {"role": "user", "content": f"استخرج 5-10 كلمات مفتاحية من:\n{content}"}
            ])
            text = response["message"]["content"]
            return [kw.strip() for kw in text.replace("،", ",").split(",") if kw.strip()][:10]
        except Exception as e:
            logger.error(f"خطأ في استخراج الكلمات: {e}")
            return []
