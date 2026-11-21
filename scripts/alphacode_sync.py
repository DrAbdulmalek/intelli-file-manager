#!/usr/bin/env python3
"""alphacode_sync.py — الرفع التلقائي لمخرجات AlphaCode إلى GitHub + التسليم للابتلاع.

الحلقة (docs/alphacode-integration.md §5①):
  outbox/ → مسح أمني (حاجز الحساسية v2) → فرع أيتام alphacode/artifacts (push عادي فقط)
          → نسخة إلى inbox/ ليببلعها IntelliFile، ويُفرَّغ الـoutbox.

قضبان صارمة:
  - لا force push ولا إعادة كتابة تاريخ إطلاقاً (فشل غير ff ⇒ جلب --ff-only ومحاولة ثانية).
  - التوكن من البيئة فقط (ALPHACODE_GH_TOKEN ثم GITHUB_TOKEN) — لا يُكتب في ملف.
  - سقوف: 4MB/ملف، 300 ملف/دفعة، 64MB/دفعة؛ تجاوز ⇒ رفض مع سجل السبب في rejected/.
  - الفرع الأيتام لا يُدمج في main أبداً؛ تاريخ main يبقى نظيفاً.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# ─── السقوف ────────────────────────────────────────────────────────────────
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_BATCH_FILES = 300
MAX_BATCH_BYTES = 64 * 1024 * 1024
ARTIFACT_BRANCH = "alphacode/artifacts"
PUSH_ATTEMPTS = 3
PUSH_BACKOFF_SEC = 2.0


class SyncError(RuntimeError):
    """خطأ آمن للعرض على المستخدم."""


def _repo_root(explicit: Path | None) -> Path:
    """جذر المستودع: من الوسيطة، أو من git، أو من موقع هذا السكربت."""
    if explicit is not None:
        if not (explicit / ".git").exists():
            raise SyncError(f"المسار المحدد ليس مستودع git: {explicit}")
        return explicit.resolve()
    probe = Path(__file__).resolve().parent
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=probe,
        capture_output=True, text=True, timeout=15,
    )
    if out.returncode == 0:
        return Path(out.stdout.strip()).resolve()
    raise SyncError("لم يُعثر على جذر المستودع — مرّر --repo")


def _git(args: list[str], cwd: Path, token: str | None = None,
         check: bool = True) -> subprocess.CompletedProcess[str]:
    """تشغيل git مع تمرير التوكن عبر credential helper عابر (لا يُخزَّن)."""
    cmd = ["git"]
    if token:
        helper = (
            "!f() { echo username=x-access-token; "
            'echo "password=$ALPHACODE_SYNC_TOKEN"; }; f'
        )
        cmd += ["-c", f"credential.helper={helper}"]
    cmd += args
    env = dict(os.environ)
    if token:
        env["ALPHACODE_SYNC_TOKEN"] = token
        env["GIT_TERMINAL_PROMPT"] = "0"
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          timeout=120, env=env)
    if check and proc.returncode != 0:
        raise SyncError(f"git {' '.join(args[:3])}… فشل: {proc.stderr.strip()[:300]}")
    return proc


def _safe_name(rel: str) -> bool:
    """رفض التجاوز والروابط الرمزية والأنماط الحساسة في الاسم النسبي."""
    parts = Path(rel).parts
    if not parts or any(p in {"..", "."} for p in parts):
        return False
    lowered = {p.casefold() for p in parts}
    forbidden = {"secrets", "credentials", "keyrings", ".ssh", ".gnupg", ".git"}
    if lowered & forbidden:
        return False
    for p in parts:
        if p.casefold().endswith((".pem", ".key", ".p12", ".pfx", ".jks", ".kdbx",
                                  ".sqlite", ".sqlite3", ".db", ".env")):
            return False
        stem = p.casefold()
        if any(t in stem for t in ("id_rsa", "id_ed25519", "password", "secret",
                                   "credential", "patient", "medical", "clinical")):
            return False
    return True


def scan_outbox(outbox: Path) -> tuple[list[Path], list[tuple[str, str]]]:
    """مسح الـoutbox: يعيد (المقبولة، المرفوضة مع السبب)."""
    accepted: list[Path] = []
    rejected: list[tuple[str, str]] = []
    total = 0
    files = sorted(p for p in outbox.rglob("*") if p.is_file())
    for f in files:
        rel = f.relative_to(outbox).as_posix()
        try:
            if f.is_symlink():
                rejected.append((rel, "رابط رمزي — مرفوق بروتوكولياً"))
                continue
            if not _safe_name(rel):
                rejected.append((rel, "اسم يطابق نمط حساس/ممنوع"))
                continue
            size = f.stat().st_size
            if size > MAX_FILE_BYTES:
                rejected.append((rel, f"تجاوز سقف الملف ({size} > {MAX_FILE_BYTES})"))
                continue
            if len(accepted) >= MAX_BATCH_FILES:
                rejected.append((rel, "تجاوز سقف عدد ملفات الدفعة"))
                continue
            if total + size > MAX_BATCH_BYTES:
                rejected.append((rel, "تجاوز سقف حجم الدفعة"))
                continue
        except OSError as exc:
            rejected.append((rel, f"خطأ نظام ملفات: {exc}"))
            continue
        accepted.append(f)
        total += size
    return accepted, rejected


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_worktree(root: Path, wt: Path) -> Path:
    """تهيئة worktree على فرع الأيتام (ينشئه أول مرة بجذر فارغ)."""
    have = _git(["worktree", "list", "--porcelain"], root).stdout
    if wt.as_posix() in have:
        return wt
    if wt.exists():
        shutil.rmtree(wt)
    branches = _git(["branch", "--list", ARTIFACT_BRANCH], root).stdout.strip()
    if branches:
        _git(["worktree", "add", wt.as_posix(), ARTIFACT_BRANCH], root)
    else:
        _git(["worktree", "add", "--detach", wt.as_posix()], root)
        _git(["checkout", "--orphan", ARTIFACT_BRANCH], wt)
        _git(["rm", "-rf", "."], wt)
        (wt / "README.md").write_text(
            "# alphacode/artifacts\n\n"
            "أرشيف مخرجات AlphaCode (تقارير، ملاحظات، لوغات) — فرع أيتام يُدار "
            "تلقائياً بواسطة scripts/alphacode_sync.py. لا يُدمج في main.\n",
            encoding="utf-8",
        )
        _git(["add", "README.md"], wt)
        _git(["commit", "-q", "-m", "alphacode: initialize artifacts orphan branch"], wt)
    return wt


def _push_with_retry(wt: Path, token: str | None, remote: str) -> None:
    last_err = ""
    for attempt in range(1, PUSH_ATTEMPTS + 1):
        proc = _git(["push", remote, ARTIFACT_BRANCH], wt, token=token, check=False)
        if proc.returncode == 0:
            return
        last_err = proc.stderr.strip()
        if "fetch first" in last_err.lower() or "non-fast-forward" in last_err.lower():
            _git(["pull", "--ff-only", remote, ARTIFACT_BRANCH], wt, check=False)
            time.sleep(PUSH_BACKOFF_SEC)
            continue
        break
    raise SyncError(f"تعذر دفع {ARTIFACT_BRANCH}: {last_err[:400]}")


def sync(repo: Path, workspace: Path, *, remote: str = "origin",
         dry_run: bool = False, push: bool = True) -> dict[str, Any]:
    """تنفيذ دورة التزامن الكاملة، ويعيد تقريراً منظماً."""
    outbox = workspace / "data" / "alphacode" / "outbox"
    inbox = workspace / "data" / "alphacode" / "inbox"
    rejected = workspace / "data" / "alphacode" / "rejected"
    for p in (outbox, inbox, rejected):
        p.mkdir(parents=True, exist_ok=True)

    accepted, rejected_list = scan_outbox(outbox)
    report: dict[str, Any] = {
        "accepted": [f.name for f in accepted],
        "rejected": [{"name": n, "reason": r} for n, r in rejected_list],
        "batch_id": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
        "pushed": False,
    }

    # نقل المرفوضات إلى rejected/ (الملف نفسه يبقى محلياً للتدقيق) + سجل السبب —
    # الـoutbox يُفرَّغ كلياً بعد كل دورة.
    if rejected_list:
        stamp = report["batch_id"]
        for name, reason in rejected_list:
            source = outbox / name
            moved_path = rejected / f"{stamp}__{name.replace('/', '__')}"
            if source.is_file():
                source.replace(moved_path)
            (rejected / f"{stamp}__{Path(name).name}.rejected.txt").write_text(
                f"file: {name}\nmoved_to: {moved_path.name}\nreason: {reason}\n",
                encoding="utf-8")

    if dry_run or not accepted:
        return report

    token = os.environ.get("ALPHACODE_GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if push and not token:
        raise SyncError("لا توكن في البيئة (ALPHACODE_GH_TOKEN / GITHUB_TOKEN) — "
                        "مرّر --no-push للمزامنة المحلية فقط")

    wt = workspace / "data" / "alphacode" / ".artifacts-worktree"
    _ensure_worktree(root=repo, wt=wt)

    batch_id = report["batch_id"]
    manifest: list[dict[str, Any]] = []
    for f in accepted:
        rel = f.relative_to(outbox).as_posix()
        dest = wt / "files" / batch_id / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)
        manifest.append({"path": f"files/{batch_id}/{rel}",
                         "bytes": f.stat().st_size, "sha256": _sha256(f)})

    (wt / "files" / batch_id / "manifest.json").write_text(
        json.dumps({"batch": batch_id, "files": manifest}, ensure_ascii=False,
                   indent=2), encoding="utf-8")
    _git(["add", f"files/{batch_id}"], wt)
    summary = "، ".join(m["path"].split("/")[-1] for m in manifest[:5])
    more = f" (+{len(manifest) - 5} أخرى)" if len(manifest) > 5 else ""
    _git(["commit", "-q", "-m",
          f"alphacode: batch {batch_id} — {len(manifest)} ملفاً ({sum(m['bytes'] for m in manifest)} بايت): {summary}{more}"], wt)

    if push:
        _push_with_retry(wt, token, remote)

    # التسليم للابتلاع + إفراغ الـoutbox
    for f in accepted:
        rel = f.relative_to(outbox).as_posix()
        dest = inbox / f"{batch_id}__{rel.replace('/', '__')}"
        shutil.copy2(f, dest)
        f.unlink()
    report["pushed"] = bool(push)
    report["batch_id"] = batch_id
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="رفع مخرجات AlphaCode تلقائياً إلى فرع alphacode/artifacts وتسليمها للابتلاع")
    parser.add_argument("--repo", type=Path, default=None,
                        help="جذر مستودع intelli-file-manager (افتراضياً يُكتشف)")
    parser.add_argument("--workspace", type=Path, default=Path.home(),
                        help="مجلد عمل AlphaCode الذي يحوي data/alphacode/outbox")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--dry-run", action="store_true",
                        help="مسح وتقرير فقط دون رفع أو نقل")
    parser.add_argument("--no-push", action="store_true",
                        help="مزامنة محلية فقط (inbox دون رفع)")
    args = parser.parse_args()

    try:
        root = _repo_root(args.repo)
        result = sync(root, args.workspace.expanduser(), remote=args.remote,
                      dry_run=args.dry_run, push=not args.no_push)
    except (SyncError, OSError) as exc:
        print(f"[alphacode_sync] فشل: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
