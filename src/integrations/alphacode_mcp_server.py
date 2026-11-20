"""Minimal, local-only MCP server for the AlphaCode desktop agent.

The server exposes metadata-only inventory and dry-run plan validation.
It deliberately has no file-content, move, delete, overwrite, or undo tool.
Transport: MCP stdio (newline-delimited JSON-RPC), legacy lifecycle
protocol 2025-11-25 for broad client compatibility.
"""
from __future__ import annotations

import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any

SERVER_NAME = "intellifile-alphacode"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2025-11-25"
MAX_MESSAGE_BYTES = 1024 * 1024
MAX_INVENTORY_ENTRIES = 1000
MAX_PLAN_ITEMS = 100
SKIP_DIRS = frozenset({
    ".git", ".ssh", ".gnupg", ".config", ".cache", ".local",
    ".venv", "venv", "node_modules", "__pycache__", ".tox",
    ".aws", ".azure", ".kube", "secrets", "credentials",
    "keyrings", "medical", "patient", "clinical",
})
SENSITIVE_SUFFIXES = frozenset({
    ".dcm", ".dicom", ".pem", ".key", ".p12", ".pfx", ".jks",
    ".keystore", ".kdbx", ".sqlite", ".sqlite3", ".db",
})
SENSITIVE_TOKENS = frozenset({
    "medical", "patient", "clinical", "dicom", "mri", "xray",
    "radiology", "credential", "credentials", "secret", "secrets",
    "private", "id_rsa", "id_ed25519", "password", "token",
})
SUPPORTED_LEGACY_VERSIONS = frozenset({
    "2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05",
})


class IntegrationError(ValueError):
    """A safe, user-displayable integration error."""


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _is_sensitive_parts(parts: tuple[str, ...]) -> bool:
    for part in parts:
        lowered = part.casefold()
        if lowered in SKIP_DIRS or lowered in SENSITIVE_TOKENS:
            return True
        if lowered.endswith(SENSITIVE_SUFFIXES):
            return True
        tokens = {token for token in re.split(r"[^a-z0-9]+", lowered) if token}
        if tokens & SENSITIVE_TOKENS:
            return True
    return False


def _configured_roots() -> tuple[Path, ...]:
    raw = os.environ.get("INTELLIFILE_AGENT_ROOTS", "")
    if not raw.strip():
        return ()
    roots: list[Path] = []
    for item in raw.split(os.pathsep):
        item = item.strip()
        if not item:
            continue
        candidate = Path(item).expanduser()
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise IntegrationError(
                "An INTELLIFILE_AGENT_ROOTS entry is missing or unreadable."
            ) from exc
        if not resolved.is_dir():
            raise IntegrationError("Every configured agent root must be a directory.")
        if _is_sensitive_parts(resolved.parts):
            raise IntegrationError("A sensitive directory cannot be configured as an agent root.")
        if resolved not in roots:
            roots.append(resolved)
    return tuple(roots)


def _is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _resolve_root(raw_root: str) -> Path:
    if not isinstance(raw_root, str) or not raw_root.strip():
        raise IntegrationError("A scan root is required.")
    requested = Path(raw_root).expanduser()
    try:
        absolute = Path(os.path.abspath(os.fspath(requested)))
        resolved = requested.resolve(strict=True)
    except OSError as exc:
        raise IntegrationError("The requested scan root does not exist or is inaccessible.") from exc
    if absolute != resolved:
        raise IntegrationError("Symlinked scan roots are not accepted.")
    if not resolved.is_dir():
        raise IntegrationError("The requested scan root is not a directory.")
    roots = _configured_roots()
    if not roots:
        raise IntegrationError(
            "No roots are enabled. Set INTELLIFILE_AGENT_ROOTS explicitly before connecting AlphaCode."
        )
    if not any(_is_within(resolved, allowed) for allowed in roots):
        raise IntegrationError("The requested root is outside the configured allowlist.")
    if _is_sensitive_parts(resolved.parts):
        raise IntegrationError("Sensitive roots are excluded from AlphaCode inventory.")
    return resolved


