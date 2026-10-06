"""Window-level update notification: floating toast, top-right, click to dismiss.

Lives as a direct child of MainWindow (not in any layout) so it never affects
page layout and stays visible across page navigation. Reposition on resize.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QLabel, QWidget

MAX_TEXT = 90


class UpdateBanner(QLabel):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("updateBanner")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Click to dismiss")
        self.setVisible(False)

    def show_message(self, text: str, error: bool = False) -> None:
        display = text if len(text) <= MAX_TEXT else text[: MAX_TEXT - 1] + "…"
        self.setProperty("error", "true" if error else "false")
        self.setText(display)
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
        self._reposition()
        self.setVisible(True)
        self.raise_()

    def clear_message(self) -> None:
        self.setVisible(False)

    def reposition(self) -> None:
        if self.isVisible():
            self._reposition()

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.setWordWrap(True)
        self.setMaximumWidth(max(240, int(parent.width() * 0.45)))
        self.adjustSize()
        x = max(16, parent.width() - self.width() - 20)
        self.move(x, 14)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.setVisible(False)
        event.accept()
