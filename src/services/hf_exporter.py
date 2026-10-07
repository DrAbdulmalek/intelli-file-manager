"""تصدير القصاصات المعتمدة إلى HuggingFace Datasets (JSONL محليًا؛ الرفع اختياري).

Export contract (training snippets -> HF dataset rows):

    {
      "id": <int>,
      "image": "images/snippet_<id>.png",     # cropped from the source image
      "text": <human-corrected text>,
      "ocr_text": <original engine output>,
      "language": "ar|en|...",
      "category": "medical|general|formula|table",
      "level": "word|line|block|character",
      "confidence": <float|0.0 unknown>,
      "source": "intelli-file-manager/human-verified",
    }

Policies:
  - Only ``approved`` snippets with non-empty text are exported.
  - Rows whose text is identical to the raw OCR text are skipped by default
    (no supervision signal in them); pass ``include_unchanged=True`` to keep.
  - The push step is NEVER automatic: ``push_to_hf`` requires an explicit
    token argument from the caller (no ambient credentials).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.db.snippet_db import SnippetDB, TrainingSnippet

logger = logging.getLogger(__name__)

HF_REPO = "DrAbdulmalek/arabic-medical-ocr-training"


class HFExporter:
    """يجمع القصاصات المعتمدة ويصدرها بصيغة HuggingFace."""

    def __init__(self, db: SnippetDB, export_dir: Path | str | None = None,
                 hf_repo: str = HF_REPO):
        self.db = db
        self.export_dir = Path(export_dir) if export_dir else (
            Path(__file__).resolve().parent.parent.parent / "data" / "hf_export"
        )
        self.hf_repo = hf_repo

    # ------------------------------------------------------------------
    def export(self, min_confidence: float = 0.0,
               include_unchanged: bool = False) -> Path:
        """Export approved snippets into ``<export_dir>/train.jsonl``.

        ``min_confidence`` filters out rows *below* the threshold; 0.0 keeps
        everything (including unknown-confidence rows, per ocr-core policy).
        Returns the written JSONL path.
        """
        self.export_dir.mkdir(parents=True, exist_ok=True)
        approved = self.db.get_approved()

        valid: list[TrainingSnippet] = []
        for s in approved:
            if not s.text.strip():
                continue
            if not include_unchanged and s.text.strip() == s.ocr_text.strip():
                continue
            if s.confidence and min_confidence and s.confidence < min_confidence:
                continue
            valid.append(s)

        image_dir = self.export_dir / "images"
        image_dir.mkdir(exist_ok=True)

        rows: list[dict] = []
        for s in valid:
            img_rel = f"images/snippet_{s.id}.png"
            img_path = self.export_dir / img_rel
            if not img_path.exists() and Path(s.source_image).exists():
                self._crop_and_save(s, img_path)
            rows.append({
                "id": s.id,
                "image": img_rel,
                "text": s.text,
                "ocr_text": s.ocr_text,
                "language": s.language,
                "category": s.category,
                "level": s.level,
                "confidence": s.confidence,
                "bbox": list(s.bbox),
                "source_image": s.source_image,
                "verified_by": s.verified_by,
                "source": "intelli-file-manager/human-verified",
            })

        out_path = self.export_dir / "train.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        meta = {
            "name": self.hf_repo.split("/")[-1],
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "total": len(rows),
            "min_confidence": min_confidence,
            "include_unchanged": include_unchanged,
            "categories": sorted({r["category"] for r in rows}),
            "levels": sorted({r["level"] for r in rows}),
        }
        (self.export_dir / "dataset_info.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("Exported %d snippets to %s", len(rows), out_path)
        return out_path

    # ------------------------------------------------------------------
    def push_to_hf(self, token: str) -> str:
        """رفع مجلد التصدير إلى HuggingFace — يتطلب توكن صريحًا من المستدعي."""
        if not token:
            raise ValueError("push_to_hf requires an explicit HuggingFace token")
        try:
            from huggingface_hub import HfApi
        except ImportError as exc:  # keep import optional
            raise RuntimeError("pip install huggingface_hub") from exc

        train_jsonl = self.export_dir / "train.jsonl"
        if not train_jsonl.exists():
            self.export()
        api = HfApi(token=token)
        api.create_repo(self.hf_repo, repo_type="dataset", exist_ok=True)
        api.upload_folder(
            repo_id=self.hf_repo,
            folder_path=str(self.export_dir),
            repo_type="dataset",
            commit_message="Auto-export from intelli-file-manager (human-verified snippets)",
        )
        logger.info("Pushed to https://huggingface.co/datasets/%s", self.hf_repo)
        return f"https://huggingface.co/datasets/{self.hf_repo}"

    # ------------------------------------------------------------------
    @staticmethod
    def _crop_and_save(snippet: TrainingSnippet, out_path: Path) -> None:
        """اقتطع الصورة من المصدر وحفظها (bbox corners x1,y1,x2,y2)."""
        try:
            from PIL import Image

            with Image.open(snippet.source_image) as img:
                x1, y1, x2, y2 = snippet.bbox
                crop = img.crop((x1, y1, x2, y2))
                crop.save(out_path)
        except Exception as exc:
            logger.warning("Failed to crop snippet %s: %s", snippet.id, exc)
