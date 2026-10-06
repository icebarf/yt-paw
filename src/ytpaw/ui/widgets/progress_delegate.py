"""Draws a themed progress bar in the Progress column.

Custom-painted (not QSS) so track/chunk colors are guaranteed in both themes.
"""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QRect, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication, QStyledItemDelegate, QStyleOptionViewItem

ModelIndex = QModelIndex | QPersistentModelIndex

THEME_COLORS = {
    "dark": {"track": "#1c2330", "chunk": "#4f6bff", "text": "#e6e9ef"},
    "light": {"track": "#e4e7ec", "chunk": "#4f6bff", "text": "#344054"},
}


class ProgressDelegate(QStyledItemDelegate):
    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: ModelIndex
    ) -> None:
        percent = index.data(Qt.ItemDataRole.UserRole)
        if percent is None:
            super().paint(painter, option, cast(QModelIndex, index))
            return
        app = QApplication.instance()
        theme = "dark"
        if isinstance(app, QApplication):
            theme = str(app.property("ytpawTheme") or "dark")
        colors = THEME_COLORS.get(theme, THEME_COLORS["dark"])

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect.adjusted(6, 7, -8, -7)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(colors["track"]))
        painter.drawRoundedRect(rect, 5, 5)

        pct = max(0.0, min(100.0, float(percent)))
        width = int(rect.width() * pct / 100.0)
        if width > 1:
            chunk = QRect(rect.x(), rect.y(), width, rect.height())
            painter.setBrush(QColor(colors["chunk"]))
            painter.drawRoundedRect(chunk, 5, 5)

        painter.setPen(QColor(colors["text"]))
        status = str(index.sibling(index.row(), 0).data() or "")
        if pct <= 0.0 and status == "Running":
            painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), "starting…")
        else:
            painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), f"{pct:.0f}%")
