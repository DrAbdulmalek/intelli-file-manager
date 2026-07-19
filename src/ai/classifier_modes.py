"""
Classifier Modes — adds rule-based + hybrid classification on top of AI-only.

This is a STUB file proposing the API for the multi-mode classifier described
in docs/DEVELOPMENT_ROADMAP.md (Task 1.3).

When implementing, decide whether to:
  (a) Merge ClassificationMode + rule/hybrid logic into src/ai/classifier.py, or
  (b) Keep this as a companion module.

Inspired by: AmazeSort (rule-based / hybrid / AI-only modes).
"""

import json
import os
import re
from enum import Enum
from typing import Dict, Any, Optional, List


class ClassificationMode(Enum):
    """Classifier operating mode."""
    RULE_BASED = "rule_based"   # Only extension/regex rules
    HYBRID = "hybrid"           # Rules first, AI fallback when confidence < threshold
    AI_ONLY = "ai_only"         # Always use AI (current behavior)


class FileClassifierModes:
    """
    File classifier with three operating modes (inspired by AmazeSort).

    Default mode is HYBRID — rules first, AI fallback.
    """

    DEFAULT_RULES = {
        "extensions": {
            ".pdf": "Documents",
            ".docx": "Documents",
            ".doc": "Documents",
            ".txt": "Documents",
            ".md": "Documents",
            ".jpg": "Images",
            ".jpeg": "Images",
            ".png": "Images",
            ".gif": "Images",
            ".mp3": "Audio",
            ".wav": "Audio",
            ".mp4": "Video",
            ".mov": "Video",
            ".py": "Code/Python",
            ".js": "Code/JavaScript",
            ".ts": "Code/TypeScript",
            ".rs": "Code/Rust",
            ".go": "Code/Go",
        },
        "patterns": {
            r".*report.*\.pdf$": "Reports",
            r".*photo.*\.(jpg|png)$": "Photos",
            r".*invoice.*\.pdf$": "Finance/Invoices",
            r".*cv.*\.pdf$": "Personal/CV",
        },
    }

    def __init__(
        self,
        ai_client=None,
        rules_file: Optional[str] = None,
        mode: ClassificationMode = ClassificationMode.HYBRID,
        hybrid_confidence_threshold: float = 0.8,
    ):
        self.ai_client = ai_client
        self.rules = self._load_rules(rules_file)
        self.mode = mode
        self.threshold = hybrid_confidence_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def classify(
        self,
        file_path: str,
        content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Classify a file according to the current mode."""
        if self.mode == ClassificationMode.RULE_BASED:
            return self._rule_based_classify(file_path)
        if self.mode == ClassificationMode.AI_ONLY:
            return self._ai_classify(file_path, content)
        return self._hybrid_classify(file_path, content)

    def set_mode(self, mode: ClassificationMode) -> None:
        self.mode = mode

    # ------------------------------------------------------------------
    # Rule-based
    # ------------------------------------------------------------------
    def _rule_based_classify(self, file_path: str) -> Dict[str, Any]:
        """Classify using only extension + regex rules."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext in self.rules["extensions"]:
            return {
                "category": self.rules["extensions"][ext],
                "confidence": 1.0,
                "method": "rule_based",
            }

        for pattern, category in self.rules["patterns"].items():
            if re.match(pattern, file_path, re.IGNORECASE):
                return {
                    "category": category,
                    "confidence": 0.9,
                    "method": "rule_based",
                }

        return {
            "category": "Uncategorized",
            "confidence": 0.0,
            "method": "rule_based",
        }

    # ------------------------------------------------------------------
    # Hybrid
    # ------------------------------------------------------------------
    def _hybrid_classify(
        self,
        file_path: str,
        content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Rules first; AI fallback when rule confidence is below threshold."""
        rule_result = self._rule_based_classify(file_path)

        if rule_result["confidence"] >= self.threshold:
            return rule_result

        ai_result = self._ai_classify(file_path, content)

        return {
            "category": ai_result.get("category", rule_result["category"]),
            "confidence": max(rule_result["confidence"], ai_result.get("confidence", 0.0)),
            "method": "hybrid",
            "rule_based_category": rule_result["category"],
            "ai_category": ai_result.get("category"),
        }

    # ------------------------------------------------------------------
    # AI-only (delegates to existing classifier)
    # ------------------------------------------------------------------
    def _ai_classify(
        self,
        file_path: str,
        content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Delegate to the existing AI classifier in src/ai/classifier.py.

        TODO: wire to the actual ai_client.classify() call.
        """
        if self.ai_client is None:
            return {"category": "Uncategorized", "confidence": 0.0, "method": "ai_only"}
        # return self.ai_client.classify(file_path, content)
        return {"category": "Uncategorized", "confidence": 0.0, "method": "ai_only"}

    # ------------------------------------------------------------------
    # Rules loading
    # ------------------------------------------------------------------
    def _load_rules(self, rules_file: Optional[str]) -> Dict[str, Any]:
        if rules_file and os.path.exists(rules_file):
            with open(rules_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return self.DEFAULT_RULES
