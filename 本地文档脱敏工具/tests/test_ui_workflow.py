from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

import shiboken6  # noqa: E402
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QComboBox,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
)

from local_redactor.app import create_window  # noqa: E402
from local_redactor.models import (  # noqa: E402
    Category,
    DocumentKind,
    FindingStatus,
    ImageDisposition,
    ProcessingMode,
)
from local_redactor.rule_library import RuleDefinition, RuleKind, RuleStore  # noqa: E402
from local_redactor.service import LocalDesktopController  # noqa: E402
from local_redactor.ui import (  # noqa: E402
    DemoDesktopController,
    MainWindow,
    ReviewBundle,
    RuleLibraryDialog,
)
from local_redactor.ui.rule_dialog import RuleEditorDialog  # noqa: E402


class _UiTestProtector:
    def protect(self, plaintext: bytes) -> bytes:
        return b"ui-v1:" + plaintext[::-1]

    def unprotect(self, ciphertext: bytes) -> bytes:
        if not ciphertext.startswith(b"ui-v1:"):
            raise ValueError("damaged")
        return ciphertext.removeprefix(b"ui-v1:")[::-1]


@pytest.fixture(scope="session")
def qapp() -> Iterator[QApplication]:
    existing = QApplication.instance()
    app = cast(QApplication, existing) if existing is not None else QApplication([])
    yield app
    shiboken6.delete(app)


@pytest.fixture()
def window(qapp: QApplication) -> Iterator[MainWindow]:
    result = MainWindow(DemoDesktopController())
    result.show()
    qapp.processEvents()
    yield result
    result.close()
    result.deleteLater()
    qapp.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def start_review(window: MainWindow, source: Path, qapp: QApplication) -> None:
    window.set_source_path(source)
    window.boundary_check.setChecked(True)
    assert window.primary_button.isEnabled()
    window.primary_button.click()
    qapp.processEvents()
    assert window.current_step == 1
    assert window.scan_progress.value() == 100
    window.primary_button.click()
    qapp.processEvents()
    assert window.current_step == 2


def test_window_uses_requested_logo(window: MainWindow) -> None:
    logo = window.findChild(QLabel, "appLogo")

    assert logo is not None
    assert logo.pixmap() is not None
    assert not logo.pixmap().isNull()
    assert not window.windowIcon().isNull()


def resolve_all_review_items(window: MainWindow, qapp: QApplication) -> None:
    window.resolve_ordinary_button.click()
    for row in range(window.findings_table.rowCount()):
        window.findings_table.selectRow(row)
        if window.apply_strategy_button.isEnabled():
            window.apply_strategy_button.click()
    for row in range(window.image_table.rowCount()):
        combo = cast(QComboBox, window.image_table.cellWidget(row, 3))
        combo.setCurrentIndex(2)
    qapp.processEvents()


def test_four_step_shell_is_offline_and_hides_source_path(
    window: MainWindow,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    source = tmp_path / "内部目录" / "虚构项目方案.docx"
    window.set_source_path(source)
    qapp.processEvents()

    offline = window.findChild(QLabel, "offlineBadge")
    assert offline is not None
    assert "本机离线处理" in offline.text()
    assert window.selected_file_name.text() == source.name
    assert str(source.parent) not in window.selected_file_name.text()
    assert window.pages.count() == 4
    assert [label.text() for label in window.step_labels] == [
        "1  选文件",
        "2  自动检查",
        "3  确认处理",
        "4  生成文件",
    ]
    assert window.balanced_mode.isChecked()
    assert window.primary_button.text() == "开始检查"
    assert not window.select_details_panel.isVisible()
    assert not window.primary_button.isEnabled()

    opened: list[bool] = []
    window.rule_library_requested.connect(lambda: opened.append(True))
    window.rules_library_button.click()
    assert opened == [True]


def test_folder_selection_builds_supported_queue_and_excludes_results(
    window: MainWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "a.docx").write_bytes(b"fixture")
    (tmp_path / "b.xlsx").write_bytes(b"fixture")
    (tmp_path / "ignore.txt").write_text("fixture", encoding="utf-8")
    (tmp_path / "~$temp.docx").write_bytes(b"fixture")
    result_dir = tmp_path / "脱敏结果_20260807_170000" / "AI交付"
    result_dir.mkdir(parents=True)
    (result_dir / "old.docx").write_bytes(b"fixture")
    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(tmp_path),
    )

    window._choose_source_folder()

    assert [path.name for path in window.source_queue] == ["a.docx", "b.xlsx"]
    assert window.source_path == window.source_queue[0]
    assert "文件队列 2 个" in window.queue_summary.text()


