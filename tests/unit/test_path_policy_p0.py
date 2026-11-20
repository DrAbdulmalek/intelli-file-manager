"""اختبارات P0 لسياسة المسارات: الاستبعاد الصريح، نقاط التركيب، وأخطاء المسح (IFM-001)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from src.core.path_policy import DEFAULT_SKIP_DIRS, iter_files, iter_files_reported


def touch(path: Path, content: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def test_secret_dirs_excluded_even_with_skip_hidden_false(tmp_path):
    """IFM-001: .ssh/.config/.gnupg مستثناة دائمًا — حتى عند skip_hidden=False."""
    touch(tmp_path / "visible.txt")
    for dirname in (".ssh", ".config", ".gnupg"):
        touch(tmp_path / dirname / "secret_key.txt")
    got = {p.name for p in iter_files(tmp_path, skip_hidden=False)}
    assert got == {"visible.txt"}


def test_default_skip_dirs_contains_secret_dirs():
    assert {".ssh", ".config", ".gnupg"} <= set(DEFAULT_SKIP_DIRS)


def test_mount_points_not_crossed_by_default(tmp_path, monkeypatch):
    """نقطة تركيب فرعية لا تُعبر افتراضيًا، وتُعبر فقط عند follow_mount_points=True."""
    touch(tmp_path / "root.txt")
    mounted = tmp_path / "mounted"
    touch(mounted / "inside.txt")
    monkeypatch.setattr(
        os.path, "ismount",
        lambda p: str(p).endswith(str(mounted)),
        raising=True,
    )
    assert {p.name for p in iter_files(tmp_path)} == {"root.txt"}
    both = {p.name for p in iter_files(tmp_path, follow_mount_points=True)}
    assert both == {"root.txt", "inside.txt"}


@pytest.mark.skipif(sys.platform == "win32", reason="chmod لا يمنع القراءة على Windows")
def test_unreadable_dir_reported_not_silent(tmp_path):
    """IFM-001: مجلد بلا صلاحية قراءة → خطأ مسجّل في iter_files_reported، لا صمت."""
    touch(tmp_path / "visible.txt")
    locked = tmp_path / "locked"
    touch(locked / "hidden_from_scan.txt")
    locked.chmod(0o000)
    try:
        files, errors = iter_files_reported(tmp_path)
    finally:
        locked.chmod(0o755)
    assert {p.name for p in files} == {"visible.txt"}
    if os.geteuid() == 0:
        pytest.skip("الجذر يتجاوز الصلاحيات — لا يمكن إحداث فشل قراءة حقيقي")
    assert errors, "يجب تسجيل فشل قراءة المجلد المقفل بدل تجاهله"
    assert any("locked" in str(e) for e in errors)


def test_on_error_callback_invoked(tmp_path, monkeypatch):
    """on_error يمرّر إلى os.walk ويُستدعى عند فشل القراءة (اختبار بالحقن)."""
    real_walk = os.walk

    def fake_walk(top, *, followlinks=False, onerror=None):
        assert onerror is not None, "iter_files_reported يجب أن يمرر on_error"
        onerror(OSError(13, "Permission denied"))
        yield from real_walk(top, followlinks=followlinks, onerror=lambda _e: None)

    monkeypatch.setattr(os, "walk", fake_walk)
    touch(tmp_path / "a.txt")
    _, errors = iter_files_reported(tmp_path)
    assert errors and "Permission denied" in str(errors[0])
