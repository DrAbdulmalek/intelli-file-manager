"""
Theme Manager — multiple UI themes for the PySide6 desktop interface.

This is a STUB file proposing the API for the theme manager described in
docs/DEVELOPMENT_ROADMAP.md (Task 2.4).

Goal: give users dark / light / high-contrast options and persist their choice.
"""

from typing import Dict, Any
import json
import os


class ThemeManager:
    """PySide6 theme manager with dark / light / high-contrast presets."""

    THEMES: Dict[str, Dict[str, str]] = {
        "dark": {
            "background": "#1e1e1e",
            "foreground": "#d4d4d4",
            "accent": "#007acc",
            "border": "#3c3c3c",
        },
        "light": {
            "background": "#ffffff",
            "foreground": "#333333",
            "accent": "#0066cc",
            "border": "#cccccc",
        },
        "high_contrast": {
            "background": "#000000",
            "foreground": "#ffffff",
            "accent": "#ffff00",
            "border": "#ffffff",
        },
    }

    def __init__(self, app, prefs_file: str = "theme_prefs.json"):
        self.app = app
        self.prefs_file = prefs_file
        self.current_theme = "dark"

    # ------------------------------------------------------------------
    # Apply theme
    # ------------------------------------------------------------------
    def apply_theme(self, theme_name: str) -> bool:
        """Apply a theme by name. Returns True on success."""
        if theme_name not in self.THEMES:
            return False

        # Lazy import — keeps the module importable without PySide6 installed
        try:
            from PySide6.QtGui import QPalette, QColor
        except ImportError:
            print("[ThemeManager] PySide6 not installed — cannot apply theme")
            return False

        theme = self.THEMES[theme_name]
        palette = QPalette()

        palette.setColor(QPalette.ColorRole.Window, QColor(theme["background"]))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(theme["foreground"]))
        palette.setColor(QPalette.ColorRole.Base, QColor(theme["background"]))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(theme["border"]))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(theme["background"]))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(theme["foreground"]))
        palette.setColor(QPalette.ColorRole.Text, QColor(theme["foreground"]))
        palette.setColor(QPalette.ColorRole.Button, QColor(theme["background"]))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(theme["foreground"]))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(theme["accent"]))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(theme["accent"]))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(theme["background"]))

        self.app.setPalette(palette)
        self.current_theme = theme_name
        self._save_preference(theme_name)
        return True

    # ------------------------------------------------------------------
    # Preferences persistence
    # ------------------------------------------------------------------
    def list_themes(self) -> Dict[str, Dict[str, str]]:
        return self.THEMES

    def get_current_theme(self) -> str:
        return self.current_theme

    def _save_preference(self, theme_name: str) -> None:
        try:
            with open(self.prefs_file, "w", encoding="utf-8") as f:
                json.dump({"theme": theme_name}, f)
        except OSError:
            pass

    def load_preference(self) -> str:
        if not os.path.exists(self.prefs_file):
            return self.current_theme
        try:
            with open(self.prefs_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            theme = data.get("theme", self.current_theme)
            if theme in self.THEMES:
                self.current_theme = theme
        except (OSError, json.JSONDecodeError):
            pass
        return self.current_theme
