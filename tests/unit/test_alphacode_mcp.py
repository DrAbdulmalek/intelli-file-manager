"""Security and protocol tests for the local AlphaCode MCP bridge."""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import src.integrations.alphacode_mcp_server as bridge
from scripts.alphacode_mcp_probe import inspect as inspect_alphacode
from src.integrations.alphacode_mcp_server import (
    IntegrationError,
    _inventory,
    _validate_plan,
    dispatch,
    serve,
)


def _configure_root(monkeypatch, root):
    monkeypatch.setenv("INTELLIFILE_AGENT_ROOTS", str(root))


def test_inventory_is_metadata_only_and_excludes_sensitive_and_hidden_paths(tmp_path, monkeypatch):
    root = tmp_path / "allowed"
    root.mkdir()
    (root / "normal report.txt").write_text("must never be read", encoding="utf-8")
    (root / ".hidden.txt").write_text("hidden", encoding="utf-8")
    (root / "patient-record.pdf").write_text("private", encoding="utf-8")
    (root / "scan.dcm").write_bytes(b"DICM")
    secret_dir = root / "credentials"
    secret_dir.mkdir()
    (secret_dir / "token.txt").write_text("secret", encoding="utf-8")
    _configure_root(monkeypatch, root)

    result = _inventory(str(root), 10)

    assert result["mode"] == "READ_ONLY"
    assert result["content_read"] is False
    assert [item["relative_path"] for item in result["files"]] == ["normal report.txt"]
    assert result["counts"]["excluded"] >= 4
    assert (root / "normal report.txt").read_text(encoding="utf-8") == "must never be read"


def test_inventory_skips_symlinks(tmp_path, monkeypatch):
    root = tmp_path / "allowed"
    root.mkdir()
    target = root / "target.txt"
    target.write_text("target", encoding="utf-8")
    link = root / "link.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not supported in this environment")
    _configure_root(monkeypatch, root)

    result = _inventory(str(root), 10)

    assert result["counts"]["symlinks"] == 1
    assert [item["relative_path"] for item in result["files"]] == ["target.txt"]


def test_inventory_rejects_root_outside_allowlist(tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    _configure_root(monkeypatch, allowed)

    with pytest.raises(IntegrationError, match="allowlist"):
        _inventory(str(outside), 10)


def test_inventory_requires_explicit_allowlist(tmp_path, monkeypatch):
    root = tmp_path / "allowed"
    root.mkdir()
    monkeypatch.delenv("INTELLIFILE_AGENT_ROOTS", raising=False)

    with pytest.raises(IntegrationError, match="No roots are enabled"):
        _inventory(str(root), 10)


def test_validate_plan_is_dry_run_and_never_moves_files(tmp_path, monkeypatch):
    root = tmp_path / "allowed"
    root.mkdir()
    source = root / "source.txt"
    source.write_text("unchanged", encoding="utf-8")
    _configure_root(monkeypatch, root)

    result = _validate_plan(str(root), [{
        "source": "source.txt",
        "destination": "Documents/source.txt",
        "reason": "document",
        "category": "Documents",
    }])

    assert result["mode"] == "DRY_RUN"
    assert result["execution_enabled"] is False
    assert result["validated_count"] == 1
    assert result["validated"][0]["requires_user_approval"] is True
    assert source.read_text(encoding="utf-8") == "unchanged"
    assert not (root / "Documents" / "source.txt").exists()


def test_validate_plan_rejects_traversal_and_existing_destination(tmp_path, monkeypatch):
    root = tmp_path / "allowed"
    root.mkdir()
    (root / "source.txt").write_text("source", encoding="utf-8")
    (root / "existing.txt").write_text("existing", encoding="utf-8")
    _configure_root(monkeypatch, root)

    result = _validate_plan(str(root), [
        {"source": "source.txt", "destination": "../escape.txt"},
        {"source": "source.txt", "destination": "existing.txt"},
    ])

    assert result["validated_count"] == 0
    assert result["rejected_count"] == 2
    assert not (tmp_path / "escape.txt").exists()
    assert (root / "existing.txt").read_text(encoding="utf-8") == "existing"


def test_mcp_requires_initialization_before_tools():
    state = {"phase": "new"}
    early = dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, state)
    assert early["error"]["code"] == -32000

    initialized = dispatch({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "initialize",
        "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
    }, state)
    assert initialized["result"]["protocolVersion"] == "2025-11-25"
    assert dispatch({"jsonrpc": "2.0", "method": "notifications/initialized"}, state) is None

    listed = dispatch({"jsonrpc": "2.0", "id": 3, "method": "tools/list"}, state)
    tools = listed["result"]["tools"]
    names = {tool["name"] for tool in tools}
    assert names == {
        "intellifile.status",
        "intellifile.inventory",
        "intellifile.validate_plan",
    }
    assert all(tool["annotations"]["readOnlyHint"] is True for tool in tools)
    assert all(tool["annotations"]["destructiveHint"] is False for tool in tools)


