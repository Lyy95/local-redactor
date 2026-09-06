from __future__ import annotations

import io
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from PIL import Image, ImageDraw

from local_redactor.history import HistoryEntry
from local_redactor.models import (
    Category,
    DocumentKind,
    ExportArtifacts,
    Finding,
    FindingStatus,
    ImageDisposition,
    Modality,
    ProcessingMode,
    SourceLocation,
    TransformMethod,
)
from local_redactor.rule_library import RuleDefinition

ProgressCallback = Callable[[int, str], None]


@dataclass(slots=True, frozen=True)
class ScanInventoryItem:
    """One non-sensitive summary row shown after the package inventory scan."""

    area: str
    count: int
    status: str
    note: str


@dataclass(slots=True)
class ImageReviewItem:
    """UI-safe description of an image that must receive a human decision."""

    id: str
    title: str
    location: str
    candidates: tuple[str, ...]
    original_summary: str
    processed_summary: str
    preview_png: bytes = field(default=b"", repr=False)
    regions: list[tuple[int, int, int, int]] = field(default_factory=list)
    disposition: ImageDisposition = ImageDisposition.PENDING


@dataclass(slots=True)
class HiddenReviewItem:
    """Hidden content or package object requiring an explicit disposition."""

    id: str
    title: str
    location: str
    kind: str
    description: str
    allowed_actions: tuple[str, ...]
    action: str = "pending"


@dataclass(slots=True, frozen=True)
class PreviewContent:
    original: str
    replacement: str
    preserved_summary: str
    blocks: tuple[dict[str, Any], ...] = ()


@dataclass(slots=True)
class ReviewBundle:
    source_name: str
    document_kind: DocumentKind
    mode: ProcessingMode
    inventory: list[ScanInventoryItem] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    images: list[ImageReviewItem] = field(default_factory=list)
    hidden_items: list[HiddenReviewItem] = field(default_factory=list)
    preview: PreviewContent = field(default_factory=lambda: PreviewContent("", "", ""))
    capability_warnings: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)


class DesktopController(Protocol):
    """Boundary between the Qt layer and local document-processing services."""

    def scan(
        self,
        source_path: Path,
        mode: ProcessingMode,
        progress: ProgressCallback | None = None,
    ) -> ReviewBundle: ...

    def resolve_finding(
        self,
        finding_id: str,
        status: FindingStatus,
        method: TransformMethod,
        ignore_reason: str = "",
        replacement: str = "",
    ) -> Finding: ...

    def resolve_ordinary_findings(self) -> list[Finding]: ...

    def save_fixed_rule(
        self,
        original: str,
        replacement: str,
        category: Category,
    ) -> RuleDefinition: ...

    def apply_rules_incrementally(self) -> int: ...

    def history_entries(self) -> tuple[HistoryEntry, ...]: ...

    def delete_history(self, entry_id: str) -> None: ...

    def clear_history(self) -> None: ...

    def record_failed_task(self, source_path: Path) -> None: ...

    def record_batch_summary(
        self,
        folder_name: str,
        total: int,
        completed: int,
        failed: int,
    ) -> None: ...

    def change_finding_category(
        self,
        finding_id: str,
        category: Category,
    ) -> Finding: ...

    def add_manual_finding(
        self,
        original: str,
        category: Category,
        method: TransformMethod,
    ) -> Finding: ...

    def resolve_image(
        self,
        image_id: str,
        disposition: ImageDisposition,
    ) -> None: ...

    def set_image_regions(
        self,
        image_id: str,
        boxes: Sequence[tuple[int, int, int, int]],
    ) -> None: ...

    def resolve_hidden(self, item_id: str, action: str) -> None: ...

    def is_review_complete(self) -> bool: ...

    def preview(self) -> PreviewContent: ...

    def export(
        self,
        result_root: Path,
        mapping_password: str,
        progress: ProgressCallback | None = None,
    ) -> ExportArtifacts: ...

    def reset(self) -> None: ...


