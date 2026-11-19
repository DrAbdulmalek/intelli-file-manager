"""Tests for read-only organization preflight."""
import errno
import json
import os

from src.core.organization import (
    STATUS_BLOCKED_PREFLIGHT,
    STATUS_PLANNED,
    STATUS_SKIPPED_EXCLUDED,
    build_organization_plan,
    classify_os_error,
    preflight_item,
    write_plan_manifest,
)


def test_excluded_source_is_skipped_before_filesystem_checks(tmp_path):
    excluded = tmp_path / "keep"
    item = preflight_item(excluded / "missing.txt", tmp_path / "out.txt",
                          excluded_paths=[excluded])
    assert item.status == STATUS_SKIPPED_EXCLUDED
    assert item.error_category == ""


def test_missing_source_preserves_errno(tmp_path):
    item = preflight_item(tmp_path / "missing.txt", tmp_path / "out.txt")
    assert item.status == STATUS_BLOCKED_PREFLIGHT
    assert item.error_category == "unknown_os_error"
    assert item.errno == errno.ENOENT


def test_destination_collision_is_blocked_without_overwrite(tmp_path):
    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"
    source.write_text("source")
    destination.write_text("keep")
    item = preflight_item(source, destination)
    assert item.status == STATUS_BLOCKED_PREFLIGHT
    assert item.error_category == "name_collision"
    assert destination.read_text() == "keep"
    assert source.read_text() == "source"


def test_path_with_spaces_is_handled_as_a_path_object(tmp_path):
    source = tmp_path / "Calibre Library" / "book.txt"
    source.parent.mkdir()
    source.write_text("book")
    destination_parent = tmp_path / "organized"
    destination_parent.mkdir()
    item = preflight_item(source, destination_parent / "book.txt")
    assert item.status == STATUS_BLOCKED_PREFLIGHT
    assert item.kind == "file"
    assert item.file_count == 1
    assert item.total_bytes == 4
    assert "SafeMover" in item.reason


def test_directory_is_classified_but_never_sent_to_file_mover(tmp_path):
    source = tmp_path / "Documents"
    source.mkdir()
    (source / "one.txt").write_text("1")
    destination_parent = tmp_path / "organized"
    destination_parent.mkdir()
    item = preflight_item(source, destination_parent / "Documents")
    assert item.status == STATUS_BLOCKED_PREFLIGHT
    assert item.kind == "directory"
    assert item.file_count == 1
    assert item.error_category == "unsupported_operation"


def test_empty_directory_is_distinguished(tmp_path):
    source = tmp_path / "Music"
    source.mkdir()
    destination_parent = tmp_path / "organized"
    destination_parent.mkdir()
    item = preflight_item(source, destination_parent / "Music")
    assert item.kind == "empty_directory"
    assert item.status == STATUS_BLOCKED_PREFLIGHT


def test_symlink_source_is_rejected(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("x")
    link = tmp_path / "link.txt"
    link.symlink_to(target)
    item = preflight_item(link, tmp_path / "out.txt")
    assert item.status == STATUS_BLOCKED_PREFLIGHT
    assert item.error_category == "symlink_rejected"


def test_source_inside_destination_is_rejected(tmp_path):
    source = tmp_path / "parent" / "child.txt"
    source.parent.mkdir()
    source.write_text("x")
    item = preflight_item(source, source.parent / "child.txt" / "nested")
    assert item.status == STATUS_BLOCKED_PREFLIGHT


def test_protected_roots_are_explicit_and_enforced(tmp_path):
    protected = tmp_path / "protected"
    protected.mkdir()
    source = protected / "data.txt"
    source.write_text("x")
    item = preflight_item(source, tmp_path / "out.txt", protected_roots=[protected])
    assert item.status == STATUS_BLOCKED_PREFLIGHT
    assert item.error_category == "protected_location"


def test_batch_summary_and_redacted_manifest(tmp_path):
    source = tmp_path / "folder with spaces" / "a.txt"
    source.parent.mkdir()
    source.write_text("abc")
    out = tmp_path / "out"
    out.mkdir()
    plan = build_organization_plan(
        [(source, out / "a.txt"), (tmp_path / "excluded.txt", out / "b.txt")],
        base_dir=tmp_path,
        excluded_paths=[tmp_path / "excluded.txt"],
    )
    assert plan.summary["total"] == 2
    assert plan.summary[STATUS_BLOCKED_PREFLIGHT] == 1
    assert plan.summary[STATUS_SKIPPED_EXCLUDED] == 1
    manifest = write_plan_manifest(plan, tmp_path / "private" / "plan.json")
    data = json.loads(manifest.read_text())
    assert data["base_dir"] == "."
    assert str(tmp_path) not in manifest.read_text()
    assert os.stat(manifest).st_mode & 0o777 == 0o600


def test_error_categories_keep_unknown_errno_visible():
    assert classify_os_error(PermissionError(errno.EACCES, "denied")) == "permission_denied"
    assert classify_os_error(OSError(errno.EXDEV, "cross-device")) == "cross_device"
    assert classify_os_error(OSError(12345, "unknown")) == "unknown_os_error"
