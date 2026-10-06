"""QAbstractTableModel over queue rows (sqlite3.Row)."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)
from PySide6.QtGui import QColor

ModelIndex = QModelIndex | QPersistentModelIndex

STATUS_TEXT = {
    "queued": "Queued",
    "running": "Running",
    "paused": "Paused",
    "done": "Done",
    "failed": "Failed",
    "cancelled": "Cancelled",
}

STATUS_COLOR = {
    "queued": "#8b94a7",
    "running": "#6c8cff",
    "paused": "#d29922",
    "done": "#3fb950",
    "failed": "#f85149",
    "cancelled": "#8b94a7",
}


def _fmt_time(raw: object) -> str:
    try:
        dt = datetime.fromisoformat(str(raw))
        return dt.astimezone().strftime("%H:%M:%S")
    except ValueError:
        return ""


class JobTableModel(QAbstractTableModel):
    COLUMNS = ("Status", "Title", "Progress", "Added")

    def __init__(self) -> None:
        super().__init__()
        self._rows: list[sqlite3.Row] = []

    def set_rows(self, rows: list[sqlite3.Row]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def row_at(self, index: int) -> sqlite3.Row | None:
        if 0 <= index < len(self._rows):
            return self._rows[index]
        return None

    def rowCount(self, parent: ModelIndex | None = None) -> int:
        return len(self._rows)

    def columnCount(self, parent: ModelIndex | None = None) -> int:
        return len(self.COLUMNS)

    def data(self, index: ModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = index.column()
        status = str(row["status"])
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return STATUS_TEXT.get(status, status)
            if col == 1:
                return str(row["title"] or row["url"])
            if col == 2:
                return f"{float(row['progress']):.0f}%"
            if col == 3:
                return _fmt_time(row["created_at"])
        elif role == Qt.ItemDataRole.UserRole and col == 2:
            return float(row["progress"])
        elif role == Qt.ItemDataRole.ForegroundRole and col == 0:
            return QColor(STATUS_COLOR.get(status, "#8b94a7"))
        elif role == Qt.ItemDataRole.ToolTipRole:
            err = str(row["error"] or "")
            return err if err else str(row["url"])
        elif role == Qt.ItemDataRole.TextAlignmentRole and col == 2:
            return int(Qt.AlignmentFlag.AlignCenter)
        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section]
        return None
