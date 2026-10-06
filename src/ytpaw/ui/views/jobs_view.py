"""JOBS page: logo | URL bar | quick Best button, job table, settings nav."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ytpaw.ui.assets import icon
from ytpaw.ui.models.job_table_model import JobTableModel
from ytpaw.ui.widgets.progress_delegate import ProgressDelegate


class JobsView(QWidget):
    download_best = Signal(str)
    open_settings = Signal()
    go_home = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 16)
        root.setSpacing(10)

        top = QHBoxLayout()
        logo = QLabel("yt-paw", self)
        logo.setObjectName("appTitleSmall")
        self.url = QLineEdit(self)
        self.url.setPlaceholderText("Paste URL for quick Best download…")
        self.url.returnPressed.connect(self._emit_download)
        self.go = QPushButton("Download", self)
        self.go.setObjectName("primaryButton")
        self.go.clicked.connect(self._emit_download)
        top.addWidget(logo)
        top.addSpacing(8)
        top.addWidget(self.url, 1)
        top.addWidget(self.go)
        root.addLayout(top)

        self.model = JobTableModel()
        table = QTableView(self)
        table.setModel(self.model)
        table.setItemDelegateForColumn(2, ProgressDelegate(table))
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        table.setWordWrap(False)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(34)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        table.setColumnWidth(2, 150)
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table = table
        root.addWidget(table, 1)

        nav = QHBoxLayout()
        self.home_btn = QPushButton("Home", self)
        self.home_btn.clicked.connect(self.go_home.emit)
        self.settings_btn = QPushButton("Settings", self)
        self.settings_btn.clicked.connect(self.open_settings.emit)
        nav.addWidget(self.home_btn)
        nav.addStretch(1)
        nav.addWidget(self.settings_btn)
        root.addLayout(nav)

    def apply_icons(self) -> None:
        self.go.setIcon(icon("download", "#ffffff"))
        self.home_btn.setIcon(icon("paw-print"))
        self.settings_btn.setIcon(icon("settings"))
        for button in (self.go, self.home_btn, self.settings_btn):
            button.setIconSize(QSize(16, 16))

    def _emit_download(self) -> None:
        url = self.url.text().strip()
        if url:
            self.download_best.emit(url)
            self.url.clear()
