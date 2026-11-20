"""سياسة اجتياز المسارات المشتركة (Path traversal policy)."""
from __future__ import annotations

import os
import stat
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Union

__all__ = ["DEFAULT_SKIP_DIRS", "is_hidden_relative", "iter_files", "iter_entries_reported", "relative_parts"]

DEFAULT_SKIP_DIRS = frozenset({"__pycache__", "node_modules", ".git", ".venv", "venv"})
PathLike = Union[str, "os.PathLike[str]"]


def relative_parts(root: PathLike, path: PathLike) -> tuple[str, ...]:
    """أجزاء path نسبةً إلى root؛ إن لم يكن تحته تُعاد أجزاؤه كاملة."""
    try:
        return Path(path).relative_to(Path(root)).parts
    except ValueError:
        return Path(path).parts


def is_hidden_relative(root: PathLike, path: PathLike) -> bool:
    """هل أي جزء من المسار النسبي يبدأ بنقطة؟ آباء الجذر مستثناة."""
    return any(part.startswith(".") for part in relative_parts(root, path))


def iter_files(
    root: PathLike,
    *,
    recursive: bool = True,
    skip_hidden: bool = True,
    skip_dirs: Iterable[str] | None = DEFAULT_SKIP_DIRS,
) -> Iterator[Path]:
    """يولّد الملفات العادية، مع تقليم المجلدات المستثناة وعدم اتباع symlinks."""
    base = Path(root)
    if not base.is_dir():
        return
    skipped = frozenset(skip_dirs or ())

    for current, dirs, files in os.walk(base, followlinks=False, onerror=lambda _e: None):
        dirs[:] = sorted(
            d for d in dirs
            if d not in skipped and not (skip_hidden and d.startswith("."))
            and not (Path(current) / d).is_symlink()
        )
        for name in sorted(files):
            if skip_hidden and name.startswith("."):
                continue
            if name in skipped:
                continue
            item = Path(current) / name
            try:
                if item.is_symlink():
                    continue
                if item.is_file():
                    yield item
            except OSError:
                continue
        if not recursive:
            break


def iter_entries_reported(
    root: PathLike,
    *,
    skip_hidden: bool = True,
    skip_dirs: Iterable[str] | None = DEFAULT_SKIP_DIRS,
    max_depth: int = 32,
) -> Iterator[tuple[Path, os.stat_result | None, OSError | None, str | None]]:
    """اجتياز محافظ يُبلغ عن العناصر المتخطاة وأخطاء القراءة.

    يعيد (path, stat_result, error, reason). لا يتبع الروابط الرمزية،
    ولا يعبر إلى نظام ملفات آخر، ويُظهر أسباب التخطي بدلاً من إسقاطها بصمت.
    لا يقرأ محتوى الملفات ولا ينفذ أي تعديل.
    """
    base = Path(root)
    if isinstance(max_depth, bool) or not isinstance(max_depth, int) or max_depth < 0:
        raise ValueError("max_depth must be a non-negative integer")
    skipped = frozenset(skip_dirs or ())
    try:
        root_device = base.stat().st_dev
    except OSError as exc:
        yield base, None, exc, "root_unreadable"
        return

    stack: list[tuple[Path, tuple[str, ...], int]] = [(base, (), 0)]
    while stack:
        current, relative, depth = stack.pop()
        try:
            with os.scandir(current) as iterator:
                entries = sorted(iterator, key=lambda entry: entry.name.casefold())
        except OSError as exc:
            yield current, None, exc, "unreadable_directory"
            continue

        child_directories: list[tuple[Path, tuple[str, ...], int]] = []
        for entry in entries:
            path = Path(entry.path)
            parts = relative + (entry.name,)
            if skip_hidden and entry.name.startswith("."):
                yield path, None, None, "hidden"
                continue
            try:
                if entry.is_symlink():
                    info = entry.stat(follow_symlinks=False)
                    yield path, info, None, "symlink"
                    continue
                info = entry.stat(follow_symlinks=False)
                # st_dev alone misses bind mounts on the same filesystem.
                if os.path.ismount(path):
                    yield path, info, None, "mount_boundary"
                    continue
                if stat.S_ISDIR(info.st_mode):
                    if entry.name in skipped:
                        yield path, info, None, "excluded_directory"
                        continue
                    if info.st_dev != root_device:
                        yield path, info, None, "mount_boundary"
                        continue
                    if depth < max_depth:
                        yield path, info, None, None
                        child_directories.append((path, parts, depth + 1))
                    else:
                        yield path, info, None, "depth_limit"
                    continue
                if info.st_dev != root_device:
                    yield path, info, None, "mount_boundary"
                elif stat.S_ISREG(info.st_mode):
                    yield path, info, None, None
                else:
                    yield path, info, None, "unsupported_type"
            except OSError as exc:
                yield path, None, exc, "unreadable_entry"
        stack.extend(reversed(child_directories))
