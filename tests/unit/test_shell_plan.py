from __future__ import annotations

import shutil
import subprocess

import pytest

from src.core.shell_plan import PlanError, render_move_script

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")


def run(script, cwd):
    return subprocess.run(["bash", "-c", script], cwd=cwd, capture_output=True, text=True)


def test_space_and_shell_metacharacters_are_quoted(tmp_path):
    source = tmp_path / "Calibre Library;$(touch PWNED)"
    source.mkdir()
    (source / "book.txt").write_text("ok")
    target = tmp_path / "organized" / "Portable Books"
    result = run(render_move_script([(str(source), str(target))]), tmp_path)
    assert result.returncode == 0, result.stderr
    assert (target / "book.txt").read_text() == "ok"
    assert not (tmp_path / "PWNED").exists()


def test_existing_destination_fails_without_nesting_or_moving_source(tmp_path):
    source = tmp_path / "Documents"
    source.mkdir()
    (source / "a.txt").write_text("a")
    target = tmp_path / "03_Documents"
    target.mkdir()
    result = run(render_move_script([(str(source), str(target))]), tmp_path)
    assert result.returncode != 0
    assert (source / "a.txt").exists()
    assert not (target / "Documents").exists()


def test_destination_symlink_collision_is_rejected(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("x")
    target = tmp_path / "target.txt"
    actual = tmp_path / "actual.txt"
    actual.write_text("keep")
    target.symlink_to(actual)
    result = run(render_move_script([(str(source), str(target))]), tmp_path)
    assert result.returncode != 0
    assert source.exists()
    assert actual.read_text() == "keep"


def test_dash_prefixed_name_is_safe(tmp_path):
    source = tmp_path / "-rf"
    source.write_text("x")
    target = tmp_path / "dest" / "-rf"
    result = run(render_move_script([(str(source), str(target))]), tmp_path)
    assert result.returncode == 0, result.stderr
    assert target.exists()


def test_missing_source_stops_plan(tmp_path):
    later = tmp_path / "later.txt"
    later.write_text("keep")
    result = run(render_move_script([
        (str(tmp_path / "missing"), str(tmp_path / "first")),
        (str(later), str(tmp_path / "second")),
    ]), tmp_path)
    assert result.returncode != 0
    assert later.exists()
    assert not (tmp_path / "second").exists()


@pytest.mark.parametrize("moves", [
    [("", "/dest")],
    [("/src", " ")],
    [("/src", "/src")],
    [("/src", "/src/child")],
    [("/a", "/dest"), ("/b", "/dest")],
    [("/src\\x00", "/dest")],
    [("one-item",)],
])
def test_unsafe_plans_are_rejected(moves):
    with pytest.raises(PlanError):
        render_move_script(moves)

def test_dot_source_cannot_move_into_its_own_child():
    with pytest.raises(PlanError):
        render_move_script([(".", "child")])