def test_production_rule_entry_applies_rule_incrementally_without_reset(
    qapp: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = RuleStore(tmp_path / "rules.dat", _UiTestProtector())
    controller = LocalDesktopController(rule_store=store)
    result = create_window(controller)
    result.show()
    source = tmp_path / "当前任务.docx"
    result.set_source_path(source)
    result.bundle = ReviewBundle(
        source_name=source.name,
        document_kind=DocumentKind.DOCX,
        mode=ProcessingMode.BALANCED,
    )
    monkeypatch.setattr(controller, "apply_rules_incrementally", lambda: 1)

    result.rules_library_button.click()
    qapp.processEvents()
    dialogs = result.findChildren(RuleLibraryDialog)
    assert len(dialogs) == 1
    assert dialogs[0].isVisible()

    dialogs[0].add_rule(RuleDefinition.fixed("公安", "GA"))
    qapp.processEvents()

    assert result.bundle is not None
    assert result.source_path == source
    assert "增量应用" in result.review_action_feedback.text()
    dialogs[0].close()
    result.close()
    result.deleteLater()
    qapp.processEvents()


def test_rule_library_distinguishes_presets_and_previews_fictional_sample(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    store = RuleStore(
        tmp_path / "rules.dat",
        _UiTestProtector(),
        include_presets=True,
    )
    dialog = RuleLibraryDialog(store)
    dialog.show()
    qapp.processEvents()

    table = dialog._tables[RuleKind.FIXED]
    assert table.rowCount() > 0
    assert "来源" in [
        table.horizontalHeaderItem(index).text()
        for index in range(table.columnCount())
    ]
    table.selectRow(0)
    qapp.processEvents()
    assert dialog._edit_buttons[RuleKind.FIXED].isEnabled()
    assert dialog._toggle_buttons[RuleKind.FIXED].isEnabled()
    assert dialog._delete_buttons[RuleKind.FIXED].isEnabled()

    editor = RuleEditorDialog(RuleKind.FIXED)
    editor.name_edit.setText("虚构地名样例")
    editor.pattern_edit.setText("海南")
    editor.replacement_edit.setText("HN")
    editor.scope_checks["all"].setChecked(True)
    editor.sample_edit.setText("虚构材料来自海南")
    editor._preview_sample()
    assert editor.sample_result.text() == "验证结果：虚构材料来自HN"
    editor.close()
    dialog.close()


def test_scan_page_shows_four_simple_stages_and_collapsed_details(
    window: MainWindow,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    window.set_source_path(tmp_path / "虚构项目方案.docx")
    window.boundary_check.setChecked(True)
    window.primary_button.click()
    qapp.processEvents()

    assert window.current_step == 1
    assert window.scan_progress.value() == 100
    assert len(window.scan_stage_labels) == 4
    assert all(label.text().startswith("✓") for label in window.scan_stage_labels)
    assert not window.inventory_table.isVisible()
    assert "需要确认" in window.scan_status.text()
    assert window.primary_button.text() == "开始确认"


def test_review_is_a_low_density_todo_and_hides_advanced_terms(
    window: MainWindow,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    start_review(window, tmp_path / "虚构项目台账.xlsx", qapp)

    assert window.review_tabs.count() == 3
    assert window.review_tabs.tabText(0).startswith("文字 ")
    assert window.review_tabs.tabText(1).startswith("图片 ")
    assert window.review_tabs.tabText(2).startswith("隐藏内容 ")
    assert window.findings_table.columnCount() == 4
    assert window.findings_table.rowCount() > 0
    assert window.image_table.rowCount() > 0
    assert window.hidden_table.rowCount() > 0
    assert window.preview_original.toPlainText()
    assert window.preview_replacement.toPlainText()
    assert window.advanced_edit_panel.isVisible()
    assert window.apply_strategy_button.text() == "采用建议"
    assert window.modify_finding_button.text() == "收起修改"
    assert window.ignore_finding_button.text() == "保留原文"
    assert window.remove_finding_button.text() == "删除"
    assert window.resolve_ordinary_button.text() == "采用全部普通建议"
    assert not window.primary_button.isEnabled()

    method_labels = {
        window.method_combo.itemText(index)
        for index in range(window.method_combo.count())
    }
    forbidden = {
        "一致别名",
        "结构模拟",
        "降低精度",
        "区间化",
        "统一平移",
        "比例变换",
        "像素处理",
        "转为可见附注",
    }
    assert method_labels.isdisjoint(forbidden)


def test_review_can_remember_a_mapping_and_mandatory_rules_cannot_keep_original(
    window: MainWindow,
    qapp: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "虚构规则沉淀.docx"
    start_review(window, source, qapp)
    assert window.bundle is not None
    finding = window._selected_finding()
    assert finding is not None
    messages: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, _title, message: messages.append(message),
    )

    window.modify_finding_button.click()
    window.replacement_edit.setText("长期代号甲")
    window.remember_rule_button.click()
    qapp.processEvents()

    controller = cast(DemoDesktopController, window.controller)
    assert controller._saved_rules[-1].replacement == "长期代号甲"  # noqa: SLF001
    assert window.bundle is not None
    assert window.source_path == source
    assert window.current_step == 2
    assert window.boundary_check.isChecked()
    assert "增量应用" in window.review_action_feedback.text()
    assert messages == []

    finding = window._selected_finding()
    assert finding is not None

    finding.metadata.update(
        {
            "rule_id": "mandatory-001",
            "rule_name": "强制代号",
            "rule_mandatory": True,
        }
    )
    finding.status = FindingStatus.TRANSFORM
    window._populate_findings(window.bundle.findings)
    rule_row = next(
        row
        for row in range(window.findings_table.rowCount())
        if window.findings_table.item(row, 0).data(Qt.ItemDataRole.UserRole) == finding.id
    )
    window.findings_table.selectRow(rule_row)
    window._show_selected_finding()
    qapp.processEvents()

    assert window.findings_table.item(rule_row, 3).text() == "已按规则处理"
    assert window.modify_finding_button.isEnabled()
    assert not window.ignore_finding_button.isEnabled()
    assert "必须使用代号或删除" in window.ignore_finding_button.toolTip()


def test_bulk_action_excludes_low_confidence_high_risk_images_and_hidden_items(
    window: MainWindow,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    start_review(window, tmp_path / "虚构批量确认.docx", qapp)
    assert window.bundle is not None
    low_confidence = next(
        finding
        for finding in window.bundle.findings
        if finding.category is not Category.COMBINATION_RISK
    )
    low_confidence.confidence = 0.79

    window.resolve_ordinary_button.click()
    qapp.processEvents()

    assert low_confidence.status is FindingStatus.PENDING
    combination = next(
        finding
        for finding in window.bundle.findings
        if finding.category is Category.COMBINATION_RISK
    )
    assert combination.status is FindingStatus.PENDING
    assert all(
        image.disposition is ImageDisposition.PENDING for image in window.bundle.images
    )
    assert all(item.action == "remove" for item in window.bundle.hidden_items)
    assert "图片、低置信度和组合风险仍需逐项确认" in (
        window.review_action_feedback.text()
    )
    assert not window.primary_button.isEnabled()


def test_single_action_feedback_moves_to_next_and_processed_row_is_idempotent(
    window: MainWindow,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    start_review(window, tmp_path / "虚构逐项确认.xlsx", qapp)
    assert window.bundle is not None
    first = window._selected_finding()
    assert first is not None
    pending_before = sum(
        finding.status is FindingStatus.PENDING for finding in window.bundle.findings
    )

    window.apply_strategy_button.click()
    qapp.processEvents()

    assert first.status is FindingStatus.TRANSFORM
    assert "已采用建议，已进入下一项" in window.review_action_feedback.text()
    assert sum(
        finding.status is FindingStatus.PENDING for finding in window.bundle.findings
    ) == pending_before - 1
    selected_after = window._selected_finding()
    assert selected_after is not None and selected_after.id != first.id

    first_row = next(
        row
        for row in range(window.findings_table.rowCount())
        if window.findings_table.item(row, 0).data(Qt.ItemDataRole.UserRole) == first.id
    )
    window.findings_table.selectRow(first_row)
    qapp.processEvents()
    assert not window.apply_strategy_button.isEnabled()
    pending_after = sum(
        finding.status is FindingStatus.PENDING for finding in window.bundle.findings
    )
    window.apply_strategy_button.click()
    assert sum(
        finding.status is FindingStatus.PENDING for finding in window.bundle.findings
    ) == pending_after


def test_complete_flow_separates_ai_delivery_and_local_mapping(
    window: MainWindow,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    start_review(window, tmp_path / "虚构项目方案.docx", qapp)
    resolve_all_review_items(window, qapp)

    assert window.controller.is_review_complete()
    assert window.primary_button.isEnabled()
    assert "全部已确认" in window.pending_summary.text()

    window.primary_button.click()
    qapp.processEvents()
    assert window.current_step == 3
    assert window.primary_button.text() == "生成文件"
    assert window.export_original.toPlainText()
    assert window.export_replacement.toPlainText()

    window.result_root_edit.setText(str(tmp_path))
    window.primary_button.click()
    qapp.processEvents()

    assert window.completed
    assert window.export_stack.currentIndex() == 1
    assert "AI交付" in window.ai_copy_path.text()
    assert "本地保管" in window.mapping_path.text()
    mapping_warning = window.findChild(QLabel, "mappingWarning")
    assert mapping_warning is not None
    assert "严禁上传" in mapping_warning.text()
    assert window.findChild(QLineEdit, "mappingPassword") is None
    assert window.findChild(QLineEdit, "mappingPasswordConfirm") is None

    button_labels = {button.text() for button in window.findChildren(QPushButton)}
    assert all("上传" not in label for label in button_labels)


def test_complete_review_uses_cached_preview_when_entering_export(
    window: MainWindow,
    qapp: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start_review(window, tmp_path / "虚构最终预览.docx", qapp)
    resolve_all_review_items(window, qapp)

    def fail_if_preview_is_rebuilt() -> None:
        raise RuntimeError("preview rebuild should not run during navigation")

    monkeypatch.setattr(window.controller, "preview", fail_if_preview_is_rebuilt)

    window.primary_button.click()
    qapp.processEvents()

    assert window.current_step == 3
    assert window.primary_button.text() == "生成文件"
    assert window.export_original.toPlainText()
    assert window.export_replacement.toPlainText()


def test_image_canvas_draws_multiple_source_pixel_regions(
    window: MainWindow,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    start_review(window, tmp_path / "虚构图片复核.docx", qapp)
    window.review_tabs.setCurrentIndex(1)
    window.image_table.selectRow(0)
    qapp.processEvents()

    canvas = window.image_canvas
    assert canvas.source_size().width() == 640
    assert canvas.source_size().height() == 360
    display = canvas.display_rect()
    assert not display.isEmpty()

    first_start = QPoint(
        round(display.left() + display.width() * 0.25),
        round(display.top() + display.height() * 0.25),
    )
    first_end = QPoint(
        round(display.left() + display.width() * 0.75),
        round(display.top() + display.height() * 0.75),
    )
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=first_start)
    QTest.mouseMove(canvas, first_end)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=first_end)

    second_start = QPoint(
        round(display.left() + display.width() * 0.05),
        round(display.top() + display.height() * 0.1),
    )
    second_end = QPoint(
        round(display.left() + display.width() * 0.2),
        round(display.top() + display.height() * 0.3),
    )
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=second_start)
    QTest.mouseMove(canvas, second_end)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=second_end)
    qapp.processEvents()

    assert window.bundle is not None
    image = window.bundle.images[0]
    assert len(image.regions) == 2
    left, top, right, bottom = image.regions[0]
    assert abs(left - 160) <= 3
    assert abs(top - 90) <= 3
    assert abs(right - 480) <= 3
    assert abs(bottom - 270) <= 3
    assert window.image_table.item(0, 4).text() == "2 个（未启用）"
    assert "preview_png" not in repr(image)
    assert not list(tmp_path.rglob("*.png"))

    window.clear_image_regions_button.click()
    qapp.processEvents()
    assert image.regions == []
    assert canvas.regions() == ()


def test_pixel_redaction_without_boxes_warns_about_whole_image_processing(
    window: MainWindow,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    start_review(window, tmp_path / "虚构整图处理.xlsx", qapp)
    window.review_tabs.setCurrentIndex(1)
    window.image_table.selectRow(0)
    action = cast(QComboBox, window.image_table.cellWidget(0, 3))
    action.setCurrentIndex(2)
    qapp.processEvents()
    window.image_table.selectRow(0)
    qapp.processEvents()

    assert window.image_table.item(0, 4).text() == "0 个（整图处理）"
    assert "未框选区域" in window.image_region_status.text()
    assert "整图处理" in window.image_region_status.text()
    assert "不会原样保留" in window.image_region_status.text()


def test_export_page_has_no_mapping_password_inputs(window: MainWindow) -> None:
    assert window.findChild(QLineEdit, "mappingPassword") is None
    assert window.findChild(QLineEdit, "mappingPasswordConfirm") is None
