"""توليد سكربت نقل يدوي آمن وقابل للمراجعة."""
from __future__ import annotations

import posixpath
import shlex
from collections.abc import Iterable, Sequence

__all__ = ["PlanError", "render_move_script"]


class PlanError(ValueError):
    """خطة نقل غير آمنة أو غير متسقة."""


def _clean(path: str, what: str) -> str:
    if not isinstance(path, str) or not path.strip():
        raise PlanError(f"{what}: مسار فارغ")
    if "\x00" in path:
        raise PlanError(f"{what}: يحوي بايت NUL")
    return posixpath.normpath(path)


def render_move_script(
    moves: Iterable[Sequence[str]],
    *,
    title: str = "IntelliFile move plan",
) -> str:
    """يبني نص سكربت bash من أزواج (مصدر، هدف نهائي)."""
    pairs: list[tuple[str, str]] = []
    seen_dst: dict[str, str] = {}
    for item in moves:
        if len(item) != 2:
            raise PlanError("كل عنصر يجب أن يكون (مصدر, هدف)")
        src, dst = _clean(item[0], "المصدر"), _clean(item[1], "الهدف")
        if src == dst:
            raise PlanError(f"المصدر والهدف متطابقان: {src}")
        if dst.startswith(src.rstrip("/") + "/"):
            raise PlanError(f"الهدف داخل المصدر نفسه: {dst}")
        if dst in seen_dst:
            raise PlanError(f"تصادم أهداف: {seen_dst[dst]} و{src} → {dst}")
        seen_dst[dst] = src
        pairs.append((src, dst))

    safe_title = title.replace("\r", " ").replace("\n", " ")
    lines = [
        "#!/usr/bin/env bash",
        f"# {safe_title}",
        "# راجع الخطة يدوياً قبل التشغيل. لا يستبدل وجهة موجودة.",
        "set -euo pipefail",
        "",
    ]
    for src, dst in pairs:
        parent = posixpath.dirname(dst) or "."
        q_src, q_dst, q_parent = (shlex.quote(x) for x in (src, dst, parent))
        lines.append(
            f"[ -e {q_src} ] || [ -L {q_src} ] || "
            f'{{ echo "source missing: " {q_src} >&2; exit 1; }}'
        )
        lines.append(f"mkdir -p -- {q_parent}")
        lines.append(
            f"[ ! -e {q_dst} ] && [ ! -L {q_dst} ] || "
            f'{{ echo "destination exists: " {q_dst} >&2; exit 1; }}'
        )
        lines.append(f"mv -nT -- {q_src} {q_dst}")
        lines.append(
            f"[ ! -e {q_src} ] && [ ! -L {q_src} ] || "
            f'{{ echo "move skipped or raced: " {q_src} >&2; exit 1; }}'
        )
    lines.append("")
    return "\n".join(lines)
