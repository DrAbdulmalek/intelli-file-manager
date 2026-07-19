"""
Plugin Manager — discover and load plugins from a plugins/ directory.

This is a STUB file proposing the API for the plugin system described in
docs/DEVELOPMENT_ROADMAP.md (Task 3.2).

Goal: allow the community to add features without modifying core code.
"""

import importlib
import json
import os
import sys
from typing import Dict, Any, List, Callable, Optional


class PluginManager:
    """
    Plugin manager with a hook system.

    Plugins live in `<plugin_dir>/<plugin_name>/main.py` and declare a
    `manifest.json` describing their hooks.
    """

    def __init__(self, plugin_dir: str = "plugins"):
        self.plugin_dir = plugin_dir
        self.plugins: Dict[str, Dict[str, Any]] = {}
        self.hooks: Dict[str, List[Callable]] = {}

        os.makedirs(plugin_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Plugin discovery & loading
    # ------------------------------------------------------------------
    def load_plugins(self) -> None:
        """Discover and load all plugins from plugin_dir."""
        if not os.path.isdir(self.plugin_dir):
            return

        # Ensure plugin_dir is importable
        if self.plugin_dir not in sys.path:
            sys.path.insert(0, os.path.dirname(os.path.abspath(self.plugin_dir)))

        for item in os.listdir(self.plugin_dir):
            plugin_path = os.path.join(self.plugin_dir, item)
            if not os.path.isdir(plugin_path):
                continue

            manifest_path = os.path.join(plugin_path, "manifest.json")
            if not os.path.exists(manifest_path):
                continue

            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)

                module = importlib.import_module(f"{item}.main")
                self.plugins[item] = {
                    "module": module,
                    "manifest": manifest_data,
                }

                # Plugin can register its own hooks
                if hasattr(module, "register_hooks"):
                    module.register_hooks(self)

            except Exception as exc:
                # Sandbox plugin failures: log and continue
                print(f"[PluginManager] Failed to load plugin {item!r}: {exc}")

    # ------------------------------------------------------------------
    # Hook system
    # ------------------------------------------------------------------
    def register_hook(self, hook_name: str, callback: Callable) -> None:
        """Register a callback for a hook name."""
        self.hooks.setdefault(hook_name, []).append(callback)

    def trigger_hook(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """Invoke all callbacks registered for a hook name."""
        results: List[Any] = []
        for callback in self.hooks.get(hook_name, []):
            try:
                results.append(callback(*args, **kwargs))
            except Exception as exc:
                # Sandbox: one bad hook does not crash the others
                print(f"[PluginManager] Error in hook {hook_name!r}: {exc}")
        return results

    # ------------------------------------------------------------------
    # Plugin introspection
    # ------------------------------------------------------------------
    def get_plugin(self, name: str) -> Optional[Dict[str, Any]]:
        return self.plugins.get(name)

    def list_plugins(self) -> List[str]:
        return list(self.plugins.keys())
