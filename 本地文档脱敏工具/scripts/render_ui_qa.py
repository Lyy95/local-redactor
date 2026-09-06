from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from local_redactor.rule_library import (  # noqa: E402
    ActionKind,
    MatchMode,
    RuleDefinition,
    RuleKind,
    RuleLibrary,
    RuleStore,
)
from local_redactor.ui import (  # noqa: E402
    DemoDesktopController,
    MainWindow,
    RuleEditorDialog,
    RuleLibraryDialog,
)


def save_window(window: QWidget, path: Path) -> None:
    app = QApplication.instance()
    if app is None:
        raise RuntimeError("Qt 应用尚未初始化")
    app.processEvents()
    image = window.grab()
    if image.isNull() or not image.save(str(path), "PNG"):
        raise RuntimeError(f"无法生成界面验收图：{path.name}")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / "build" / "qa"
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    window = MainWindow(DemoDesktopController())
    window.resize(1280, 720)
    window.set_source_path(Path("虚构项目方案.docx"))
    window.show()
    save_window(window, output / "01-极简选文件.png")

    window.boundary_check.setChecked(True)
    window._begin_scan()
    window._set_step(2)
    window.review_tabs.setCurrentIndex(1)
    save_window(window, output / "02-图片确认处理.png")

    window.review_tabs.setCurrentIndex(0)
    save_window(window, output / "03-文字确认处理.png")
    with tempfile.TemporaryDirectory(prefix="local-redactor-rule-qa-") as directory:
        store = RuleStore(Path(directory) / "rules.dat")
        store.save(
            RuleLibrary(
                (
                    RuleDefinition.fixed("虚构单位", "GA", name="单位固定代号"),
                    RuleDefinition.standard(
                        "网络名称隐藏",
                        match_mode=MatchMode.CONTAINS,
                        patterns=("530网",),
                        action=ActionKind.MASK_MIDDLE,
                        positive_examples=("530网",),
                    ),
                )
            )
        )
        dialog = RuleLibraryDialog(store, window)
        dialog.show()
        save_window(dialog, output / "04-本地规则库.png")
        editor = RuleEditorDialog(RuleKind.STANDARD, parent=dialog)
        editor.name_edit.setText("内部网络名称隐藏")
        editor.match_mode_combo.setCurrentIndex(
            editor.match_mode_combo.findData(MatchMode.REGEX.value)
        )
        editor.pattern_edit.setText(r"\d{3}网")
        editor.action_combo.setCurrentIndex(
            editor.action_combo.findData(ActionKind.MASK_MIDDLE.value)
        )
        editor.positive_examples_edit.setText("530网")
        editor.show()
        save_window(editor, output / "05-判断标准编辑.png")
        editor.close()
        dialog.close()
    window.close()
    app.processEvents()
    print(f"ui qa rendered: {output}")


if __name__ == "__main__":
    main()
