"""Theme system: Fusion style + explicit QPalette + QSS, per theme.

Setting only a stylesheet is not enough — QSS-unspecified colors fall back to
the app palette, which can be dark or light depending on the OS and lead to
invisible text (e.g. white text on white table after switching themes).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

THEMES_DIR = Path(__file__).parent / "resources" / "themes"
VALID = ("auto", "light", "dark")

PALETTES: dict[str, dict[str, str]] = {
    "light": {
        "window": "#f2f4f7",
        "window_text": "#1d2939",
        "base": "#ffffff",
        "alternate": "#f8f9fb",
        "text": "#1d2939",
        "button": "#ffffff",
        "button_text": "#344054",
        "highlight": "#4f6bff",
        "highlight_text": "#ffffff",
        "tooltip_base": "#101828",
        "tooltip_text": "#f9fafb",
        "placeholder": "#98a2b3",
    },
    "dark": {
        "window": "#0f1117",
        "window_text": "#e6e9ef",
        "base": "#12161d",
        "alternate": "#141922",
        "text": "#e6e9ef",
        "button": "#1b212c",
        "button_text": "#e6e9ef",
        "highlight": "#4f6bff",
        "highlight_text": "#ffffff",
        "tooltip_base": "#1b212c",
        "tooltip_text": "#e6e9ef",
        "placeholder": "#6b7385",
    },
}


def resolve(name: str) -> str:
    if name not in VALID:
        name = "auto"
    if name != "auto":
        return name
    hints = QApplication.styleHints()
    scheme = hints.colorScheme() if hints is not None else Qt.ColorScheme.Light
    return "dark" if scheme == Qt.ColorScheme.Dark else "light"


def _build_palette(name: str) -> QPalette:
    c = PALETTES[name]
    p = QPalette()
    roles = {
        QPalette.ColorRole.Window: c["window"],
        QPalette.ColorRole.WindowText: c["window_text"],
        QPalette.ColorRole.Base: c["base"],
        QPalette.ColorRole.AlternateBase: c["alternate"],
        QPalette.ColorRole.Text: c["text"],
        QPalette.ColorRole.Button: c["button"],
        QPalette.ColorRole.ButtonText: c["button_text"],
        QPalette.ColorRole.Highlight: c["highlight"],
        QPalette.ColorRole.HighlightedText: c["highlight_text"],
        QPalette.ColorRole.ToolTipBase: c["tooltip_base"],
        QPalette.ColorRole.ToolTipText: c["tooltip_text"],
        QPalette.ColorRole.PlaceholderText: c["placeholder"],
    }
    for role, value in roles.items():
        p.setColor(role, QColor(value))
    return p


def apply_theme(app: QApplication, name: str) -> str:
    resolved = resolve(name)
    app.setStyle("Fusion")
    app.setPalette(_build_palette(resolved))
    qss = (THEMES_DIR / f"{resolved}.qss").read_text(encoding="utf-8")
    app.setStyleSheet(qss)
    app.setProperty("ytpawTheme", resolved)
    return resolved
