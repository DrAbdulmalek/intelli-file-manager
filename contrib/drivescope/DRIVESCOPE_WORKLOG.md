# DriveScope — Comprehensive Development Log

> Read-only external-drive organization toolkit inspired by
> [intelli-file-manager](https://github.com/DrAbdulmalek/intelli-file-manager).
> **Nothing is moved, copied, renamed, or deleted by this tool.** It only reads
> metadata and emits a plan + reports for human review.

## 1. Objective

Organize `/run/media/xorthomson/My Passport` (1.9 TB USB, ~240 K files) using the
sorting **features, rules, and tools** of `intelli-file-manager`, produce a
comprehensive development log, and surface **duplicate files** and **empty
folders** as deletion candidates — **without deleting anything without explicit
user approval.**

## 2. Reference project — extracted design

Cloned `DrAbdulmalek/intelli-file-manager` (LFS checkout bypassed via
`git show HEAD:<path>`). The following modules were ported in spirit:

| intelli-file-manager module | Purpose | DriveScope equivalent |
|---|---|---|
| `src/core/config.py` (`CATEGORIES`, `EXTENSION_MAP`) | 9 categories + extension→category map | `CATEGORIES`, `EXTENSION_MAP`, `category_of()` |
| `src/core/classifier.py` (`SmartFileClassifier`) | classify by extension/content | `category_of()` (extension tier) |
| `src/core/duplicate_detector.py` | exact SHA-256 + near (embedding) groups, `reclaimable_bytes`, `suggested_keep` (largest) | `hash_duplicates()`, `DupGroup` |
| `src/core/organization.py` (`preflight`, `OrganizationPlan`) | read-only plan, never mutates, explainable statuses | `build_plan()` (read-only) |
| `rules/default_rules.yaml` (RuleEngine) | priority rules, `move`/`tag`/`delete_flag`, duplicate tagging not deletion | category rule in `build_plan()` |

### Key design invariants inherited
1. **Read-only preflight** — plan is advisory; a *separate, confirmed* executor acts.
2. **Duplicates are tagged, never auto-deleted** (`delete_flag` only on manual enable).
3. **Keep strategy = largest file** (then alphabetical) per duplicate group.
4. **Protected roots** (`$RECYCLE.BIN`, `System Volume Information`) never touched.
5. **Symlinks / nested mounts** are not traversed.

## 3. Categories (from config.py)

`مستندات · صور · فيديو · صوت · أرشيفات · برمجة · أنظمة · خطوط · أخرى`
(documents, images, video, audio, archives, code, systems, fonts, other).

## 4. Drive profile (read-only `du`/`find`)

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
| found.000–found.069 | ~1,100 | ~100 M (chkdsk `.chk` fragments) |
| $RECYCLE.BIN / System Volume Information | 59 | 147 M (protected) |

**Observations**
- `sorted`, `sorted2`, `New Folder`, `NewFolder`, `new`, `مجلد جديد` are
  **prior manual organization attempts** → high duplication risk across them.
- `found.0NN` are **chkdsk recovery fragments** (`.chk`) — review, not content.
- `msdownld.tmp` is empty (0 files).

## 5. Tool: `drivescope.py`

```
python3 drivescope.py "<drive>" --out ./drivescope_out [--no-hash]
```

Phases: **(1)** inventory scan → **(2)** category distribution → **(3)** exact
SHA-256 duplicate grouping (size-bucketed) → **(4)** empty-dir list → **(5)**
category organization plan → **(6)** top-level breakdown. Emits:

- `drivescope_log.md` — full human-readable report
- `organization_plan.json` — proposed moves (review-only)
- `duplicates.json` — duplicate groups w/ keep + redundant lists
- `empty_dirs.json` — empty directory candidates

## 6. Safety posture

- No destructive syscall in the codebase (only `os.walk`, `lstat`, `open(rb)`, `json.dump`).
- Deletion candidates are **reported only**; execution gated on user approval.
- Protected/system dirs skipped.

## 7. Next steps (pending user approval)

1. Review `drivescope_out/duplicates.json` → approve keep/redundant sets.
2. Review `drivescope_out/empty_dirs.json` → approve empty-dir removal.
3. Approve category-based move plan (or a subset).
4. Only then run a *separate* confirmed executor (not yet written).