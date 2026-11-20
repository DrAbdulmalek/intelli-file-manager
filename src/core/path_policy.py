"""سياسة اجتياز المسارات المشتركة (Path traversal policy)."""
from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Union

__all__ = [
    "DEFAULT_SKIP_DIRS",
    "is_hidden_relative",
    "iter_files",
    "iter_files_reported",
    "relative_parts",
]

# مجلدات لا تُعبر أبدًا، حتى لو طُلب تضمين الملفات المخفية (skip_hidden=False).
# IFM-001: .ssh و.config و.gnupg كانت تُعبر عند skip_hidden=False لأنها لم تكن هنا.
DEFAULT_SKIP_DIRS = frozenset({
    "__pycache__", "node_modules", ".git", ".venv", "venv",
    ".ssh", ".config", ".gnupg",
})
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
    follow_mount_points: bool = False,
    on_error: Callable[[OSError], None] | None = None,
) -> Iterator[Path]:
    """يولّد الملفات العادية، مع تقليم المجلدات المستثناة وعدم اتباع symlinks.

    Args:
        follow_mount_points: افتراضيًا False — لا تُعبر نقاط التركيب الفرعية
            (سياسة صريحة للعبور وفق البروتوكول؛ لا عبور دون قرار معلن).
        on_error: تُستدعى عند فشل قراءة مجلد أثناء المسح (OSError). افتراضيًا
            None (سلوك قديم: تجاهل صامت) — استخدم iter_files_reported لمعرفة
            ما لم يُفحص بدل الاعتماد على هذا المعامل مباشرة.
    """
    base = Path(root)
    if not base.is_dir():
        return
    skipped = frozenset(skip_dirs or ())

    for current, dirs, files in os.walk(base, followlinks=False, onerror=on_error):
        dirs[:] = sorted(
            d for d in dirs
            if d not in skipped and not (skip_hidden and d.startswith("."))
            and not (Path(current) / d).is_symlink()
            and (follow_mount_points or not os.path.ismount(str(Path(current) / d)))
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


def iter_files_reported(
    root: PathLike,
    **kwargs,
) -> tuple[list[Path], list[OSError]]:
    """يجمع الملفات وأخطاء المسح معًا — لا اجتياز صامت (IFM-001).

    يغلف iter_files ويجمع أخطاء os.walk (مثلاً مجلد بلا صلاحية قراءة) بحيث
    يعرف المستأنِف أن جزءًا من الشجرة لم يُفحص. معاملات iter_files نفسها
    تُمرر كما هي (on_error يُدار داخليًا).
    """
    errors: list[OSError] = []
    files = list(iter_files(root, on_error=errors.append, **kwargs))
    return files, errors
