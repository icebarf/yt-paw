"""Async thumbnail download via QtNetwork. Bytes only, no disk cache."""

from __future__ import annotations

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest


class ThumbnailLoader(QObject):
    loaded = Signal(str, bytes)  # url, image bytes
    failed = Signal(str)  # url

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._nam = QNetworkAccessManager(self)

    def fetch(self, url: str) -> None:
        if not url:
            return
        request = QNetworkRequest(QUrl(url))
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy,
        )
        reply = self._nam.get(request)
        reply.finished.connect(lambda: self._on_finished(reply, url))

    def _on_finished(self, reply: QNetworkReply, url: str) -> None:
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = reply.readAll().data()
            if data:
                self.loaded.emit(url, data)
                reply.deleteLater()
                return
        self.failed.emit(url)
        reply.deleteLater()