def _inventory(root_arg: str, max_entries: int = 300) -> dict[str, Any]:
    if isinstance(max_entries, bool) or not isinstance(max_entries, int):
        raise IntegrationError("max_entries must be an integer.")
    if not 1 <= max_entries <= MAX_INVENTORY_ENTRIES:
        raise IntegrationError(f"max_entries must be between 1 and {MAX_INVENTORY_ENTRIES}.")
    root = _resolve_root(root_arg)
    try:
        root_device = root.stat().st_dev
    except OSError as exc:
        raise IntegrationError("Unable to inspect the selected root.") from exc

    stack: list[tuple[Path, tuple[str, ...], int]] = [(root, (), 0)]
    files: list[dict[str, Any]] = []
    totals: dict[str, int] = {}
    counts = {
        "files": 0, "directories": 0, "excluded": 0,
        "symlinks": 0, "mount_boundaries": 0, "unreadable": 0,
    }
    truncated = False
    while stack:
        directory, relative, depth = stack.pop()
        try:
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda entry: entry.name.casefold(), reverse=True)
        except OSError:
            counts["unreadable"] += 1
            continue
        for entry in entries:
            name = entry.name
            rel_parts = relative + (name,)
            if name.startswith(".") or name.casefold() in SKIP_DIRS or _is_sensitive_parts(rel_parts):
                counts["excluded"] += 1
                continue
            try:
                if entry.is_symlink():
                    counts["symlinks"] += 1
                    continue
                info = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    counts["directories"] += 1
                    if info.st_dev != root_device:
                        counts["mount_boundaries"] += 1
                        continue
                    if depth < 32:
                        stack.append((Path(entry.path), rel_parts, depth + 1))
                    else:
                        counts["excluded"] += 1
                    continue
                if not stat.S_ISREG(info.st_mode):
                    counts["excluded"] += 1
                    continue
                if info.st_dev != root_device:
                    counts["mount_boundaries"] += 1
                    continue
                counts["files"] += 1
                suffix = Path(name).suffix.casefold()
                totals[suffix or "[no_extension]"] = totals.get(suffix or "[no_extension]", 0) + 1
                if len(files) < max_entries:
                    files.append({
                        "relative_path": Path(*rel_parts).as_posix(),
                        "size_bytes": info.st_size,
                        "mtime_ns": info.st_mtime_ns,
                        "extension": suffix,
                    })
                else:
                    truncated = True
            except OSError:
                counts["unreadable"] += 1
    files.sort(key=lambda item: item["relative_path"].casefold())
    return {
        "root": str(root),
        "mode": "READ_ONLY",
        "content_read": False,
        "files_returned": len(files),
        "truncated": truncated,
        "counts": counts,
        "extensions": dict(sorted(totals.items())),
        "files": files,
        "limitations": [
            "Only filesystem metadata is returned; file contents are never opened.",
            "Hidden, credential-related, and likely medical paths are excluded.",
            "Symlinks and mount-point crossings are not followed.",
            "Inventory is not an atomic filesystem snapshot.",
        ],
    }


