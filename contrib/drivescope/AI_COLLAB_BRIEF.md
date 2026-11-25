# AI Collaboration Brief — Drive Organization Task
**Project:** DriveScope (external drive organization toolkit)
**Target:** `/run/media/xorthomson/My Passport` (Seagate USB, NTFS, 1.9 TB)
**Date:** 2026-11-24
**Status:** Analysis in progress. **Nothing has been moved or deleted.**

---

## 1. Objective (exact user requirements)

1. Organize / sort the files on the external drive.
2. Import the **features, rules, and tools** from
   `https://github.com/DrAbdulmalek/intelli-file-manager`.
3. Produce a **comprehensive log** useful for project development.
4. Detect **duplicate files** and **empty folders**.
5. **Deletion constraint (hard rule):** delete only files that are
   **100% identical in both size AND content**. Never delete near-duplicates.
6. **No deletion without explicit user approval.**

## 2. Verified environment facts

| Item | Value |
|---|---|
| Mount point | `/run/media/xorthomson/My Passport` |
| Device | `/dev/sdb1`, NTFS, 1.9 T total / 1.6 T used / 323 G free (83%) |
| File count | ~240,000 regular files |
| Python | 3.13.11 |
| Reference repo (local, updated) | `/home/xorthomson/02_Projects/GitHub/GitHub/intelli-file-manager` @ `2153f7c` |
| Work dir | `/home/xorthomson/02_Projects/GitHub/GitHub/arabic-handwriting-ocr-toolkit` |

### Top-level directories (measured)
| Directory | Files | Size |
|---|---:|---:|
| Lenovo laptop | 113,477 | 871 G |
| sorted | 35,923 | 311 G |
| sorted2 | 31,524 | 191 G |
| new | 7,073 | 76 G |
| samsung a12 | 26,575 | 26 G |
| مجلد جديد | 19,635 | 26 G |
| New Folder | 1,029 | 11 G |
| samsung sd card | 7,545 | 9.2 G |
| Documents | 16,801 | 8.9 G |
| NewFolder | 1,323 | 8.4 G |
| My memoQ projects | 13,819 | 2.2 G |
| PROGRAMME MAJAR | 62 | 1.5 G |
| DuplicateCleanerPro | 53 | 520 M |
| found.000 … found.069 | ~1,100 | ~100 M |
| $RECYCLE.BIN, System Volume Information | 59 | 147 M |

**Key insight:** `sorted`, `sorted2`, `new`, `New Folder`, `NewFolder`,
`مجلد جديد` are **previous manual sorting attempts** → high probability of
cross-folder duplication. `found.NNN` are **chkdsk recovery fragments**
(`.chk`), not real content. `msdownld.tmp` is empty.

## 3. Rules extracted from intelli-file-manager (authoritative)

Source files read from the repo (git objects, LFS bypassed):
`src/core/config.py`, `src/core/classifier.py`,
`src/core/duplicate_detector.py`, `src/core/organization.py`,
`rules/default_rules.yaml`.

### 3.1 Categories (9) and extension map
```
مستندات  صور  فيديو  صوت  أرشيفات  برمجة  أنظمة  خطوط  أخرى
```
Full extension→category map is in `drivescope_exec.py` (`EXTENSION_MAP`),
copied verbatim from `config.py`.

### 3.2 Duplicate detection contract
- **Exact**: identical SHA-256 ⇒ duplicates. Keep = **largest file**, tie-break
  by path (`suggested_keep`). `reclaimable_bytes = Σsizes − size(keep)`.
- **Near** (embedding cosine ≥ 0.95): *detected in the reference project but
  explicitly NOT deleted here*, per user rule.
- Reference behaviour: duplicates are **tagged**, deletion requires
  `delete_flag` and manual enablement.

### 3.3 Organization contract
- `organization.py` is a **read-only preflight**: it never moves, copies,
  renames or deletes. It emits an explainable plan with statuses
  (`planned`, `skipped_excluded`, `blocked_preflight`) and error categories
  (`permission_denied`, `read_only_filesystem`, `cross_device`,
  `name_collision`, `symlink_rejected`, `mount_boundary`).
- Skipped dirs: `.ssh .config .gnupg .git .venv venv __pycache__ node_modules`.
- Symlinks and nested mounts are never traversed.
- Protected roots are never touched.

## 4. Deliverables produced so far

| File | Purpose |
|---|---|
| `drivescope.py` | Read-only analyzer: inventory, categories, SHA-256 duplicates, empty dirs, plan, full log |
| `drivescope_exec.py` | Executor: `--dry-run` (default) / `--execute`. Exact-dup delete + smart sort |
| `DRIVESCOPE_WORKLOG.md` | Development log (design mapping, invariants, findings) |
| `drivescope_out/REVIEW_REPORT_ar.md` | Arabic review report (summary + categories + candidates) |
| `drivescope_out/execution_plan.json` | Pending: moves + 100%-identical deletes |
| `drivescope_out/duplicates.json` | Pending: duplicate groups |
| `drivescope_out/empty_dirs.json` | Pending: empty directories |

## 5. Exact algorithms (for independent reimplementation / review)

### 5.1 Scan
`os.walk(topdown=True, followlinks=False)`; prune `SKIP_DIRS` and `found.*`;
`lstat()` each entry; skip symlinks and non-regular files.

### 5.2 Exact duplicates (the only deletable class)
```
bucket by size; for buckets with ≥2 files: compute SHA-256 (1 MiB chunks)
group by digest; groups with ≥2 members are exact duplicates
keep = max(size, path); delete candidates = the rest
```
Two files are deletable **only if** size equal **and** digest equal.

### 5.3 Smart sort
For each non-duplicate, non-protected file whose top-level dir is not already a
category: target `‹root›/‹category›/‹name›`. Never overwrite an existing
destination (skip + count as error).

### 5.4 Execution safety
Protected roots untouched; no overwrite; `os.rename` within same filesystem;
per-item error counting; full JSON plan written before any mutation.

## 6. Current blocker / performance note

Duplicate hashing is **I/O-bound on USB** (~24,000 candidates hashed at last
check). Two processes currently scan the same spindle concurrently
(`drivescope.py` analyzer and `drivescope_exec.py --dry-run`), which slows both.
Recommended: let one finish, or run with `--no-hash` for a fast plan.

## 7. What we need from the collaborating model

1. Review `EXTENSION_MAP` for gaps (e.g. `.heic`, `.m4a`, `.tar.gz`, `.7z`,
   Arabic/RTL filenames, files with **no extension**).
2. Advise on collision handling when `‹category›/‹name›` already exists
   (rename with suffix vs. skip vs. content-hash subfolder).
3. Advise on whether to sort **inside** `Lenovo laptop`, `sorted`, `sorted2`
   or only at drive root (sorting inside 871 G of nested data is riskier).
4. Recommend an empty-directory policy (delete vs. keep, and whether to
   recurse bottom-up).
5. Suggest how to treat `found.*.chk` (chkdsk fragments) and
   `$RECYCLE.BIN`.
6. Propose verification steps proving no data loss (pre/post counts, sizes,
   checksum manifest).
7. Suggest the safest execution order and rollback strategy.

## 8. Hard constraints (must be preserved)

- No deletion except 100% identical (size + SHA-256).
- No action without explicit user approval.
- Never touch `$RECYCLE.BIN`, `System Volume Information`.
- Never overwrite an existing file.
- Keep an auditable JSON log of every planned and executed action.