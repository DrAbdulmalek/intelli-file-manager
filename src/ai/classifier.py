# -*- coding: utf-8 -*-
"""
وحدة تصنيف الملفات باستخدام الذكاء الاصطناعي
=============================================

تصنيف الملفات تلقائياً باستخدام نماذج Ollama المحلية
مع إمكانية التخزين المؤقت عبر ChromaDB ودعم التصنيف الدفعي.
"""

from __future__ import annotations

import json
import logging
import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

# ─── إعداد التسجيل ──────────────────────────────────────────────
logger = logging.getLogger(__name__)


# ─── أنواع البيانات ─────────────────────────────────────────────
@dataclass
class ClassificationResult:
    """نتيجة تصنيف ملف واحد"""

    category: str
    confidence: float
    filename: str = ""
    file_type: str = ""
    model: str = ""
    cached: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """تحويل النتيجة إلى قاموس"""
        return {
            "category": self.category,
            "confidence": self.confidence,
            "filename": self.filename,
            "file_type": self.file_type,
            "model": self.model,
            "cached": self.cached,
        }


@dataclass
class FileInput:
    """بيانات الملف المُدخل للتصنيف"""

    content: str
    file_type: str = ""
    filename: str = ""


# ─── فئة التصنيف الرئيسية ──────────────────────────────────────
class AIClassifier:
    """
    مصنّف ذكي للملفات يعتمد على Ollama.

    يقوم بتصنيف الملفات تلقائياً إلى فئات محددة بناءً على
    محتواها ونوعها واسمها، مع دعم التخزين المؤقت والإسناد.

    المعاملات
    ---------
    model : str
        اسم النموذج المستخدم في Ollama (الافتراضي: gemma3)
    ollama_url : str
        عنوان خادم Ollama المحلي
    chroma_collection : Any, اختياري
        مجموعة ChromaDB للتخزين المؤقت للتصنيفات
    timeout : float
        مهلة الاتصال بالخادم بالثواني
    max_retries : int
        عدد محاولات إعادة المحاولة عند الفشل
    """

    # القوالب الافتراضية
    _DEFAULT_SYSTEM_PROMPT: str = (
        "أنت مساعد متخصص في تصنيف الملفات. "
        "قم بتحليل المحتوى المقدم وتصنيفه إلى أحد الفئات التالية:\n"
        "- documents: مستندات نصية وتقارير\n"
        "- images: صور ورسومات\n"
        "- code: ملفات برمجية وأكواد مصدرية\n"
        "- data: بيانات وجداول وملفات CSV/JSON\n"
        "- audio: ملفات صوتية\n"
        "- video: ملفات فيديو\n"
        "- archives: ملفات مضغوطة\n"
        "- config: ملفات إعدادات\n"
        "- other: أي ملفات أخرى\n\n"
        "أجب فقط بصيغة JSON التالية بدون أي نص إضافي:\n"
        '{"category": "الفئة", "confidence": 0.95}'
    )

    def __init__(
        self,
        model: str = "gemma3",
        ollama_url: str = "http://localhost:11434",
        chroma_collection: Any | None = None,
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        # ─── الإعدادات الأساسية ───────────────────────────────
        self.model: str = model
        self.ollama_url: str = ollama_url.rstrip("/")
        self.timeout: float = timeout
        self.max_retries: int = max_retries

        # ─── التخزين المؤقت ───────────────────────────────────
        self._chroma_collection: Any | None = chroma_collection
        self._cache_enabled: bool = chroma_collection is not None

        # ─── عميل HTTP ────────────────────────────────────────
        self._client: httpx.Client = httpx.Client(
            base_url=self.ollama_url,
            timeout=httpx.Timeout(self.timeout),
        )

        # ─── عداد التصنيفات ───────────────────────────────────
        self._classification_count: int = 0
        self._cache_hits: int = 0

        logger.info(
            "تم تهيئة المصنّف | النموذج=%s | العنوان=%s | التخزين المؤقت=%s",
            self.model,
            self.ollama_url,
            "مُفعّل" if self._cache_enabled else "معطّل",
        )

    # ─── خصائص عامة ─────────────────────────────────────────────
    @property
    def name(self) -> str:
        """اسم المصنّف"""
        return f"AIClassifier({self.model})"

    @property
    def is_cache_enabled(self) -> bool:
        """هل التخزين المؤقت مُفعّل؟"""
        return self._cache_enabled

    @property
    def stats(self) -> Dict[str, int]:
        """إحصائيات التصنيف"""
        return {
            "total_classifications": self._classification_count,
            "cache_hits": self._cache_hits,
        }

    # ─── الطرق الداخلية ─────────────────────────────────────────
    def _generate_cache_key(
        self,
        file_content: str,
        file_type: str,
        filename: str,
    ) -> str:
        """
        إنشاء مفتاح فريد للتخزين المؤقت.

        المعاملات
        ---------
        file_content : str
            محتوى الملف
        file_type : str
            نوع الملف
        filename : str
            اسم الملف

        العائد
        -------
        str
            المفتاح الفريد (هاش SHA-256)
        """
        raw_key = f"{self.model}:{file_type}:{filename}:{file_content[:5000]}"
        return hashlib.sha256(raw_key.encode("utf-8", errors="replace")).hexdigest()

    def _check_cache(
        self,
        cache_key: str,
    ) -> Optional[ClassificationResult]:
        """
        البحث في التخزين المؤقت عن نتيجة سابقة.

        المعاملات
        ---------
        cache_key : str
            مفتاح البحث

        العائد
        -------
        ClassificationResult أو None
        """
        if not self._cache_enabled or self._chroma_collection is None:
            return None

        try:
            results = self._chroma_collection.get(
                ids=[cache_key],
                include=["metadatas"],
            )
            if results and results["metadatas"] and len(results["metadatas"]) > 0:
                meta = results["metadatas"][0]
                self._cache_hits += 1
                logger.debug("ضربة تخزين مؤقت للملف: %s", meta.get("filename", ""))
                return ClassificationResult(
                    category=meta.get("category", "unknown"),
                    confidence=float(meta.get("confidence", 0.0)),
                    filename=meta.get("filename", ""),
                    file_type=meta.get("file_type", ""),
                    model=meta.get("model", self.model),
                    cached=True,
                )
        except Exception as exc:
            logger.warning("خطأ في البحث بالتخزين المؤقت: %s", exc)

        return None

    def _store_cache(
        self,
        cache_key: str,
        result: ClassificationResult,
        embedding: Optional[List[float]] = None,
    ) -> None:
        """
        تخزين نتيجة التصنيف في التخزين المؤقت.

        المعاملات
        ---------
        cache_key : str
            مفتاح التخزين
        result : ClassificationResult
            نتيجة التصنيف
        embedding : list[float], اختياري
            التمثيل المتجهي للمحتوى
        """
        if not self._cache_enabled or self._chroma_collection is None:
            return

        try:
            metadata: Dict[str, Any] = {
                "category": result.category,
                "confidence": result.confidence,
                "filename": result.filename,
                "file_type": result.file_type,
                "model": result.model,
            }

            self._chroma_collection.upsert(
                ids=[cache_key],
                documents=[f"{result.filename}:{result.category}"],
                metadatas=[metadata],
                embeddings=[embedding] if embedding else None,
            )
            logger.debug("تم تخزين نتيجة التصنيف مؤقتاً: %s", result.filename)
        except Exception as exc:
            logger.warning("خطأ في التخزين المؤقت: %s", exc)

    def _build_prompt(
        self,
        file_content: str,
        file_type: str,
        filename: str,
    ) -> str:
        """
        بناء الموجه (prompt) للنموذج.

        المعاملات
        ---------
        file_content : str
            محتوى الملف
        file_type : str
            نوع الملف
        filename : str
            اسم الملف

        العائد
        -------
        str
            الموجه المُعد للنموذج
        """
        # اقتطاع المحتوى الطويل لتجنب تجاوز الحد
        max_length: int = 8000
        truncated_content: str = (
            file_content[:max_length] + "..."
            if len(file_content) > max_length
            else file_content
        )

        prompt: str = (
            f"اسم الملف: {filename}\n"
            f"نوع الملف: {file_type}\n"
            f"المحتوى:\n```\n{truncated_content}\n```\n\n"
            f"صنّف هذا الملف."
        )
        return prompt

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        تحليل استجابة النموذج واستخراج التصنيف.

        المعاملات
        ---------
        response_text : str
            نص الاستجابة من النموذج

        العائد
        -------
        dict
            قاموس يحتوي على {category, confidence}

        الاستثناءات
        -----------
        ValueError
            إذا تعذر تحليل الاستجابة
        """
        # تنظيف النص من المحتوى الزائد
        cleaned: str = response_text.strip()

        # محاولة استخراج JSON من النص
        # البحث عن أول { وآخر }
        start_idx: int = cleaned.find("{")
        end_idx: int = cleaned.rfind("}")

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str: str = cleaned[start_idx : end_idx + 1]
            try:
                data: Dict[str, Any] = json.loads(json_str)
                category: str = str(data.get("category", "other")).strip().lower()
                confidence: float = float(data.get("confidence", 0.0))

                # التحقق من صحة الثقة
                if not (0.0 <= confidence <= 1.0):
                    logger.warning(
                        "قيمة الثقة غير صالحة: %.2f، تعديل إلى النطاق [0, 1]",
                        confidence,
                    )
                    confidence = max(0.0, min(1.0, confidence))

                return {"category": category, "confidence": confidence}

            except json.JSONDecodeError as exc:
                logger.warning("فشل تحليل JSON: %s | النص: %s", exc, json_str)

        # محاولة ثانية: البحث عن أنماط نصية شائعة
        import re

        category_match = re.search(r"category['\"]\s*:\s*['\"](\w+)['\"]", cleaned)
        confidence_match = re.search(r"confidence['\"]\s*:\s*([\d.]+)", cleaned)

        if category_match:
            cat: str = category_match.group(1).lower()
            conf: float = (
                float(confidence_match.group(1))
                if confidence_match
                else 0.7
            )
            return {"category": cat, "confidence": conf}

        # إذا فشلت كل المحاولات
        raise ValueError(
            f"تعذر تحليل استجابة النموذج: {response_text[:200]}"
        )

    def _call_ollama(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        استدعاء واجهة Ollama وإرجاع الاستجابة.

        المعاملات
        ---------
        prompt : str
            الموجه المُرسل للنموذج
        system_prompt : str, اختياري
            موجه النظام

        العائد
        -------
        str
            نص الاستجابة من النموذج

        الاستثناءات
        -----------
        ConnectionError
            عند فشل الاتصال بخادم Ollama
        RuntimeError
            عند فشل الاستجابة بعد جميع المحاولات
        """
        sys_prompt: str = system_prompt or self._DEFAULT_SYSTEM_PROMPT
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response: httpx.Response = self._client.post(
                    "/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "system": sys_prompt,
                        "stream": False,
                        "format": "json",
                        "options": {
                            "temperature": 0.1,
                            "top_p": 0.9,
                        },
                    },
                )
                response.raise_for_status()

                data: Dict[str, Any] = response.json()
                generated_text: str = data.get("response", "").strip()

                if not generated_text:
                    raise RuntimeError("استجابة فارغة من النموذج")

                logger.debug(
                    "استجابة النموذج (محاولة %d/%d): %s",
                    attempt,
                    self.max_retries,
                    generated_text[:200],
                )
                return generated_text

            except httpx.ConnectError as exc:
                last_error = exc
                logger.error(
                    "فشل الاتصال بخادم Ollama في المحاولة %d/%d: %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    import time

                    time.sleep(2 ** attempt)  # انتظار أسّي

            except httpx.HTTPStatusError as exc:
                last_error = exc
                logger.error(
                    "خطأ HTTP %d في المحاولة %d/%d: %s",
                    exc.response.status_code,
                    attempt,
                    self.max_retries,
                    exc,
                )
                if exc.response.status_code == 404:
                    raise ConnectionError(
                        f"النموذج '{self.model}' غير موجود. "
                        f"تأكد من تحميله: ollama pull {self.model}"
                    ) from exc

            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning(
                    "انتهت مهلة الاتصال في المحاولة %d/%d",
                    attempt,
                    self.max_retries,
                )

            except Exception as exc:
                last_error = exc
                logger.error("خطأ غير متوقع: %s", exc)

        raise RuntimeError(
            f"فشل استدعاء النموذج بعد {self.max_retries} محاولات: {last_error}"
        )

    # ─── الواجهة العامة ──────────────────────────────────────────
    def classify(
        self,
        file_content: str,
        file_type: str = "",
        filename: str = "",
    ) -> Dict[str, Any]:
        """
        تصنيف ملف واحد.

        يقوم بتحليل محتوى الملف باستخدام نموذج Ollama وتحديد
        فئته المناسبة مع مستوى الثقة.

        المعاملات
        ---------
        file_content : str
            المحتوى النصي للملف
        file_type : str
            نوع/امتداد الملف (مثال: .pdf, .py, .txt)
        filename : str
            اسم الملف

        العائد
        -------
        dict
            قاموس يحتوي على:
            - category (str): الفئة المحددة
            - confidence (float): مستوى الثقة (0.0 - 1.0)
            - filename (str): اسم الملف
            - file_type (str): نوع الملف
            - model (str): النموذج المستخدم
            - cached (bool): هل النتيجة من التخزين المؤقت

        المثال
        -------
        >>> classifier = AIClassifier()
        >>> result = classifier.classify("print('Hello')", ".py", "main.py")
        >>> print(result["category"])
        'code'
        """
        # ─── التحقق من المدخلات ────────────────────────────────
        if not file_content or not file_content.strip():
            logger.warning("محتوى فارغ للملف: %s", filename)
            return {
                "category": "unknown",
                "confidence": 0.0,
                "filename": filename,
                "file_type": file_type,
                "model": self.model,
                "cached": False,
            }

        # ─── البحث في التخزين المؤقت ───────────────────────────
        cache_key: str = self._generate_cache_key(file_content, file_type, filename)
        cached_result: Optional[ClassificationResult] = self._check_cache(cache_key)
        if cached_result is not None:
            return cached_result.to_dict()

        # ─── بناء الموجه واستدعاء النموذج ───────────────────────
        prompt: str = self._build_prompt(file_content, file_type, filename)

        try:
            response_text: str = self._call_ollama(prompt)
            parsed: Dict[str, Any] = self._parse_response(response_text)

            result: ClassificationResult = ClassificationResult(
                category=parsed["category"],
                confidence=parsed["confidence"],
                filename=filename,
                file_type=file_type,
                model=self.model,
                cached=False,
            )

            # ─── تخزين النتيجة مؤقتاً ──────────────────────────
            self._store_cache(cache_key, result)

            self._classification_count += 1
            logger.info(
                "تصنيف: '%s' → %s (ثقة: %.1f%%)",
                filename or "بدون اسم",
                result.category,
                result.confidence * 100,
            )

            return result.to_dict()

        except (ConnectionError, RuntimeError, ValueError) as exc:
            logger.error("فشل تصنيف الملف '%s': %s", filename, exc)
            return {
                "category": "error",
                "confidence": 0.0,
                "filename": filename,
                "file_type": file_type,
                "model": self.model,
                "error": str(exc),
                "cached": False,
            }

    def batch_classify(
        self,
        files: List[Dict[str, str]],
    ) -> List[Dict[str, Any]]:
        """
        تصنيف مجموعة من الملفات دفعة واحدة.

        المعاملات
        ---------
        files : list[dict]
            قائمة بأقوامس الملفات، كل قاموس يحتوي على:
            - content (str): محتوى الملف (مطلوب)
            - type (str): نوع الملف (اختياري)
            - filename (str): اسم الملف (اختياري)

        العائد
        -------
        list[dict]
            قائمة نتائج التصنيف بالترتيب نفسه

        المثال
        -------
        >>> files = [
        ...     {"content": "import os", "type": ".py", "filename": "os_mod.py"},
        ...     {"content": "# Title\\nHello", "type": ".md", "filename": "readme.md"},
        ... ]
        >>> results = classifier.batch_classify(files)
        """
        if not files:
            logger.warning("قائمة ملفات فارغة للتصنيف الدفعي")
            return []

        logger.info(
            "بدء التصنيف الدفعي لـ %d ملف باستخدام النموذج '%s'",
            len(files),
            self.model,
        )

        results: List[Dict[str, Any]] = []
        success_count: int = 0
        error_count: int = 0

        for idx, file_data in enumerate(files):
            # استخراج البيانات مع القيم الافتراضية
            content: str = str(file_data.get("content", "") or "")
            file_type: str = str(file_data.get("type", "") or "")
            fname: str = str(file_data.get("filename", "") or f"file_{idx}")

            result: Dict[str, Any] = self.classify(content, file_type, fname)
            results.append(result)

            if result.get("category") == "error":
                error_count += 1
            else:
                success_count += 1

        logger.info(
            "اكتمل التصنيف الدفعي | نجح: %d | أخطاء: %d | إجمالي: %d",
            success_count,
            error_count,
            len(files),
        )

        return results

    # ─── إدارة دورة الحياة ──────────────────────────────────────
    def check_connection(self) -> bool:
        """
        التحقق من اتصال خادم Ollama.

        العائد
        -------
        bool
            True إذا كان الخادم متصلاً، False خلاف ذلك
        """
        try:
            response: httpx.Response = self._client.get("/api/tags", timeout=5.0)
            if response.status_code == 200:
                models: List[Dict[str, Any]] = response.json().get("models", [])
                model_names: List[str] = [m.get("name", "") for m in models]
                logger.info(
                    "الاتصال بخادم Ollama ناجح | النماذج المتاحة: %s",
                    model_names,
                )
                return True
            return False
        except Exception as exc:
            logger.error("فشل الاتصال بخادم Ollama: %s", exc)
            return False

    def close(self) -> None:
        """إغلاق اتصالات الشبكة وإطلاق الموارد"""
        try:
            self._client.close()
            logger.info("تم إغلاق المصنّف بنجاح")
        except Exception as exc:
            logger.error("خطأ أثناء إغلاق المصنّف: %s", exc)

    def __enter__(self) -> "AIClassifier":
        """دعم بروتوكول context manager"""
        return self

    def __exit__(
        self,
        exc_type: Any | None,
        exc_val: Any | None,
        exc_tb: Any | None,
    ) -> None:
        """إغلاق تلقائي عند الخروج من السياق"""
        self.close()

    def __repr__(self) -> str:
        """تمثيل نصي للمصنّف"""
        return (
            f"AIClassifier(model='{self.model}', "
            f"url='{self.ollama_url}', "
            f"cache={'on' if self._cache_enabled else 'off'})"
        )
