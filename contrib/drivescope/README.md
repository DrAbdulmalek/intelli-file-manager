# contrib/drivescope — Drive organization toolkit

Port of **intelli-file-manager** design to local-first external-drive organization.

> **IMPORTANT:** Nothing is moved or deleted by default. All scripts run in
> `--dry-run` mode and write a plan for review before any `--execute`.

## Files

| File | Purpose |
|---|---|
| `drivescope.py` | Read-only analyzer: inventory → categories → exact SHA-256 duplicates → empty dirs → plan + full log |
| `drivescope_exec.py` | Executor: smart sort + **100%-identical-only** deletion (`--dry-run` default / `--execute`) |
| `REVIEW_REPORT_ar.md` | Arabic review report (target: My Passport, 1.9 TB NTFS, ~273K files) |
| `DRIVESCOPE_WORKLOG.md` | Development log (design mapping from intelli-file-manager, invariants) |
| `AI_COLLAB_BRIEF.md` | Detailed brief for a collaborating model |

## Design source (intelli-file-manager)

- `src/core/config.py` → `CATEGORIES` (9) + `EXTENSION_MAP` (extension → category)
- `src/core/duplicate_detector.py` → exact SHA-256 groups, `reclaimable_bytes`, `suggested_keep` (largest)
- `src/core/organization.py` → read-only preflight (`planned`/`skipped_excluded`/`blocked_preflight`)
- `rules/default_rules.yaml` → category-based move targets

## Safety invariants

1. Delete **only** files identical in size **and** SHA-256 (100% duplicates).
   Near-duplicates are never deleted.
2. Keep = largest file per duplicate group.
3. Never overwrite; never touch `$RECYCLE.BIN` / `System Volume Information`.
4. Never follow/move symlinks.
5. Full JSON plan written before any mutation.

## Usage

```bash
# 1. Analyze (read-only, writes plan + log)
python3 drivescope.py /run/media/xorthomson/My Passport --out ./drivescope_out

# 2. Build execution plan (dry-run, no changes)
python3 drivescope_exec.py /run/media/xorthomson/My Passport --out ./drivescope_out

# 3. Review drivescope_out/execution_plan.json
#    (exact-dup deletes + sort moves)

# 4. Apply ONLY after explicit approval
python3 drivescope_exec.py /run/media/xorthomson/My Passport --out ./drivescope_out --execute
```

## Notes

- Duplicate hashing is I/O-bound on USB; do not run two scans concurrently on the
  same spindle.
- Empty folders found in the target: **2,654** (candidates only, not deleted).