"""Read-only preflight for safe local file organization.

This module deliberately does not move, copy, rename, delete, elevate privileges,
or invoke a shell. It creates an explainable plan that a later, separately
confirmed executor can consume. A preflight is advisory: permissions and mounts
can change between inspection and execution, so the executor must still handle
the original OSError and errno.
"""
from __future__ import annotations

import errno
import json
import os
import stat
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


STATUS_PLANNED = "planned"
STATUS_SKIPPED_EXCLUDED = "skipped_excluded"
STATUS_BLOCKED_PREFLIGHT = "blocked_preflight"

ERROR_CATEGORIES = {
    errno.EACCES: "permission_denied",
    errno.EPERM: "permission_denied",
    errno.EROFS: "read_only_filesystem",
    errno.EXDEV: "cross_device",
    errno.ENOENT: "destination_missing",
    errno.EEXIST: "name_collision",
}


def classify_os_error(error: OSError) -> str:
    """Return a stable category while preserving errno in the plan."""
    return ERROR_CATEGORIES.get(error.errno, "unknown_os_error")


def _absolute(path: os.PathLike[str] | str) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _has_symlink_component(path: Path) -> bool:
    """Inspect every existing component without following symlinks."""
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            return False
        if stat.S_ISLNK(mode):
            return True
    return False


def _access(path: Path, mode: int) -> bool:
    """Use effective credentials where supported; never attempt a write."""
    try:
        return os.access(path, mode, effective_ids=True)
    except (TypeError, NotImplementedError):
        return os.access(path, mode)


def _raise_walk_error(error: OSError) -> None:
    raise error


def _tree_summary(root: Path) -> tuple[int, int, bool]:
    """Return regular-file count, byte count, and whether any symlink exists."""
    count = 0
    total_bytes = 0
    has_symlink = False
    for current, dirs, files in os.walk(
        root, topdown=True, followlinks=False, onerror=_raise_walk_error
    ):
        current_path = Path(current)
        kept_dirs = []
        for name in dirs:
            child = current_path / name
            if child.is_symlink():
                has_symlink = True
            else:
                kept_dirs.append(name)
        dirs[:] = kept_dirs
        for name in files:
            child = current_path / name
            try:
                info = child.lstat()
            except OSError:
                raise
            if stat.S_ISLNK(info.st_mode):
                has_symlink = True
            elif stat.S_ISREG(info.st_mode):
                count += 1
                total_bytes += info.st_size
    return count, total_bytes, has_symlink


@dataclass
class OrganizationPlanItem:
    source: str
    destination: str
    kind: str
    status: str
    reason: str = ""
    error_category: str = ""
    errno: Optional[int] = None
    file_count: int = 0
    total_bytes: int = 0
    same_filesystem: Optional[bool] = None
    operation_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class OrganizationPlan:
    created_at: str
    base_dir: str
    items: list[OrganizationPlanItem]
    schema_version: int = 1

    @property
    def summary(self) -> dict[str, int]:
        counts = {STATUS_PLANNED: 0, STATUS_SKIPPED_EXCLUDED: 0,
                  STATUS_BLOCKED_PREFLIGHT: 0}
        for item in self.items:
            counts[item.status] = counts.get(item.status, 0) + 1
        counts["total"] = len(self.items)
        return counts

    def to_dict(self, *, redact_absolute_paths: bool = False) -> dict:
        items = []
        base = Path(self.base_dir)
        for item in self.items:
            record = item.to_dict()
            if redact_absolute_paths:
                for key in ("source", "destination"):
                    path = Path(record[key])
                    try:
                        record[key] = path.relative_to(base).as_posix()
                    except ValueError:
                        record[key] = path.name
            items.append(record)
        return {
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "base_dir": "." if redact_absolute_paths else self.base_dir,
            "summary": self.summary,
            "items": items,
        }


