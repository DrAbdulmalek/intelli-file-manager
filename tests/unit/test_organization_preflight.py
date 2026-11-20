"""Tests for read-only organization preflight."""
import errno
import json
import os

from src.core.organization import (
    STATUS_BLOCKED_PREFLIGHT, STATUS_SKIPPED_EXCLUDED,
    build_organization_plan, classify_os_error, preflight_item,
    write_plan_manifest,
)


def test_exclusion_precedes_source_inspection(tmp_path):
    item = preflight_item(tmp_path / "keep/missing", tmp_path / "out",
                          excluded_paths=[tmp_path / "keep"])
    assert item.status == STATUS_SKIPPED_EXCLUDED and not item.error_category


def test_missing_source_keeps_errno(tmp_path):
    item = preflight_item(tmp_path / "missing", tmp_path / "out")
    assert (item.status, item.error_category, item.errno) == (
        STATUS_BLOCKED_PREFLIGHT, "source_missing", errno.ENOENT)


def test_collision_never_overwrites(tmp_path):
    src, dst = tmp_path / "source", tmp_path / "destination"
    src.write_text("source"); dst.write_text("keep")
    item = preflight_item(src, dst)
    assert item.error_category == "name_collision"
    assert src.read_text() == "source" and dst.read_text() == "keep"


def test_spaces_are_path_components_not_shell_tokens(tmp_path):
    src = tmp_path / "Calibre Library/book.txt"
    src.parent.mkdir(); src.write_text("book")
    out = tmp_path / "organized"; out.mkdir()
    item = preflight_item(src, out / "book.txt")
    assert item.kind == "file" and item.file_count == 1 and item.total_bytes == 4
    assert item.status == STATUS_BLOCKED_PREFLIGHT and "SafeMover" in item.reason


def test_nonempty_and_empty_directories_are_distinguished(tmp_path):
    out = tmp_path / "organized"; out.mkdir()
    docs = tmp_path / "Documents"; docs.mkdir(); (docs / "one").write_text("1")
    music = tmp_path / "Music"; music.mkdir()
    nonempty = preflight_item(docs, out / "Documents")
    empty = preflight_item(music, out / "Music")
    assert (nonempty.kind, nonempty.file_count, nonempty.error_category) == (
        "directory", 1, "unsupported_operation")
    assert empty.kind == "empty_directory"
    assert nonempty.status == empty.status == STATUS_BLOCKED_PREFLIGHT


def test_symlink_source_is_rejected(tmp_path):
    target = tmp_path / "target"; target.write_text("x")
    link = tmp_path / "link"; link.symlink_to(target)
    assert preflight_item(link, tmp_path / "out").error_category == "symlink_rejected"


def test_source_inside_destination_is_rejected(tmp_path):
    src = tmp_path / "parent/child"; src.parent.mkdir(); src.write_text("x")
    assert preflight_item(src, src / "nested").status == STATUS_BLOCKED_PREFLIGHT


def test_explicit_protected_root_is_enforced(tmp_path):
    root = tmp_path / "protected"; root.mkdir()
    src = root / "data"; src.write_text("x")
    item = preflight_item(src, tmp_path / "out", protected_roots=[root])
    assert item.error_category == "protected_location"


def test_batch_summary_and_private_manifest(tmp_path):
    src = tmp_path / "folder with spaces/a"; src.parent.mkdir(); src.write_text("abc")
    out = tmp_path / "out"; out.mkdir()
    plan = build_organization_plan(
        [(src, out / "a"), (tmp_path / "excluded", out / "b")],
        base_dir=tmp_path, excluded_paths=[tmp_path / "excluded"])
    assert plan.summary["total"] == 2
    assert plan.summary[STATUS_BLOCKED_PREFLIGHT] == plan.summary[STATUS_SKIPPED_EXCLUDED] == 1
    manifest = write_plan_manifest(plan, tmp_path / "private/plan.json")
    data = json.loads(manifest.read_text())
    assert data["base_dir"] == "." and str(tmp_path) not in manifest.read_text()
    assert os.stat(manifest).st_mode & 0o777 == 0o600


def test_errno_categories_are_stable():
    assert classify_os_error(PermissionError(errno.EACCES, "denied")) == "permission_denied"
    assert classify_os_error(OSError(errno.EXDEV, "cross-device")) == "cross_device"
    assert classify_os_error(OSError(12345, "unknown")) == "unknown_os_error"



def test_manifest_never_overwrites_existing_file(tmp_path):
    plan = build_organization_plan([], base_dir=tmp_path)
    target = tmp_path / "private" / "plan.json"
    first = write_plan_manifest(plan, target)
    original = first.read_bytes()

    import pytest
    with pytest.raises(FileExistsError):
        write_plan_manifest(plan, target)

    assert target.read_bytes() == original
    assert not list(target.parent.glob(".ifm-plan-*"))


def test_manifest_rejects_symlinked_parent(tmp_path):
    import pytest

    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    try:
        linked.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable on this platform")

    plan = build_organization_plan([], base_dir=tmp_path)
    with pytest.raises(OSError, match="symlinked manifest path"):
        write_plan_manifest(plan, linked / "plan.json")
    assert not (real / "plan.json").exists()


def test_manifest_never_uses_replace_fallback(tmp_path, monkeypatch):
    import pytest

    plan = build_organization_plan([], base_dir=tmp_path)

    def forbidden_replace(*args, **kwargs):
        raise AssertionError("manifest publication must not call os.replace")

    monkeypatch.setattr(os, "replace", forbidden_replace)
    target = write_plan_manifest(plan, tmp_path / "plan.json")
    assert target.exists()
    assert not list(tmp_path.glob(".ifm-plan-*"))


def test_directory_preflight_prunes_nested_mount_points(tmp_path, monkeypatch):
    from pathlib import Path

    root = tmp_path / "source"
    root.mkdir()
    (root / "visible.txt").write_text("visible")
    nested = root / "mounted"
    nested.mkdir()
    (nested / "hidden-by-mount.txt").write_text("not traversed")
    destination = tmp_path / "out"
    destination.mkdir()

    real_is_mount = Path.is_mount

    def fake_is_mount(self):
        if self == nested:
            return True
        return real_is_mount(self)

    monkeypatch.setattr(Path, "is_mount", fake_is_mount)
    item = preflight_item(root, destination / "source")

    assert item.error_category == "mount_boundary"
    assert item.file_count == 1


def test_directory_preflight_skips_hidden_system_trees(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "visible.txt").write_text("visible")
    hidden = root / ".ssh"
    hidden.mkdir()
    (hidden / "private-key.txt").write_text("not counted")
    destination = tmp_path / "out"
    destination.mkdir()

    item = preflight_item(root, destination / "source")

    assert item.file_count == 1
