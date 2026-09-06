from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from local_redactor.runtime import (
    ModelIntegrityError,
    enforce_offline_runtime,
    verify_bundled_models,
)

from .host import DesktopWindow


def ui_root() -> Path:
    bundled_root = getattr(sys, "_MEIPASS", None)
    if bundled_root:
        return Path(bundled_root) / "ui" / "dist" / "client"
    executable_root = Path(sys.executable).resolve().parent
    bundled_ui = executable_root / "ui" / "dist" / "client"
    if bundled_ui.is_dir():
        return bundled_ui
    return Path(__file__).resolve().parents[2] / "ui" / "dist" / "client"



def _prepare_desktop_runtime() -> None:
    """Reduce WebEngine noise and set macOS Dock label before QApplication."""
    import os

    os.environ.setdefault(
        "QTWEBENGINE_CHROMIUM_FLAGS",
        "--disable-gpu --disable-gpu-compositing --no-sandbox",
    )
    if sys.platform != "darwin":
        return
    try:
        from Foundation import NSBundle  # type: ignore

        info = NSBundle.mainBundle().infoDictionary()
        if info is not None:
            info["CFBundleName"] = "本地文档脱敏工具"
            info["CFBundleDisplayName"] = "本地文档脱敏工具"
    except Exception:
        # PyObjC optional under plain venv; a real .app Info.plist still wins.
        return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--demo-docx", action="store_true")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    enforce_offline_runtime()
    _prepare_desktop_runtime()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("本地文档脱敏工具")
    app.setApplicationDisplayName("本地文档脱敏工具")
    app.setOrganizationName("LocalRedactorV2")
    try:
        verify_bundled_models()
    except ModelIntegrityError as exc:
        QMessageBox.critical(
            None,
            "离线识别组件校验失败",
            f"{exc}\n\n为避免遗漏敏感内容，本次未启动文档处理。",
        )
        return 2
    try:
        window = DesktopWindow(ui_root(), demo_mode=args.demo_docx)
    except FileNotFoundError as exc:
        QMessageBox.critical(None, "界面构建缺失", str(exc))
        return 2
    if args.self_test:
        window.show()
        QTimer.singleShot(1500, window.close)
        QTimer.singleShot(3000, app.quit)
        return app.exec()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