def test_mcp_exposes_no_mutation_tools_and_unknown_tool_is_rejected():
    state = {"phase": "ready"}
    response = dispatch({
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {"name": "intellifile.move_file", "arguments": {}},
    }, state)
    assert response["result"]["isError"] is True
    assert "Unknown IntelliFile tool" in response["result"]["content"][0]["text"]


def test_stdio_emits_only_jsonrpc_frames():
    incoming = "\n".join([
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                               "clientInfo": {"name": "test", "version": "1"}}}),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
        "",
    ])
    output = io.StringIO()
    assert serve(io.StringIO(incoming), output, io.StringIO()) == 0
    frames = [json.loads(line) for line in output.getvalue().splitlines()]
    assert [frame["id"] for frame in frames] == [1, 2]
    assert all(frame["jsonrpc"] == "2.0" for frame in frames)



def test_inventory_caps_returned_entries_but_reports_truncation(tmp_path, monkeypatch):
    root = tmp_path / "allowed"
    root.mkdir()
    for name in ("a.txt", "b.txt", "c.txt"):
        (root / name).write_text(name, encoding="utf-8")
    _configure_root(monkeypatch, root)

    result = _inventory(str(root), 2)

    assert result["counts"]["files"] == 3
    assert result["files_returned"] == 2
    assert result["truncated"] is True


def test_validate_plan_rejects_symlinked_source_parent(tmp_path, monkeypatch):
    root = tmp_path / "allowed"
    real = root / "real"
    real.mkdir(parents=True)
    (real / "source.txt").write_text("source", encoding="utf-8")
    alias = root / "alias"
    try:
        alias.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not supported in this environment")
    _configure_root(monkeypatch, root)

    result = _validate_plan(str(root), [{
        "source": "alias/source.txt",
        "destination": "out/source.txt",
    }])

    assert result["validated_count"] == 0
    assert result["rejected"][0]["reason"] == "symlinked_source_component"


def test_symlinked_scan_root_is_rejected(tmp_path, monkeypatch):
    root = tmp_path / "allowed"
    root.mkdir()
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(root, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not supported in this environment")
    _configure_root(monkeypatch, root)

    with pytest.raises(IntegrationError, match="Symlinked scan roots"):
        _inventory(str(alias), 10)



def test_server_direct_script_launch_works_from_external_working_directory(tmp_path):
    script = Path(__file__).resolve().parents[2] / "src" / "integrations" / "alphacode_mcp_server.py"
    incoming = "\n".join([
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                               "clientInfo": {"name": "test", "version": "1"}}}),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
        "",
    ])
    env = os.environ.copy()
    env.pop("INTELLIFILE_AGENT_ROOTS", None)

    completed = subprocess.run(
        [sys.executable, str(script)],
        input=incoming,
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=env,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    frames = [json.loads(line) for line in completed.stdout.splitlines()]
    assert [frame["id"] for frame in frames] == [1, 2]
    assert all(frame["jsonrpc"] == "2.0" for frame in frames)



def test_inventory_has_a_hard_scan_limit(tmp_path, monkeypatch):
    root = tmp_path / "allowed"
    root.mkdir()
    for name in ("a.txt", "b.txt", "c.txt", "d.txt"):
        (root / name).write_text(name, encoding="utf-8")
    _configure_root(monkeypatch, root)
    monkeypatch.setattr(bridge, "MAX_SCAN_ENTRIES", 2)

    result = bridge._inventory(str(root), 10)

    assert result["entries_scanned"] == 2
    assert result["scan_complete"] is False
    assert result["truncated"] is True
    assert result["counts"]["files"] == 2



def test_local_probe_reports_mcp_keys_without_configuration_values(tmp_path):
    config_dir = tmp_path / ".alphacode"
    config_dir.mkdir()
    secret_value = "never-print-this-token"
    (config_dir / "settings.json").write_text(
        json.dumps({"mcpServers": {"intellifile": {"token": secret_value}}}),
        encoding="utf-8",
    )

    report = inspect_alphacode(tmp_path)
    rendered = json.dumps(report, ensure_ascii=False)

    assert report["mode"] == "READ_ONLY_DISCOVERY"
    assert report["mcp_configuration_hint_found"] is True
    assert report["mcp_config_hints"][0]["mcp_key_names_only"] == ["mcpServers"]
    assert secret_value not in rendered
    assert str(tmp_path) not in rendered
