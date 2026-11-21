#!/usr/bin/env python3
"""alphacode_apply.py — بوابة الموافقة الإلزامية على تعديلات AlphaCode المقترحة.

القاعدة الذهبية (docs/alphacode-integration.md §5⑤):
  لا تُعدَّل شجرة المشروع إلا بموافقة مستخدم موقّعة بتجزئة patch.

سير الإجراء عند apply:
  1) فحص الـpatch أمنياً (مسارات داخل الجذر، لا أنماط حساسة، لا روابط)
  2) تحقق الموافقة: تفاعلية (--interactive) أو من approvals.jsonl بمطابقة
     sha256(patch.diff) بالضبط — تجزئة غير مطابقة ⇒ رفض قاطع
  3) git apply --check ثم نسخة احتياطية لكل ملف مستهدف في backups/<id>/
  4) التطبيق ثم pytest (tests/unit افتراضياً)
  5) فشل الاختبارات ⇒ تراجع تلقائي بايت-بايت (إلا مع --keep-failed)
التراجع اليدوي متاح دائماً: apply --rollback <id>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

DIFF_TARGET_RE = re.compile(r"^(?:\+\+\+|---) [ab]/(.+?)(?:\t.*)?$")
FORBIDDEN_PARTS = {"secrets", "credentials", "keyrings", ".ssh", ".gnupg", ".git"}
FORBIDDEN_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".jks", ".kdbx",
                      ".sqlite", ".sqlite3", ".db")
FORBIDDEN_TOKENS = ("id_rsa", "id_ed25519", "password", "secret",
                    "credential", "patient", "medical", "clinical")


class ApplyError(RuntimeError):
    """خطأ آمن للعرض."""


def _repo_root(explicit: Path | None) -> Path:
    if explicit is not None:
        if not (explicit / ".git").exists():
            raise ApplyError(f"المسار المحدد ليس مستودع git: {explicit}")
        return explicit.resolve()
    probe = Path(__file__).resolve().parent
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=probe,
                         capture_output=True, text=True, timeout=15)
    if out.returncode == 0:
        return Path(out.stdout.strip()).resolve()
    raise ApplyError("لم يُعثر على جذر المستودع — مرّر --repo")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True, timeout=300)
    if check and proc.returncode != 0:
        raise ApplyError(f"git {' '.join(args[:2])}… فشل: {proc.stderr.strip()[:300]}")
    return proc


def _base(workspace: Path) -> Path:
    base = workspace / "data" / "alphacode"
    for sub in ("proposals", "approvals", "backups"):
        (base / sub).mkdir(parents=True, exist_ok=True)
    return base


def _validate_target(rel: str, root: Path) -> Path:
    """لا تجاوز، لا مسار مطلق، لا أنماط حساسة — ويعيد المسار الحقيقي داخل الجذر."""
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts or not p.parts:
        raise ApplyError(f"مسار مستهدف غير سليم: {rel!r}")
    lowered = {part.casefold() for part in p.parts}
    if lowered & FORBIDDEN_PARTS:
        raise ApplyError(f"مسار مستهدف يحوي مجلداً محظوراً: {rel!r}")
    for part in p.parts:
        stem = part.casefold()
        if stem.endswith(FORBIDDEN_SUFFIXES) or stem == "data" \
                or stem.startswith(".env") or any(t in stem for t in FORBIDDEN_TOKENS):
            raise ApplyError(f"مسار مستهدف يطابق نمطاً حساساً: {rel!r}")
    resolved = (root / p).resolve()
    root_resolved = root.resolve()
    if root_resolved != resolved and root_resolved not in resolved.parents:
        raise ApplyError(f"المسار يخرج عن جذر المشروع: {rel!r}")
    return resolved


def _patch_targets(patch: Path) -> list[str]:
    targets: set[str] = set()
    for line in patch.read_text(encoding="utf-8", errors="replace").splitlines():
        match = DIFF_TARGET_RE.match(line)
        if match and match.group(1) not in {"/dev/null"}:
            targets.add(match.group(1))
    if not targets:
        raise ApplyError("لا مسارات مستهدفة في الـpatch")
    return sorted(targets)


def _approval_for(base: Path, proposal_id: str, expected_sha: str,
                  interactive: bool, patch: Path) -> dict[str, Any]:
    """الموافقة إما تفاعلية الآن أو سجل سابق في approvals.jsonl مطابق بالتجزئة."""
    if interactive:
        text = patch.read_text(encoding="utf-8", errors="replace")
        print("=" * 60)
        print(text[:6000])
        print("=" * 60)
        answer = input(f"توافق على تطبيق {proposal_id} (sha256={expected_sha[:12]}…)؟ [y/N] ")
        if answer.strip().casefold() not in {"y", "yes", "نعم"}:
            raise ApplyError("رفض المستخدم — لم يُعدَّل أي شيء")
        record = {"id": proposal_id, "sha256": expected_sha,
                  "decision": "approved", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                  "mode": "interactive"}
        with (base / "approvals.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return record
    approval_file = base / "approvals.jsonl"
    if not approval_file.exists():
        raise ApplyError(f"لا موافقة: {proposal_id} غير موجود في approvals.jsonl")
    last: dict[str, Any] | None = None
    for line in approval_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("id") == proposal_id:
            last = record
    if not last:
        raise ApplyError(f"لا موافقة مسجلة لـ{proposal_id}")
    if last.get("sha256") != expected_sha:
        raise ApplyError("تجزئة patch لا تطابق الموافقة المسجلة — احتمال تلاعب بعد "
                         "الموافقة؛ اطلب موافقة جديدة على النسخة الحالية")
    if last.get("decision") != "approved":
        raise ApplyError(f"قرار الموافقة المسجل للـ{proposal_id} ليس approved")
    return last


def _backup_targets(base: Path, proposal_id: str, root: Path,
                    targets: list[str]) -> tuple[Path, list[dict[str, str]]]:
    backup_dir = base / "backups" / proposal_id
    if backup_dir.exists():
        raise ApplyError(f"يوجد نسخ احتياطي سابق لـ{proposal_id} — rollback أولاً")
    backup_dir.mkdir(parents=True)
    manifest: list[dict[str, str]] = []
    for rel in targets:
        target = _validate_target(rel, root)
        if target.exists():
            dest = backup_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, dest)
            manifest.append({"path": rel, "sha256": _sha256(target), "state": "existed"})
        else:
            manifest.append({"path": rel, "sha256": "", "state": "new"})
    (backup_dir / "backup-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return backup_dir, manifest


def _rollback(base: Path, root: Path, proposal_id: str) -> dict[str, Any]:
    """إرجاع كل ملف بايت-بايت من النسخة الاحتياطية وحذف ما كان جديداً."""
    backup_dir = base / "backups" / proposal_id
    manifest_path = backup_dir / "backup-manifest.json"
    if not manifest_path.exists():
        raise ApplyError(f"لا نسخة احتياطية لـ{proposal_id} — لا شيء للتراجع")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    restored, deleted = [], []
    for item in manifest:
        target = _validate_target(item["path"], root)
        if item["state"] == "existed":
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_dir / item["path"], target)
            if _sha256(target) != item["sha256"]:
                raise ApplyError(f"فشل تحقق التراجع عن {item['path']}")
            restored.append(item["path"])
        else:
            if target.exists():
                target.unlink()
            deleted.append(item["path"])
    shutil.rmtree(backup_dir)
    return {"restored": restored, "deleted": deleted}


def _run_tests(root: Path, full: bool) -> tuple[bool, str]:
    scope = ["tests/unit", "tests/integration"] if full else ["tests/unit"]
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *scope, "-q", "--tb=short",
         "-p", "no:cacheprovider"],
        cwd=root, capture_output=True, text=True, timeout=1200,
        env={"QT_QPA_PLATFORM": "offscreen", "PATH": "/usr/bin:/bin:/usr/local/bin",
             "HOME": str(Path.home())},
    )
    tail = "\n".join((proc.stdout or proc.stderr).strip().splitlines()[-6:])
    return proc.returncode == 0, tail


def apply_proposal(workspace: Path, root: Path, proposal_id: str, *,
                   interactive: bool = False, full_tests: bool = False,
                   keep_failed: bool = False) -> dict[str, Any]:
    """تنفيذ دورة apply كاملة مع بوابة الموافقة والتراجع عند الفشل."""
    base = _base(workspace)
    proposal = base / "proposals" / proposal_id
    patch = proposal / "patch.diff"
    if not patch.is_file():
        raise ApplyError(f"لا يوجد patch.diff في proposals/{proposal_id}")
    expected_sha = _sha256(patch)

    targets = _patch_targets(patch)
    for rel in targets:
        _validate_target(rel, root)

    approval = _approval_for(base, proposal_id, expected_sha, interactive, patch)

    check = _git(["apply", "--check", patch.as_posix()], root, check=False)
    if check.returncode != 0:
        raise ApplyError(f"git apply --check رفض الـpatch: {check.stderr.strip()[:300]}")

    backup_dir, manifest = _backup_targets(base, proposal_id, root, targets)

    _git(["apply", patch.as_posix()], root)
    applied = True
    tests_ok, tests_tail = _run_tests(root, full_tests)
    outcome: dict[str, Any] = {
        "id": proposal_id, "sha256": expected_sha, "targets": targets,
        "approval_ts": approval.get("ts"), "tests_ok": tests_ok,
        "tests_tail": tests_tail, "rolled_back": False, "ts":
        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if not tests_ok and not keep_failed:
        _rollback(base, root, proposal_id)
        applied = False
        outcome["rolled_back"] = True
        outcome["note"] = "فشلت الاختبارات — تراجع تلقائي بايت-بايت (الشجرة كما كانت)"
    elif not tests_ok:
        outcome["note"] = "فشلت الاختبارات و--keep-failed مفعّل — التراجع اليدوي: apply --rollback"
    # النسخة الاحتياطية تبقى بعد التطبيق الناجح (حتى التراجع اليدوي لاحقاً)
    if applied:
        outcome["backup_dir"] = str(backup_dir)
    log = base / "apply_log.jsonl"
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(outcome, ensure_ascii=False, sort_keys=True) + "\n")
    return outcome


def list_proposals(workspace: Path) -> list[dict[str, Any]]:
    base = _base(workspace)
    result: list[dict[str, Any]] = []
    for proposal in sorted((base / "proposals").iterdir()):
        if not proposal.is_dir():
            continue
        patch = proposal / "patch.diff"
        meta = proposal / "meta.json"
        item: dict[str, Any] = {"id": proposal.name,
                                 "has_patch": patch.is_file(),
                                 "has_meta": meta.is_file()}
        if patch.is_file():
            item["sha256"] = _sha256(patch)[:12]
            try:
                item["targets"] = _patch_targets(patch)
            except ApplyError:
                item["targets"] = []
        if meta.is_file():
            try:
                item["meta"] = json.loads(meta.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                item["meta"] = None
        # حالة القرار الحالية
        approval_file = base / "approvals.jsonl"
        decision = None
        if approval_file.exists() and patch.is_file():
            for line in approval_file.read_text(encoding="utf-8").splitlines():
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("id") == proposal.name and \
                        record.get("sha256") == _sha256(patch):
                    decision = record.get("decision")
        item["decision"] = decision
        result.append(item)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="بوابة الموافقة الإلزامية على اقتراحات تعديل AlphaCode")
    parser.add_argument("action", choices=["list", "apply", "rollback"])
    parser.add_argument("id", nargs="?", help="معرّف الاقتراح (apply/rollback)")
    parser.add_argument("--repo", type=Path, default=None)
    parser.add_argument("--workspace", type=Path, default=Path.home())
    parser.add_argument("--interactive", action="store_true",
                        help="عرض الـdiff والموافقة تفاعلياً الآن (تُسجل بالتجزئة)")
    parser.add_argument("--full-tests", action="store_true",
                        help="تشغيل tests/unit + tests/integration بعد التطبيق")
    parser.add_argument("--keep-failed", action="store_true",
                        help="عدم التراجع التلقائي عند فشل الاختبارات (غير منصوح)")
    args = parser.parse_args()
    workspace = args.workspace.expanduser()

    try:
        if args.action == "list":
            items = list_proposals(workspace)
            print(json.dumps(items, ensure_ascii=False, indent=2))
            return 0
        root = _repo_root(args.repo)
        if not args.id:
            parser.error(f"الإجراء {args.action} يتطلب معرّف اقتراح")
        if args.action == "apply":
            outcome = apply_proposal(workspace, root, args.id,
                                     interactive=args.interactive,
                                     full_tests=args.full_tests,
                                     keep_failed=args.keep_failed)
        else:
            outcome = _rollback(_base(workspace), root, args.id)
        print(json.dumps(outcome, ensure_ascii=False, indent=2))
        return 0
    except (ApplyError, OSError, subprocess.SubprocessError) as exc:
        print(f"[alphacode_apply] فشل: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
