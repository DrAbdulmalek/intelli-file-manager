"""خدمة المسارد الطبية — اقتراحات تصحيح/إكمال عربي-إنجليزي لتحرير OCR.

Data source (offline, privacy-first):
  - bundled ``data/medical_glossary.csv`` (741 ar↔en pairs) curated from the
    ``arabic-medical-glossary`` repo (cleaned/terms.csv + comprehensive glossary,
    high-confidence term pairs only, markdown artifacts removed).
  - override path via ``INTELLIFILE_GLOSSARY_PATH`` env var (e.g. point at the
    full ``arabic-medical-glossary/cleaned/terms.csv`` for 21k+ terms).

Matching is deliberately simple and deterministic (normalized substring +
prefix scoring, both directions). It is a *suggestion* engine for the OCR
editor, not a translation system — no LLM, no network.
"""
from __future__ import annotations

import csv
import logging
import os
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_BUNDLED = Path(__file__).resolve().parent.parent.parent / "data" / "medical_glossary.csv"

# Arabic diacritics (tashkeel) + tatweel — stripped before comparison
_TASHKEEL = set(range(0x064B, 0x0653)) | {0x0640, 0x0670}


def normalize_ar(text: str) -> str:
    """Normalize Arabic for comparison: strip tashkeel/tatweel, unify alef/hamza forms."""
    out = []
    for ch in text:
        code = ord(ch)
        if code in _TASHKEEL:
            continue
        out.append(ch)
    s = "".join(out)
    # unify alef variants and yaa/alif maqsura, taa marbuta -> haa (light touch)
    s = (
        s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
        .replace("ى", "ي").replace("ة", "ه")
    )
    return unicodedata.normalize("NFKC", s).lower().strip()


def normalize_en(text: str) -> str:
    return unicodedata.normalize("NFKC", text).lower().strip()


@dataclass(frozen=True)
class GlossaryTerm:
    en: str
    ar: str
    confidence: str = "high"


class GlossaryService:
    """Suggest medical terms for the OCR editor (ar↔en, offline)."""

    def __init__(self, glossary_path: Path | str | None = None):
        path = Path(
            glossary_path
            or os.environ.get("INTELLIFILE_GLOSSARY_PATH", "")
            or _BUNDLED
        )
        self.path = path
        self.terms: list[GlossaryTerm] = []
        self._by_ar: dict[str, list[GlossaryTerm]] = {}
        self._by_en: dict[str, list[GlossaryTerm]] = {}
        self._load()

    # ------------------------------------------------------------------
    def _load(self) -> None:
        if not self.path.exists():
            logger.warning("glossary file not found: %s (empty suggestions)", self.path)
            return
        try:
            with open(self.path, encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    en, ar = (row.get("en") or "").strip(), (row.get("ar") or "").strip()
                    if not en or not ar:
                        continue
                    conf = (row.get("confidence") or "high").strip()
                    term = GlossaryTerm(en=en, ar=ar, confidence=conf)
                    self.terms.append(term)
                    self._by_ar.setdefault(normalize_ar(ar), []).append(term)
                    self._by_en.setdefault(normalize_en(en), []).append(term)
            logger.info("glossary loaded: %d terms from %s", len(self.terms), self.path)
        except (csv.Error, OSError) as exc:
            logger.error("failed to load glossary %s: %s", self.path, exc)

    # ------------------------------------------------------------------
    def suggest(self, text: str, limit: int = 8) -> list[str]:
        """Return ranked suggestion strings for a partially-typed term.

        Ranking: exact normalized match > prefix > substring; Arabic input
        matches Arabic side (normalized), English input matches English side.
        """
        raw = (text or "").strip()
        if not raw:
            return []
        limit = max(1, min(limit, 25))
        has_arabic = any("\u0600" <= ch <= "\u06FF" for ch in raw)
        index = self._by_ar if has_arabic else self._by_en
        needle = normalize_ar(raw) if has_arabic else normalize_en(raw)

        exact: list[str] = []
        prefix: list[str] = []
        substring: list[str] = []
        for key, terms in index.items():
            surface = terms[0].ar if has_arabic else terms[0].en
            if key == needle:
                exact.append(surface)
            elif key.startswith(needle):
                prefix.append(surface)
            elif needle in key:
                substring.append(surface)
        ranked = (exact + prefix + substring)[:limit]
        # de-duplicate while preserving rank order
        seen: set[str] = set()
        unique = [s for s in ranked if not (s in seen or seen.add(s))]
        return unique

    def lookup(self, text: str) -> GlossaryTerm | None:
        """Exact (normalized) lookup of a term on either language side."""
        raw = normalize_ar(text or "")
        if raw in self._by_ar:
            return self._by_ar[raw][0]
        en = normalize_en(text or "")
        if en in self._by_en:
            return self._by_en[en][0]
        return None

    @property
    def size(self) -> int:
        return len(self.terms)


@lru_cache(maxsize=1)
def get_glossary_service() -> GlossaryService:
    """Process-wide singleton (lazily built on first use)."""
    return GlossaryService()
