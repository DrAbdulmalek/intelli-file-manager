#!/usr/bin/env python3
"""alphacode_ingest.py — IntelliFile يبتلع مخرجات AlphaCode ويحوّلها إلى evidence.

الحلقة (docs/alphacode-integration.md §5③):
  inbox/ → أرشفة باسم غير قابل للتغيير (<UTC>__<sha256-8>__<الاسم>) في processed/
         → تصنيف (SmartFileClassifier) → تسجيل manifest.jsonl
         → evidence في FeedbackEngine بحالة pending (لا تفعّل أي قاعدة بدون تأكيدك)
         → توليد لوحة summary.md.

آمن بلا اعتماديات ثقيلة: إذا غاب المصنّف أو محرك الملاحظات يهبط للأوضاع
النصية ويكمل — الابتلاع لا يفشل كله بسبب وحدة واحدة.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

# ─── استيرادات اختيارية بتدهور لطيف ────────────────────────────────────────
try:
    from src.core.classifier import SmartFileClassifier
    _HAS_CLASSIFIER = True
except Exception:  # pragma: no cover — بيئة بلا اعتماديات التصنيف
    _HAS_CLASSIFIER = False

try:
    from src.core.preference_engine import PreferenceEngine
    from src.core.preference_store import PreferenceStore
    from src.core.feedback_engine import FeedbackEngine
    _HAS_FEEDBACK = True
except Exception:  # pragma: no cover
    _HAS_FEEDBACK = False

MAX_INGEST_FILES = 500


class IngestError(RuntimeError):
    """خطأ آمن للعرض."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_safe(value: Any) -> Any:
    """تحويل عميق لقيم غير قابلة للتسلسل (Path/datetime/bytes) إلى نصوص."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _classify(path: Path) -> dict[str, Any]:
    """تصنيف آمن: dict ثابت على الأقل عند غياب المصنّف."""
    if _HAS_CLASSIFIER:
        try:
            result = SmartFileClassifier().classify_file(str(path))
            if isinstance(result, dict):
                return _json_safe(result)
        except Exception as exc:  # noqa: BLE001 — التصنيف اختياري وليس حرجاً
            return {"classifier_error": str(exc)[:200]}
    return {"classifier": "unavailable"}


def _register_feedback(workspace: Path, entries: list[dict[str, Any]],
                       session_id: str) -> list[str]:
    """تسجيل evidence بحالة pending — لا يفعّل أي قاعدة تفضيل بذاته."""
    ids: list[str] = []
    if not _HAS_FEEDBACK or not entries:
        return ids
    try:
        store = PreferenceStore()  # الافتراضي ~/.intellifile/preferences.json
        engine = PreferenceEngine(store)
        feedback = FeedbackEngine(engine)
        for e in entries:
            record = feedback.capture(
                user_action=e["user_action"],
                original_prediction=e["original_prediction"],
                session_id=session_id,
                file_fingerprint=e["file_fingerprint"],
                evidence=e.get("evidence"),
            )
            ids.append(str(record.get("id", "")))
    except Exception as exc:  # noqa: BLE001 — الابتلاع لا يفشل بسبب التسجيل
        print(f"[alphacode_ingest] تنبيه: تعذر تسجيل evidence: {exc}",
              file=sys.stderr)
    return ids


def ingest(workspace: Path, *, session_id: str | None = None) -> dict[str, Any]:
    """تنفيذ دورة ابتلاع كاملة ويعيد تقريراً منظماً."""
    base = workspace / "data" / "alphacode"
    inbox = base / "inbox"
    processed = base / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in inbox.iterdir() if p.is_file()) if inbox.exists() else []
    if len(files) > MAX_INGEST_FILES:
        raise IngestError(f"الـinbox يضم {len(files)} ملفاً — السقف {MAX_INGEST_FILES}")

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    sid = session_id or f"alphacode-{stamp}"
    manifest_path = processed / "manifest.jsonl"
    entries: list[dict[str, Any]] = []
    archived: list[dict[str, Any]] = []

    for f in files:
        digest = _sha256(f)
        new_name = f"{stamp}__{digest[:8]}__{f.name}"
        dest = processed / new_name
        # اسم غير قابل للتغيير: يُرفض إن وُجد (تكرار كامل نفس البصمة واللحظة)
        if dest.exists():
            f.unlink()  # مطابق تماماً لأرشيف موجود — مجرد إعادة تسليم
            continue
        shutil_move = f.rename(dest)
        info: dict[str, Any] = {
            "archived": new_name,
            "original": f.name,
            "sha256": digest,
            "bytes": dest.stat().st_size,
            "moved": bool(shutil_move is None or True),  # rename يعيد None
        }
        classification = _classify(dest)
        info["classification"] = classification
        archived.append(info)
        entries.append({
            "user_action": "alphacode_artifact_delivered",
            "original_prediction": "unclassified_workspace_artifact",
            "file_fingerprint": digest[:16],
            "evidence": {
                "kind": "alphacode_artifact",
                "archived": new_name,
                "classification": classification,
                "session_id": sid,
            },
        })

    # سجل manifest بصيغة append-only
    with manifest_path.open("a", encoding="utf-8") as fh:
        for info in archived:
            fh.write(json.dumps(info, ensure_ascii=False, sort_keys=True,
                                default=str) + "\n")

    feedback_ids = _register_feedback(workspace, entries, sid)

    summary = _write_summary(workspace, archived, feedback_ids)
    return {"archived": len(archived), "feedback_ids": feedback_ids,
            "summary": str(summary)}


def _write_summary(workspace: Path, archived: list[dict[str, Any]],
                   feedback_ids: list[str]) -> Path:
    """لوحة الحالة: آخر ما وصل، العدّادات، ما ينتظر تأكيدك."""
    base = workspace / "data" / "alphacode"
    processed = base / "processed"
    proposals = base / "proposals"
    rejected = base / "rejected"
    summary_path = base / "summary.md"

    total = 0
    if manifest_path := (processed / "manifest.jsonl"):
        if manifest_path.exists():
            with manifest_path.open(encoding="utf-8") as fh:
                total = sum(1 for line in fh if line.strip())

    open_proposals = sorted(p.name for p in proposals.glob("*") if p.is_dir()) \
        if proposals.exists() else []
    rejected_count = len(list(rejected.glob("*.rejected.txt"))) \
        if rejected.exists() else 0

    lines = [
        "# لوحة تكامل AlphaCode — IntelliFile",
        f"_آخر تحديث: {time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime())}_",
        "",
        "## العدّادات",
        f"- مجموع الأرشيف في `processed/`: **{total}**",
        f"- وصل حديثاً في هذه الدورة: **{len(archived)}**",
        f"- اقتراحات تعديل مفتوحة في `proposals/`: **{len(open_proposals)}**"
        + (f" — {', '.join(open_proposals[:5])}" if open_proposals else ""),
        f"- ملفات مرفوضة أمنياً: **{rejected_count}**",
        f"- evidence مسجلة في FeedbackEngine بحالة **pending**: **{len(feedback_ids)}**"
        + (" — تنتظر تأكيدك من واجهة التطبيق" if feedback_ids else ""),
        "",
        "## آخر ما وصل",
    ]
    for info in archived[:10]:
        cls = info.get("classification") or {}
        label = cls.get("category") or cls.get("classifier", "—")
        lines.append(f"- `{info['archived']}` ({info['bytes']} بايت) — تصنيف: {label}")
    if not archived:
        lines.append("- (لا جديد في هذه الدورة)")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ابتلاع مخرجات AlphaCode في IntelliFile (أرشفة + تصنيف + evidence + لوحة)")
    parser.add_argument("--workspace", type=Path, default=Path.home(),
                        help="مجلد العمل الذي يحوي data/alphacode/inbox")
    parser.add_argument("--session-id", default=None)
    args = parser.parse_args()
    try:
        result = ingest(args.workspace.expanduser(), session_id=args.session_id)
    except (IngestError, OSError) as exc:
        print(f"[alphacode_ingest] فشل: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