class DemoDesktopController:
    """Offline-only controller with deliberately fictional, in-memory content.

    It exists so the desktop flow can be exercised independently from the
    document engine. It neither reads document contents nor makes network calls.
    """

    def __init__(self) -> None:
        self._bundle: ReviewBundle | None = None
        self._saved_rules: list[RuleDefinition] = []

    def scan(
        self,
        source_path: Path,
        mode: ProcessingMode,
        progress: ProgressCallback | None = None,
    ) -> ReviewBundle:
        suffix = source_path.suffix.lower()
        if suffix not in {".docx", ".xlsx"}:
            raise ValueError("unsupported source")
        if progress is not None:
            progress(12, "正在检查文件结构")
            progress(36, "正在识别文字与表格")
            progress(68, "正在检查图片与二维码")
            progress(88, "正在检查隐藏内容与对象")

        kind = DocumentKind.DOCX if suffix == ".docx" else DocumentKind.XLSX
        findings = self._demo_findings(mode)
        images = [
            ImageReviewItem(
                id="image-001",
                title="图片 1 · 项目现场照片",
                location="正文 / 第 2 张图片",
                candidates=("照片", "人脸候选", "图片文字"),
                original_summary="虚构项目现场照片；发现 2 处人脸候选和 1 处文字区域。",
                processed_summary="可选择局部实心遮挡，或整图移除。",
                preview_png=_demo_preview_png("scene"),
            ),
            ImageReviewItem(
                id="image-002",
                title="图片 2 · 盖章确认页",
                location="附件说明 / 第 1 张图片",
                candidates=("印章候选", "签名候选", "二维码"),
                original_summary="发现红色印章、手写签名和二维码候选。",
                processed_summary="二维码载荷与敏感区域需像素级处理后重新编码。",
                preview_png=_demo_preview_png("document"),
            ),
        ]
        hidden_items = [
            HiddenReviewItem(
                id="hidden-001",
                title="文件作者属性",
                location="文档属性",
                kind="文件属性",
                description="作者和最后修改者会从新文件中移除。",
                allowed_actions=("remove", "visible_note"),
                action="remove",
            ),
            HiddenReviewItem(
                id="hidden-002",
                title="批注与修订记录",
                location="正文 / 修订与批注",
                kind="批注、修订",
                description="原始批注与修订历史不会进入 AI 分析副本。",
                allowed_actions=("remove", "visible_note"),
                action="remove",
            ),
            HiddenReviewItem(
                id="hidden-003",
                title="页眉与超链接",
                location="页眉 / 外部关系",
                kind="页眉页脚、超链接",
                description="可移除，或将必要内容转成不含链接的可见附注。",
                allowed_actions=("remove", "visible_note"),
                action="remove",
            ),
            HiddenReviewItem(
                id="hidden-004",
                title="嵌入对象",
                location="正文 / 对象 1",
                kind="嵌入对象",
                description="嵌入对象不能静默带入副本，必须移除或另作任务处理。",
                allowed_actions=("remove", "separate_task"),
                action="remove",
            ),
        ]
        inventory = [
            ScanInventoryItem("文字与表格", 18, "已识别", "正文、表格与单元格已进入候选复核"),
            ScanInventoryItem(
                "图片与二维码", len(images), "待人工决定", "每张图片必须逐项选择处理方式"
            ),
            ScanInventoryItem(
                "隐藏内容与对象",
                len(hidden_items),
                "待人工决定",
                "属性、批注、关系与对象不会静默带入",
            ),
            ScanInventoryItem("组合识别风险", 1, "需单独确认", "地点、时间、角色与事件共同出现"),
        ]
        self._bundle = ReviewBundle(
            source_name=source_path.name,
            document_kind=kind,
            mode=mode,
            inventory=inventory,
            findings=findings,
            images=images,
            hidden_items=hidden_items,
            preview=self._document_preview(mode),
        )
        if progress is not None:
            progress(100, "自动检查已完成，等待确认")
        return self._bundle

    def resolve_finding(
        self,
        finding_id: str,
        status: FindingStatus,
        method: TransformMethod,
        ignore_reason: str = "",
        replacement: str = "",
    ) -> Finding:
        bundle = self._require_bundle()
        finding = next(item for item in bundle.findings if item.id == finding_id)
        finding.status = status
        finding.suggested_method = method
        finding.ignore_reason = ignore_reason if status is FindingStatus.KEEP_FALSE_POSITIVE else ""
        if status is FindingStatus.REMOVE:
            finding.replacement = "[已移除]"
        elif status is FindingStatus.KEEP_FALSE_POSITIVE:
            finding.replacement = finding.original
        elif replacement.strip():
            finding.replacement = replacement.strip()
        self._refresh_combination_status()
        return finding

    def resolve_ordinary_findings(self) -> list[Finding]:
        """Apply only deterministic, ordinary text suggestions.

        Images and hidden objects live on separate review surfaces.  Text
        findings that are low-confidence, describe a combination risk, or use
        an image/hidden-object category stay pending for a human decision.
        Calling this method again is intentionally a no-op for already
        resolved findings.
        """

        excluded_categories = {
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
        resolved: list[Finding] = []
        for finding in self._require_bundle().findings:
            has_fixed_rule = bool(finding.metadata.get("rule_id"))
            if (
                finding.status is not FindingStatus.PENDING
                or finding.modality not in {Modality.TEXT, Modality.CELL}
                or any(location.image_id is not None for location in finding.locations)
                or (finding.confidence < 0.8 and not has_fixed_rule)
                or finding.category in excluded_categories
            ):
                continue
            finding.status = FindingStatus.TRANSFORM
            finding.ignore_reason = ""
            resolved.append(finding)
        self._refresh_combination_status()
        return resolved

    def save_fixed_rule(
        self,
        original: str,
        replacement: str,
        category: Category,
    ) -> RuleDefinition:
        rule = RuleDefinition.fixed(
            original,
            replacement,
            name=f"{original[:40]} → {replacement[:40]}",
            category=category.value,
        )
        self._saved_rules.append(rule)
        return rule

    def apply_rules_incrementally(self) -> int:
        return 0

    def history_entries(self) -> tuple[HistoryEntry, ...]:
        return ()

    def delete_history(self, entry_id: str) -> None:
        return None

    def clear_history(self) -> None:
        return None

    def record_failed_task(self, source_path: Path) -> None:
        return None

    def record_batch_summary(
        self,
        folder_name: str,
        total: int,
        completed: int,
        failed: int,
    ) -> None:
        return None

    def _refresh_combination_status(self) -> None:
        bundle = self._require_bundle()
        contributors = [
            item for item in bundle.findings if item.category is not Category.COMBINATION_RISK
        ]
        if not contributors or any(item.status is FindingStatus.PENDING for item in contributors):
            return
        for risk in bundle.findings:
            if risk.category is Category.COMBINATION_RISK:
                risk.status = FindingStatus.TRANSFORM
                risk.suggested_method = TransformMethod.GENERALIZE

    def change_finding_category(
        self,
        finding_id: str,
        category: Category,
    ) -> Finding:
        finding = next(item for item in self._require_bundle().findings if item.id == finding_id)
        finding.category = category
        finding.status = FindingStatus.PENDING
        finding.ignore_reason = ""
        return finding

    def add_manual_finding(
        self,
        original: str,
        category: Category,
        method: TransformMethod,
    ) -> Finding:
        bundle = self._require_bundle()
        finding = Finding(
            category=category,
            modality=Modality.TEXT,
            original=original.strip(),
            locations=[
                SourceLocation(
                    part="manual",
                    display="人工补充候选",
                )
            ],
            detector="人工选择",
            confidence=1.0,
            suggested_method=method,
            preserved_semantics="按人工选择的类别和策略处理",
            context="由用户在当前任务中手动补充。",
        )
        bundle.findings.append(finding)
        return finding

    def resolve_image(
        self,
        image_id: str,
        disposition: ImageDisposition,
    ) -> None:
        bundle = self._require_bundle()
        image = next(item for item in bundle.images if item.id == image_id)
        image.disposition = disposition

    def set_image_regions(
        self,
        image_id: str,
        boxes: Sequence[tuple[int, int, int, int]],
    ) -> None:
        bundle = self._require_bundle()
        image = next(item for item in bundle.images if item.id == image_id)
        normalized: list[tuple[int, int, int, int]] = []
        for left, top, right, bottom in boxes:
            if left < 0 or top < 0 or right <= left or bottom <= top:
                raise ValueError("invalid image region")
            normalized.append((left, top, right, bottom))
        image.regions = normalized

    def resolve_hidden(self, item_id: str, action: str) -> None:
        bundle = self._require_bundle()
        item = next(entry for entry in bundle.hidden_items if entry.id == item_id)
        if action != "pending" and action not in item.allowed_actions:
            raise ValueError("invalid hidden-object action")
        item.action = action

    def is_review_complete(self) -> bool:
        if self._bundle is None:
            return False
        findings_done = all(
            item.status is not FindingStatus.PENDING for item in self._bundle.findings
        )
        images_done = all(
            item.disposition is not ImageDisposition.PENDING for item in self._bundle.images
        )
        hidden_done = all(item.action != "pending" for item in self._bundle.hidden_items)
        return findings_done and images_done and hidden_done

    def preview(self) -> PreviewContent:
        return self._require_bundle().preview

    def export(
        self,
        result_root: Path,
        mapping_password: str,
        progress: ProgressCallback | None = None,
    ) -> ExportArtifacts:
        bundle = self._require_bundle()
        if not self.is_review_complete():
            raise ValueError("review incomplete")
        del mapping_password
        if progress is not None:
            progress(20, "正在从空白容器重建 AI 分析副本")
            progress(50, "正在生成本地脱敏映射表")
            progress(76, "正在检查实际导出文件")
            progress(100, "技术检查已完成")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        task_root = result_root / f"脱敏结果_{timestamp}"
        suffix = ".docx" if bundle.document_kind is DocumentKind.DOCX else ".xlsx"
        return ExportArtifacts(
            result_root=task_root,
            ai_copy=task_root / "AI交付" / f"AI分析副本{suffix}",
            encrypted_mapping=task_root / "本地保管" / "脱敏映射表.xlsx",
            report=task_root / "本地保管" / "脱敏检查报告.html",
            hashes={
                "ai_copy": "demo-" + "0" * 59,
                "mapping": "demo-" + "1" * 59,
                "report": "demo-" + "2" * 59,
            },
            warnings=["本界面当前使用虚构数据控制器，未生成真实文件。"],
        )

    def reset(self) -> None:
        self._bundle = None

    def _require_bundle(self) -> ReviewBundle:
        if self._bundle is None:
            raise RuntimeError("no active review")
        return self._bundle

    @staticmethod
    def _document_preview(mode: ProcessingMode) -> PreviewContent:
        original = (
            "2026年7月18日，星澜数据技术有限公司项目负责人林青河在云港区，"
            "与数据治理处沟通“晨星协同系统”试点，预算约128万元。"
        )
        if mode is ProcessingMode.STRICT:
            replacement = (
                "[日期_001]，[机构_001]项目负责人[人员_001]在[区域_001]，"
                "与[部门_001]沟通“[系统_001]”试点，预算为[金额区间_001]。"
            )
        else:
            replacement = (
                "2026年5月9日，远岑科技有限公司项目负责人陈顾问在云川区，"
                "与业务协同处沟通“远航协同平台”试点，预算约100万—150万元。"
            )
        return PreviewContent(
            original=original,
            replacement=replacement,
            preserved_summary="保留负责人角色、单位与部门关系、事件先后和预算数量级。",
        )

    @staticmethod
    def _demo_findings(mode: ProcessingMode) -> list[Finding]:
        replacements = {
            ProcessingMode.BALANCED: {
                Category.NAME: "陈顾问",
                Category.ORGANIZATION: "远岑科技有限公司",
                Category.DEPARTMENT: "业务协同处",
                Category.SYSTEM: "远航协同平台",
                Category.LOCATION: "云川区",
                Category.TIME: "2026年5月9日",
                Category.MONEY: "100万—150万元",
                Category.PHONE: "139-0000-0000（模拟）",
                Category.COMBINATION_RISK: "降低地点和日期精度",
            },
            ProcessingMode.STRICT: {
                Category.NAME: "[人员_001]",
                Category.ORGANIZATION: "[机构_001]",
                Category.DEPARTMENT: "[部门_001]",
                Category.SYSTEM: "[系统_001]",
                Category.LOCATION: "[区域_001]",
                Category.TIME: "[日期_001]",
                Category.MONEY: "[金额区间_001]",
                Category.PHONE: "[电话_001]",
                Category.COMBINATION_RISK: "[组合信息已泛化]",
            },
        }[mode]
        source_values = [
            (Category.NAME, "林青河", "正文 / 第 1 段", TransformMethod.ALIAS),
            (
                Category.ORGANIZATION,
                "星澜数据技术有限公司",
                "正文 / 第 1 段",
                TransformMethod.ALIAS,
            ),
            (Category.DEPARTMENT, "数据治理处", "正文 / 第 1 段", TransformMethod.ALIAS),
            (Category.SYSTEM, "晨星协同系统", "正文 / 第 1 段", TransformMethod.ALIAS),
            (Category.LOCATION, "云港区", "正文 / 第 1 段", TransformMethod.GENERALIZE),
            (Category.TIME, "2026年7月18日", "正文 / 第 1 段", TransformMethod.SHIFT),
            (Category.MONEY, "128万元", "预算表 / B6", TransformMethod.RANGE),
            (Category.PHONE, "138-0000-0000（示例）", "联系人表 / C3", TransformMethod.SIMULATE),
            (
                Category.COMBINATION_RISK,
                "地点 + 日期 + 稀有角色 + 试点事件",
                "正文 / 第 1 段",
                TransformMethod.GENERALIZE,
            ),
        ]
        findings: list[Finding] = []
        for index, (category, value, display, method) in enumerate(source_values, start=1):
            location = SourceLocation(part="demo", display=display)
            findings.append(
                Finding(
                    category=category,
                    modality=Modality.CELL
                    if " / B" in display or " / C" in display
                    else Modality.TEXT,
                    original=value,
                    locations=[location],
                    detector="组合规则"
                    if category is Category.COMBINATION_RISK
                    else "本地规则与实体候选",
                    confidence=0.83 if category is Category.COMBINATION_RISK else 0.96,
                    suggested_method=method,
                    replacement=replacements[category],
                    preserved_semantics=(
                        "保留共同出现关系，降低最少必要字段精度"
                        if category is Category.COMBINATION_RISK
                        else "保留角色、关系和同一性"
                    ),
                    context=f"虚构资料候选 {index}，仅用于界面流程验证。",
                    combination_score=4 if category is Category.COMBINATION_RISK else 0,
                    id=f"finding-{index:03d}",
                )
            )
        return findings


def _demo_preview_png(kind: str) -> bytes:
    """Create a clearly fictional in-memory preview without reading any file."""

    image = Image.new("RGB", (640, 360), color=(232, 238, 240))
    drawer = ImageDraw.Draw(image)
    if kind == "scene":
        drawer.rectangle((0, 230, 640, 360), fill=(118, 148, 128))
        drawer.rectangle((54, 92, 300, 244), fill=(194, 208, 213), outline=(62, 96, 104), width=4)
        drawer.rectangle((318, 120, 588, 244), fill=(210, 219, 222), outline=(62, 96, 104), width=4)
        drawer.ellipse((145, 128, 205, 188), fill=(214, 174, 142), outline=(82, 70, 60), width=3)
        drawer.ellipse((420, 144, 480, 204), fill=(214, 174, 142), outline=(82, 70, 60), width=3)
        drawer.rectangle((118, 260, 516, 306), fill=(255, 255, 255), outline=(23, 107, 98), width=4)
    else:
        drawer.rectangle((78, 36, 562, 330), fill=(255, 255, 255), outline=(122, 132, 139), width=4)
        for y in (86, 118, 150, 182):
            drawer.rectangle((122, y, 388, y + 8), fill=(174, 185, 190))
        drawer.ellipse((384, 190, 508, 314), outline=(183, 35, 29), width=10)
        drawer.line((126, 262, 320, 230, 356, 292), fill=(38, 67, 125), width=6)
        start_x, start_y, unit = 458, 66, 10
        for row in range(9):
            for column in range(9):
                if (row * 3 + column * 5 + row * column) % 4 < 2:
                    x = start_x + column * unit
                    y = start_y + row * unit
                    drawer.rectangle((x, y, x + unit - 1, y + unit - 1), fill=(25, 31, 34))
    output = io.BytesIO()
    image.save(output, format="PNG", compress_level=9)
    return output.getvalue()
