from __future__ import annotations

import os
from pathlib import Path

from src.core.path_policy import iter_files, is_hidden_relative, relative_parts


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


def test_excluded_directories_remain_excluded_when_hidden_files_are_enabled(tmp_path):
    touch(tmp_path / ".git" / "HEAD")
    touch(tmp_path / ".custom-hidden" / "visible-if-not-pruned.txt")
    found = {p.relative_to(tmp_path).as_posix() for p in iter_files(tmp_path, skip_hidden=False)}
    assert found == {".custom-hidden/visible-if-not-pruned.txt"}


def test_file_agent_duplicate_scan_does_not_enter_hidden_trees(tmp_path):
    from src.core.file_agent import FileAgent

    touch(tmp_path / "visible.txt", "same-content")
    touch(tmp_path / ".git" / "objects" / "hidden-copy.txt", "same-content")
    assert FileAgent().detect_duplicates(str(tmp_path)) == []


def test_file_handler_scan_does_not_enter_hidden_trees(tmp_path):
    from src.core.file_handler import FileHandler

    touch(tmp_path / "visible.txt")
    touch(tmp_path / ".ssh" / "id_rsa.txt")
    touch(tmp_path / "nested" / "nested-visible.txt")
    found = {item["name"] for item in FileHandler().scan_directory(str(tmp_path))}
    assert found == {"visible.txt", "nested-visible.txt"}


def test_file_handler_can_scan_root_under_hidden_ancestor(tmp_path):
    from src.core.file_handler import FileHandler

    root = tmp_path / ".alphacode" / "scratch"
    touch(root / "visible.txt")
    found = {item["name"] for item in FileHandler().scan_directory(str(root))}
    assert found == {"visible.txt"}
