# -*- coding: utf-8 -*-
"""
وحدة التمثيل المتجهي للنصوص
==============================

توليد التمثيلات المتجهية (embeddings) للنصوص باستخدام نماذج
sentence-transformers مع دعم التشغيل الكسول وحساب التشابه.
"""

from __future__ import annotations

import logging
import math
from typing import Any, List, Optional

# ─── إعداد التسجيل ──────────────────────────────────────────────
logger = logging.getLogger(__name__)


# ─── فئة محرك التمثيل المتجهي ───────────────────────────────────
class EmbeddingEngine:
    """
    محرك توليد التمثيلات المتجهية للنصوص.

    يستخدم نماذج sentence-transformers لتحويل النصوص إلى
    متجهات رقمية تُستخدم في البحث الدلالي وتحليل التشابه.

    يتم تحميل النموذج بشكل كسول (lazy) عند أول استخدام
    فعلي، وليس عند إنشاء الكائن.

    المعاملات
    ---------
    model_name : str
        اسم النموذج المستخدم (الافتراضي: all-MiniLM-L6-v2)
    device : str, اختياري
        جهاز التشغيل (cpu أو cuda)
    normalize_embeddings : bool
        هل تُطبع المتجهات (تُعيَّر لطول الوحدة)
    batch_size : int
        حجم الدفعة في المعالجة الدفعية
    show_progress : bool
        إظهار شريط التقدم أثناء المعالجة
    """

    # ─── حالة التحميل المشترك ──────────────────────────────────
    # تجنب إعادة تحميل النموذج عند إنشاء عدة كائنات
    _model_cache: dict[str, Any] = {}

    def __init__(
        self,
        model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
        device: Optional[str] = None,
        normalize_embeddings: bool = True,
        batch_size: int = 32,
        show_progress: bool = False,
    ) -> None:
        # ─── الإعدادات ────────────────────────────────────────
        self._model_name: str = model_name
        self._device: str | None = device
        self._normalize: bool = normalize_embeddings
        self._batch_size: int = batch_size
        self._show_progress: bool = show_progress

        # ─── حالة التحميل ─────────────────────────────────────
        self._model: Any = None
        self._is_loaded: bool = False
        self._load_error: Optional[str] = None

        # ─── عدادات ───────────────────────────────────────────
        self._total_encoded: int = 0
        self._total_comparisons: int = 0

        logger.info(
            "تم تهيئة محرك التمثيل المتجهي | النموذج=%s | التطبيع=%s",
            model_name,
            "مُفعّل" if normalize_embeddings else "معطّل",
        )

    # ─── خصائص عامة ─────────────────────────────────────────────
    @property
    def name(self) -> str:
        """اسم المحرك مع النموذج"""
        return f"EmbeddingEngine({self._model_name})"

    @property
    def model_name(self) -> str:
        """اسم النموذج الحالي"""
        return self._model_name

    @property
    def is_loaded(self) -> bool:
        """هل تم تحميل النموذج؟"""
        return self._is_loaded

    @property
    def dimension(self) -> Optional[int]:
        """أبعاد المتجهات (أو None إذا لم يُحمَّل النموذج)"""
        if self._model is not None:
            # sentence-transformers v5+ renamed the method
            _fn = getattr(self._model, "get_embedding_dimension", None) or getattr(self._model, "get_sentence_embedding_dimension", None)
            return _fn() if _fn else None
        return None

    @property
    def stats(self) -> dict[str, int]:
        """إحصائيات المحرك"""
        return {
            "total_encoded": self._total_encoded,
            "total_comparisons": self._total_comparisons,
            "model_loaded": self._is_loaded,
        }

    # ─── التحميل الكسول ─────────────────────────────────────────
    def _load_model(self) -> None:
        """
        تحميل النموذج بشكل كسول عند أول استخدام.

        يستخدم ذاكرة تخزين مؤقت على مستوى الفئة لتجنب
        إعادة تحميل نفس النموذج عدة مرات.

        الاستثناءات
        -----------
        ImportError
            إذا لم تكن مكتبة sentence-transformers مثبتة
        RuntimeError
            إذا فشل تحميل النموذج
        """
        if self._is_loaded:
            return

        if self._load_error is not None:
            raise RuntimeError(
                f"النموذج غير متاح بسبب خطأ سابق: {self._load_error}"
            )

        # ─── البحث في ذاكرة التخزين المؤقت ────────────────────
        cache_key: str = self._model_name
        if cache_key in self._model_cache:
            self._model = self._model_cache[cache_key]
            self._is_loaded = True
            logger.info(
                "تم تحميل النموذج '%s' من ذاكرة التخزين المؤقت",
                cache_key,
            )
            return

        # ─── محاولة الاستيراد ──────────────────────────────────
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            self._load_error = (
                "مكتبة sentence-transformers غير مثبتة. "
                "قم بتثبيتها: pip install sentence-transformers"
            )
            logger.error(self._load_error)
            raise ImportError(self._load_error) from exc

        # ─── تحميل النموذج ────────────────────────────────────
        try:
            logger.info("جاري تحميل النموذج '%s'...", self._model_name)

            load_kwargs: dict[str, Any] = {}
            if self._device is not None:
                load_kwargs["device"] = self._device

            self._model = SentenceTransformer(
                self._model_name,
                **load_kwargs,
            )

            # تطبيق إعدادات التطبيع
            if self._normalize and hasattr(self._model, "encode"):
                # سيتم تطبيق التطبيع عند التشفير
                pass

            self._is_loaded = True
            self._model_cache[cache_key] = self._model

            dim: Optional[int] = self.dimension
            logger.info(
                "تم تحميل النموذج '%s' بنجاح | الأبعاد: %s | الجهاز: %s",
                self._model_name,
                dim,
                getattr(self._model, "device", "غير معروف"),
            )

        except Exception as exc:
            self._load_error = f"فشل تحميل النموذج '{self._model_name}': {exc}"
            logger.error(self._load_error)
            raise RuntimeError(self._load_error) from exc

    def load(self) -> None:
        """
        تحميل النموذج يدوياً (بدون انتظار أول استخدام).

        مفيد لتحميل النموذج مسبقاً قبل بدء المعالجة.
        """
        self._load_model()

    def unload(self) -> None:
        """
        إلغاء تحميل النموذج وتحرير الذاكرة.

        ملاحظة: لا يزيل النموذج من ذاكرة التخزين المؤقت
        على مستوى الفئة.
        """
        if self._model is not None:
            try:
                # محاولة تحرير الذاكرة
                if hasattr(self._model, "cpu"):
                    self._model.cpu()
                del self._model
            except Exception as exc:
                logger.warning("خطأ أثناء إلغاء تحميل النموذج: %s", exc)
            finally:
                self._model = None
                self._is_loaded = False
                logger.info("تم إلغاء تحميل النموذج '%s'", self._model_name)

    @classmethod
    def clear_model_cache(cls) -> None:
        """مسح ذاكرة التخزين المؤقت للنماذج على مستوى الفئة"""
        cls._model_cache.clear()
        logger.info("تم مسح ذاكرة التخزين المؤقت للنماذج")

    # ─── التشفير (Encoding) ─────────────────────────────────────
    def encode(
        self,
        text: str,
        normalize: Optional[bool] = None,
    ) -> List[float]:
        """
        تحويل نص واحد إلى متجه رقمي.

        المعاملات
        ---------
        text : str
            النص المُراد تحويله
        normalize : bool, اختياري
            تجاوز إعداد التطبيع الافتراضي

        العائد
        -------
        list[float]
            المتجه الرقمي المُمثِّل للنص

        الاستثناءات
        -----------
        RuntimeError
            إذا لم يكن النموذج محملاً
        ValueError
            إذا كان النص فارغاً

        المثال
        -------
        >>> engine = EmbeddingEngine()
        >>> vec = engine.encode("مرحبا بالعالم")
        >>> len(vec)
        384
        """
        # ─── التحقق من المدخلات ────────────────────────────────
        if not text or not text.strip():
            raise ValueError("لا يمكن تشفير نص فارغ")

        # ─── التحميل الكسول ────────────────────────────────────
        self._load_model()

        # ─── تحديد إعداد التطبيع ──────────────────────────────
        should_normalize: bool = (
            normalize if normalize is not None else self._normalize
        )

        try:
            import numpy as np  # noqa: F401

            embedding = self._model.encode(
                text,
                normalize_embeddings=should_normalize,
                show_progress_bar=False,
                convert_to_numpy=True,
            )

            # تحويل NumPy إلى قائمة Python
            result: List[float] = embedding.tolist()

            self._total_encoded += 1
            logger.debug(
                "تم تشفير نص (طول=%d حرف) → متجه (بعد=%d)",
                len(text),
                len(result),
            )
            return result

        except ImportError:
            # بدون NumPy — استخدام القوائم مباشرة
            embedding = self._model.encode(
                text,
                normalize_embeddings=should_normalize,
                show_progress_bar=False,
                convert_to_numpy=False,
            )

            result = list(embedding)

            if should_normalize:
                norm = math.sqrt(sum(x * x for x in result))
                if norm > 0:
                    result = [x / norm for x in result]

            self._total_encoded += 1
            return result

        except Exception as exc:
            logger.error("فشل تشفير النص: %s", exc)
            raise RuntimeError(f"فشل تشفير النص: {exc}") from exc

    def encode_batch(
        self,
        texts: List[str],
        normalize: Optional[bool] = None,
        batch_size: Optional[int] = None,
    ) -> List[List[float]]:
        """
        تحويل مجموعة من النصوص إلى متجهات رقمية.

        المعاملات
        ---------
        texts : list[str]
            قائمة النصوص المُراد تحويلها
        normalize : bool, اختياري
            تجاوز إعداد التطبيع الافتراضي
        batch_size : int, اختياري
            تجاوز حجم الدفعة الافتراضي

        العائد
        -------
        list[list[float]]
            قائمة المتجهات الرقمية بالترتيب نفسه

        الاستثناءات
        -----------
        RuntimeError
            إذا لم يكن النموذج محمولاً
        ValueError
            إذا كانت القائمة فارغة

        المثال
        -------
        >>> engine = EmbeddingEngine()
        >>> vecs = engine.encode_batch(["مرحبا", "أهلا", "سلام"])
        >>> len(vecs)
        3
        """
        # ─── التحقق من المدخلات ────────────────────────────────
        if not texts:
            raise ValueError("قائمة النصوص فارغة")

        # ─── التحميل الكسول ────────────────────────────────────
        self._load_model()

        # ─── تحديد الإعدادات ──────────────────────────────────
        should_normalize: bool = (
            normalize if normalize is not None else self._normalize
        )
        effective_batch: int = batch_size or self._batch_size

        # ─── تصفية النصوص الفارغة ─────────────────────────────
        valid_indices: List[int] = []
        valid_texts: List[str] = []
        for i, t in enumerate(texts):
            if t and t.strip():
                valid_indices.append(i)
                valid_texts.append(t)

        if not valid_texts:
            logger.warning("جميع النصوص فارغة في الدفعة")
            return [[] for _ in texts]

        try:
            embeddings = self._model.encode(
                valid_texts,
                normalize_embeddings=should_normalize,
                batch_size=effective_batch,
                show_progress_bar=self._show_progress,
                convert_to_numpy=False,
            )

            # بناء النتيجة مع المحافظة على الترتيب الأصلي
            result_map: dict[int, List[float]] = {}
            for idx, emb in zip(valid_indices, embeddings):
                vec: List[float] = list(emb)
                if should_normalize and not isinstance(emb, list):
                    # تطبيع يدوي إذا لزم الأمر
                    norm = math.sqrt(sum(x * x for x in vec))
                    if norm > 0:
                        vec = [x / norm for x in vec]
                result_map[idx] = vec

            # إعادة الترتيب
            results: List[List[float]] = []
            for i in range(len(texts)):
                if i in result_map:
                    results.append(result_map[i])
                else:
                    results.append([])

            self._total_encoded += len(valid_texts)
            logger.info(
                "تم تشفير دفعة من %d نص (صالح: %d) → %d متجه",
                len(texts),
                len(valid_texts),
                len(results),
            )
            return results

        except Exception as exc:
            logger.error("فشل التشفير الدفعي: %s", exc)
            raise RuntimeError(f"فشل التشفير الدفعي: {exc}") from exc

    # ─── حساب التشابه ───────────────────────────────────────────
    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """
        حساب تشابه جيب التمام بين متجهين.

        المعاملات
        ---------
        vec1 : list[float]
            المتجه الأول
        vec2 : list[float]
            المتجه الثاني

        العائد
        -------
        float
            قيمة التشابه بين -1 و 1 (1 = متطابقان تماماً)
        """
        if len(vec1) != len(vec2):
            raise ValueError(
                f"أبعاد المتجهات غير متساوية: {len(vec1)} ≠ {len(vec2)}"
            )

        if len(vec1) == 0:
            return 0.0

        # حساب الجداء النقطي ومربعات الأطوال
        dot_product: float = 0.0
        norm1_sq: float = 0.0
        norm2_sq: float = 0.0

        for a, b in zip(vec1, vec2):
            dot_product += a * b
            norm1_sq += a * a
            norm2_sq += b * b

        norm1: float = math.sqrt(norm1_sq)
        norm2: float = math.sqrt(norm2_sq)

        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0

        # تقليص القيمة إلى النطاق [-1, 1] بسبب أخطاء الفاصلة العائمة
        cos_sim: float = dot_product / (norm1 * norm2)
        return max(-1.0, min(1.0, cos_sim))

    def similarity(
        self,
        text1: str,
        text2: str,
    ) -> float:
        """
        حساب التشابه الدلالي بين نصين.

        يحوّل النصين إلى متجهات ثم يحسب تشابه جيب التمام
        بينهما كقياس للتقارب الدلالي.

        المعاملات
        ---------
        text1 : str
            النص الأول
        text2 : str
            النص الثاني

        العائد
        -------
        float
            قيمة التشابه بين 0.0 (مختلفان تماماً) و 1.0 (متطابقان)

        الاستثناءات
        -----------
        ValueError
            إذا كان أي من النصين فارغاً

        المثال
        -------
        >>> engine = EmbeddingEngine()
        >>> engine.similarity("قطط", "هررة")
        0.92
        >>> engine.similarity("قطط", "برمجة")
        0.05
        """
        # ─── التحقق من المدخلات ────────────────────────────────
        if not text1 or not text1.strip():
            raise ValueError("النص الأول فارغ")
        if not text2 or not text2.strip():
            raise ValueError("النص الثاني فارغ")

        # ─── تحويل النصين إلى متجهات ─────────────────────────
        vec1: List[float] = self.encode(text1)
        vec2: List[float] = self.encode(text2)

        # ─── حساب التشابه ──────────────────────────────────────
        sim: float = self._cosine_similarity(vec1, vec2)
        # تحويل إلى نطاق [0, 1] للتشابه (التشابه الإيجابي فقط)
        positive_sim: float = max(0.0, sim)

        self._total_comparisons += 1
        logger.debug(
            "تشابه: '%s' ↔ '%s' = %.4f",
            text1[:30],
            text2[:30],
            positive_sim,
        )
        return positive_sim

    def similarity_vectors(
        self,
        vec1: List[float],
        vec2: List[float],
    ) -> float:
        """
        حساب التشابه بين متجهين جاهزين (بدون تشفير).

        مفيد عند وجود متجهات مُخزَّنة مسبقاً.

        المعاملات
        ---------
        vec1 : list[float]
            المتجه الأول
        vec2 : list[float]
            المتجه الثاني

        العائد
        -------
        float
            قيمة التشابه بين 0.0 و 1.0
        """
        raw_sim: float = self._cosine_similarity(vec1, vec2)
        return max(0.0, raw_sim)

    # ─── إدارة دورة الحياة ──────────────────────────────────────
    def __repr__(self) -> str:
        """تمثيل نصي للمحرك"""
        status: str = "مُحمَّل" if self._is_loaded else "غير مُحمَّل"
        dim_str: str = f", dim={self.dimension}" if self.dimension else ""
        return f"EmbeddingEngine(model='{self._model_name}', {status}{dim_str})"

    def __enter__(self) -> "EmbeddingEngine":
        """دعم بروتوكول context manager"""
        self._load_model()
        return self

    def __exit__(
        self,
        exc_type: Any | None,
        exc_val: Any | None,
        exc_tb: Any | None,
    ) -> None:
        """إغلاق تلقائي عند الخروج من السياق"""
        self.unload()
