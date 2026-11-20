from __future__ import annotations

import os
from pathlib import Path

from src.core.path_policy import iter_entries_reported, iter_files, is_hidden_relative, relative_parts


def touch(path: Path, content: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def test_hidden_parent_of_scan_root_is_not_hidden(tmp_path):
    root = tmp_path / ".cache" / "work"
    touch(root / "visible.txt")
    assert [p.name for p in iter_files(root)] == ["visible.txt"]
    assert not is_hidden_relative(root, root / "visible.txt")


def test_hidden_and_excluded_directories_are_pruned(tmp_path):
    touch(tmp_path / "visible.txt")
    for dirname in (".git", ".ssh", ".config", ".venv", "node_modules", "__pycache__"):
        touch(tmp_path / dirname / "secret.txt")
    assert {p.name for p in iter_files(tmp_path)} == {"visible.txt"}


def test_hidden_files_are_skipped_by_default_but_can_be_included(tmp_path):
    touch(tmp_path / ".env")
    touch(tmp_path / "visible.txt")
    assert {p.name for p in iter_files(tmp_path)} == {"visible.txt"}
    assert {p.name for p in iter_files(tmp_path, skip_hidden=False)} == {".env", "visible.txt"}


def test_symlinked_directory_and_file_are_never_followed(tmp_path):
    outside = tmp_path / "outside"
    touch(outside / "secret.txt")
    root = tmp_path / "root"
    touch(root / "visible.txt")
    os.symlink(outside, root / "linked-dir", target_is_directory=True)
    os.symlink(outside / "secret.txt", root / "linked-file")
    assert {p.name for p in iter_files(root)} == {"visible.txt"}


def test_recursive_false_only_returns_root_files(tmp_path):
    touch(tmp_path / "root.txt")
    touch(tmp_path / "nested" / "child.txt")
    assert {p.name for p in iter_files(tmp_path, recursive=False)} == {"root.txt"}


def test_nonexistent_or_file_root_yields_nothing(tmp_path):
    file_path = touch(tmp_path / "file.txt")
    assert list(iter_files(tmp_path / "missing")) == []
    assert list(iter_files(file_path)) == []


def test_iteration_is_deterministic(tmp_path):
    for name in ("z.txt", "a.txt", "m.txt"):
        touch(tmp_path / name)
    assert [p.name for p in iter_files(tmp_path)] == ["a.txt", "m.txt", "z.txt"]


def test_relative_parts_ignores_hidden_ancestor_of_root(tmp_path):
    root = tmp_path / ".hidden-parent" / "root"
    assert relative_parts(root, root / "a" / "b.txt") == ("a", "b.txt")
    assert is_hidden_relative(root, root / ".private" / "b.txt")



def test_reported_traversal_reports_hidden_and_excluded_entries(tmp_path):
    touch(tmp_path / "visible.txt")
    touch(tmp_path / ".hidden.txt")
    touch(tmp_path / ".git" / "ignored.txt")
    touch(tmp_path / "node_modules" / "ignored.js")

    entries = list(iter_entries_reported(tmp_path))
    reasons = {path.name: reason for path, _info, _error, reason in entries}

    assert reasons[".hidden.txt"] == "hidden"
    assert reasons[".git"] == "hidden"
    assert reasons["node_modules"] == "excluded_directory"
    assert any(path.name == "visible.txt" and reason is None for path, _info, _error, reason in entries)


def test_reported_traversal_never_follows_symlinks(tmp_path):
    target = touch(tmp_path / "outside" / "secret.txt")
    root = tmp_path / "root"
    root.mkdir()
    try:
        (root / "linked").symlink_to(target)
    except (OSError, NotImplementedError):
        import pytest
        pytest.skip("symlinks are not supported in this environment")

    entries = list(iter_entries_reported(root))
    assert any(path.name == "linked" and reason == "symlink" for path, _info, _error, reason in entries)
    assert not any(path.name == "secret.txt" for path, _info, _error, reason in entries)


def test_reported_traversal_marks_depth_limit_without_duplicate_directory(tmp_path):
    touch(tmp_path / "one" / "two" / "three.txt")

    entries = list(iter_entries_reported(tmp_path, max_depth=1))
    two_entries = [entry for entry in entries if entry[0].name == "two"]

    assert len(two_entries) == 1
    assert two_entries[0][3] == "depth_limit"