def _validate_plan(root_arg: str, items: Any) -> dict[str, Any]:
    root = _resolve_root(root_arg)
    if not isinstance(items, list) or not items:
        raise IntegrationError("items must be a non-empty array.")
    if len(items) > MAX_PLAN_ITEMS:
        raise IntegrationError(f"At most {MAX_PLAN_ITEMS} plan items are accepted.")
    seen_sources: set[str] = set()
    seen_destinations: set[str] = set()
    validated: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            rejected.append({"index": str(index), "reason": "item_not_object"})
            continue
        source_raw = item.get("source")
        destination_raw = item.get("destination")
        if not isinstance(source_raw, str) or not isinstance(destination_raw, str):
            rejected.append({"index": str(index), "reason": "source_and_destination_required"})
            continue
        source_rel = Path(source_raw)
        destination_rel = Path(destination_raw)
        if (source_rel.is_absolute() or destination_rel.is_absolute()
                or ".." in source_rel.parts or ".." in destination_rel.parts
                or not source_rel.parts or not destination_rel.parts
                or any(part.startswith(".") for part in source_rel.parts + destination_rel.parts)):
            rejected.append({"index": str(index), "reason": "unsafe_relative_path"})
            continue
        if _is_sensitive_parts(source_rel.parts) or _is_sensitive_parts(destination_rel.parts):
            rejected.append({"index": str(index), "reason": "sensitive_path"})
            continue
        source_key = source_rel.as_posix()
        destination_key = destination_rel.as_posix()
        if source_key in seen_sources or destination_key in seen_destinations:
            rejected.append({"index": str(index), "reason": "duplicate_plan_path"})
            continue
        seen_sources.add(source_key)
        seen_destinations.add(destination_key)
        source = root / source_rel
        destination = root / destination_rel
        try:
            resolved_source = source.resolve(strict=True)
            resolved_parent = destination.parent.resolve(strict=False)
            if not _is_within(resolved_source, root) or not _is_within(resolved_parent, root):
                raise IntegrationError("path_escape")
            if source.is_symlink() or not resolved_source.is_file():
                raise IntegrationError("source_not_regular_file")
            if os.path.lexists(destination):
                raise IntegrationError("destination_exists")
            # Reject any existing symlink in the destination's parent chain.
            current = destination.parent
            while current != root and _is_within(current, root):
                if current.is_symlink():
                    raise IntegrationError("symlinked_destination_parent")
                current = current.parent
        except (OSError, RuntimeError, IntegrationError) as exc:
            reason = str(exc) if isinstance(exc, IntegrationError) else "path_unavailable"
            rejected.append({"index": str(index), "reason": reason})
            continue
        validated.append({
            "source": source_key,
            "destination": destination_key,
            "reason": str(item.get("reason", ""))[:300],
            "category": str(item.get("category", ""))[:100],
            "requires_user_approval": True,
        })
    return {
        "mode": "DRY_RUN",
        "execution_enabled": False,
        "validated_count": len(validated),
        "rejected_count": len(rejected),
        "validated": validated,
        "rejected": rejected,
        "notice": "Validation does not reserve destinations and is not authorization to execute.",
    }


TOOLS = [
    {
        "name": "intellifile.status",
        "description": "Return local integration health and the enforced read-only capability boundary.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "intellifile.inventory",
        "description": "Read-only metadata inventory for a user-allowlisted directory. Never reads file contents; excludes hidden, credential-related, likely medical, symlinked, and cross-mount entries.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string", "description": "Directory under INTELLIFILE_AGENT_ROOTS."},
                "max_entries": {"type": "integer", "minimum": 1, "maximum": MAX_INVENTORY_ENTRIES, "default": 300},
            },
            "required": ["root"],
            "additionalProperties": False,
        },
    },
    {
        "name": "intellifile.validate_plan",
        "description": "Validate a proposed file-move plan without changing files. Every accepted item still requires explicit human approval; execution is disabled.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string"},
                "items": {
                    "type": "array",
                    "maxItems": MAX_PLAN_ITEMS,
                    "items": {
                        "type": "object",
                        "properties": {
                            "source": {"type": "string"},
                            "destination": {"type": "string"},
                            "reason": {"type": "string"},
                            "category": {"type": "string"},
                        },
                        "required": ["source", "destination"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["root", "items"],
            "additionalProperties": False,
        },
    },
]


def _tool_result(value: Any, *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": _json_text(value)}],
        "isError": is_error,
    }


