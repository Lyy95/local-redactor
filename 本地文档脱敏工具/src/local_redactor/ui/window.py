from __future__ import annotations

import sys
from functools import partial
from pathlib import Path
from typing import cast

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from local_redactor.models import (
    Category,
    ExportArtifacts,
    Finding,
    FindingStatus,
    ImageDisposition,
    Modality,
    ProcessingMode,
    TransformMethod,
)

from .controller import DesktopController, HiddenReviewItem, ImageReviewItem, ReviewBundle
from .image_canvas import ImageBox, ImageRegionCanvas

PRIMARY = "#176B62"
INFO = "#2563EB"
WARNING = "#B45309"
ERROR = "#B42318"
SUCCESS = "#15803D"
LOGO_FILENAME = "logo-glass-transparent-cropped.png"


def _asset_path(filename: str) -> Path:
    """Resolve assets both from the source tree and a PyInstaller bundle."""

    bundle_root = getattr(sys, "_MEIPASS", None)
    root = Path(bundle_root) if bundle_root else Path(__file__).resolve().parents[3]
    return root / "assets" / filename

CATEGORY_LABELS: dict[Category, str] = {
    Category.NAME: "姓名",
    Category.ID_CARD: "身份证号",
    Category.PHONE: "手机号",
    Category.BANK_CARD: "银行卡号",
    Category.LANDLINE: "固定电话",
    Category.ADDRESS: "地址",
    Category.VEHICLE_PLATE: "车牌",
    Category.ACCOUNT: "账号",
    Category.ORGANIZATION: "单位",
    Category.DEPARTMENT: "部门",
    Category.PROJECT: "项目",
    Category.SYSTEM: "系统名称",
    Category.LOCATION: "地点",
    Category.TIME: "时间",
    Category.MONEY: "金额",
    Category.CASE_ID: "案件编号",
    Category.DEVICE_ID: "设备编号",
    Category.PUBLIC_IP: "公网 IP",
    Category.PRIVATE_IP: "内网地址",
    Category.DOMAIN: "域名",
    Category.EMAIL: "邮箱",
    Category.USERNAME: "用户名",
    Category.SECRET: "密码、密钥或令牌",
    Category.IMAGE_TEXT: "图片文字",
    Category.SEAL: "印章",
    Category.SIGNATURE: "签名",
    Category.QR_CODE: "二维码",
    Category.PHOTO: "照片",
    Category.FILE_PROPERTY: "文件属性",
    Category.REVISION: "修订记录",
    Category.COMMENT: "批注",
    Category.HIDDEN_CONTENT: "隐藏内容",
    Category.HEADER_FOOTER: "页眉页脚",
    Category.WATERMARK: "水印",
    Category.ATTACHMENT: "附件",
    Category.EMBEDDED_OBJECT: "嵌入对象",
    Category.HYPERLINK: "超链接",
    Category.COMBINATION_RISK: "组合识别风险",
    Category.OTHER: "其他",
}

METHOD_LABELS: tuple[tuple[str, TransformMethod], ...] = (
    ("换成统一代号", TransformMethod.ALIAS),
    ("换成虚构值", TransformMethod.SIMULATE),
    ("模糊一些", TransformMethod.GENERALIZE),
    ("显示大致范围", TransformMethod.RANGE),
    ("调整日期但保持先后", TransformMethod.SHIFT),
    ("调整数值但保持大小关系", TransformMethod.SCALE),
    ("遮住敏感区域", TransformMethod.PIXEL_REDACT),
    ("保留成普通文字", TransformMethod.VISIBLE_NOTE),
    ("不放入 AI 文件", TransformMethod.REMOVE),
)

STATUS_LABELS: dict[FindingStatus, str] = {
    FindingStatus.PENDING: "待确认",
    FindingStatus.TRANSFORM: "已采用",
    FindingStatus.KEEP_FALSE_POSITIVE: "已保留原文",
    FindingStatus.REMOVE: "已删除",
}

IMAGE_ACTIONS: tuple[tuple[str, ImageDisposition], ...] = (
    ("请选择（每张图片必选）", ImageDisposition.PENDING),
    ("确认无敏感内容，保留图片", ImageDisposition.KEEP_REENCODED),
    ("遮住敏感区域", ImageDisposition.PIXEL_REDACT),
    ("删除整张图片", ImageDisposition.REMOVE),
)
MANUAL_TEXT_CATEGORIES: tuple[Category, ...] = (
    Category.NAME,
    Category.ID_CARD,
    Category.PHONE,
    Category.BANK_CARD,
    Category.LANDLINE,
    Category.ADDRESS,
    Category.VEHICLE_PLATE,
    Category.ACCOUNT,
    Category.ORGANIZATION,
    Category.DEPARTMENT,
    Category.PROJECT,
    Category.SYSTEM,
    Category.LOCATION,
    Category.TIME,
    Category.MONEY,
    Category.CASE_ID,
    Category.DEVICE_ID,
    Category.PUBLIC_IP,
    Category.PRIVATE_IP,
    Category.DOMAIN,
    Category.EMAIL,
    Category.USERNAME,
    Category.OTHER,
)

