#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DriveScope — read-only organization analyzer for external drives.

Faithfully ports the *design* of DrAbdulmalek/intelli-file-manager:
  - SmartFileClassifier   -> EXTENSION_MAP / CATEGORIES (src/core/config.py)
  - DuplicateDetector      -> exact SHA-256 groups + reclaimable bytes
                              (src/core/duplicate_detector.py)
  - organization.preflight -> read-only plan, never mutates (src/core/organization.py)
  - RuleEngine default_rules.yaml -> category ruleset (rules/default_rules.yaml)

GUARANTEE: this script NEVER moves, copies, renames or deletes anything.
It only reads metadata and writes a plan + a comprehensive log under --out.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import stat
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

# ── Categories / extension map (ported from intelli-file-manager config.py) ──
CATEGORIES = ["مستندات", "صور", "فيديو", "صوت",
              "أرشيفات", "برمجة", "أنظمة", "خطوط", "أخرى"]

EXTENSION_MAP = {
    ".pdf": "مستندات", ".doc": "مستندات", ".docx": "مستندات",
    ".odt": "مستندات", ".txt": "مستندات", ".rtf": "مستندات",
    ".md": "مستندات", ".tex": "مستندات", ".epub": "مستندات",
    ".xls": "مستندات", ".xlsx": "مستندات", ".csv": "مستندات",
    ".ods": "مستندات", ".ppt": "مستندات", ".pptx": "مستندات",
    ".jpg": "صور", ".jpeg": "صور", ".png": "صور", ".gif": "صور",
    ".bmp": "صور", ".svg": "صور", ".webp": "صور", ".ico": "صور",
    ".tiff": "صور", ".raw": "صور", ".psd": "صور", ".heic": "صور",
    ".mp4": "فيديو", ".avi": "فيديو", ".mkv": "فيديو", ".mov": "فيديو",
    ".wmv": "فيديو", ".flv": "فيديو", ".webm": "فيديو", ".m4v": "فيديو",
    ".3gp": "فيديو",
    ".mp3": "صوت", ".wav": "صوت", ".ogg": "صوت", ".flac": "صوت",
    ".aac": "صوت", ".wma": "صوت", ".m4a": "صوت", ".opus": "صوت",
    ".zip": "أرشيفات", ".rar": "أرشيفات", ".7z": "أرشيفات",
    ".tar": "أرشيفات", ".gz": "أرشيفات", ".bz2": "أرشيفات",
    ".xz": "أرشيفات", ".tgz": "أرشيفات",
    ".py": "برمجة", ".js": "برمجة", ".ts": "برمجة", ".html": "برمجة",
    ".css": "برمجة", ".json": "برمجة", ".xml": "برمجة", ".yaml": "برمجة",
    ".yml": "برمجة", ".sql": "برمجة", ".java": "برمجة", ".cpp": "برمجة",
    ".c": "برمجة", ".h": "برمجة", ".go": "برمجة", ".rs": "برمجة",
    ".rb": "برمجة", ".php": "برمجة", ".sh": "برمجة", ".bat": "برمجة",
    ".jsx": "برمجة", ".tsx": "برمجة", ".vue": "برمجة", ".swift": "برمجة",
    ".kt": "برمجة", ".dart": "برمجة",
    ".exe": "أنظمة", ".msi": "أنظمة", ".deb": "أنظمة", ".pkg": "أنظمة",
    ".rpm": "أنظمة", ".AppImage": "أنظمة", ".iso": "أنظمة",
    ".dmg": "أنظمة", ".img": "أنظمة", ".dll": "أنظمة",
    ".so": "أنظمة", ".ini": "أنظمة", ".cfg": "أنظمة", ".conf": "أنظمة",
    ".log": "أنظمة", ".sys": "أنظمة", ".tmp": "أنظمة",
    ".ttf": "خطوط", ".otf": "خطوط", ".woff": "خطوط",
    ".woff2": "خطوط", ".eot": "خطوط",
}

# Directories never traversed (mirror intelli-file-manager _tree_summary skip set)
SKIP_DIRS = {".ssh", ".config", ".gnupg", ".git", ".venv", "venv",
             "__pycache__", "node_modules", "$RECYCLE.BIN",
             "System Volume Information", "found.000"}
# found.NNN are chkdsk recovery fragments — scanned separately, not as content.
PROTECT = {"$RECYCLE.BIN", "System Volume Information"}


def category_of(name: str) -> str:
    ext = os.path.splitext(name)[1].lower()
    if ext == ".tar" and name.lower().endswith(".tar.gz"):
        return "أرشيفات"
    return EXTENSION_MAP.get(ext, "أخرى")


