"""المنظم الاستباقي - يتعلم من سلوك المستخدم"""
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class PredictiveOrganizer:
    """يتعلم من تصنيفات المستخدم ويتوقع تلقائياً"""

    def __init__(self, model_path: str = None):
        self._model_path = Path(model_path or "~/.intellifile/predictive_model.json").expanduser()
        self._features: Dict[str, Dict] = defaultdict(lambda: {
            "extension_counts": defaultdict(int),
            "name_keywords": defaultdict(int),
            "size_patterns": [],
            "user_actions": [],
        })
        self._predictions: Dict[str, str] = {}
        self.load_model()

    def record_action(self, filepath: str, category: str):
        """تسجيل تصنيف المستخدم للتعلم منه"""
        path = Path(filepath)
        ext = path.suffix.lower()
        name = path.stem.lower()
        size = path.stat().st_size if path.exists() else 0

        entry = self._features[str(path)]
        entry["extension_counts"][ext] += 1
        entry["user_actions"].append({
            "extension": ext,
            "name": name,
            "category": category,
            "size": size,
            "timestamp": __import__("time").time(),
        })

        # تحديث التوقعات
        self._predictions[str(path)] = category
        self._update_predictions()
        logger.info(f"تم تعلم: {path.name} -> {category}")

    def predict_category(self, filepath: str) -> Tuple[str, float]:
        """توقع التصنيف بناءً على التعلم السابق"""
        path = Path(filepath)
        ext = path.suffix.lower()
        name = path.stem.lower()

        scores = defaultdict(float)
        total_actions = sum(1 for f in self._features.values() if f["user_actions"])

        if total_actions == 0:
            return "أخرى", 0.0

        # وزن الامتداد
        ext_counts = defaultdict(float)
        for feat in self._features.values():
            for action in feat["user_actions"]:
                if action["extension"] == ext:
                    ext_counts[action["category"]] += 1

        for cat, count in ext_counts.items():
            scores[cat] += (count / total_actions) * 50

        # وزن الكلمات في الاسم
        for feat in self._features.values():
            for action in feat["user_actions"]:
                if action["extension"] == ext and action["name"] == name:
                    scores[action["category"]] += 30
                elif action["extension"] == ext:
                    # تشابه جزئي
                    common = len(set(name) & set(action["name"]))
                    if common > 2:
                        scores[action["category"]] += common * 5

        if scores:
            best_cat = max(scores, key=scores.get)
            confidence = min(scores[best_cat] / 50 * 100, 90)
            return best_cat, confidence

        return "أخرى", 0.0

    def _update_predictions(self):
        """تحديث التوقعات لجميع الملفات"""
        for filepath_str in self._features:
            path = Path(filepath_str)
            if path.exists():
                self._predictions[filepath_str] = self.predict_category(filepath_str)[0]

    def save_model(self):
        """حفظ النموذج"""
        self._model_path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        for fp, feat in self._features.items():
            data[fp] = {
                "extension_counts": dict(feat["extension_counts"]),
                "name_keywords": dict(feat["name_keywords"]),
                "user_actions": feat["user_actions"][-100:],  # آخر 100 عملية
            }
        with open(self._model_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"تم حفظ النموذج التنبؤي")

    def load_model(self) -> bool:
        """تحميل النموذج المحفوظ"""
        if not self._model_path.exists():
            return False
        try:
            with open(self._model_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for fp, feat in data.items():
                self._features[fp] = {
                    "extension_counts": defaultdict(int, feat.get("extension_counts", {})),
                    "name_keywords": defaultdict(int, feat.get("name_keywords", {})),
                    "user_actions": feat.get("user_actions", []),
                }
            logger.info(f"تم تحميل النموذج التنبؤي: {len(data)} ملف")
            return True
        except Exception as e:
            logger.error(f"خطأ في تحميل النموذج: {e}")
            return False

    @property
    def accuracy(self) -> float:
        """دقة التنبؤ (إذا توفرت بيانات اختبار)"""
        correct = sum(1 for fp, feat in self._features.items()
                     if feat["user_actions"] and
                     self._predictions.get(fp) == feat["user_actions"][-1]["category"])
        total = sum(1 for feat in self._features.values() if feat["user_actions"])
        return correct / total if total > 0 else 0.0
