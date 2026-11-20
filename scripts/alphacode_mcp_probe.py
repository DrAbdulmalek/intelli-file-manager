"""Read-only discovery of local AlphaCode MCP configuration hints.

This script never launches AlphaCode, executes shell commands, changes files,
or prints configuration values/secrets. It reports only launcher executable
basenames and MCP-related configuration key names.
"""
from __future__ import annotations

import json
import os
import re
import shlex
from pathlib import Path
from typing import Any

MAX_CONFIG_BYTES = 1024 * 1024
MAX_FILES = 500
MAX_DEPTH = 3
SKIP_DIRS = {".cache", "cache", "node_modules", "__pycache__", ".git"}
CONFIG_NAME_RE = re.compile(r"(mcp|config|settings|server|alphacode)", re.IGNORECASE)
MCP_KEY_RE = re.compile(
    r"""^\s*["']?(mcpServers|mcp_servers|mcp|modelContextProtocol|model_context_protocol)["']?\s*[:=]""",
    re.IGNORECASE,
)
MCP_SECTION_RE = re.compile(r"^\s*\[([^\]]*mcp[^\]]*)\]\s*$", re.IGNORECASE)


def _mcp_keys(path: Path) -> list[str]:
    """Return matching key names only; never return line values."""
    keys: set[str] = set()
    try:
        if path.stat().st_size > MAX_CONFIG_BYTES:
            return []
        with path.open("r", encoding="utf-8", errors="replace") as stream:
            for line in stream:
                match = MCP_KEY_RE.match(line)
                if match:
                    keys.add(match.group(1))
                    continue
                section = MCP_SECTION_RE.match(line)
                if section:
                    keys.add("[" + section.group(1) + "]")
    except OSError:
        return []
    return sorted(keys, key=str.casefold)


def _candidate_files(root: Path):
    if not root.is_dir() or root.is_symlink():
        return
    seen = 0
    for current, dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        try:
            depth = len(current_path.relative_to(root).parts)
        except ValueError:
            continue
        if depth >= MAX_DEPTH:
            dirs[:] = []
        else:
            dirs[:] = sorted(
                name for name in dirs
                if name not in SKIP_DIRS and not name.startswith(".")
                and not (current_path / name).is_symlink()
            )
        for name in sorted(files):
            if seen >= MAX_FILES:
                return
            if not CONFIG_NAME_RE.search(name):
                continue
            path = current_path / name
            if path.is_symlink() or path.suffix.casefold() not in {
                ".json", ".toml", ".yaml", ".yml", ".ini", ".conf", ".cfg", ".md", ".txt"
            }:
                continue
            seen += 1
            yield path


def _desktop_launchers(home: Path) -> list[dict[str, str]]:
    roots = [home / ".local/share/applications", Path("/usr/share/applications")]
    found: list[dict[str, str]] = []
    for root in roots:
        if not root.is_dir():
            continue
        try:
            entries = sorted(root.glob("*.desktop"))
        except OSError:
            continue
        for entry in entries:
            if "alphacode" not in entry.name.casefold() or entry.is_symlink():
                continue
            executable = ""
            try:
                for line in entry.read_text(encoding="utf-8", errors="replace").splitlines():
                    if line.startswith("Exec="):
                        parts = shlex.split(line[5:])
                        if parts:
                            index = 1 if Path(parts[0]).name == "env" and len(parts) > 1 else 0
                            executable = Path(parts[index]).name
                        break
            except (OSError, ValueError):
                pass
            found.append({
                "desktop_entry": entry.name,
                "exec_program_basename": executable or "not_detected",
            })
    return found


def inspect(home: Path | None = None) -> dict[str, Any]:
    home = (home or Path.home()).resolve()
    roots = [
        home / ".alphacode",
        home / ".config/alphacode",
        home / ".config/AlphaCode",
        home / ".config/alphacode-agent",
    ]
    config_reports: list[dict[str, Any]] = []
    visited: set[Path] = set()
    for root in roots:
        if not root.is_dir() or root.is_symlink():
            continue
        for path in _candidate_files(root):
            try:
                resolved = path.resolve(strict=True)
            except OSError:
                continue
            if resolved in visited:
                continue
            visited.add(resolved)
            keys = _mcp_keys(resolved)
            if keys:
                config_reports.append({
                    "location": "~/" + resolved.relative_to(home).as_posix(),
                    "mcp_key_names_only": keys,
                })
    launchers = _desktop_launchers(home)
    return {
        "mode": "READ_ONLY_DISCOVERY",
        "home_path_disclosed": False,
        "launchers": launchers,
        "mcp_config_hints": config_reports,
        "mcp_configuration_hint_found": bool(config_reports),
        "interpretation": (
            "MCP configuration keys were found; validate the AlphaCode client behavior manually."
            if config_reports else
            "No MCP configuration hint was found in the inspected locations; MCP support remains unverified."
        ),
        "limitations": [
            "Only known AlphaCode configuration locations and matching small text files were inspected.",
            "No AlphaCode process was launched and no executable was run.",
            "Configuration values, tokens, prompts, and file contents are never printed.",
        ],
    }


def main() -> int:
    print(json.dumps(inspect(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