def human(n: float) -> str:
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024 or u == "TB":
            return f"{n:.2f} {u}"
        n /= 1024
    return f"{n:.2f} TB"# ── Data records ────────────────────────────────────────────────────────────
@dataclass
class FileRec:
    path: str
    name: str
    size: int
    category: str
    ext: str
    mtime: float
    sha256: Optional[str] = None


@dataclass
class DupGroup:
    signature: str
    files: list = field(default_factory=list)   # list of FileRec
    reclaimable: int = 0

    def to_dict(self):
        keep = self.keep()
        return {
            "signature": self.signature,
            "file_count": len(self.files),
            "reclaimable_bytes": self.reclaimable,
            "reclaimable_human": human(self.reclaimable),
            "keep": keep.path if keep else None,
            "redundant": [f.path for f in self.files if f is not keep],
        }

    def keep(self) -> Optional[FileRec]:
        if not self.files:
            return None
        return max(self.files, key=lambda f: (f.size, f.name))


# ── Scanner ─────────────────────────────────────────────────────────────────
def scan(root: Path, hash_files: bool, progress=True):
    files: list[FileRec] = []
    empty_dirs: list[str] = []
    total = 0
    t0 = time.time()
    for cur, dirs, names in os.walk(root, topdown=True, followlinks=False):
        curp = Path(cur)
        # prune skip dirs
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith("found.")]
        # empty dir detection (after pruning)
        if not dirs and not names:
            empty_dirs.append(str(curp))
        for n in names:
            fp = curp / n
            try:
                st = fp.lstat()
            except OSError:
                continue
            if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
                continue
            total += 1
            rec = FileRec(
                path=str(fp), name=n, size=st.st_size,
                category=category_of(n),
                ext=os.path.splitext(n)[1].lower(),
                mtime=st.st_mtime,
            )
            files.append(rec)
            if progress and total % 5000 == 0:
                el = time.time() - t0
                print(f"ALPHACODE_PROGRESS {json.dumps({'current': total, 'unit': 'files', 'message': f'scanning {el:.0f}s'})}", flush=True)
    return files, empty_dirs


def hash_duplicates(files: list[FileRec], progress=True):
    """Exact SHA-256 grouping, size-bucketed to avoid hashing unique sizes."""
    by_size: dict[int, list[FileRec]] = defaultdict(list)
    for f in files:
        by_size[f.size].append(f)
    done = 0
    for size, group in by_size.items():
        if len(group) < 2:
            continue
        # hash each candidate in this size bucket
        for f in group:
            h = hashlib.sha256()
            try:
                with open(f.path, "rb") as fh:
                    for chunk in iter(lambda: fh.read(1 << 20), b""):
                        h.update(chunk)
                f.sha256 = h.hexdigest()
            except OSError:
                f.sha256 = None
            done += 1
            if progress and done % 2000 == 0:
                print(f"ALPHACODE_PROGRESS {json.dumps({'current': done, 'unit': 'hashed', 'message': 'hashing duplicates'})}", flush=True)
    buckets: dict[str, list[FileRec]] = defaultdict(list)
    for f in files:
        if f.sha256:
            buckets[f.sha256].append(f)
    groups: list[DupGroup] = []
    for sig, fs in buckets.items():
        if len(fs) < 2:
            continue
        fs.sort(key=lambda f: (-f.size, f.path))
        reclaim = sum(f.size for f in fs) - fs[0].size
        groups.append(DupGroup(signature=sig, files=fs, reclaimable=reclaim))
    groups.sort(key=lambda g: g.reclaimable, reverse=True)
    return groups# ── Rule engine (ported from default_rules.yaml) ────────────────────────────
# Each rule: name, priority, predicate(rec)->bool, target category/folder.
def build_plan(files: list[FileRec]):
    """Return list of proposed moves (source -> category folder). Read-only."""
    plan = []
    for f in files:
        # skip system/protected
        top = Path(f.path).relative_to(ROOT).parts[0] if ROOT in Path(f.path).parents or Path(f.path).parent == ROOT else None
        if top in PROTECT:
            continue
        target = f"/{f.category}"   # proposed destination root per category
        plan.append({
            "source": f.path,
            "destination_category": f.category,
            "proposed_target": target,
            "size": f.size,
            "reason": "category rule (extension -> CATEGORIES)",
        })
    return plan


