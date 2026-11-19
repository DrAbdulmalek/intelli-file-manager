"""سياسة اجتياز المسارات المشتركة (Path traversal policy)."""
from __future__ import annotations

import os
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Union

__all__ = ["DEFAULT_SKIP_DIRS", "is_hidden_relative", "iter_files", "relative_parts"]

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
