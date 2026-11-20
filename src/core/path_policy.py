"""سياسة اجتياز المسارات المشتركة (Path traversal policy)."""
from __future__ import annotations

import os
import stat
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Union

__all__ = [
    "DEFAULT_SKIP_DIRS",
    "is_hidden_relative",
    "iter_files",
    "relative_parts",
]

DEFAULT_SKIP_DIRS = frozenset(
    {
        "__pycache__",
        "node_modules",
        ".git",
        ".venv",
        "venv",
        ".ssh",
        ".config",
        ".gnupg",
    }
)
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


def _is_mount_point(path: Path) -> bool:
    """هل المسار يمثل نقطة تركيب (mount point)؟"""
    try:
        return Path(path).is_mount()
    except OSError:
        # Fail closed: تعذر التحقق من حدّ التركيب يعني عدم دخول هذا الفرع.
        return True


def _has_symlink_component(path: Path) -> bool:
    """يفحص جميع المكونات الموجودة دون اتباع الروابط الرمزية."""
    absolute = Path(os.path.abspath(os.fspath(path)))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            return False
        except OSError:
            return True
        if stat.S_ISLNK(info.st_mode):
            return True
    return False


def iter_files(
    root: PathLike,
    *,
    recursive: bool = True,
    skip_hidden: bool = True,
    skip_dirs: Iterable[str] | None = DEFAULT_SKIP_DIRS,
) -> Iterator[Path]:
    """يولّد الملفات العادية، مع تقليم المجلدات المستثناة وعدم اتباع symlinks.

    سلوك السلامة:
      - لا يتبع الروابط الرمزية (symlinks).
      - لا يعبر نقاط التركيب (mount points).
      - لا يخفي أخطاء os.walk (تُرفع كاستثناءات OSError).
      - لا يدخل المجلدات المحددة في skip_dirs.
    """
    base = Path(root)
    if _has_symlink_component(base):
        raise OSError(f"جذر المسح يحتوي مكوّن رابط رمزي محظور: {base}")
    if not base.is_dir():
        return

    # الجذر الذي اختاره المستخدم صراحةً مسموح حتى لو كان mount point
    # (مثلاً قرصاً خارجياً). تُمنع نقاط التركيب الفرعية غير المختارة.
    skipped = frozenset(skip_dirs or ())

    def on_walk_error(error: OSError) -> None:
        """معالج أخطاء os.walk: لا يُخفي الأخطاء بصمت."""
        raise error

    for current, dirs, files in os.walk(
        base, followlinks=False, onerror=on_walk_error
    ):
        current_path = Path(current)

        # عدم عبور نقاط التركيب داخل الشجرة.
        if _is_mount_point(current_path) and current_path != base:
            dirs[:] = []
            continue

        # تقليم المجلدات المستثناة والمخفية والروابط الرمزية ونقاط التركيب.
        dirs[:] = sorted(
            d
            for d in dirs
            if d not in skipped
            and not (skip_hidden and d.startswith("."))
            and not (current_path / d).is_symlink()
            and not _is_mount_point(current_path / d)
        )

        for name in sorted(files):
            if skip_hidden and name.startswith("."):
                continue
            if name in skipped:
                continue
            item = current_path / name
            if item.is_symlink():
                continue
            if not item.is_file():
                continue
            yield item

        if not recursive:
            break
