"""
Platform utilities — cross-platform path handling.

This is a STUB file proposing the API for the cross-platform support described
in docs/DEVELOPMENT_ROADMAP.md (Task 3.1).

Goal: make IntelliFile work on Linux (Manjaro), macOS, and Windows.
"""

import os
import platform
import sys
from typing import Optional


class PlatformUtils:
    """Cross-platform path and behavior utilities."""

    @staticmethod
    def get_platform() -> str:
        """Return 'linux', 'macos', 'windows', or 'unknown'."""
        system = platform.system()
        if system == "Linux":
            return "linux"
        if system == "Darwin":
            return "macos"
        if system == "Windows":
            return "windows"
        return "unknown"

    # ------------------------------------------------------------------
    # Standard user folders
    # ------------------------------------------------------------------
    @staticmethod
    def get_default_downloads() -> str:
        """Return the user's Downloads folder."""
        sys_name = PlatformUtils.get_platform()

        if sys_name == "windows":
            # Windows: read from registry if possible, fallback to USERPROFILE
            return PlatformUtils._windows_downloads()
        if sys_name == "macos":
            return os.path.expanduser("~/Downloads")
        # linux
        return os.path.expanduser("~/Downloads")

    @staticmethod
    def get_default_documents() -> str:
        sys_name = PlatformUtils.get_platform()
        if sys_name == "macos":
            return os.path.expanduser("~/Documents")
        return os.path.expanduser("~/Documents")

    # ------------------------------------------------------------------
    # App data directory
    # ------------------------------------------------------------------
    @staticmethod
    def get_app_data_dir(app_name: str) -> str:
        """Return the per-app data directory (creates it if missing)."""
        sys_name = PlatformUtils.get_platform()

        if sys_name == "windows":
            base = os.getenv("APPDATA") or os.path.expanduser("~")
        elif sys_name == "macos":
            base = os.path.expanduser("~/Library/Application Support")
        else:  # linux
            base = os.getenv("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")

        app_dir = os.path.join(base, app_name)
        os.makedirs(app_dir, exist_ok=True)
        return app_dir

    @staticmethod
    def get_cache_dir(app_name: str) -> str:
        """Return the per-app cache directory (creates it if missing)."""
        sys_name = PlatformUtils.get_platform()

        if sys_name == "windows":
            base = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or os.path.expanduser("~")
        elif sys_name == "macos":
            base = os.path.expanduser("~/Library/Caches")
        else:  # linux
            base = os.getenv("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")

        cache_dir = os.path.join(base, app_name)
        os.makedirs(cache_dir, exist_ok=True)
        return cache_dir

    # ------------------------------------------------------------------
    # Windows-specific helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _windows_downloads() -> str:
        """Read the Windows Downloads path from the registry (or fallback)."""
        # Lazy import — only runs on Windows
        # try:
        #     import winreg
        #     key = winreg.OpenKey(
        #         winreg.HKEY_CURRENT_USER,
        #         r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
        #     )
        #     downloads_guid = "{374DE290-123F-4565-9164-39C4925E467B}"
        #     path, _ = winreg.QueryValueEx(key, downloads_guid)
        #     return path
        # except Exception:
        #     pass
        return os.path.join(os.path.expanduser("~"), "Downloads")
