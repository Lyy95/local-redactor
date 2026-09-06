from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
    QWebEngineUrlRequestInfo,
    QWebEngineUrlRequestInterceptor,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QMainWindow

from .bridge import DesktopBridge


class OfflineRequestInterceptor(QWebEngineUrlRequestInterceptor):
    """Allow only resources embedded in the local desktop package."""

    def interceptRequest(self, info: QWebEngineUrlRequestInfo) -> None:
        if info.requestUrl().scheme() not in {"file", "qrc", "data", "blob"}:
            info.block(True)


class OfflinePage(QWebEnginePage):
    """Reject every navigation except the bundled local UI."""

    def __init__(self, profile: QWebEngineProfile, ui_root: Path, parent: QMainWindow) -> None:
        super().__init__(profile, parent)
        self._ui_root = ui_root.resolve()

    def acceptNavigationRequest(
        self, url: QUrl | str, navigation_type: QWebEnginePage.NavigationType, is_main_frame: bool
    ) -> bool:
        del navigation_type
        target = QUrl(url) if isinstance(url, str) else url
        if target.scheme() in {"", "qrc"}:
            return True
        if target.scheme() != "file":
            return False
        try:
            Path(target.toLocalFile()).resolve().relative_to(self._ui_root)
        except (OSError, ValueError):
            return False
        return True


class DesktopWindow(QMainWindow):
    def __init__(self, ui_root: Path, *, demo_mode: bool = False) -> None:
        super().__init__()
        self.setWindowTitle("本地文档脱敏工具")
        self.resize(1536, 1024)

        profile = QWebEngineProfile(self)
        profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        )
        profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.NoCache)
        self.request_interceptor = OfflineRequestInterceptor(profile)
        profile.setUrlRequestInterceptor(self.request_interceptor)
        profile.downloadRequested.connect(lambda download: download.cancel())
        page = OfflinePage(profile, ui_root, self)
        page.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
            False,
        )
        page.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls,
            True,
        )
        page.settings().setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows,
            False,
        )

        self.bridge = DesktopBridge(ui_root, self, demo_mode=demo_mode)
        self.channel = QWebChannel(page)
        self.channel.registerObject("desktopBridge", self.bridge)
        page.setWebChannel(self.channel)

        self.view = QWebEngineView(self)
        self.view.setPage(page)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setCentralWidget(self.view)

        index = (ui_root / "index.html").resolve()
        if not index.is_file():
            raise FileNotFoundError(f"V2 UI build is missing: {index}")
        self.view.load(QUrl.fromLocalFile(str(index)))

    def closeEvent(self, event: object) -> None:
        self.view.page().profile().clearHttpCache()
        super().closeEvent(event)  # type: ignore[arg-type]
