# Organization Preflight Implementation

**Status:** Implemented as an isolated, read-only core module; not yet integrated into the desktop/API workflow.  
**Module:** `src/core/organization.py`  
**Tests:** `tests/unit/test_organization_preflight.py`

## Implemented in this change

- A read-only planner for proposed source → destination mappings.
- Core-layer exclusion enforcement; excluded sources are reported as `skipped_excluded` before source inspection.
- Explicit, caller-configured protected roots. The module does not guess that a path is OS-protected.
- Source type and directory inventory (regular-file count and byte total).
- Distinct classifications for missing source, permission denial, read-only filesystem, cross-device, collision, symlink, containment, unsupported type, and unknown OS errors; original errno is retained when available.
- Checks for symlink sources/components and symlinks encountered during directory inventory.
- Destination collision rejection; no implicit overwrite.
- Same-filesystem detection.
- A batch summary with per-item operation IDs and statuses.
- An explicit manifest writer using atomic replacement and mode 0600; absolute paths are redacted by default.

## Deliberate execution gate

The planner currently reports all non-excluded items as blocked from execution, including files whose read-only checks pass. This is intentional, not a false negative: review of the existing `SafeMover` found two blockers that must be fixed before the application can safely execute organization plans:

1. Its collision resolution is check-then-use, so a destination can appear between the check and `os.rename`.
2. Its `overwrite=True` path unlinks an existing destination before the source move is known to have succeeded.
3. Its cross-device fallback copies and publishes a temporary file, then deletes the source without verifying the copied checksum first.
4. The current mover is file-oriented and does not implement safe directory-tree moves.

Accordingly, this change does **not** call `SafeMover`, `RuleEngine.execute`, shell commands, privilege escalation, or any file mutation during planning. It does not claim that `os.access` guarantees a later operation will succeed; every future executor must still handle the actual OS error and errno.

## Not yet implemented

- Atomic no-overwrite execution and safe cross-device copy/verify/publish/source-retention semantics.
- Directory-tree execution, resumable batch execution, and rollback/recovery journal.
- UI/API preflight review and explicit execution confirmation.
- ActionLog integration and shareable diagnostic export UI.
- Full mount-boundary policy and race-resistant descriptor-relative traversal.

These items require a separate implementation phase and tests. Do not interpret a `planned` state as permission to execute: in this initial implementation, the execution gate intentionally leaves every non-excluded item in `blocked_preflight`.

## Validation status

Unit tests were added but have not been run in this environment. No claim is made that tests, lint, or CI passed. The next gate is to run the focused tests and static checks in a clean checkout, fix any findings, then independently review SafeMover hardening before enabling execution.
