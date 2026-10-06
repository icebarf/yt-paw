"""Asset paths + pixmap helpers (icons live in ui/resources/icons)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

ICONS_DIR = Path(__file__).parent / "resources" / "icons"

_ICON_COLORS = {"dark": "#c9d3e0", "light": "#344054"}


def current_icon_color() -> str:
    app = QApplication.instance()
    theme = "dark"
    if isinstance(app, QApplication):
        theme = str(app.property("ytpawTheme") or "dark")
    return _ICON_COLORS.get(theme, _ICON_COLORS["dark"])


def icon(name: str, color: str | None = None, size: int = 16) -> QIcon:
    """Load an SVG icon and tint it (Qt cannot render `currentColor`).

    Color resolves from the active theme unless overridden; rendered at 2x
    for crisp HiDPI.
    """
    path = ICONS_DIR / f"{name}.svg"
    if not path.exists():
        return QIcon()
    renderer = QSvgRenderer(str(path))
    scale = 2
    pixmap = QPixmap(size * scale, size * scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), QColor(color or current_icon_color()))
    painter.end()
    return QIcon(pixmap)


def app_icon() -> QIcon:
    ico = ICONS_DIR / "app.ico"
    if ico.exists():
        return QIcon(str(ico))
    return QIcon(str(ICONS_DIR / "app.png"))


def logo_pixmap(size: int = 112, radius: int = 26) -> QPixmap:
    """Rounded-corner hero logo. Returns a null pixmap if the asset is missing."""
    src = QPixmap(str(ICONS_DIR / "logo.png"))
    if src.isNull():
        return src
    scaled = src.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    out = QPixmap(scaled.size())
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, scaled.width(), scaled.height(), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, scaled)
    painter.end()
    return out
