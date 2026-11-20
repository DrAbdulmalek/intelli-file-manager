"""Safety tests for local-only session handoff helpers."""
import os
import sys
from pathlib import Path

import pytest

from scripts.session_handoff import write_new_output


def test_handoff_output_is_exclusive_and_private(tmp_path):
    target = write_new_output(tmp_path, Path("session-handoff.md"), "first")
    assert target.read_text(encoding="utf-8") == "first"
    assert os.stat(target).st_mode & 0o777 == 0o600

    with pytest.raises(FileExistsError):
        write_new_output(tmp_path, Path("session-handoff.md"), "second")

    assert target.read_text(encoding="utf-8") == "first"


def test_handoff_rejects_symlinked_parent(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    try:
        linked.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable on this platform")

    with pytest.raises(OSError, match="symlinked output parent"):
        write_new_output(tmp_path, Path("linked/out.md"), "content")
    assert not (real / "out.md").exists()


def test_handoff_rejects_output_outside_project(tmp_path):
    outside = tmp_path.parent / "outside-handoff.md"
    with pytest.raises(ValueError, match="inside the selected project"):
        write_new_output(tmp_path, outside, "content")
    assert not outside.exists()


def test_mem0_test_script_requires_explicit_remote_confirmation(monkeypatch):
    from scripts import test_mem0_memory

    monkeypatch.setattr(sys, "argv", ["test_mem0_memory.py"])
    assert test_mem0_memory.main() == 2
