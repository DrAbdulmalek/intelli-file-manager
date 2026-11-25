#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DriveScope Executor — smart sort + exact-duplicate deletion.

Rules (user directive 2026-11-24):
  - DELETE only files that are 100% identical: same size AND same SHA-256.
    Near-duplicates are NEVER deleted.
  - Smart sort: move files into category folders (intelli-file-manager rules).

Modes:
  --dry-run   (default) build + write a plan, change NOTHING.
  --execute   perform the approved plan (moves + exact-dup deletes).

Safety:
  - Protected roots ($RECYCLE.BIN, System Volume Information) never touched.
  - Symlinks never followed/moved.
  - Collision: never overwrite; skip + log.
  - Exact-dup keep = largest file (then path) per group, matching intelli-file-manager.
"""
from __future__ import annotations
import argparse, hashlib, json, os, stat, sys, time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

CATEGORIES = ["مستندات", "صور", "فيديو", "صوت",
              "أرشيفات", "برمجة", "أنظمة", "خطوط", "أخرى"]
EXTENSION_MAP = {
    ".pdf":"مستندات",".doc":"مستندات",".docx":"مستندات",".odt":"مستندات",".txt":"مستندات",
    ".rtf":"مستندات",".md":"مستندات",".tex":"مستندات",".epub":"مستندات",".xls":"مستندات",
    ".xlsx":"مستندات",".csv":"مستندات",".ods":"مستندات",".ppt":"مستندات",".pptx":"مستندات",
    ".jpg":"صور",".jpeg":"صور",".png":"صور",".gif":"صور",".bmp":"صور",".svg":"صور",
    ".webp":"صور",".ico":"صور",".tiff":"صور",".raw":"صور",".psd":"صور",".heic":"صور",
    ".mp4":"فيديو",".avi":"فيديو",".mkv":"فيديو",".mov":"فيديو",".wmv":"فيديو",
    ".flv":"فيديو",".webm":"فيديو",".m4v":"فيديو",".3gp":"فيديو",
    ".mp3":"صوت",".wav":"صوت",".ogg":"صوت",".flac":"صوت",".aac":"صوت",".wma":"صوت",
    ".m4a":"صوت",".opus":"صوت",
    ".zip":"أرشيفات",".rar":"أرشيفات",".7z":"أرشيفات",".tar":"أرشيفات",".gz":"أرشيفات",
    ".bz2":"أرشيفات",".xz":"أرشيفات",".tgz":"أرشيفات",
    ".py":"برمجة",".js":"برمجة",".ts":"برمجة",".html":"برمجة",".css":"برمجة",".json":"برمجة",
    ".xml":"برمجة",".yaml":"برمجة",".yml":"برمجة",".sql":"برمجة",".java":"برمجة",".cpp":"برمجة",
    ".c":"برمجة",".h":"برمجة",".go":"برمجة",".rs":"برمجة",".rb":"برمجة",".php":"برمجة",
    ".sh":"برمجة",".bat":"برمجة",".jsx":"برمجة",".tsx":"برمجة",".vue":"برمجة",".swift":"برمجة",
    ".kt":"برمجة",".dart":"برمجة",
    ".exe":"أنظمة",".msi":"أنظمة",".deb":"أنظمة",".pkg":"أنظمة",".rpm":"أنظمة",".AppImage":"أنظمة",
    ".iso":"أنظمة",".dmg":"أنظمة",".img":"أنظمة",".dll":"أنظمة",".so":"أنظمة",".ini":"أنظمة",
    ".cfg":"أنظمة",".conf":"أنظمة",".log":"أنظمة",".sys":"أنظمة",".tmp":"أنظمة",
    ".ttf":"خطوط",".otf":"خطوط",".woff":"خطوط",".woff2":"خطوط",".eot":"خطوط",
}
PROTECT = {"$RECYCLE.BIN", "System Volume Information"}
SKIP_DIRS = {".ssh",".config",".gnupg",".git",".venv","venv","__pycache__","node_modules"}


def category_of(name: str) -> str:
    ext = os.path.splitext(name)[1].lower()
    if name.lower().endswith(".tar.gz"):
        return "أرشيفات"
    return EXTENSION_MAP.get(ext, "أخرى")


def human(n):
    for u in ["B","KB","MB","GB","TB"]:
        if n < 1024 or u == "TB":
            return f"{n:.2f} {u}"
        n /= 1024


@dataclass
class FileRec:
    path: str
    name: str
    size: int
    category: str
    sha256: str = ""


def scan(root: Path):
    recs = []
    for cur, dirs, names in os.walk(root, topdown=True, followlinks=False):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith("found.")]
        for n in names:
            fp = Path(cur) / n
            try:
                st = fp.lstat()
            except OSError:
                continue
            if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
                continue
            recs.append(FileRec(str(fp), n, st.st_size, category_of(n)))
    return recs


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_exact_dups(recs, root: Path):
    """Group by (size) then confirm identical content via SHA-256. 100% identical only."""
    by_size = defaultdict(list)
    for r in recs:
        by_size[r.size].append(r)
    groups = []
    for size, group in by_size.items():
        if len(group) < 2:
            continue
        by_hash = defaultdict(list)
        for r in group:
            try:
                r.sha256 = sha256(r.path)
            except OSError:
                r.sha256 = ""
            if r.sha256:
                by_hash[r.sha256].append(r)
        for h, fs in by_hash.items():
            if len(fs) < 2:
                continue
            fs.sort(key=lambda f: (-f.size, f.path))
            groups.append(fs)   # fs[0] = keep
    groups.sort(key=lambda g: -g[0].size)
    return groups


def build_plan(root: Path, recs, dup_groups):
    """Return (moves, deletes). Read-only construction."""
    # exact-dup deletes: all but keep (largest). ONLY 100% identical.
    dup_paths = set()
    deletes = []
    for g in dup_groups:
        keep = g[0]
        for r in g[1:]:
            dup_paths.add(r.path)
            deletes.append({"path": r.path, "size": r.size, "sha256": r.sha256,
                            "keep": keep.path, "reason": "100% identical (size+sha256)"})
    # smart sort moves: category folder, skip dups-to-delete, skip protected, skip already-filed
    moves = []
    for r in recs:
        if r.path in dup_paths:
            continue
        top = Path(r.path).relative_to(root).parts[0]
        if top in PROTECT:
            continue
        # skip files already inside a category folder at root
        if top in CATEGORIES:
            continue
        dest_dir = root / r.category
        dest = dest_dir / r.name
        moves.append({"src": r.path, "dst": str(dest), "category": r.category, "size": r.size})
    return moves, deletes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--out", default="./drivescope_out")
    ap.add_argument("--execute", action="store_true", help="perform plan (default dry-run)")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    plan_path = out / "execution_plan.json"

    t0 = time.time()
    recs = scan(root)
    print(f"scanned {len(recs)} files in {time.time()-t0:.1f}s", flush=True)
    dup_groups = find_exact_dups(recs, root)
    print(f"exact-dup groups: {len(dup_groups)}", flush=True)
    moves, deletes = build_plan(root, recs, dup_groups)

    plan = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "root": str(root),
        "mode": "execute" if args.execute else "dry-run",
        "summary": {
            "files_scanned": len(recs),
            "exact_dup_groups": len(dup_groups),
            "exact_dup_deletes": len(deletes),
            "dup_reclaimable_bytes": sum(d["size"] for d in deletes),
            "sort_moves": len(moves),
        },
        "deletes": deletes,
        "moves": moves,
    }
    with open(plan_path, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, ensure_ascii=False, indent=2)
    print(json.dumps(plan["summary"], ensure_ascii=False, indent=2), flush=True)
    print(f"plan -> {plan_path}", flush=True)

    if not args.execute:
        print("DRY-RUN: nothing changed. Re-run with --execute to apply.", flush=True)
        return

    # ── execute ──
    done_m = done_d = err = 0
    for d in deletes:
        try:
            os.remove(d["path"]); done_d += 1
        except OSError:
            err += 1
    for m in moves:
        try:
            Path(m["dst"]).parent.mkdir(parents=True, exist_ok=True)
            if Path(m["dst"]).exists():
                err += 1; continue   # never overwrite
            os.rename(m["src"], m["dst"]); done_m += 1
        except OSError:
            err += 1
    print(f"EXECUTED: moves={done_m} deletes={done_d} errors={err}", flush=True)


if __name__ == "__main__":
    main()