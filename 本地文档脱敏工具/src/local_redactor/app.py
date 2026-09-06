from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from PySide6.QtWidgets import QApplication, QMessageBox

from .runtime import ModelIntegrityError, enforce_offline_runtime, verify_bundled_models
from .service import LocalDesktopController
from .ui import DemoDesktopController, DesktopController, MainWindow
from .ui.rule_dialog import RuleLibraryDialog


def create_window(controller: DesktopController | None = None) -> MainWindow:
    """Create the desktop window with an injectable local-processing controller."""

    selected_controller = controller or LocalDesktopController()
    window = MainWindow(selected_controller)
    if isinstance(selected_controller, LocalDesktopController):
        _connect_rule_library(window, selected_controller)
    return window


def _connect_rule_library(
    window: MainWindow,
    controller: LocalDesktopController,
) -> None:
    dialogs: list[RuleLibraryDialog] = []

    def remove_dialog(dialog: RuleLibraryDialog) -> None:
        if dialog in dialogs:
            dialogs.remove(dialog)

    def require_rescan(_library: object) -> None:
        if window.bundle is None:
            return
        window.apply_rule_library_change()

    def open_dialog() -> None:
        visible = next((dialog for dialog in dialogs if dialog.isVisible()), None)
        if visible is not None:
            visible.raise_()
            visible.activateWindow()
            return
        dialog = RuleLibraryDialog(controller.rule_store, window)
        dialog.setModal(False)
        dialog.library_changed.connect(require_rescan)
        dialog.finished.connect(
            lambda _result, current=dialog: remove_dialog(current)
        )
        dialogs.append(dialog)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    window.rule_library_requested.connect(open_dialog)


def main(
    argv: Sequence[str] | None = None,
    controller: DesktopController | None = None,
) -> int:
    arguments = list(sys.argv if argv is None else argv)
    enforce_offline_runtime()
    existing = QApplication.instance()
    app = cast(QApplication, existing) if existing is not None else QApplication(arguments)
    app.setApplicationName("本地文档脱敏工具")
    app.setOrganizationName("LocalRedactor")
    try:
        verify_bundled_models()
    except ModelIntegrityError as exc:
        QMessageBox.critical(
            None,
            "离线识别组件校验失败",
            f"{exc}\n\n为避免遗漏敏感内容，本次未启动文档处理。",
        )
        return 2

    selected_controller = controller
    if selected_controller is None and ("--demo-docx" in arguments or "--demo-xlsx" in arguments):
        selected_controller = DemoDesktopController()
    window = create_window(selected_controller)
    if "--demo-docx" in arguments:
        window.set_source_path(Path("虚构项目方案.docx"))
    elif "--demo-xlsx" in arguments:
        window.set_source_path(Path("虚构项目台账.xlsx"))

    if "--self-test" in arguments:
        window.show()
        app.processEvents()
        window.close()
        return 0

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
