"""First-run setup dialog: choose how to provide the download engine."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SetupWizardDialog(QDialog):
    CHOICE_SYSTEM = "system"
    CHOICE_AUTO = "auto"
    CHOICE_PATH = "path"
    CHOICE_LATER = "later"

    def __init__(
        self,
        engine_name: str,
        system_path: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.choice = self.CHOICE_LATER
        self.selected_path: str | None = None
        self.setWindowTitle("yt-paw — first run")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 18, 20, 16)

        title = QLabel("Welcome to yt-paw", self)
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        if system_path:
            body_text = (
                f"yt-paw downloads videos through an engine ({engine_name}). "
                "An existing installation was found on this system."
            )
        else:
            body_text = (
                f"yt-paw downloads videos through an engine ({engine_name}), "
                "and none was found on this system."
            )
        body = QLabel(body_text, self)
        body.setWordWrap(True)
        layout.addWidget(body)

        hint = QLabel(
            "Automatic mode downloads the engine into yt-paw's own folder and "
            "keeps it updated. You can change this later in Settings.",
            self,
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addSpacing(6)

        buttons = QHBoxLayout()
        path_btn = QPushButton("Choose binary…", self)
        path_btn.clicked.connect(self._pick_path)
        later_btn = QPushButton("Set up later", self)
        later_btn.clicked.connect(self.reject)
        buttons.addWidget(path_btn)
        buttons.addStretch(1)
        buttons.addWidget(later_btn)
        if system_path:
            system_btn = QPushButton("Use system install", self)
            system_btn.setToolTip(system_path)
            system_btn.clicked.connect(self._choose_system)
            buttons.addWidget(system_btn)
        auto_btn = QPushButton("Download automatically", self)
        auto_btn.setObjectName("primaryButton")
        auto_btn.clicked.connect(self._choose_auto)
        buttons.addWidget(auto_btn)
        layout.addLayout(buttons)

    def _choose_system(self) -> None:
        self.choice = self.CHOICE_SYSTEM
        self.accept()

    def _choose_auto(self) -> None:
        self.choice = self.CHOICE_AUTO
        self.accept()

    def _pick_path(self) -> None:
        chosen, _ = QFileDialog.getOpenFileName(self, "Select engine binary")
        if chosen:
            self.choice = self.CHOICE_PATH
            self.selected_path = chosen
            self.accept()

    def keyPressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
