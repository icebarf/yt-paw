"""HOME: hero logo, URL + Analyze, jobs/settings nav."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ytpaw.ui.assets import icon, logo_pixmap


class HomeView(QWidget):
    analyze = Signal(str)
    open_jobs = Signal()
    open_settings = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 16)
        root.setSpacing(10)

        header = QHBoxLayout()
        logo_col = QVBoxLayout()
        logo_col.setSpacing(4)
        logo = QLabel(self)
        logo.setObjectName("heroLogo")
        logo.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        pix = logo_pixmap(112)
        if pix.isNull():
            logo.setText("yt-paw")
            logo.setObjectName("appTitle")
        else:
            logo.setPixmap(pix)
        title = QLabel("yt-paw", self)
        title.setObjectName("appTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        sub = QLabel("simple, yet feature rich", self)
        sub.setObjectName("appSubtitle")
        sub.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        logo_col.addWidget(logo)
        logo_col.addWidget(title)
        logo_col.addWidget(sub)
        header.addStretch(1)
        header.addLayout(logo_col)
        header.addStretch(1)
        root.addLayout(header)

        root.addStretch(2)

        url_row = QHBoxLayout()
        url_row.addStretch(1)
        self.url = QLineEdit(self)
        self.url.setPlaceholderText("Paste video URL here…")
        self.url.setMinimumWidth(420)
        self.url.returnPressed.connect(self._emit_analyze)
        self.go = QPushButton("Analyze", self)
        self.go.setObjectName("primaryButton")
        self.go.clicked.connect(self._emit_analyze)
        url_row.addWidget(self.url, 3)
        url_row.addSpacing(8)
        url_row.addWidget(self.go, 0)
        url_row.addStretch(1)
        root.addLayout(url_row)

        root.addStretch(3)

        nav = QHBoxLayout()
        self.jobs_btn = QPushButton("Jobs", self)
        self.jobs_btn.clicked.connect(self.open_jobs.emit)
        self.settings_btn = QPushButton("Settings", self)
        self.settings_btn.clicked.connect(self.open_settings.emit)
        nav.addWidget(self.jobs_btn)
        nav.addStretch(1)
        nav.addWidget(self.settings_btn)
        root.addLayout(nav)

    def apply_icons(self) -> None:
        self.go.setIcon(icon("zap", "#ffffff"))
        self.jobs_btn.setIcon(icon("clock-9"))
        self.settings_btn.setIcon(icon("settings"))
        for button in (self.go, self.jobs_btn, self.settings_btn):
            button.setIconSize(QSize(16, 16))

    def _emit_analyze(self) -> None:
        url = self.url.text().strip()
        if url:
            self.analyze.emit(url)