def preflight_item(
    source: os.PathLike[str] | str,
    destination: os.PathLike[str] | str,
    *,
    excluded_paths: Iterable[os.PathLike[str] | str] = (),
    protected_roots: Iterable[os.PathLike[str] | str] = (),
) -> OrganizationPlanItem:
    """Inspect one proposed move without changing the filesystem.

    The current SafeMover implementation handles files, not directory trees.
    Directories are therefore classified for review but never marked executable.
    """
    src = _absolute(source)
    dst = _absolute(destination)
    item = OrganizationPlanItem(
        source=str(src), destination=str(dst), kind="unknown", status=STATUS_PLANNED
    )

    try:
        excluded = [_absolute(p) for p in excluded_paths]
        if any(_is_within(src, path) for path in excluded):
            item.status = STATUS_SKIPPED_EXCLUDED
            item.reason = "Path is covered by an explicit user exclusion."
            return item

        roots = [_absolute(p) for p in protected_roots]
        if any(_is_within(src, root) or _is_within(dst, root) for root in roots):
            item.status = STATUS_BLOCKED_PREFLIGHT
            item.reason = "Path is inside a user-configured protected root."
            item.error_category = "protected_location"
            return item

        try:
            source_info = src.lstat()
        except OSError as exc:
            item.status = STATUS_BLOCKED_PREFLIGHT
            item.reason = "Source cannot be inspected."
            item.error_category = "source_missing" if exc.errno == errno.ENOENT else classify_os_error(exc)
            item.errno = exc.errno
            return item

        if stat.S_ISLNK(source_info.st_mode):
            item.status = STATUS_BLOCKED_PREFLIGHT
            item.reason = "Symbolic-link sources are not accepted by this preflight."
            item.error_category = "symlink_rejected"
            return item
        if stat.S_ISREG(source_info.st_mode):
            item.kind = "file"
            item.file_count = 1
            item.total_bytes = source_info.st_size
        elif stat.S_ISDIR(source_info.st_mode):
            count, size, has_symlink = _tree_summary(src)
            item.kind = "empty_directory" if count == 0 and not any(src.iterdir()) else "directory"
            item.file_count = count
            item.total_bytes = size
            if has_symlink:
                item.status = STATUS_BLOCKED_PREFLIGHT
                item.reason = "Directory contains symbolic links; traversal is blocked."
                item.error_category = "symlink_rejected"
                return item
            item.status = STATUS_BLOCKED_PREFLIGHT
            item.reason = "Directory moves are not supported by the current file-only SafeMover."
            item.error_category = "unsupported_operation"
            return item
        else:
            item.status = STATUS_BLOCKED_PREFLIGHT
            item.reason = "Only regular files and directories are supported."
            item.error_category = "unsupported_file_type"
            return item

        if _has_symlink_component(src) or _has_symlink_component(dst.parent):
            item.status = STATUS_BLOCKED_PREFLIGHT
            item.reason = "A symbolic-link path component was detected."
            item.error_category = "symlink_rejected"
            return item

        try:
            src_real = src.resolve(strict=True)
            dst_parent_real = dst.parent.resolve(strict=True)
        except OSError as exc:
            item.status = STATUS_BLOCKED_PREFLIGHT
            item.reason = "Source or destination parent cannot be resolved."
            item.error_category = classify_os_error(exc)
            item.errno = exc.errno
            return item

        if src_real == dst_parent_real or _is_within(dst_parent_real, src_real):
            item.status = STATUS_BLOCKED_PREFLIGHT
            item.reason = "Destination is the source or is inside the source."
            item.error_category = "path_containment"
            return item
        if _is_within(src_real, dst_parent_real) and src.name == dst.name:
            item.status = STATUS_BLOCKED_PREFLIGHT
            item.reason = "Source and destination resolve to the same location."
            item.error_category = "same_path"
            return item

        if dst.exists() or dst.is_symlink():
            item.status = STATUS_BLOCKED_PREFLIGHT
            item.reason = "Destination already exists; overwrite is never implicit."
            item.error_category = "name_collision"
            item.errno = errno.EEXIST
            return item

        if not _access(src, os.R_OK):
            item.status = STATUS_BLOCKED_PREFLIGHT
            item.reason = "Source is not readable by the current process."
            item.error_category = "permission_denied"
            item.errno = errno.EACCES
            return item
        if not _access(src.parent, os.W_OK | os.X_OK):
            item.status = STATUS_BLOCKED_PREFLIGHT
            item.reason = "Source parent is not writable by the current process."
            item.error_category = "permission_denied"
            item.errno = errno.EACCES
            return item
        if not _access(dst.parent, os.W_OK | os.X_OK):
            item.status = STATUS_BLOCKED_PREFLIGHT
            item.reason = "Destination parent is not writable by the current process."
            item.error_category = "permission_denied"
            item.errno = errno.EACCES
            return item

        item.same_filesystem = src.stat().st_dev == dst.parent.stat().st_dev
        if not item.same_filesystem:
            item.reason = (
                "Cross-filesystem move detected; current SafeMover must be hardened "
                "before this item can be executed."
            )
            item.status = STATUS_BLOCKED_PREFLIGHT
            item.error_category = "cross_device"
            item.errno = errno.EXDEV
            return item

        # SafeMover's current collision resolver is check-then-use, and its
        # overwrite path deletes existing destinations before the move succeeds.
        # Do not mark this as executable until those races are fixed.
        item.status = STATUS_BLOCKED_PREFLIGHT
        item.reason = (
            "Preflight passed, but execution is gated pending SafeMover race/"
            "rollback hardening. No filesystem operation was attempted."
        )
        item.error_category = "executor_not_hardened"
        return item

    except OSError as exc:
        item.status = STATUS_BLOCKED_PREFLIGHT
        item.reason = "Preflight failed with an operating-system error."
        item.error_category = classify_os_error(exc)
        item.errno = exc.errno
        return item


def build_organization_plan(
    mappings: Iterable[tuple[os.PathLike[str] | str, os.PathLike[str] | str]],
    *,
    base_dir: os.PathLike[str] | str,
    excluded_paths: Iterable[os.PathLike[str] | str] = (),
    protected_roots: Iterable[os.PathLike[str] | str] = (),
) -> OrganizationPlan:
    """Build a read-only batch plan; exclusions are checked in the core layer."""
    base = _absolute(base_dir)
    exclusions = tuple(excluded_paths)
    protected = tuple(protected_roots)
    items = [
        preflight_item(src, dst, excluded_paths=exclusions, protected_roots=protected)
        for src, dst in mappings
    ]
    return OrganizationPlan(
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        base_dir=str(base),
        items=items,
    )


def write_plan_manifest(
    plan: OrganizationPlan,
    destination: os.PathLike[str] | str,
    *,
    redact_absolute_paths: bool = True,
) -> Path:
    """Explicitly persist a private manifest using atomic replacement.

    This function is separate from planning because writing a manifest is a
    filesystem mutation. It creates the parent directory and a mode-0600 file.
    """
    target = _absolute(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        plan.to_dict(redact_absolute_paths=redact_absolute_paths),
        ensure_ascii=False,
        indent=2,
    )
    fd, temporary_name = tempfile.mkstemp(prefix=".ifm-plan-", dir=str(target.parent))
    temporary = Path(temporary_name)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            temporary.unlink()
        except OSError:
            pass
        raise
    return target
