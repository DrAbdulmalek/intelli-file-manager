# SafeMover no-clobber hardening

## Scope
This change hardens file-level move/copy operations only. It does not enable directory-tree moves or claim that the preflight planner is an execution authorization.

## Publication protocol

1. Reject missing, symlink, and non-regular sources using `lstat`; also reject existing symlinked source/destination path components (failing closed if a component cannot be inspected).
2. Stage a copy in the destination directory (same filesystem as the final entry).
3. Flush the staged file and compute SHA-256 for the source before/after staging and for the staged copy. Compare source identity metadata as an additional mutation check.
4. Publish with `os.link(temp, destination)`. This is an atomic create-if-absent operation: if another process creates the destination after collision selection, publication fails with `EEXIST`; the existing target is never replaced.
5. For a move, compute and compare the published destination digest and re-check source identity/content. Delete the source only as the final commit step.
6. For cross-filesystem moves, the same verified copy/publish/delete protocol applies; no `EXDEV` path deletes the source before verification.

## Explicit safety choices

- `overwrite=True` no longer deletes or replaces an existing destination. It returns a failure and preserves both source and destination. This is a deliberate compatibility change to prevent destructive replacement.
- Name collision suffix selection is advisory; the atomic publish operation is authoritative. If a race occurs, the operation fails safely rather than retrying against a possibly changed namespace.
- Filesystems without hard-link support fail closed. There is no fallback to `os.rename` or `os.replace`, because those may replace an existing target.
- A failed source unlink after successful publication may leave both source and destination. This is reported as a failed/incomplete move; neither copy is discarded.
- Sidecar collisions are not merged or overwritten implicitly. The source sidecar is retained and a warning is logged.
- A directory fsync failure is logged as a durability warning after publication; it does not cause the code to pretend the published destination was absent.

## Known limits requiring future work

- There remains a narrow external-process race between path-component checks and subsequent pathname operations, and between the final source identity check and pathname unlink; Python's portable path API does not provide an atomic unlink-if-inode-matches primitive. Stronger protection requires descriptor-relative operations and platform-specific support, or an OS-level lock/transaction strategy.
- A hard-link publication requirement can reject exFAT and other filesystems that do not support hard links. This is intentionally safer than silently falling back to overwrite-capable rename. A separately designed platform-aware no-replace primitive is needed before supporting those filesystems.
- The operation is file-only. Directory trees, mount-boundary traversal, resumable batch transactions, and durable operation journals remain out of scope.
- Sidecar merge semantics are disabled for collisions until an atomic, lossless merge protocol is designed.

## Validation added

Integration tests cover overwrite refusal, collision-race failure with source retention, symlink source/parent rejection, and staged-copy checksum failure. The tests must run in CI and on Linux; additional filesystem compatibility testing is required before release. No test result is claimed until CI reports it.
