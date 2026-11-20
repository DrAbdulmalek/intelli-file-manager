"""اختبارات لقطة/تحقق الأشجار — حالات فقد حقيقية لا مجرد مسار سعيد."""
from __future__ import annotations

import os

import pytest

from src.core.tree_manifest import ManifestError, snapshot, verify


def _w(p, text="x"):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "src tree"
    _w(root / "a.txt", "aaa")
    _w(root / "sub dir" / "b.txt", "bbbb")
    _w(root / ".hidden" / "c.txt", "c")
    (root / "empty").mkdir()
    return root


def test_snapshot_counts_hidden_and_empty_dirs(tree, tmp_path):
    s = snapshot(tree, tmp_path / "m.jsonl")
    assert s["files"] == 3 and s["dirs"] == 3 and s["bytes"] == 8 and s["errors"] == 0


def test_directory_rename_verifies_ok(tree, tmp_path):
    m = tmp_path / "m.jsonl"
    snapshot(tree, m, hash_files=True)
    moved = tmp_path / "dest" / "moved"
    moved.parent.mkdir()
    os.rename(tree, moved)
    rep = verify(m, moved, check_hash=True, strict=True)
    assert rep["ok"] and rep["checked"] == 6


def test_missing_file_and_missing_empty_dir_detected(tree, tmp_path):
    m = tmp_path / "m.jsonl"
    snapshot(tree, m)
    (tree / "a.txt").unlink()
    (tree / "empty").rmdir()
    rep = verify(m, tree)
    assert not rep["ok"] and set(rep["missing"]) == {"a.txt", "empty"}


def test_size_change_and_same_size_content_change(tree, tmp_path):
    m = tmp_path / "m.jsonl"
    snapshot(tree, m, hash_files=True)
    (tree / "a.txt").write_text("aaaaaa")          # حجم مختلف
    (tree / "sub dir" / "b.txt").write_text("zzzz")  # الحجم نفسه، المحتوى مختلف
    cheap = verify(m, tree)
    assert cheap["size_changed"] == ["a.txt"] and not cheap["hash_changed"]
    deep = verify(m, tree, check_hash=True)
    assert deep["hash_changed"] == ["sub dir/b.txt"] and not deep["ok"]


def test_extra_files_fail_only_in_strict_mode(tree, tmp_path):
    m = tmp_path / "m.jsonl"
    snapshot(tree, m)
    _w(tree / "new.txt")
    assert verify(m, tree)["ok"] is True
    assert verify(m, tree, strict=True)["ok"] is False


def test_symlink_is_recorded_not_followed_and_type_change_detected(tree, tmp_path):
    outside = tmp_path / "outside"
    _w(outside / "leak.txt")
    os.symlink(outside, tree / "link", target_is_directory=True)
    m = tmp_path / "m.jsonl"
    s = snapshot(tree, m)
    assert s["symlinks"] == 1 and s["files"] == 3          # leak.txt غير مُتتبَّع
    (tree / "link").unlink()
    (tree / "link").mkdir()                                 # صار مجلداً حقيقياً
    assert verify(m, tree)["type_changed"] == ["link"]


def test_nonexistent_new_root_reports_everything_missing(tree, tmp_path):
    m = tmp_path / "m.jsonl"
    snapshot(tree, m)
    rep = verify(m, tmp_path / "nope")
    assert not rep["ok"] and len(rep["missing"]) == 6


def test_unreadable_dir_makes_snapshot_incomplete_not_silently_ok(tree, tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root يتجاوز الصلاحيات")
    locked = tree / "sub dir"
    locked.chmod(0)
    try:
        m = tmp_path / "m.jsonl"
        s = snapshot(tree, m)
        assert s["errors"] >= 1
    finally:
        locked.chmod(0o700)
    rep = verify(m, tree)
    assert rep["complete"] is False and rep["ok"] is False


def test_hash_check_requires_hashed_snapshot(tree, tmp_path):
    m = tmp_path / "m.jsonl"
    snapshot(tree, m)
    with pytest.raises(ManifestError):
        verify(m, tree, check_hash=True)


def test_corrupt_manifest_is_rejected(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text("{not json}\n")
    with pytest.raises(ManifestError):
        verify(bad, tmp_path)


def test_unreadable_dir_via_injected_error_is_not_silently_ok(tree, tmp_path, monkeypatch):
    """يعمل حتى كـ root: نحقن PermissionError عند فتح مجلد فرعي."""
    import src.core.tree_manifest as tm

    real = tm.os.scandir

    def flaky(path):
        if str(path).endswith("sub dir"):
            raise PermissionError(13, "denied", str(path))
        return real(path)

    monkeypatch.setattr(tm.os, "scandir", flaky)
    m = tmp_path / "m.jsonl"
    s = snapshot(tree, m)
    assert s["errors"] == 1
    monkeypatch.setattr(tm.os, "scandir", real)
    rep = verify(m, tree)
    assert rep["snapshot_errors"] == 1 and rep["complete"] is False and rep["ok"] is False


def test_cli_exit_codes_end_to_end(tree, tmp_path):
    import subprocess
    import sys
    cli = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "tree_manifest.py")
    m = str(tmp_path / "m.jsonl")

    def run(*args):
        return subprocess.run([sys.executable, cli, *args], capture_output=True, text=True, check=False)

    assert run("snapshot", str(tree), m, "--hash").returncode == 0
    moved = tmp_path / "moved"
    os.rename(tree, moved)
    assert run("verify", m, str(moved), "--hash").returncode == 0
    (moved / "a.txt").unlink()
    r = run("verify", m, str(moved))
    assert r.returncode == 1 and "missing" in r.stderr
    assert run("verify", str(tmp_path / "none.jsonl"), str(moved)).returncode == 2
