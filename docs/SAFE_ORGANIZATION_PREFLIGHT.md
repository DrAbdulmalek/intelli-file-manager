# Safe Organization Preflight: Lessons from Real-World Home Folder Operations

**Status:** Proposal for implementation  
**Scope:** Desktop-first local file organization  
**Evidence source:** Manually authored operational notes committed on 2026-11-19 in `LOGS/home_organization_stage1.log` (the source file contains an absolute home path and is not sanitized)  
**Non-goal:** This document does not authorize moving any user's files or changing protected operating-system locations.

## 1. What the operational log tells us

A real organization session recorded these outcomes:

- Two user-selected folders were moved successfully.
- A non-empty documents folder and a small library folder could not be moved because the operation was blocked at the home-directory boundary.
- Empty media folders were also listed as blocked, although an empty-folder move should be treated as a separate, low-complexity case.
- Two explicitly excluded directories were preserved.
- The log records the outcome, but does not include the exact OS error code, filesystem/mount details, destination preflight, or a post-move content manifest.

This is useful workflow evidence, not an IntelliFile runtime/crash log. It does **not** prove whether the block came from permissions, a sandbox, a desktop portal, filesystem policy, or another OS mechanism. IntelliFile must report the observed error rather than guessing its cause.

The log's suggested shell commands are not safe to reuse verbatim: `Calibre Library/` is unquoted despite containing a space, and `2>/dev/null || true` suppresses errors for the empty media-folder moves. The application must use filesystem APIs, preserve each error, and report per-item outcomes instead of copying these commands.

## 2. Product improvements justified by this evidence

### P0 — Preflight every planned operation

Before any move/copy batch, produce a read-only plan for each item:

- Resolve and display source and destination paths.
- Confirm the source exists and classify it as file, non-empty directory, or empty directory.
- Confirm the destination parent exists or can be created without crossing a protected boundary.
- Check source readability and destination-parent writability using actual OS operations that do not mutate user data.
- Detect same-filesystem versus cross-filesystem moves.
- Detect collisions, symlink components, mount boundaries, and source/destination containment hazards.
- Capture the exact failure category and errno when a check fails.

Do not treat a failed preflight as permission to retry with elevated privileges.

### P0 — Explain protected-path failures without unsafe workarounds

Represent at least these outcomes distinctly:

- `permission_denied` (`EACCES` / `EPERM`)
- `read_only_filesystem` (`EROFS`)
- `cross_device` (`EXDEV`)
- `destination_missing`
- `name_collision`
- `protected_location` only when the OS/API provides evidence for that classification
- `unknown_os_error` with the original errno and a safe, concise message

The UI should identify the blocked item, source, destination, exact reason available from the OS, and a safe next step. Never suggest `sudo`, silently bypass errors, or generate shell commands with unquoted paths.

### P0 — Preserve explicit exclusions

Allow the user to mark paths as excluded before planning. Exclusions must be enforced by the operation layer, not only hidden in the UI. Show excluded items in the plan and record that no operation was attempted on them.

### P1 — Make batch operations resumable and auditable

Use per-item states such as `planned`, `skipped_excluded`, `blocked_preflight`, `in_progress`, `verified`, `failed`, and `rolled_back`. A blocked item must not prevent independent eligible items from being reported, but the batch summary must never say “complete” while any planned item remains blocked.

Persist a manifest containing relative paths, file counts, byte totals, timestamps, operation IDs, and per-item results. Avoid storing unrelated file contents.

### P1 — Verify cross-filesystem moves before deleting sources

For `EXDEV` moves, use copy-to-temporary-destination, flush/close, verify size and checksum, atomically publish the destination, and only then remove the source. If verification or publication fails, retain the source and clean up only the operation's own temporary file. Do not report success until the final state is verified.

### P1 — Handle empty directories explicitly

An empty directory should not be reported as an ordinary permission failure without a real OS error. Detect emptiness and show a separate no-content operation result. Do not hide errors with shell constructs such as `|| true`.

## 3. UI behavior

Add a reviewable “Organization preflight” step before execution:

1. Preview the proposed source → destination mapping.
2. Show file count and estimated bytes.
3. Show excluded, empty, blocked, and collision items separately.
4. Require explicit confirmation for the eligible operations.
5. Show per-item progress and final verification.
6. Offer retry only after the user changes the destination or resolves the reported OS restriction; never auto-elevate.

## 4. Privacy and safety

- Keep plans, manifests, and diagnostics local by default.
- Do not upload directory listings, filenames, or logs to remote AI services.
- Redact usernames and absolute home paths from shareable diagnostic exports unless the user explicitly opts in.
- Never move, rename, or delete excluded paths.
- Never execute generated shell snippets as an implementation mechanism; call filesystem APIs with argument-safe paths.
- Do not infer that a location is system-protected solely from a human-written log.

## 5. Acceptance tests

Add tests before implementation is considered complete:

1. Permission denied on a destination parent is reported with the original errno and leaves the source unchanged.
2. A protected-path preflight blocks execution and does not invoke an elevated retry.
3. A path containing spaces is handled as a single path component; no shell parsing is involved.
4. Explicitly excluded paths are never passed to the mover.
5. Empty directories are classified separately from non-empty directories.
6. A batch with one blocked item and one eligible item reports partial completion accurately.
7. Cross-device copy verification failure retains the source and removes only its own temporary destination.
8. A collision is surfaced before execution and does not overwrite existing data.
9. Symlink and source-inside-destination cases are rejected or handled by a documented safe policy.
10. A resumed batch does not repeat already verified operations.

## 6. Implementation boundary

This proposal is intentionally documentation-only. It does not change `SafeMover`, `RuleEngine`, the filesystem watcher, or existing operation semantics. A first read-only preflight implementation and focused tests are proposed separately in PR #54. That implementation deliberately blocks all execution until the current mover's rollback, collision, symlink, and cross-device behavior has been independently reviewed.

## 7. Evidence and limitations

The source log reports successful moves for two folders, blocked attempts for several others, and two user-requested exclusions. It also contains an absolute home path; redact that path in any shareable copy. The log's claims are treated as reported observations, not independently verified filesystem facts. It does not include command output, errno values, filesystem metadata, checksums, or a complete before/after manifest. Therefore this proposal converts the observed workflow into testable product requirements without claiming that IntelliFile itself caused or resolved the operating-system restriction.