def main():
    global ROOT
    ap = argparse.ArgumentParser(description="DriveScope read-only analyzer")
    ap.add_argument("root")
    ap.add_argument("--out", default="./drivescope_out")
    ap.add_argument("--no-hash", action="store_true", help="skip duplicate hashing")
    ap.add_argument("--max-report-dups", type=int, default=500)
    args = ap.parse_args()

    ROOT = Path(args.root).resolve()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    log_path = out / "drivescope_log.md"
    plan_path = out / "organization_plan.json"
    dup_path = out / "duplicates.json"
    empty_path = out / "empty_dirs.json"

    t_start = time.time()
    log = []
    def L(s=""):
        log.append(s)
        print(s, flush=True)

    L(f"# DriveScope Report — {ROOT}")
    L(f"\nGenerated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    L(f"Mode: **READ-ONLY** (no files moved/copied/deleted)\n")
    L("## 1. Scanning file inventory")
    files, empty_dirs = scan(ROOT, hash_files=not args.no_hash)
    scan_t = time.time() - t_start
    total_bytes = sum(f.size for f in files)
    L(f"- Files scanned: **{len(files)}**")
    L(f"- Total size: **{human(total_bytes)}**")
    L(f"- Empty directories: **{len(empty_dirs)}**")
    L(f"- Scan time: {scan_t:.1f}s\n")

    # category distribution
    L("## 2. Category distribution (SmartFileClassifier)")
    L("| Category | Files | Size |")
    L("|---|---:|---:|")
    cat_stats = defaultdict(lambda: [0, 0])
    for f in files:
        cat_stats[f.category][0] += 1
        cat_stats[f.category][1] += f.size
    for cat in CATEGORIES:
        c, b = cat_stats.get(cat, [0, 0])
        L(f"| {cat} | {c} | {human(b)} |")
    L("")

    # duplicates
    L("## 3. Duplicate detection (exact SHA-256)")
    if not args.no_hash:
        groups = hash_duplicates(files)
        total_reclaim = sum(g.reclaimable for g in groups)
        dup_files = sum(len(g.files) - 1 for g in groups)
        L(f"- Duplicate groups: **{len(groups)}**")
        L(f"- Redundant files: **{dup_files}**")
        L(f"- Reclaimable space: **{human(total_reclaim)}**\n")
        if groups:
            L(f"### Top {min(args.max_report_dups, len(groups))} duplicate groups (by reclaimable size)")
            L("| # | Files | Reclaimable | Keep | Redundant (first 3) |")
            L("|---:|---:|---:|---|---|")
            for i, g in enumerate(groups[:args.max_report_dups], 1):
                keep = g.keep()
                red = [Path(f.path).name for f in g.files if f is not keep][:3]
                L(f"| {i} | {len(g.files)} | {human(g.reclaimable)} | {keep.name if keep else '-'} | {', '.join(red)} |")
            L("")
        with open(dup_path, "w", encoding="utf-8") as fh:
            json.dump([g.to_dict() for g in groups], fh, ensure_ascii=False, indent=2)
    else:
        L("(skipped — --no-hash)\n")

    # empty dirs
    L("## 4. Empty directories (deletion candidates — NOT deleted)")
    if empty_dirs:
        L(f"Found **{len(empty_dirs)}** empty directories:\n")
        for d in empty_dirs[:200]:
            L(f"- `{d}`")
        if len(empty_dirs) > 200:
            L(f"- ... and {len(empty_dirs)-200} more (see {empty_path.name})")
        L("")
        with open(empty_path, "w", encoding="utf-8") as fh:
            json.dump(empty_dirs, fh, ensure_ascii=False, indent=2)
    else:
        L("None found.\n")

    # organization plan
    L("## 5. Organization plan (RuleEngine — category-based)")
    plan = build_plan(files)
    L(f"- Proposed moves: **{len(plan)}** (grouped by category folder)")
    L(f"- Plan written to `{plan_path.name}` (review before any execution)\n")
    with open(plan_path, "w", encoding="utf-8") as fh:
        json.dump({"root": str(ROOT), "total_items": len(plan),
                   "note": "READ-ONLY plan. Nothing executed. Review + approve before moving.",
                   "items": plan[:5000]}, fh, ensure_ascii=False, indent=2)

    # top-level breakdown
    L("## 6. Top-level directory breakdown")
    L("| Directory | Files | Size |")
    L("|---|---:|---:|")
    top_stats = defaultdict(lambda: [0, 0])
    for f in files:
        try:
            top = Path(f.path).relative_to(ROOT).parts[0]
        except Exception:
            top = "(root)"
        top_stats[top][0] += 1
        top_stats[top][1] += f.size
    for top, (c, b) in sorted(top_stats.items(), key=lambda x: -x[1][1]):
        L(f"| {top} | {c} | {human(b)} |")
    L("")
    L(f"\n---\nTotal time: {time.time()-t_start:.1f}s")

    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(log))
    print(f"\nLog written to {log_path}", flush=True)


if __name__ == "__main__":
    ROOT = None
    main()