class MainWindow(QMainWindow):
    """Single-window, four-step desktop workflow."""

    rule_library_requested = Signal()

    def __init__(self, controller: DesktopController) -> None:
        super().__init__()
        self.controller = controller
        self.source_path: Path | None = None
        self.bundle: ReviewBundle | None = None
        self.artifacts: ExportArtifacts | None = None
        self.current_step = 0
        self.completed = False
        self.source_queue: list[Path] = []
        self.queue_index = -1
        self.queue_status: dict[Path, str] = {}
        self.queue_root: Path | None = None
        self._batch_history_recorded = False
        self._review_action_active = False
        self.step_labels: list[QLabel] = []

        self.setObjectName("mainWindow")
        self.setWindowTitle("本地文档脱敏工具")
        logo_path = _asset_path(LOGO_FILENAME)
        if logo_path.is_file():
            self.setWindowIcon(QIcon(str(logo_path)))
        self.setMinimumSize(1180, 700)
        self.resize(1280, 760)
        self._build_ui()
        self._apply_style()
        self._set_step(0)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("windowRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        layout.addWidget(self._build_header())
        layout.addWidget(self._build_step_bar())

        self.pages = QStackedWidget()
        self.pages.setObjectName("workflowPages")
        self.pages.addWidget(self._build_select_page())
        self.pages.addWidget(self._build_scan_page())
        self.pages.addWidget(self._build_review_page())
        self.pages.addWidget(self._build_export_page())
        layout.addWidget(self.pages, 1)
        layout.addWidget(self._build_footer())
        self.setCentralWidget(root)

    def _build_header(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("headerPanel")
        row = QHBoxLayout(panel)
        row.setContentsMargins(16, 12, 16, 12)

        logo = QLabel()
        logo.setObjectName("appLogo")
        logo.setFixedSize(52, 52)
        logo.setPixmap(
            QPixmap(str(_asset_path(LOGO_FILENAME))).scaled(
                52,
                52,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        row.addWidget(logo)

        title_box = QVBoxLayout()
        title = QLabel("本地文档脱敏")
        title.setObjectName("appTitle")
        title_box.addWidget(title)
        row.addLayout(title_box)
        row.addStretch()

        self.file_badge = QLabel("尚未选择文件")
        self.file_badge.setObjectName("fileBadge")
        self.file_badge.setToolTip("界面只显示文件名，不显示原文件完整路径")
        row.addWidget(self.file_badge)

        self.technical_status = QLabel("● 等待开始")
        self.technical_status.setObjectName("technicalStatus")
        self.technical_status.setVisible(False)

        self.rules_library_button = QPushButton("规则库")
        self.rules_library_button.setObjectName("rulesLibraryButton")
        self.rules_library_button.setToolTip("维护固定替换词和长期判断标准")
        self.rules_library_button.clicked.connect(self.rule_library_requested.emit)
        row.addWidget(self.rules_library_button)

        offline = QLabel("● 本机离线处理")
        offline.setObjectName("offlineBadge")
        offline.setToolTip("本工具不提供上传入口，也不调用云端服务")
        row.addWidget(offline)
        return panel

    def _build_step_bar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("stepPanel")
        row = QHBoxLayout(panel)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(6)
        names = ("选文件", "自动检查", "确认处理", "生成文件")
        for index, name in enumerate(names):
            label = QLabel(f"{index + 1}  {name}")
            label.setObjectName(f"step_{index + 1}")
            label.setProperty("stepState", "upcoming")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setMinimumHeight(34)
            self.step_labels.append(label)
            row.addWidget(label, 1)
            if index < len(names) - 1:
                arrow = QLabel("→")
                arrow.setObjectName("stepArrow")
                row.addWidget(arrow)
        return panel

    def _build_select_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("selectPage")
        outer = QVBoxLayout(page)
        outer.setContentsMargins(100, 32, 100, 24)
        outer.setSpacing(14)
        outer.addStretch()

        heading = QLabel("选择要检查的文件")
        heading.setObjectName("pageTitle")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(heading)

        file_group = QGroupBox()
        file_group.setObjectName("primaryTaskCard")
        file_layout = QVBoxLayout(file_group)
        file_row = QHBoxLayout()
        self.selected_file_name = QLineEdit()
        self.selected_file_name.setObjectName("selectedFileName")
        self.selected_file_name.setReadOnly(True)
        self.selected_file_name.setPlaceholderText("未选择文件")
        self.select_file_button = QPushButton("选择 Word 或 Excel 文件")
        self.select_file_button.setObjectName("selectFileButton")
        self.select_file_button.clicked.connect(self._choose_source_file)
        self.select_folder_button = QPushButton("选择文件夹")
        self.select_folder_button.clicked.connect(self._choose_source_folder)
        file_row.addWidget(self.selected_file_name, 1)
        file_row.addWidget(self.select_file_button)
        file_row.addWidget(self.select_folder_button)
        file_layout.addLayout(file_row)
        folder_row = QHBoxLayout()
        self.include_subfolders_check = QCheckBox("包含子文件夹")
        self.queue_summary = QLabel("当前为单文件处理")
        self.queue_summary.setObjectName("mutedText")
        folder_row.addWidget(self.include_subfolders_check)
        folder_row.addWidget(self.queue_summary, 1)
        file_layout.addLayout(folder_row)
        source_note = QLabel("支持 .docx 和 .xlsx；原文件只读，全部处理都在本机完成。")
        source_note.setObjectName("mutedText")
        file_layout.addWidget(source_note)
        outer.addWidget(file_group)

        self.history_group = QGroupBox("历史处理记录（本机加密）")
        history_layout = QVBoxLayout(self.history_group)
        self.history_table = QTableWidget(0, 5)
        self.history_table.setHorizontalHeaderLabels(("时间", "文件", "格式", "状态", "处理摘要"))
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_table.setMaximumHeight(150)
        history_layout.addWidget(self.history_table)
        history_actions = QHBoxLayout()
        refresh_history = QPushButton("刷新历史")
        refresh_history.clicked.connect(self._refresh_history)
        open_history = QPushButton("打开结果目录")
        open_history.clicked.connect(self._open_history_result)
        delete_history = QPushButton("删除本条")
        delete_history.clicked.connect(self._delete_history_entry)
        clear_history = QPushButton("清空历史")
        clear_history.clicked.connect(self._clear_history)
        for button in (refresh_history, open_history, delete_history, clear_history):
            history_actions.addWidget(button)
        history_actions.addStretch(1)
        history_layout.addLayout(history_actions)
        outer.addWidget(self.history_group)
        self._refresh_history()

        mode_summary = QLabel("处理方式：保留可读性（推荐）")
        mode_summary.setObjectName("modeSummary")
        mode_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(mode_summary)

        self.boundary_check = QCheckBox(
            "我已理解：工具不改变文件密级，是否外发仍按单位制度确认。"
        )
        self.boundary_check.setObjectName("boundaryCheck")
        self.boundary_check.stateChanged.connect(self._update_navigation)
        self.boundary_check.setStyleSheet("font-weight:600;")
        outer.addWidget(self.boundary_check, 0, Qt.AlignmentFlag.AlignCenter)

        self.select_details_button = QPushButton("了解详情与更多设置")
        self.select_details_button.setObjectName("selectDetailsButton")
        self.select_details_button.setCheckable(True)
        outer.addWidget(self.select_details_button, 0, Qt.AlignmentFlag.AlignCenter)

        self.select_details_panel = QFrame()
        self.select_details_panel.setObjectName("detailPanel")
        details_layout = QHBoxLayout(self.select_details_panel)
        details_layout.setContentsMargins(16, 12, 16, 12)
        mode_group = QGroupBox("处理方式")
        mode_layout = QVBoxLayout(mode_group)
        self.mode_buttons = QButtonGroup(self)
        self.balanced_mode = QRadioButton("保留可读性（推荐）")
        self.balanced_mode.setObjectName("balancedMode")
        self.balanced_mode.setChecked(True)
        self.strict_mode = QRadioButton("隐藏更多细节")
        self.strict_mode.setObjectName("strictMode")
        self.mode_buttons.addButton(self.balanced_mode)
        self.mode_buttons.addButton(self.strict_mode)
        mode_layout.addWidget(self.balanced_mode)
        balanced_note = QLabel("用统一代号、虚构值和大致范围保留上下文。")
        balanced_note.setWordWrap(True)
        balanced_note.setObjectName("mutedText")
        mode_layout.addWidget(balanced_note)
        mode_layout.addWidget(self.strict_mode)
        strict_note = QLabel("更多使用类型编号，并模糊日期、地点和金额。")
        strict_note.setWordWrap(True)
        strict_note.setObjectName("mutedText")
        mode_layout.addWidget(strict_note)
        details_layout.addWidget(mode_group, 2)

        coverage = QGroupBox("检查范围")
        grid = QGridLayout(coverage)
        items = (
            ("文字与表格", "身份、单位、地点、时间、金额、网络标识"),
            ("图片与二维码", "文字、印章、签名、二维码和照片；每张必审"),
            ("隐藏内容", "属性、修订、批注、附件、对象和链接"),
            ("组合风险", "多个普通字段组合后可能指向特定对象"),
        )
        for index, (item_heading, copy) in enumerate(items):
            heading_label = QLabel(item_heading)
            heading_label.setObjectName("coverageTitle")
            copy_label = QLabel(copy)
            copy_label.setWordWrap(True)
            copy_label.setObjectName("mutedText")
            grid.addWidget(heading_label, index // 2 * 2, index % 2)
            grid.addWidget(copy_label, index // 2 * 2 + 1, index % 2)
        details_layout.addWidget(coverage, 3)
        self.select_details_panel.setVisible(False)
        self.select_details_button.toggled.connect(self.select_details_panel.setVisible)
        self.select_details_button.toggled.connect(
            lambda expanded: self.select_details_button.setText(
                "收起详情" if expanded else "了解详情与更多设置"
            )
        )
        outer.addWidget(self.select_details_panel)

        outer.addStretch()
        return page

    def _build_scan_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("scanPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(80, 28, 80, 20)
        layout.setSpacing(12)

        heading = QLabel("正在自动检查")
        heading.setObjectName("pageTitle")
        copy = QLabel("文件只在本机读取。检查完成后，你只需要确认有风险的项目。")
        copy.setObjectName("mutedText")
        layout.addWidget(heading)
        layout.addWidget(copy)

        self.scan_progress = QProgressBar()
        self.scan_progress.setObjectName("scanProgress")
        self.scan_progress.setRange(0, 100)
        self.scan_progress.setValue(0)
        layout.addWidget(self.scan_progress)
        self.scan_status = QLabel("等待开始")
        self.scan_status.setObjectName("scanStatus")
        layout.addWidget(self.scan_status)

        stages = QFrame()
        stages.setObjectName("primaryTaskCard")
        stages_layout = QVBoxLayout(stages)
        self.scan_stage_labels: list[QLabel] = []
        for text in (
            "○ 文字与表格",
            "○ 图片与二维码",
            "○ 隐藏内容",
            "○ 组合识别风险",
        ):
            label = QLabel(text)
            label.setObjectName("scanStage")
            self.scan_stage_labels.append(label)
            stages_layout.addWidget(label)
        layout.addWidget(stages)

        self.scan_details_button = QPushButton("查看检查详情")
        self.scan_details_button.setObjectName("scanDetailsButton")
        self.scan_details_button.setCheckable(True)
        layout.addWidget(self.scan_details_button, 0, Qt.AlignmentFlag.AlignLeft)

        self.inventory_table = QTableWidget(0, 4)
        self.inventory_table.setObjectName("inventoryTable")
        self.inventory_table.setHorizontalHeaderLabels(("检查范围", "数量", "状态", "说明"))
        self.inventory_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.inventory_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.inventory_table.verticalHeader().setVisible(False)
        header = self.inventory_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.inventory_table.setVisible(False)
        self.scan_details_button.toggled.connect(self.inventory_table.setVisible)
        self.scan_details_button.toggled.connect(
            lambda expanded: self.scan_details_button.setText(
                "收起检查详情" if expanded else "查看检查详情"
            )
        )
        layout.addWidget(self.inventory_table, 1)

        note = QFrame()
        note.setObjectName("warningCallout")
        note_layout = QHBoxLayout(note)
        note_label = QLabel(
            "图片、低置信度、组合风险和未知对象不会自动跳过，必须由你确认。"
        )
        note_label.setWordWrap(True)
        note_layout.addWidget(note_label)
        layout.addWidget(note)
        return page

    def _build_review_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("reviewPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)

        heading_row = QHBoxLayout()
        heading_box = QVBoxLayout()
        heading = QLabel("确认处理")
        heading.setObjectName("pageTitle")
        subheading = QLabel("普通建议可一次采用；图片和需要判断的项目仍要逐项确认。")
        subheading.setObjectName("mutedText")
        heading_box.addWidget(heading)
        heading_box.addWidget(subheading)
        heading_row.addLayout(heading_box)
        heading_row.addStretch()
        self.resolve_ordinary_button = QPushButton("采用全部普通建议")
        self.resolve_ordinary_button.setObjectName("resolveOrdinaryButton")
        self.resolve_ordinary_button.clicked.connect(self._resolve_ordinary_findings)
        heading_row.addWidget(self.resolve_ordinary_button)
        self.pending_summary = QLabel("待确认：—")
        self.pending_summary.setObjectName("pendingSummary")
        heading_row.addWidget(self.pending_summary)
        layout.addLayout(heading_row)

        self.review_action_feedback = QLabel("")
        self.review_action_feedback.setObjectName("reviewActionFeedback")
        self.review_action_feedback.setWordWrap(True)
        self.review_action_feedback.setVisible(False)
        layout.addWidget(self.review_action_feedback)

        self.review_tabs = QTabWidget()
        self.review_tabs.setObjectName("reviewTabs")
        self.review_tabs.addTab(self._build_text_review_tab(), "文字")
        self.review_tabs.addTab(self._build_image_review_tab(), "图片")
        self.review_tabs.addTab(self._build_hidden_review_tab(), "隐藏内容")
        layout.addWidget(self.review_tabs, 1)
        return page

    def _build_text_review_tab(self) -> QWidget:
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.findings_table = QTableWidget(0, 4)
        self.findings_table.setObjectName("textFindingsTable")
        self.findings_table.setHorizontalHeaderLabels(("待办", "内容", "位置", "状态"))
        self.findings_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.findings_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.findings_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.findings_table.verticalHeader().setVisible(False)
        self.findings_table.verticalHeader().setDefaultSectionSize(42)
        self.findings_table.itemSelectionChanged.connect(self._show_selected_finding)
        finding_header = self.findings_table.horizontalHeader()
        finding_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        finding_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        finding_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        finding_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        splitter.addWidget(self.findings_table)

        detail = QFrame()
        detail.setObjectName("detailPanel")
        detail.setMinimumWidth(410)
        detail_layout = QVBoxLayout(detail)
        self.finding_title = QLabel("选择一项待办")
        self.finding_title.setObjectName("sectionTitle")
        detail_layout.addWidget(self.finding_title)
        self.finding_meta = QLabel("位置和出现次数将在这里显示")
        self.finding_meta.setWordWrap(True)
        self.finding_meta.setObjectName("mutedText")
        detail_layout.addWidget(self.finding_meta)

        preview_row = QHBoxLayout()
        original_group = QGroupBox("当前内容")
        original_layout = QVBoxLayout(original_group)
        self.preview_original = QPlainTextEdit()
        self.preview_original.setObjectName("previewOriginal")
        self.preview_original.setReadOnly(True)
        original_layout.addWidget(self.preview_original)
        replacement_group = QGroupBox("采用建议后")
        replacement_layout = QVBoxLayout(replacement_group)
        self.preview_replacement = QPlainTextEdit()
        self.preview_replacement.setObjectName("previewReplacement")
        self.preview_replacement.setReadOnly(True)
        replacement_layout.addWidget(self.preview_replacement)
        preview_row.addWidget(original_group)
        preview_row.addWidget(replacement_group)
        detail_layout.addLayout(preview_row, 1)

        self.preserved_semantics = QLabel("系统建议：—")
        self.preserved_semantics.setObjectName("preservedSemantics")
        self.preserved_semantics.setWordWrap(True)
        detail_layout.addWidget(self.preserved_semantics)

        self.advanced_edit_panel = QFrame()
        self.advanced_edit_panel.setObjectName("advancedEditPanel")
        edit_grid = QGridLayout(self.advanced_edit_panel)
        edit_grid.addWidget(QLabel("内容类型"), 0, 0)
        self.category_combo = QComboBox()
        self.category_combo.setObjectName("categoryCombo")
        for category in MANUAL_TEXT_CATEGORIES:
            self.category_combo.addItem(CATEGORY_LABELS[category], category)
        edit_grid.addWidget(self.category_combo, 0, 1)
        edit_grid.addWidget(QLabel("怎么处理"), 0, 2)
        self.method_combo = QComboBox()
        self.method_combo.setObjectName("methodCombo")
        for label, method in METHOD_LABELS:
            self.method_combo.addItem(label, method)
        edit_grid.addWidget(self.method_combo, 0, 3)
        edit_grid.addWidget(QLabel("改成"), 1, 0)
        self.replacement_edit = QLineEdit()
        self.replacement_edit.setObjectName("replacementEdit")
        self.replacement_edit.setPlaceholderText("输入希望在 AI 文件中显示的内容")
        edit_grid.addWidget(self.replacement_edit, 1, 1, 1, 2)
        self.manual_finding_button = QPushButton("补充漏检内容")
        self.manual_finding_button.setObjectName("manualFindingButton")
        self.manual_finding_button.clicked.connect(self._add_manual_text_finding)
        edit_grid.addWidget(self.manual_finding_button, 1, 3)
        remember_note = QLabel("确认合适后，可保存成以后自动使用的本机规则。")
        remember_note.setObjectName("mutedText")
        self.remember_rule_button = QPushButton("以后都这样处理")
        self.remember_rule_button.setObjectName("rememberRuleButton")
        self.remember_rule_button.clicked.connect(self._remember_selected_rule)
        edit_grid.addWidget(remember_note, 2, 0, 1, 3)
        edit_grid.addWidget(self.remember_rule_button, 2, 3)
        edit_grid.setColumnStretch(1, 1)
        edit_grid.setColumnStretch(3, 1)
        self.advanced_edit_panel.setVisible(False)
        detail_layout.addWidget(self.advanced_edit_panel)

        actions = QHBoxLayout()
        self.apply_strategy_button = QPushButton("采用建议")
        self.apply_strategy_button.setObjectName("confirmFindingButton")
        self.apply_strategy_button.setProperty("primary", True)
        self.apply_strategy_button.clicked.connect(self._confirm_selected_finding)
        self.modify_finding_button = QPushButton("修改")
        self.modify_finding_button.setObjectName("modifyFindingButton")
        self.modify_finding_button.setCheckable(True)
        self.modify_finding_button.toggled.connect(self._toggle_finding_edit)
        self.ignore_finding_button = QPushButton("保留原文")
        self.ignore_finding_button.setObjectName("ignoreFindingButton")
        self.ignore_finding_button.clicked.connect(self._ask_ignore_selected_finding)
        self.remove_finding_button = QPushButton("删除")
        self.remove_finding_button.setObjectName("removeFindingButton")
        self.remove_finding_button.clicked.connect(self._remove_selected_finding)
        actions.addWidget(self.apply_strategy_button)
        actions.addWidget(self.modify_finding_button)
        actions.addWidget(self.ignore_finding_button)
        actions.addWidget(self.remove_finding_button)
        detail_layout.addLayout(actions)
        splitter.addWidget(detail)
        splitter.setSizes([690, 430])
        layout.addWidget(splitter)
        return tab

    def _build_image_review_tab(self) -> QWidget:
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.image_table = QTableWidget(0, 5)
        self.image_table.setObjectName("imageReviewTable")
        self.image_table.setHorizontalHeaderLabels(
            ("图片", "发现内容", "位置", "你的决定（必选）", "已框选")
        )
        self.image_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.image_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.image_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.image_table.verticalHeader().setVisible(False)
        self.image_table.verticalHeader().setDefaultSectionSize(40)
        self.image_table.itemSelectionChanged.connect(self._show_selected_image)
        image_header = self.image_table.horizontalHeader()
        image_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        image_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        image_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        image_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        image_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        splitter.addWidget(self.image_table)

        detail = QFrame()
        detail.setObjectName("detailPanel")
        detail.setMinimumWidth(450)
        detail_layout = QVBoxLayout(detail)
        self.image_title = QLabel("选择一张图片查看候选")
        self.image_title.setObjectName("sectionTitle")
        detail_layout.addWidget(self.image_title)
        self.image_canvas = ImageRegionCanvas()
        self.image_canvas.regionsChanged.connect(self._on_canvas_regions_changed)
        detail_layout.addWidget(self.image_canvas, 3)

        drawing_help = QLabel("拖动鼠标框住要遮挡的区域；可框选多个位置。")
        drawing_help.setObjectName("mutedText")
        drawing_help.setWordWrap(True)
        detail_layout.addWidget(drawing_help)
        region_row = QHBoxLayout()
        self.image_region_status = QLabel("尚未框选区域")
        self.image_region_status.setObjectName("imageRegionStatus")
        self.image_region_status.setWordWrap(True)
        self.clear_image_regions_button = QPushButton("清空框选")
        self.clear_image_regions_button.setObjectName("clearImageRegionsButton")
        self.clear_image_regions_button.clicked.connect(self._clear_selected_image_regions)
        region_row.addWidget(self.image_region_status, 1)
        region_row.addWidget(self.clear_image_regions_button)
        detail_layout.addLayout(region_row)

        self.image_original = QPlainTextEdit()
        self.image_original.setObjectName("imageOriginalPreview")
        self.image_original.setReadOnly(True)
        self.image_original.setPlaceholderText("原图候选说明")
        self.image_original.setMaximumHeight(64)
        self.image_processed = QPlainTextEdit()
        self.image_processed.setObjectName("imageProcessedPreview")
        self.image_processed.setReadOnly(True)
        self.image_processed.setPlaceholderText("处理后效果说明")
        self.image_processed.setMaximumHeight(64)
        summary_row = QHBoxLayout()
        original_summary = QGroupBox("原图与检测候选")
        original_summary_layout = QVBoxLayout(original_summary)
        original_summary_layout.addWidget(self.image_original)
        processed_summary = QGroupBox("处理后效果")
        processed_summary_layout = QVBoxLayout(processed_summary)
        processed_summary_layout.addWidget(self.image_processed)
        summary_row.addWidget(original_summary)
        summary_row.addWidget(processed_summary)
        detail_layout.addLayout(summary_row)
        image_warning = QLabel(
            "每张图片都要明确决定。选择遮挡后，框选区域会写入新图片，不会只盖一层图形。"
        )
        image_warning.setWordWrap(True)
        image_warning.setObjectName("warningText")
        detail_layout.addWidget(image_warning)
        splitter.addWidget(detail)
        splitter.setSizes([690, 470])
        layout.addWidget(splitter)
        return tab

    def _build_hidden_review_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        copy = QLabel(
            "文件属性、隐藏内容、脚注尾注、附件、外链和嵌入对象已由系统自动清理，"
            "这里只展示处理结果，不再要求逐项确认。"
        )
        copy.setWordWrap(True)
        copy.setObjectName("warningText")
        layout.addWidget(copy)
        self.hidden_table = QTableWidget(0, 5)
        self.hidden_table.setObjectName("hiddenReviewTable")
        self.hidden_table.setHorizontalHeaderLabels(
            ("内容", "类型", "位置", "处理说明", "处理结果")
        )
        self.hidden_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.hidden_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.hidden_table.verticalHeader().setVisible(False)
        self.hidden_table.verticalHeader().setDefaultSectionSize(40)
        hidden_header = self.hidden_table.horizontalHeader()
        hidden_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hidden_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hidden_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hidden_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hidden_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.hidden_table, 1)
        return tab

    def _build_export_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("exportPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 4)
        self.export_stack = QStackedWidget()
        self.export_stack.setObjectName("exportStack")
        self.export_stack.addWidget(self._build_export_setup())
        self.export_stack.addWidget(self._build_completed_panel())
        layout.addWidget(self.export_stack)
        return page

    def _build_export_setup(self) -> QWidget:
        page = QWidget()
        page.setObjectName("exportSetupPanel")
        layout = QVBoxLayout(page)
        heading = QLabel("生成文件")
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)

        compare = QSplitter(Qt.Orientation.Horizontal)
        original_group = QGroupBox("原内容（只在当前界面显示）")
        original_layout = QVBoxLayout(original_group)
        self.export_original = QPlainTextEdit()
        self.export_original.setObjectName("exportOriginal")
        self.export_original.setReadOnly(True)
        original_layout.addWidget(self.export_original)
        compare.addWidget(original_group)
        replacement_group = QGroupBox("AI 分析副本")
        replacement_layout = QVBoxLayout(replacement_group)
        self.export_replacement = QPlainTextEdit()
        self.export_replacement.setObjectName("exportReplacement")
        self.export_replacement.setReadOnly(True)
        replacement_layout.addWidget(self.export_replacement)
        compare.addWidget(replacement_group)
        compare.setSizes([560, 560])
        layout.addWidget(compare, 1)
        self.export_preserved = QLabel("语义保留说明：—")
        self.export_preserved.setObjectName("preservedSemantics")
        self.export_preserved.setWordWrap(True)
        layout.addWidget(self.export_preserved)

        settings = QGroupBox("结果位置与脱敏映射表")
        grid = QGridLayout(settings)
        grid.addWidget(QLabel("结果保存到"), 0, 0)
        self.result_root_edit = QLineEdit()
        self.result_root_edit.setObjectName("resultRootEdit")
        self.result_root_edit.setPlaceholderText("请选择结果目录")
        browse = QPushButton("选择目录")
        browse.setObjectName("browseResultRootButton")
        browse.clicked.connect(self._choose_result_root)
        grid.addWidget(self.result_root_edit, 0, 1)
        grid.addWidget(browse, 0, 2)

        local_mapping_note = QLabel(
            "映射表直接保存在“本地保管”目录，不再要求设置密码。请按敏感文件管理，严禁上传。"
        )
        local_mapping_note.setObjectName("passwordFeedback")
        local_mapping_note.setWordWrap(True)
        grid.addWidget(local_mapping_note, 1, 1, 1, 2)
        layout.addWidget(settings)

        warning = QFrame()
        warning.setObjectName("dangerCallout")
        warning_layout = QVBoxLayout(warning)
        warning_title = QLabel("脱敏映射表含真实原值，严禁上传")
        warning_title.setObjectName("dangerTitle")
        warning_copy = QLabel(
            "工具会自动分成“AI交付”和“本地保管”两个目录。只把 AI 分析副本交给外部 AI；"
            "映射表和检查报告仅用于本机核对及后续还原。"
        )
        warning_copy.setWordWrap(True)
        warning_layout.addWidget(warning_title)
        warning_layout.addWidget(warning_copy)
        layout.addWidget(warning)
        return page

    def _build_completed_panel(self) -> QWidget:
        page = QWidget()
        page.setObjectName("completedPanel")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(14)

        status = QFrame()
        status.setObjectName("successCallout")
        status_layout = QVBoxLayout(status)
        status_title = QLabel("✓ 技术检查已完成")
        status_title.setObjectName("successTitle")
        status_copy = QLabel("仍需按单位制度确认是否可外发。本工具不提供“安全可上传”结论。")
        status_copy.setWordWrap(True)
        status_layout.addWidget(status_title)
        status_layout.addWidget(status_copy)
        layout.addWidget(status)

        cards = QHBoxLayout()
        ai_card = QGroupBox("AI交付")
        ai_card.setObjectName("aiDeliveryCard")
        ai_layout = QVBoxLayout(ai_card)
        ai_title = QLabel("AI分析副本")
        ai_title.setObjectName("sectionTitle")
        self.ai_copy_path = QLabel("—")
        self.ai_copy_path.setObjectName("aiCopyPath")
        self.ai_copy_path.setWordWrap(True)
        ai_copy = QLabel("这是本次拟交给 AI 阅读的文件。请在交付前再次按单位制度核对。")
        ai_copy.setWordWrap(True)
        self.open_ai_folder_button = QPushButton("打开 AI交付 文件夹")
        self.open_ai_folder_button.setObjectName("openAiFolderButton")
        self.open_ai_folder_button.clicked.connect(self._open_ai_folder)
        ai_layout.addWidget(ai_title)
        ai_layout.addWidget(self.ai_copy_path)
        ai_layout.addWidget(ai_copy)
        ai_layout.addStretch()
        ai_layout.addWidget(self.open_ai_folder_button)
        cards.addWidget(ai_card)

        local_card = QGroupBox("本地保管")
        local_card.setObjectName("localCustodyCard")
        local_layout = QVBoxLayout(local_card)
        mapping_title = QLabel("脱敏映射表.xlsx")
        mapping_title.setObjectName("sectionTitle")
        self.mapping_path = QLabel("—")
        self.mapping_path.setObjectName("mappingPath")
        self.mapping_path.setWordWrap(True)
        mapping_warning = QLabel("严禁上传 · 含真实原值 · 密码遗失无法恢复")
        mapping_warning.setObjectName("mappingWarning")
        self.report_path = QLabel("脱敏检查报告.html\n—")
        self.report_path.setObjectName("reportPath")
        self.report_path.setWordWrap(True)
        local_actions = QHBoxLayout()
        self.open_local_folder_button = QPushButton("打开 本地保管 文件夹")
        self.open_local_folder_button.setObjectName("openLocalFolderButton")
        self.open_local_folder_button.clicked.connect(self._open_local_folder)
        self.view_report_button = QPushButton("查看检查报告")
        self.view_report_button.setObjectName("viewReportButton")
        self.view_report_button.clicked.connect(self._open_report)
        local_actions.addWidget(self.open_local_folder_button)
        local_actions.addWidget(self.view_report_button)
        local_layout.addWidget(mapping_title)
        local_layout.addWidget(self.mapping_path)
        local_layout.addWidget(mapping_warning)
        local_layout.addWidget(self.report_path)
        local_layout.addStretch()
        local_layout.addLayout(local_actions)
        cards.addWidget(local_card)
        layout.addLayout(cards, 1)

        separation_note = QLabel(
            "界面没有上传按钮。完成后只会打开本机文件夹，不会连接或跳转到任何 AI 平台。"
        )
        separation_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        separation_note.setObjectName("mutedText")
        layout.addWidget(separation_note)
        return page

    def _build_footer(self) -> QWidget:
        footer = QFrame()
        footer.setObjectName("footerPanel")
        row = QHBoxLayout(footer)
        row.setContentsMargins(12, 10, 12, 10)
        self.back_button = QPushButton("上一步")
        self.back_button.setObjectName("backButton")
        self.back_button.clicked.connect(self._go_back)
        row.addWidget(self.back_button)
        self.footer_hint = QLabel("")
        self.footer_hint.setObjectName("footerHint")
        row.addWidget(self.footer_hint)
        row.addStretch()
        self.primary_button = QPushButton("开始检查")
        self.primary_button.setObjectName("primaryButton")
        self.primary_button.setProperty("primary", True)
        self.primary_button.setMinimumWidth(160)
        self.primary_button.clicked.connect(self._on_primary_action)
        row.addWidget(self.primary_button)
        return footer

    def _apply_style(self) -> None:
        self.setStyleSheet(
            f"""
            QWidget {{
                color: #1F2937;
                font-family: "Microsoft YaHei UI", "Segoe UI";
                font-size: 14px;
            }}
            QWidget#windowRoot {{ background: #F4F6F8; }}
            QFrame#headerPanel, QFrame#stepPanel, QFrame#footerPanel,
            QFrame#detailPanel {{
                background: #FFFFFF;
                border: 1px solid #D7DCE2;
                border-radius: 8px;
            }}
            QFrame#detailPanel {{ border-radius: 6px; }}
            QLabel#appTitle, QLabel#pageTitle {{
                font-size: 20px;
                font-weight: 700;
                color: #14201E;
            }}
            QLabel#appSubtitle, QLabel#mutedText, QLabel#finding_meta {{
                color: #667085;
                font-size: 12px;
            }}
            QLabel#sectionTitle {{ font-size: 16px; font-weight: 700; }}
            QLabel#coverageTitle {{ font-weight: 700; color: {PRIMARY}; }}
            QLabel#offlineBadge {{
                background: #E7F5F1;
                color: {PRIMARY};
                border: 1px solid #A9D8CF;
                border-radius: 15px;
                padding: 6px 10px;
                font-weight: 700;
            }}
            QLabel#fileBadge {{
                background: #F2F4F7;
                border: 1px solid #D7DCE2;
                border-radius: 15px;
                padding: 6px 10px;
            }}
            QLabel#technicalStatus {{
                color: #475467;
                padding: 6px 4px;
            }}
            QLabel[stepState="active"] {{
                background: {PRIMARY};
                color: #FFFFFF;
                border-radius: 6px;
                font-weight: 700;
            }}
            QLabel[stepState="done"] {{
                background: #E7F5F1;
                color: {PRIMARY};
                border-radius: 6px;
                font-weight: 700;
            }}
            QLabel[stepState="upcoming"] {{
                background: #F2F4F7;
                color: #667085;
                border-radius: 6px;
            }}
            QLabel#stepArrow {{ color: #98A2B3; font-size: 18px; }}
            QGroupBox {{
                background: #FFFFFF;
                border: 1px solid #D7DCE2;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: 600;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }}
            QLineEdit, QPlainTextEdit, QComboBox {{
                background: #FFFFFF;
                border: 1px solid #C9D0D8;
                border-radius: 6px;
                padding: 7px;
                selection-background-color: #CDE9E3;
            }}
            QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
                border: 1px solid {PRIMARY};
            }}
            QPushButton {{
                background: #FFFFFF;
                border: 1px solid #B9C1CA;
                border-radius: 6px;
                padding: 8px 14px;
            }}
            QPushButton:hover {{ background: #F2F7F6; border-color: {PRIMARY}; }}
            QPushButton:disabled {{ color: #98A2B3; background: #F2F4F7; }}
            QPushButton[primary="true"] {{
                background: {PRIMARY};
                color: #FFFFFF;
                border-color: {PRIMARY};
                font-weight: 700;
            }}
            QPushButton[primary="true"]:hover {{ background: #12564F; }}
            QPushButton[primary="true"]:disabled {{
                background: #AFC2BF;
                border-color: #AFC2BF;
                color: #F8FAFC;
            }}
            QTableWidget {{
                background: #FFFFFF;
                alternate-background-color: #F8FAFB;
                border: 1px solid #D7DCE2;
                border-radius: 6px;
                gridline-color: #E5E9EE;
            }}
            QTableWidget::item {{ padding: 5px; }}
            QTableWidget::item:selected {{ background: #DDF1EC; color: #14201E; }}
            QHeaderView::section {{
                background: #EEF2F4;
                color: #344054;
                border: none;
                border-right: 1px solid #D7DCE2;
                border-bottom: 1px solid #D7DCE2;
                padding: 7px;
                font-weight: 700;
            }}
            QTabWidget::pane {{
                border: 1px solid #D7DCE2;
                background: #FFFFFF;
                border-radius: 6px;
            }}
            QTabBar::tab {{
                background: #E9EDF1;
                padding: 9px 18px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }}
            QTabBar::tab:selected {{ background: {PRIMARY}; color: #FFFFFF; }}
            QProgressBar {{
                border: 1px solid #D7DCE2;
                border-radius: 6px;
                background: #E9EDF1;
                text-align: center;
            }}
            QProgressBar::chunk {{ background: {INFO}; border-radius: 5px; }}
            QFrame#infoCallout {{
                background: #EEF6FF;
                border: 1px solid #B9D5FA;
                border-left: 4px solid {INFO};
                border-radius: 8px;
            }}
            QFrame#warningCallout {{
                background: #FFF7ED;
                border: 1px solid #F2C99A;
                border-left: 4px solid {WARNING};
                border-radius: 8px;
            }}
            QFrame#dangerCallout {{
                background: #FFF1F0;
                border: 1px solid #F4B4AE;
                border-left: 4px solid {ERROR};
                border-radius: 8px;
            }}
            QFrame#successCallout {{
                background: #ECFDF3;
                border: 1px solid #A9DFC0;
                border-left: 4px solid {SUCCESS};
                border-radius: 8px;
            }}
            QLabel#dangerTitle, QLabel#mappingWarning {{
                color: {ERROR};
                font-weight: 800;
            }}
            QLabel#successTitle {{ color: {SUCCESS}; font-size: 18px; font-weight: 800; }}
            QLabel#warningText {{ color: {WARNING}; }}
            QLabel#pendingSummary {{
                background: #FFF7ED;
                color: {WARNING};
                border: 1px solid #F2C99A;
                border-radius: 14px;
                padding: 6px 10px;
                font-weight: 700;
            }}
            QLabel#preservedSemantics {{
                background: #F0F9F6;
                color: #175D56;
                border-radius: 6px;
                padding: 8px;
            }}
            """
        )

    def set_source_path(self, path: Path) -> None:
        """Set a source without exposing its full path in the interface."""

        self.source_path = path
        self.selected_file_name.setText(path.name)
        self.file_badge.setText(path.name)
        self._update_navigation()

    def apply_rule_library_change(self) -> None:
        """Refresh the current review from cached text without reopening the file."""

        if self.bundle is None:
            return
        try:
            added = self.controller.apply_rules_incrementally()
        except Exception as exc:
            self._show_warning(
                "规则未应用",
                f"新规则与当前任务冲突，已保留原复核结果。\n\n{exc}",
            )
            return
        self._populate_inventory()
        self._populate_review()
        self.refresh_review_state()
        self._set_review_feedback(
            f"✓ 已在当前文字/OCR 缓存中增量应用，新增 {added} 项；"
            "未重新读取文件，未重跑 OCR，原决定已保留。"
        )
        self._update_navigation()

    def _choose_source_file(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "选择 Word 或 Excel 文件",
            "",
            "支持的 Office 文件 (*.docx *.xlsx);;Word 文档 (*.docx);;Excel 工作簿 (*.xlsx)",
        )
        if selected:
            self.source_queue = []
            self.queue_status = {}
            self.queue_index = -1
            self.queue_root = None
            self._batch_history_recorded = False
            self.queue_summary.setText("当前为单文件处理")
            self.set_source_path(Path(selected))

    def _choose_source_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "选择要批量处理的文件夹")
        if not selected:
            return
        root = Path(selected)
        iterator = root.rglob("*") if self.include_subfolders_check.isChecked() else root.glob("*")
        queue = sorted(
            (
                path
                for path in iterator
                if path.is_file()
                and path.suffix.casefold() in {".docx", ".xlsx"}
                and not path.name.startswith(("~$", "."))
                and not any(
                    part.startswith("脱敏结果_") or part in {"AI交付", "本地保管"}
                    for part in path.parts
                )
            ),
            key=lambda path: str(path).casefold(),
        )
        if not queue:
            self._show_warning("未找到可处理文件", "文件夹中没有符合条件的 .docx 或 .xlsx。")
            return
        self.source_queue = queue
        self.queue_index = 0
        self.queue_status = {path: "pending" for path in queue}
        self.queue_root = root
        self._batch_history_recorded = False
        self.set_source_path(queue[0])
        self._refresh_queue_summary()

    def _refresh_queue_summary(self) -> None:
        if not self.source_queue:
            self.queue_summary.setText("当前为单文件处理")
            return
        counts = {status: list(self.queue_status.values()).count(status) for status in {"pending", "completed", "failed"}}
        self.queue_summary.setText(
            f"文件队列 {len(self.source_queue)} 个，当前 {self.queue_index + 1}/{len(self.source_queue)}；"
            f"成功 {counts['completed']}，失败 {counts['failed']}，待处理 {counts['pending']}"
        )

    def _queue_has_next(self) -> bool:
        return bool(self.source_queue) and self.queue_index + 1 < len(self.source_queue)

    def _advance_queue(self) -> None:
        if not self._queue_has_next():
            self.reset_task()
            return
        self.queue_index += 1
        next_path = self.source_queue[self.queue_index]
        self.reset_task(preserve_queue=True)
        self.set_source_path(next_path)
        self.boundary_check.setChecked(True)
        self._refresh_queue_summary()

    def _record_batch_summary_if_finished(self) -> None:
        if not self.source_queue or self._batch_history_recorded or self._queue_has_next():
            return
        counts = {
            status: list(self.queue_status.values()).count(status)
            for status in {"completed", "failed"}
        }
        try:
            self.controller.record_batch_summary(
                self.queue_root.name if self.queue_root is not None else "文件夹批量任务",
                len(self.source_queue),
                counts["completed"],
                counts["failed"],
            )
            self._batch_history_recorded = True
        except Exception:
            self.history_group.setToolTip("批量任务已结束，但本地加密历史暂未写入")

    def _refresh_history(self) -> None:
        try:
            entries = self.controller.history_entries()
        except Exception:
            self.history_table.setRowCount(0)
            self.history_group.setToolTip("本地加密历史暂时无法读取")
            return
        self.history_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            is_batch = entry.document_kind == "batch"
            values = (
                entry.created_at.replace("T", " ")[:19],
                entry.source_name,
                "文件夹" if is_batch else entry.document_kind.upper(),
                ("批次完成" if entry.status == "completed" else "部分失败")
                if is_batch
                else ("已完成" if entry.status == "completed" else "未完成"),
                (f"共 {entry.finding_count} 个，成功 {entry.transformed_count}，失败 {entry.removed_count}")
                if is_batch
                else f"命中 {entry.finding_count}，替换 {entry.transformed_count}，删除 {entry.removed_count}",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, entry.id)
                    item.setData(Qt.ItemDataRole.UserRole + 1, entry.result_path)
                self.history_table.setItem(row, column, item)

    def _selected_history(self) -> tuple[str, str] | None:
        row = self.history_table.currentRow()
        item = self.history_table.item(row, 0) if row >= 0 else None
        if item is None:
            return None
        return str(item.data(Qt.ItemDataRole.UserRole)), str(item.data(Qt.ItemDataRole.UserRole + 1) or "")

    def _open_history_result(self) -> None:
        selected = self._selected_history()
        if selected and selected[1] and Path(selected[1]).is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(selected[1]))

    def _delete_history_entry(self) -> None:
        selected = self._selected_history()
        if selected is None:
            return
        self.controller.delete_history(selected[0])
        self._refresh_history()

    def _clear_history(self) -> None:
        if QMessageBox.question(
            self,
            "清空历史",
            "确定清空本机加密的处理历史吗？已生成的文件不会被删除。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        self.controller.clear_history()
        self._refresh_history()

    def _choose_result_root(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "选择结果保存目录")
        if selected:
            self.result_root_edit.setText(selected)

    def _mode(self) -> ProcessingMode:
        return ProcessingMode.STRICT if self.strict_mode.isChecked() else ProcessingMode.BALANCED

    def _on_primary_action(self) -> None:
        if self.completed:
            if self._queue_has_next():
                self._advance_queue()
            else:
                self.reset_task()
            return
        if self.current_step == 0:
            self._begin_scan()
        elif self.current_step == 1:
            self._set_step(2)
        elif self.current_step == 2:
            if not self.controller.is_review_complete():
                return
            try:
                self._prepare_export()
            except Exception:
                self._show_warning(
                    "无法检查最终效果",
                    "最终效果预览未能准备，请返回复核后重试。",
                )
                return
            self._set_step(3)
        elif self.current_step == 3:
            self._generate_results()

    def _begin_scan(self) -> None:
        if self.source_path is None or not self.boundary_check.isChecked():
            return
        if self.source_path.suffix.lower() not in {".docx", ".xlsx"}:
            self._show_warning(
                "不支持此文件",
                "请选择 .docx 或 .xlsx。旧格式、宏格式和其他文件不会进入识别。",
            )
            return
        self._set_step(1)
        self.technical_status.setText("● 本机检查中")
        self.scan_progress.setValue(0)
        self.scan_status.setText("正在准备只读检查")
        for label, text in zip(
            self.scan_stage_labels,
            ("○ 文字与表格", "○ 图片与二维码", "○ 隐藏内容", "○ 组合识别风险"),
            strict=True,
        ):
            label.setText(text)
        QApplication.processEvents()
        try:
            self.bundle = self.controller.scan(
                self.source_path,
                self._mode(),
                self._on_scan_progress,
            )
        except Exception:
            self.bundle = None
            if self.source_queue and self.source_path is not None:
                self.queue_status[self.source_path] = "failed"
                self._refresh_queue_summary()
            if self.source_path is not None:
                try:
                    self.controller.record_failed_task(self.source_path)
                except Exception:
                    self.history_group.setToolTip("失败任务本地加密历史暂未写入")
            self.technical_status.setText("● 已阻断")
            self.scan_status.setText("文件未进入处理，请检查格式、加密或文件完整性。")
            self.primary_button.setEnabled(False)
            self._show_warning(
                "无法安全处理此文件",
                "文件可能加密、损坏、包含宏或无法安全解析的对象。原文件未被修改。",
            )
            if self._queue_has_next():
                self.completed = True
                self._update_navigation()
            elif self.source_queue:
                self.completed = True
                self._record_batch_summary_if_finished()
                self._refresh_history()
                self._update_navigation()
            return
        self._populate_inventory()
        self._populate_review()
        if self.bundle.blocking_issues:
            self.scan_status.setText("必需的本地识别组件异常，本次任务已阻断，不能生成分析副本。")
            self.technical_status.setText("● 已阻断")
        elif self.bundle.capability_warnings:
            self.scan_status.setText(
                "图片识别能力异常；仍可继续复核，但所有图片只能整图处理或移除。"
            )
            self.technical_status.setText("● 需整图安全处理")
        else:
            count = (
                len(self.bundle.findings)
                + len(self.bundle.images)
                + len(self.bundle.hidden_items)
            )
            self.scan_status.setText(f"已找到 {count} 项需要确认。")
            self.technical_status.setText("● 等待确认")
        self._update_navigation()

    def _on_scan_progress(self, value: int, message: str) -> None:
        self.scan_progress.setValue(value)
        self.scan_status.setText(message)
        thresholds = (36, 68, 88, 100)
        names = ("文字与表格", "图片与二维码", "隐藏内容", "组合识别风险")
        for index, (threshold, name) in enumerate(zip(thresholds, names, strict=True)):
            if value >= threshold:
                prefix = "✓"
            elif index == 0 or value >= thresholds[index - 1]:
                prefix = "●"
            else:
                prefix = "○"
            self.scan_stage_labels[index].setText(f"{prefix} {name}")
        QApplication.processEvents()

    def _populate_inventory(self) -> None:
        if self.bundle is None:
            return
        self.inventory_table.setRowCount(len(self.bundle.inventory))
        for row, item in enumerate(self.bundle.inventory):
            values = (item.area, str(item.count), item.status, item.note)
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column == 1:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.inventory_table.setItem(row, column, cell)
        for index, label in enumerate(self.scan_stage_labels):
            if index < len(self.bundle.inventory):
                item = self.bundle.inventory[index]
                label.setText(f"✓ {item.area}　{item.count} 项")

    def _populate_review(self) -> None:
        if self.bundle is None:
            return
        self._populate_findings(self.bundle.findings)
        self._populate_images(self.bundle.images)
        self._populate_hidden_items(self.bundle.hidden_items)
        self.refresh_review_state()

    def _populate_findings(self, findings: list[Finding]) -> None:
        self.findings_table.setRowCount(len(findings))
        for row, finding in enumerate(findings):
            location = finding.locations[0].display if finding.locations else "未标注位置"
            values = (
                CATEGORY_LABELS.get(finding.category, finding.category.value),
                self._mask_candidate(finding.original),
                location,
                self._finding_status_label(finding),
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, finding.id)
                self.findings_table.setItem(row, column, cell)
        if findings:
            self.findings_table.selectRow(0)

    def _populate_images(self, images: list[ImageReviewItem]) -> None:
        self.image_table.setRowCount(len(images))
        for row, image in enumerate(images):
            title = QTableWidgetItem(image.title)
            title.setData(Qt.ItemDataRole.UserRole, image.id)
            self.image_table.setItem(row, 0, title)
            self.image_table.setItem(row, 1, QTableWidgetItem("、".join(image.candidates)))
            self.image_table.setItem(row, 2, QTableWidgetItem(image.location))
            combo = QComboBox()
            combo.setObjectName(f"imageAction_{image.id}")
            combo.setMinimumHeight(32)
            image_actions = IMAGE_ACTIONS
            if self.bundle is not None and self.bundle.capability_warnings:
                image_actions = tuple(
                    action
                    for action in IMAGE_ACTIONS
                    if action[1] is not ImageDisposition.KEEP_REENCODED
                )
            for label, disposition in image_actions:
                combo.addItem(label, disposition)
            selected = combo.findData(image.disposition)
            combo.setCurrentIndex(max(selected, 0))
            combo.currentIndexChanged.connect(
                partial(self._resolve_image_from_combo, image.id, combo)
            )
            self.image_table.setCellWidget(row, 3, combo)
            self.image_table.setItem(row, 4, QTableWidgetItem(self._image_region_table_text(image)))
        if images:
            self.image_table.selectRow(0)

    def _populate_hidden_items(self, items: list[HiddenReviewItem]) -> None:
        self.hidden_table.setRowCount(len(items))
        for row, item in enumerate(items):
            title = QTableWidgetItem(item.title)
            title.setData(Qt.ItemDataRole.UserRole, item.id)
            self.hidden_table.setItem(row, 0, title)
            self.hidden_table.setItem(row, 1, QTableWidgetItem(item.kind))
            self.hidden_table.setItem(row, 2, QTableWidgetItem(item.location))
            self.hidden_table.setItem(row, 3, QTableWidgetItem(item.description))
            self.hidden_table.setItem(row, 4, QTableWidgetItem("已自动移除"))

    def _show_selected_finding(self) -> None:
        finding = self._selected_finding()
        is_rule = finding is not None and bool(finding.metadata.get("rule_id"))
        is_rule_edit = (
            is_rule
            and finding is not None
            and finding.status is FindingStatus.TRANSFORM
        )
        is_combination = finding is not None and finding.category is Category.COMBINATION_RISK
        editable = (
            finding is not None
            and not is_combination
            and (finding.status is FindingStatus.PENDING or is_rule_edit)
        )
        mandatory = finding is not None and bool(finding.metadata.get("rule_mandatory"))
        self.apply_strategy_button.setEnabled(editable)
        self.modify_finding_button.setEnabled(editable)
        self.ignore_finding_button.setEnabled(
            finding is not None
            and finding.status is FindingStatus.PENDING
            and not is_combination
            and not mandatory
        )
        self.ignore_finding_button.setToolTip(
            "此项命中你的强制规则，必须使用代号或删除" if mandatory else ""
        )
        self.remove_finding_button.setEnabled(editable)
        self.category_combo.setEnabled(editable)
        self.method_combo.setEnabled(editable)
        self.replacement_edit.setEnabled(editable)
        self.remember_rule_button.setEnabled(editable and not is_rule)
        self.remember_rule_button.setText("规则已保存" if is_rule else "以后都这样处理")
        self.apply_strategy_button.setText("保存本次修改" if is_rule_edit else "采用建议")
        if finding is None:
            return
        self.modify_finding_button.setChecked(True)
        category = CATEGORY_LABELS.get(finding.category, finding.category.value)
        locations = tuple(dict.fromkeys(location.display for location in finding.locations))
        location = "；".join(locations) if locations else "未标注位置"
        self.finding_title.setText(category)
        self.finding_meta.setText(
            f"{location}　出现 {finding.occurrence_count} 处"
        )
        context = finding.context.strip()
        if finding.category is Category.COMBINATION_RISK:
            categories = str(finding.metadata.get("categories", "")).replace(
                ",",
                "、",
            )
            recommendations = str(finding.metadata.get("recommended_categories", "")).replace(
                ",", "、"
            )
            context = (
                f"{context}\n贡献字段：{categories or '见关联候选'}"
                f"\n建议优先模糊：{recommendations or '由关联内容决定'}"
                "\n这项不会被“采用全部普通建议”处理，需要你亲自确认。"
            )
        original = finding.original
        replacement = finding.replacement or "等待生成替代值"
        self.preview_original.setPlainText(
            f"{context}\n\n原值：{original}" if context else f"原值：{original}"
        )
        self.preview_replacement.setPlainText(
            f"{context}\n\n替代值：{replacement}" if context else f"替代值：{replacement}"
        )
        self.preserved_semantics.setText(
            (
                "必须替换：命中你的强制规则。"
                if mandatory
                else f"系统建议：{self._method_label(finding.suggested_method)}。"
            )
            + f"{finding.preserved_semantics or '请确认处理结果是否合适。'}"
        )
        category_index = self.category_combo.findData(finding.category)
        if category_index >= 0:
            self.category_combo.setCurrentIndex(category_index)
        method_index = self.method_combo.findData(finding.suggested_method)
        if method_index >= 0:
            self.method_combo.setCurrentIndex(method_index)
        self.replacement_edit.setText(finding.replacement)

    def _show_selected_image(self) -> None:
        image = self._selected_image()
        if image is None:
            return
        self.image_title.setText(f"{image.title} · {image.location}")
        self.image_original.setPlainText(
            f"{image.original_summary}\n\n检测候选：{'、'.join(image.candidates)}"
        )
        self.image_processed.setPlainText(image.processed_summary)
        self.image_canvas.set_preview(image.preview_png, image.regions)
        self._update_image_region_feedback(image)

    def _selected_finding(self) -> Finding | None:
        if self.bundle is None:
            return None
        row = self.findings_table.currentRow()
        if row < 0:
            return None
        cell = self.findings_table.item(row, 0)
        if cell is None:
            return None
        finding_id = cast(str, cell.data(Qt.ItemDataRole.UserRole))
        return next((item for item in self.bundle.findings if item.id == finding_id), None)

    def _selected_image(self) -> ImageReviewItem | None:
        if self.bundle is None:
            return None
        row = self.image_table.currentRow()
        if row < 0:
            return None
        cell = self.image_table.item(row, 0)
        if cell is None:
            return None
        image_id = cast(str, cell.data(Qt.ItemDataRole.UserRole))
        return next((item for item in self.bundle.images if item.id == image_id), None)

    def _toggle_finding_edit(self, expanded: bool) -> None:
        self.advanced_edit_panel.setVisible(expanded)
        self.modify_finding_button.setText("收起修改" if expanded else "修改")

    def _set_review_feedback(self, message: str, *, error: bool = False) -> None:
        self.review_action_feedback.setText(message)
        self.review_action_feedback.setVisible(bool(message))
        color = ERROR if error else SUCCESS
        background = "#FEF3F2" if error else "#ECFDF3"
        border = "#FDA29B" if error else "#A9DFC0"
        self.review_action_feedback.setStyleSheet(
            f"color:{color}; background:{background}; border:1px solid {border};"
            "border-radius:8px; padding:7px 10px; font-weight:600;"
        )

    def _select_next_pending_finding(self, completed_id: str | None = None) -> None:
        if self.bundle is None:
            return
        pending_ids = {
            finding.id
            for finding in self.bundle.findings
            if finding.status is FindingStatus.PENDING
        }
        if not pending_ids:
            return
        start_row = max(self.findings_table.currentRow(), 0)
        row_count = self.findings_table.rowCount()
        for offset in range(1, row_count + 1):
            row = (start_row + offset) % row_count
            cell = self.findings_table.item(row, 0)
            if cell is not None and cell.data(Qt.ItemDataRole.UserRole) in pending_ids:
                self.findings_table.selectRow(row)
                return
        if completed_id is None:
            return

    def _after_finding_action(self, finding: Finding, action: str) -> None:
        self._review_action_active = True
        try:
            self._refresh_finding_row(finding)
            self.refresh_review_state()
            self._set_review_feedback(f"✓ 已{action}，已进入下一项。")
            self._select_next_pending_finding(finding.id)
        finally:
            self._review_action_active = False

    def _resolve_ordinary_findings(self) -> None:
        if self.bundle is None:
            return
        self._review_action_active = True
        try:
            resolved = self.controller.resolve_ordinary_findings()
        except Exception as exc:
            self._set_review_feedback(
                f"未能完成批量处理：{exc or '请逐项处理，或稍后重试。'}",
                error=True,
            )
            return
        finally:
            self._review_action_active = False
        self.refresh_review_state()
        self._select_next_pending_finding()
        if resolved:
            self._set_review_feedback(
                f"✓ 已采用 {len(resolved)} 项普通建议。"
                "图片、低置信度和组合风险仍需逐项确认。"
            )
        else:
            self._set_review_feedback("普通建议已经处理完了，剩余项目需要你逐项确认。")

    def _confirm_selected_finding(self) -> None:
        finding = self._selected_finding()
        if finding is None:
            return
        editable_rule = (
            bool(finding.metadata.get("rule_id"))
            and finding.status is FindingStatus.TRANSFORM
        )
        if finding.status is not FindingStatus.PENDING and not editable_rule:
            self._set_review_feedback("这项已经处理，无需重复操作。")
            return
        method_data = self.method_combo.currentData()
        try:
            method = TransformMethod(str(method_data))
        except ValueError:
            self._set_review_feedback("请选择一种处理方式后再试。", error=True)
            return
        if method is TransformMethod.REMOVE:
            status = FindingStatus.REMOVE
        elif method is TransformMethod.KEEP:
            status = FindingStatus.KEEP_FALSE_POSITIVE
        else:
            status = FindingStatus.TRANSFORM
        category_data = self.category_combo.currentData()
        try:
            selected_category = Category(str(category_data))
        except ValueError:
            self._set_review_feedback("请选择内容类型后再试。", error=True)
            return
        try:
            if selected_category is not finding.category:
                finding = self.controller.change_finding_category(
                    finding.id,
                    selected_category,
                )
            finding = self.controller.resolve_finding(
                finding.id,
                status,
                method,
                ignore_reason="用户选择保留原文" if status is FindingStatus.KEEP_FALSE_POSITIVE else "",
                replacement=self.replacement_edit.text(),
            )
        except Exception as exc:
            self._set_review_feedback(
                f"这项没有处理成功：{exc or '请检查修改内容后重试。'}",
                error=True,
            )
            return
        self._after_finding_action(finding, "采用建议")

    def _remember_selected_rule(self) -> None:
        finding = self._selected_finding()
        if finding is None or finding.category is Category.COMBINATION_RISK:
            return
        replacement = self.replacement_edit.text().strip() or finding.replacement.strip()
        try:
            selected_category = Category(str(self.category_combo.currentData()))
            self.controller.save_fixed_rule(
                finding.original,
                replacement,
                selected_category,
            )
        except Exception as exc:
            self._set_review_feedback(
                f"规则没有保存：{exc or '请检查原词和代号后重试。'}",
                error=True,
            )
            return
        self.apply_rule_library_change()

    def _add_manual_text_finding(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        selected = self.preview_original.textCursor().selectedText().strip()
        if not selected:
            selected, accepted = QInputDialog.getText(
                self,
                "补充文字候选",
                "输入当前文档中需要补充识别的完整文字：",
            )
            if not accepted:
                return
        selected = selected.strip()
        labels = [CATEGORY_LABELS[category] for category in MANUAL_TEXT_CATEGORIES]
        label, accepted = QInputDialog.getItem(
            self,
            "选择候选类别",
            "该文字属于哪一类？",
            labels,
            0,
            False,
        )
        if not accepted:
            return
        category = MANUAL_TEXT_CATEGORIES[labels.index(str(label))]
        try:
            finding = self.controller.add_manual_finding(
                selected,
                category,
                self._default_method_for_category(category),
            )
        except ValueError as exc:
            self._show_warning("无法补充候选", str(exc))
            return
        if self.bundle is None:
            return
        self._populate_findings(self.bundle.findings)
        for row in range(self.findings_table.rowCount()):
            item = self.findings_table.item(row, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == finding.id:
                self.findings_table.selectRow(row)
                break
        self.refresh_review_state()

    def _ask_ignore_selected_finding(self) -> None:
        reasons = ("误报", "公开信息", "分析必需且经确认", "其他")
        from PySide6.QtWidgets import QInputDialog

        reason, accepted = QInputDialog.getItem(
            self,
            "说明保留原因",
            "保留原文会让该内容出现在 AI 文件中，请选择原因：",
            reasons,
            0,
            False,
        )
        if accepted and reason:
            self.ignore_selected_finding(str(reason))

    def ignore_selected_finding(self, reason: str) -> None:
        """Resolve the selected finding as ignored with an explicit reason."""

        finding = self._selected_finding()
        if finding is None or not reason.strip():
            return
        if finding.status is not FindingStatus.PENDING:
            self._set_review_feedback("这项已经处理，无需重复操作。")
            return
        try:
            finding = self.controller.resolve_finding(
                finding.id,
                FindingStatus.KEEP_FALSE_POSITIVE,
                TransformMethod.KEEP,
                reason.strip(),
            )
        except Exception as exc:
            self._set_review_feedback(
                f"原文未能保留：{exc or '此项可能命中必须处理的规则，请改用代号或删除。'}",
                error=True,
            )
            return
        self._after_finding_action(finding, "保留原文")

    def _remove_selected_finding(self) -> None:
        finding = self._selected_finding()
        if finding is None:
            return
        editable_rule = (
            bool(finding.metadata.get("rule_id"))
            and finding.status is FindingStatus.TRANSFORM
        )
        if finding.status is not FindingStatus.PENDING and not editable_rule:
            self._set_review_feedback("这项已经处理，无需重复操作。")
            return
        try:
            finding = self.controller.resolve_finding(
                finding.id,
                FindingStatus.REMOVE,
                TransformMethod.REMOVE,
            )
        except Exception as exc:
            self._set_review_feedback(
                f"这项没有删除成功：{exc or '请稍后重试。'}",
                error=True,
            )
            return
        self._after_finding_action(finding, "从 AI 文件删除")

    def _refresh_finding_row(self, finding: Finding) -> None:
        for row in range(self.findings_table.rowCount()):
            cell = self.findings_table.item(row, 0)
            if cell is not None and cell.data(Qt.ItemDataRole.UserRole) == finding.id:
                method_cell = self.findings_table.item(row, 2)
                status_cell = self.findings_table.item(row, 3)
                cell.setText(CATEGORY_LABELS.get(finding.category, finding.category.value))
                if method_cell is not None:
                    location = finding.locations[0].display if finding.locations else "未标注位置"
                    method_cell.setText(location)
                if status_cell is not None:
                    status_cell.setText(self._finding_status_label(finding))
                break

    @staticmethod
    def _default_method_for_category(category: Category) -> TransformMethod:
        if category in {
            Category.NAME,
            Category.ORGANIZATION,
            Category.DEPARTMENT,
            Category.PROJECT,
            Category.SYSTEM,
        }:
            return TransformMethod.ALIAS
        if category in {
            Category.ADDRESS,
            Category.LOCATION,
            Category.DOMAIN,
            Category.EMAIL,
        }:
            return TransformMethod.GENERALIZE
        if category is Category.TIME:
            return TransformMethod.SHIFT
        if category is Category.MONEY:
            return TransformMethod.RANGE
        return TransformMethod.SIMULATE

    def _resolve_image_from_combo(
        self,
        image_id: str,
        combo: QComboBox,
        _index: int,
    ) -> None:
        try:
            disposition = ImageDisposition(str(combo.currentData()))
        except ValueError:
            self._set_review_feedback("请选择图片处理方式。", error=True)
            return
        image = None
        if self.bundle is not None:
            image = next((item for item in self.bundle.images if item.id == image_id), None)
        if image is None:
            return
        if image.disposition is disposition:
            return
        try:
            self.controller.resolve_image(image_id, disposition)
        except Exception as exc:
            self._set_review_feedback(
                f"图片决定未保存：{exc or '请重新选择。'}",
                error=True,
            )
            return
        image.disposition = disposition
        self._refresh_image_region_cell(image_id)
        selected = self._selected_image()
        if selected is not None and selected.id == image_id:
            self._update_image_region_feedback(selected)
        self.refresh_review_state()
        if disposition is not ImageDisposition.PENDING:
            self._set_review_feedback("✓ 图片已确认，已进入下一张。")
            self._select_next_pending_image()

    def _on_canvas_regions_changed(self, boxes_object: object) -> None:
        image = self._selected_image()
        if image is None:
            return
        boxes = tuple(
            tuple(int(coordinate) for coordinate in box)
            for box in cast(tuple[ImageBox, ...], boxes_object)
        )
        typed_boxes = cast(tuple[ImageBox, ...], boxes)
        self.controller.set_image_regions(image.id, typed_boxes)
        image.regions = list(typed_boxes)
        self._refresh_image_region_cell(image.id)
        self._update_image_region_feedback(image)

    def _clear_selected_image_regions(self) -> None:
        image = self._selected_image()
        if image is None:
            return
        if self.image_canvas.regions():
            self.image_canvas.clear_regions()
            return
        self.controller.set_image_regions(image.id, ())
        image.regions.clear()
        self._refresh_image_region_cell(image.id)
        self._update_image_region_feedback(image)

    def _refresh_image_region_cell(self, image_id: str) -> None:
        if self.bundle is None:
            return
        image = next((item for item in self.bundle.images if item.id == image_id), None)
        if image is None:
            return
        for row in range(self.image_table.rowCount()):
            cell = self.image_table.item(row, 0)
            if cell is not None and cell.data(Qt.ItemDataRole.UserRole) == image_id:
                region_cell = self.image_table.item(row, 4)
                if region_cell is not None:
                    region_cell.setText(self._image_region_table_text(image))
                break

    def _update_image_region_feedback(self, image: ImageReviewItem) -> None:
        count = len(image.regions)
        self.clear_image_regions_button.setEnabled(count > 0)
        if not image.preview_png:
            text = "图片预览不可用。请整图移除，或返回检查图片解析状态。"
            color = ERROR
        elif image.disposition is ImageDisposition.PIXEL_REDACT and count == 0:
            text = "未框选区域；按当前决定导出时将整图处理，不会原样保留。"
            color = WARNING
        elif image.disposition is ImageDisposition.PIXEL_REDACT:
            text = f"已框选 {count} 个区域；导出时将实心改写这些像素并重新编码图片。"
            color = SUCCESS
        elif count:
            text = f"已框选 {count} 个区域；选择“局部实心遮挡”后这些框选才会生效。"
            color = INFO
        else:
            text = "尚未框选区域。你可以拖动框选，或直接选择整图移除。"
            color = "#667085"
        self.image_region_status.setText(text)
        self.image_region_status.setStyleSheet(f"color:{color};")

    @staticmethod
    def _image_region_table_text(image: ImageReviewItem) -> str:
        count = len(image.regions)
        if image.disposition is ImageDisposition.PIXEL_REDACT:
            return f"{count} 个" if count else "0 个（整图处理）"
        if count:
            return f"{count} 个（未启用）"
        return "—"

    def _select_next_pending_image(self) -> None:
        if self.bundle is None:
            return
        pending = {
            item.id
            for item in self.bundle.images
            if item.disposition is ImageDisposition.PENDING
        }
        for row in range(self.image_table.rowCount()):
            cell = self.image_table.item(row, 0)
            if cell is not None and cell.data(Qt.ItemDataRole.UserRole) in pending:
                self.image_table.selectRow(row)
                return

    def refresh_review_state(self) -> None:
        if self.bundle is None:
            self.pending_summary.setText("待确认：—")
            self.resolve_ordinary_button.setEnabled(False)
            self._update_navigation()
            return
        for finding in self.bundle.findings:
            self._refresh_finding_row(finding)
        text_pending = sum(item.status is FindingStatus.PENDING for item in self.bundle.findings)
        image_pending = sum(
            item.disposition is ImageDisposition.PENDING for item in self.bundle.images
        )
        hidden_pending = sum(item.action == "pending" for item in self.bundle.hidden_items)
        total_pending = text_pending + image_pending + hidden_pending
        self.pending_summary.setText(
            f"待确认 {total_pending} 项"
        )
        self.review_tabs.setTabText(0, f"文字 {text_pending}")
        self.review_tabs.setTabText(1, f"图片 {image_pending}")
        self.review_tabs.setTabText(2, f"隐藏内容 {hidden_pending}")
        self.resolve_ordinary_button.setEnabled(
            any(self._is_ordinary_finding(item) for item in self.bundle.findings)
        )
        if total_pending == 0:
            self.pending_summary.setText("✓ 全部已确认")
            self.pending_summary.setStyleSheet(
                f"color:{SUCCESS}; background:#ECFDF3; border:1px solid #A9DFC0;"
                "border-radius:14px; padding:6px 10px; font-weight:700;"
            )
        else:
            self.pending_summary.setStyleSheet("")
        self._update_navigation()

    @staticmethod
    def _is_ordinary_finding(finding: Finding) -> bool:
        review_only = {
            Category.IMAGE_TEXT,
            Category.SEAL,
            Category.SIGNATURE,
            Category.QR_CODE,
            Category.PHOTO,
            Category.FILE_PROPERTY,
            Category.REVISION,
            Category.COMMENT,
            Category.HIDDEN_CONTENT,
            Category.HEADER_FOOTER,
            Category.WATERMARK,
            Category.ATTACHMENT,
            Category.EMBEDDED_OBJECT,
            Category.HYPERLINK,
            Category.COMBINATION_RISK,
        }
        return (
            finding.status is FindingStatus.PENDING
            and finding.modality in {Modality.TEXT, Modality.CELL}
            and not any(location.image_id is not None for location in finding.locations)
            and (finding.confidence >= 0.8 or bool(finding.metadata.get("rule_id")))
            and finding.category not in review_only
        )

    def _prepare_export(self) -> None:
        if self.bundle is None:
            raise RuntimeError("当前没有可供检查的任务")
        # The production controller refreshes this preview whenever a text
        # decision changes.  Rebuilding it again while changing steps can
        # raise inside a Qt slot and leave the enabled button looking inert.
        preview = self.bundle.preview
        self.export_original.setPlainText(preview.original)
        self.export_replacement.setPlainText(preview.replacement)
        self.export_preserved.setText(f"语义保留说明：{preview.preserved_summary}")
        if not self.result_root_edit.text().strip():
            self.result_root_edit.setText(str(Path.home() / "Documents"))

    def _generate_results(self) -> None:
        result_root = self.result_root_edit.text().strip()
        if not result_root:
            self._show_warning("请选择结果目录", "需要先选择本机结果保存目录。")
            return
        self.primary_button.setEnabled(False)
        self.back_button.setEnabled(False)
        self.technical_status.setText("● 正在生成并复扫")
        QApplication.processEvents()
        try:
            artifacts = self.controller.export(
                Path(result_root),
                "",
                self._on_export_progress,
            )
        except Exception as exc:
            self.technical_status.setText("● 技术检查失败")
            if self.source_queue and self.source_path is not None:
                self.queue_status[self.source_path] = "failed"
                self._refresh_queue_summary()
            self.primary_button.setEnabled(True)
            self.back_button.setEnabled(True)
            self._show_warning(
                "结果未完成",
                f"生成或复扫未通过：{str(exc).strip() or '请返回复核后重试。'}",
            )
            self._refresh_history()
            if self.source_queue:
                self.completed = True
                self._record_batch_summary_if_finished()
                self._refresh_history()
                self._update_navigation()
            return
        self._show_completed(artifacts)

    def _on_export_progress(self, _value: int, message: str) -> None:
        self.footer_hint.setText(message)
        QApplication.processEvents()

    def _show_completed(self, artifacts: ExportArtifacts) -> None:
        self.artifacts = artifacts
        self.ai_copy_path.setText(f"AI交付 / {artifacts.ai_copy.name}")
        self.mapping_path.setText(f"本地保管 / {artifacts.encrypted_mapping.name}")
        self.report_path.setText(f"本地保管 / {artifacts.report.name}")
        self.export_stack.setCurrentIndex(1)
        self.completed = True
        if self.source_queue and self.source_path is not None:
            self.queue_status[self.source_path] = "completed"
            self._refresh_queue_summary()
            self._record_batch_summary_if_finished()
        self._refresh_history()
        self.technical_status.setText("● 技术检查已完成")
        self.footer_hint.setText("原文件未修改；映射表严禁上传。")
        self._update_navigation()

    def _go_back(self) -> None:
        if self.completed or self.current_step == 0:
            return
        self._set_step(self.current_step - 1)

    def _set_step(self, index: int) -> None:
        if self._review_action_active and index < self.current_step:
            return
        self.current_step = max(0, min(index, 3))
        self.pages.setCurrentIndex(self.current_step)
        for step_index, label in enumerate(self.step_labels):
            state = (
                "active"
                if step_index == self.current_step
                else "done"
                if step_index < self.current_step
                else "upcoming"
            )
            label.setProperty("stepState", state)
            label.style().unpolish(label)
            label.style().polish(label)
        self._update_navigation()

    def _update_navigation(self) -> None:
        self.back_button.setVisible(self.current_step > 0 and not self.completed)
        self.back_button.setEnabled(self.current_step > 0 and not self.completed)
        if self.completed:
            self.primary_button.setText("处理下一个文件" if self._queue_has_next() else "开始新任务")
            self.primary_button.setEnabled(True)
            return
        if self.current_step == 0:
            self.primary_button.setText("开始检查")
            self.primary_button.setEnabled(
                self.source_path is not None and self.boundary_check.isChecked()
            )
            self.footer_hint.setText("所有处理均在本机完成，不提供上传入口。")
        elif self.current_step == 1:
            self.primary_button.setText("开始确认")
            blocked = self.bundle is not None and bool(self.bundle.blocking_issues)
            self.primary_button.setEnabled(self.bundle is not None and not blocked)
            self.footer_hint.setText(
                "本地识别组件异常，本次任务不能继续。"
                if blocked
                else "检查详情默认收起；下一步只确认需要处理的项目。"
            )
        elif self.current_step == 2:
            self.primary_button.setText("检查最终效果")
            complete = self.bundle is not None and self.controller.is_review_complete()
            self.primary_button.setEnabled(complete)
            if self.bundle is not None and self.bundle.blocking_issues:
                self.footer_hint.setText("本地识别组件异常，本次任务已阻断。")
            elif self.bundle is not None and self.bundle.capability_warnings and not complete:
                self.footer_hint.setText("图片检查异常：每张图片都要选择遮挡或删除整图。")
            else:
                self.footer_hint.setText(
                    "全部项目已确认，可以检查最终效果。"
                    if complete
                    else "文字和图片都确认后才能生成文件。"
                )
        else:
            complete = self.bundle is not None and self.controller.is_review_complete()
            if complete:
                self.primary_button.setText("生成文件")
                self.primary_button.setEnabled(True)
                self.footer_hint.setText("映射表只放在本地保管目录，严禁上传。")
            else:
                self.primary_button.setText("生成文件")
                self.primary_button.setEnabled(False)
                self.footer_hint.setText(
                    "仍有未处理项，请返回补充处理后再生成文件。"
                )

    def reset_task(self, *, preserve_queue: bool = False) -> None:
        self.controller.reset()
        self.source_path = None
        self.bundle = None
        self.artifacts = None
        self.completed = False
        if not preserve_queue:
            self.source_queue = []
            self.queue_index = -1
            self.queue_status = {}
            self.queue_root = None
            self._batch_history_recorded = False
        self.selected_file_name.clear()
        self.file_badge.setText("尚未选择文件")
        self.technical_status.setText("● 等待开始")
        self.boundary_check.setChecked(False)
        self.balanced_mode.setChecked(True)
        self.select_details_button.setChecked(False)
        self.scan_details_button.setChecked(False)
        self.scan_progress.setValue(0)
        self.scan_status.setText("等待开始")
        for label, text in zip(
            self.scan_stage_labels,
            ("○ 文字与表格", "○ 图片与二维码", "○ 隐藏内容", "○ 组合识别风险"),
            strict=True,
        ):
            label.setText(text)
        self.inventory_table.setRowCount(0)
        self.findings_table.setRowCount(0)
        self.image_table.setRowCount(0)
        self.hidden_table.setRowCount(0)
        self.preview_original.clear()
        self.preview_replacement.clear()
        self.export_original.clear()
        self.export_replacement.clear()
        self.result_root_edit.clear()
        self.modify_finding_button.setChecked(False)
        self.review_action_feedback.clear()
        self.review_action_feedback.setVisible(False)
        self.export_stack.setCurrentIndex(0)
        self._refresh_queue_summary()
        self._set_step(0)

    def _open_ai_folder(self) -> None:
        if self.artifacts is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.artifacts.ai_copy.parent)))

    def _open_local_folder(self) -> None:
        if self.artifacts is not None:
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(self.artifacts.encrypted_mapping.parent))
            )

    def _open_report(self) -> None:
        if self.artifacts is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.artifacts.report)))

    def _show_warning(self, title: str, message: str) -> None:
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle(title)
        dialog.setText(title)
        dialog.setInformativeText(message)
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.exec()

    @staticmethod
    def _finding_status_label(finding: Finding) -> str:
        if finding.metadata.get("rule_id") and finding.status is FindingStatus.TRANSFORM:
            return "已按规则处理"
        return STATUS_LABELS[finding.status]

    @staticmethod
    def _method_label(method: TransformMethod) -> str:
        return next((label for label, value in METHOD_LABELS if value is method), method.value)

    @staticmethod
    def _mask_candidate(value: str) -> str:
        if len(value) <= 1:
            return "＊"
        if len(value) == 2:
            return value[0] + "＊"
        if len(value) <= 4:
            return value[0] + "＊" * (len(value) - 2) + value[-1]
        return value[:2] + "…" + value[-2:]