def dispatch(message: dict[str, Any], state: dict[str, Any]) -> dict[str, Any] | None:
    """Handle one JSON-RPC/MCP message; return None for notifications."""
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "id": message.get("id") if isinstance(message, dict) else None,
                "error": {"code": -32600, "message": "Invalid Request"}}
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}
    if not isinstance(params, dict):
        params = {}

    if method == "initialize" and request_id is not None:
        requested = params.get("protocolVersion", PROTOCOL_VERSION)
        negotiated = requested if requested in SUPPORTED_LEGACY_VERSIONS else PROTOCOL_VERSION
        state["phase"] = "awaiting_initialized"
        state["protocol_version"] = negotiated
        return {
            "jsonrpc": "2.0", "id": request_id,
            "result": {
                "protocolVersion": negotiated,
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": SERVER_NAME,
                    "title": "IntelliFile Manager — AlphaCode Local Bridge",
                    "version": SERVER_VERSION,
                },
                "instructions": (
                    "Local-only, read-only bridge. File contents and sensitive paths are not exposed. "
                    "No file mutation or execution tools are available."
                ),
            },
        }
    if method == "notifications/initialized":
        if state.get("phase") == "awaiting_initialized":
            state["phase"] = "ready"
        return None
    if method == "notifications/cancelled":
        return None
    if method == "ping" and request_id is not None:
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method in {"tools/list", "tools/call"} and state.get("phase") != "ready":
        return {"jsonrpc": "2.0", "id": request_id,
                "error": {"code": -32002, "message": "Server not initialized"}}
    if method == "tools/list" and request_id is not None:
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call" and request_id is not None:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            if not isinstance(arguments, dict):
                raise IntegrationError("Tool arguments must be an object.")
            if name == "intellifile.status":
                roots = _configured_roots()
                result = {
                    "status": "ok",
                    "server": SERVER_NAME,
                    "version": SERVER_VERSION,
                    "mode": "READ_ONLY",
                    "configured_root_count": len(roots),
                    "file_content_access": False,
                    "execution_enabled": False,
                    "external_network": False,
                }
            elif name == "intellifile.inventory":
                result = _inventory(arguments.get("root"), arguments.get("max_entries", 300))
            elif name == "intellifile.validate_plan":
                result = _validate_plan(arguments.get("root"), arguments.get("items"))
            else:
                raise IntegrationError("Unknown IntelliFile tool.")
            return {"jsonrpc": "2.0", "id": request_id, "result": _tool_result(result)}
        except (IntegrationError, OSError, TypeError, ValueError) as exc:
            return {
                "jsonrpc": "2.0", "id": request_id,
                "result": _tool_result({"error": str(exc)}, is_error=True),
            }
    if request_id is None:
        return None
    return {"jsonrpc": "2.0", "id": request_id,
            "error": {"code": -32601, "message": "Method not found"}}


def serve(stdin: Any = None, stdout: Any = None, stderr: Any = None) -> int:
    """Run the MCP stdio loop. stdout is reserved exclusively for protocol frames."""
    source = stdin or sys.stdin
    sink = stdout or sys.stdout
    diagnostics = stderr or sys.stderr
    state: dict[str, Any] = {"phase": "new"}
    while True:
        line = source.buffer.readline(MAX_MESSAGE_BYTES + 1) if hasattr(source, "buffer") else source.readline()
        if not line:
            return 0
        if isinstance(line, bytes):
            if len(line) > MAX_MESSAGE_BYTES:
                diagnostics.write("AlphaCode MCP: incoming frame exceeds size limit.\n")
                return 2
            try:
                line = line.decode("utf-8")
            except UnicodeDecodeError:
                diagnostics.write("AlphaCode MCP: incoming frame is not UTF-8.\n")
                return 2
        if len(line.encode("utf-8")) > MAX_MESSAGE_BYTES:
            diagnostics.write("AlphaCode MCP: incoming frame exceeds size limit.\n")
            return 2
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            response = {"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32700, "message": "Parse error"}}
        else:
            response = dispatch(message, state)
        if response is not None:
            sink.write(_json_text(response) + "\n")
            sink.flush()


if __name__ == "__main__":
    raise SystemExit(serve())
