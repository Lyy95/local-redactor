from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from .core import (
    CombinationRiskScorer,
    CompositeFindingDetector,
    SemanticTransformationEngine,
)
from .core.common import (
    clone_location,
    contains_normalized_original,
    merge_findings,
    modality_for_block,
    normalize_entity,
)
from .history import HistoryEntry, HistoryStore, HistoryStoreProtocol, new_history_id
from .models import (
    Category,
    DocumentModel,
    ExportArtifacts,
    Finding,
    FindingStatus,
    ImageDisposition,
    ImageRegion,
    MappingEntry,
    Modality,
    ObjectDisposition,
    PackageItem,
    ProcessingMode,
    SourceLocation,
    TransformMethod,
)
from .office import DocxAdapter, XlsxAdapter
from .office.common import apply_findings_to_text
from .office.security import sha256_file
from .rule_library import (
    ActionKind,
    RuleConflictError,
    RuleDefinition,
    RuleLibrary,
    RuleLibraryError,
    RuleMatch,
    RuleSession,
    RuleStore,
    default_rule_store_path,
)
from .runtime import create_local_image_analyzer
from .ui.controller import (
    HiddenReviewItem,
    ImageReviewItem,
    PreviewContent,
    ProgressCallback,
    ReviewBundle,
    ScanInventoryItem,
)

_CATEGORY_LABELS: dict[Category, str] = {
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
    Category.SEAL: "印章候选",
    Category.SIGNATURE: "签名候选",
    Category.QR_CODE: "二维码",
    Category.PHOTO: "人脸/照片候选",
    Category.COMBINATION_RISK: "组合识别风险",
}

_OBJECT_LABELS = {
    "embedded_object": "嵌入对象",
    "custom_xml": "自定义数据",
    "comment": "批注",
    "footnote": "脚注",
    "endnote": "尾注",
    "header": "页眉",
    "footer": "页脚",
    "external_link": "外部链接",
    "data_connection": "数据连接",
    "pivot_cache": "数据透视缓存",
    "chart": "图表",
    "binary": "未知二进制对象",
}

_BLOCKING_RECOGNITION_CODES = {
    "NER_MODEL_UNAVAILABLE",
    "NER_PIPELINE_FAILED",
    "NER_RULER_UNAVAILABLE",
}
_IMAGE_DEGRADED_PREFIX = "IMAGE_"


class LocalDesktopController:
    """Real, offline controller for one in-memory redaction task."""

    def __init__(
        self,
        *,
        detector: Any | None = None,
        transformer: SemanticTransformationEngine | None = None,
        image_analyzer_factory: Callable[[], Any] | None = None,
        artifact_writer: Any | None = None,
        rule_store: Any | None = None,
        history_store: HistoryStoreProtocol | None = None,
    ) -> None:
        self._detector = detector or CompositeFindingDetector.default(
            combination_scorer=CombinationRiskScorer()
        )
        self._transformer = transformer or SemanticTransformationEngine()
        self._image_analyzer_factory = image_analyzer_factory or create_local_image_analyzer
        self._artifact_writer = artifact_writer
        self._rule_store = rule_store or RuleStore(include_presets=True)
        self._history_store = history_store or HistoryStore()
        self._rule_snapshot = RuleLibrary()
        self._rule_session = RuleSession(self._rule_snapshot)
        self._document: DocumentModel | None = None
        self._adapter: Any | None = None
        self._mode: ProcessingMode | None = None
        self._bundle: ReviewBundle | None = None
        self._hidden_items: dict[str, PackageItem] = {}
        self._image_region_overrides: dict[
            str,
            list[tuple[int, int, int, int]],
        ] = {}
        self._cached_image_findings: list[Finding] = []

    def scan(
        self,
        source_path: Path,
        mode: ProcessingMode,
        progress: ProgressCallback | None = None,
    ) -> ReviewBundle:
        self.reset()
        try:
            self._rule_snapshot = self._rule_store.load()
        except RuleLibraryError as exc:
            raise ValueError(
                "本地规则库无法安全读取。请先修复或恢复规则库，再重新检查文档。"
            ) from exc
        self._rule_session = RuleSession(self._rule_snapshot)
        path = Path(source_path)
        adapter = self._adapter_for(path)
        self._progress(progress, 8, "正在只读检查 Office 文件结构")
        document = adapter.scan(path)
        self._progress(progress, 34, "正在本机识别文字、表格与组合风险")
        detected_findings = self._detector.detect(document)
        time_finding_ids = {
            finding.id for finding in detected_findings if finding.category is Category.TIME
        }
        findings = [
            finding
            for finding in detected_findings
            if finding.category is not Category.TIME
            and finding.modality not in {Modality.METADATA, Modality.HIDDEN}
            and not (
                finding.category is Category.COMBINATION_RISK
                and time_finding_ids.intersection(
                    str(item) for item in finding.metadata.get("contributor_ids", ())
                )
            )
        ]
        for finding in findings:
            if finding.category is Category.SECRET:
                finding.status = FindingStatus.REMOVE
                finding.suggested_method = TransformMethod.REMOVE
                finding.replacement = ""
                finding.metadata["auto_handled"] = "secret"
        try:
            findings = self._apply_text_rules(document, findings)
        except RuleLibraryError as exc:
            raise ValueError(
                "本地规则在当前文档中产生冲突。请先调整冲突规则，再重新检查。"
            ) from exc
        self._progress(progress, 62, "正在本机识别图片文字、二维码和视觉候选")
        image_result = self._image_analyzer_factory().analyze(document)
        self._cached_image_findings = [
            replace(
                finding,
                locations=list(finding.locations),
                metadata=dict(finding.metadata),
            )
            for finding in image_result.findings
        ]
        for warning in image_result.warnings:
            if warning not in document.warnings:
                document.warnings.append(warning)
        try:
            image_findings = [
                finding
                for finding in self._apply_image_rules(self._cached_image_findings)
                if finding.category is not Category.TIME and self._keep_image_finding(finding)
            ]
        except RuleLibraryError as exc:
            raise ValueError(
                "本地规则在图片文字中产生冲突。请先调整冲突规则，再重新检查。"
            ) from exc
        findings = merge_findings([*findings, *image_findings])
        prepared, _ = self._prepare_findings(document, findings, mode)
        self._seed_image_regions(document, prepared)
        self._auto_keep_clean_images(document, prepared)
        self._progress(progress, 84, "正在整理隐藏内容与文件对象")
        capability_warnings = self._capability_warnings(document.warnings)
        blocking_issues = [
            warning
            for warning in capability_warnings
            if self._warning_code(warning) in _BLOCKING_RECOGNITION_CODES
        ]

        bundle = ReviewBundle(
            source_name=document.display_name,
            document_kind=document.kind,
            mode=mode,
            inventory=self._inventory_rows(
                document,
                prepared,
                capability_warnings=capability_warnings,
                blocking_issues=blocking_issues,
            ),
            findings=prepared,
            images=self._image_rows(document, prepared),
            hidden_items=self._hidden_rows(document),
            preview=self._preview_for(document, prepared),
            capability_warnings=capability_warnings,
            blocking_issues=blocking_issues,
        )
        self._document = document
        self._adapter = adapter
        self._mode = mode
        self._bundle = bundle
        self._progress(progress, 100, "检查完成，隐藏内容已自动清理，请确认可见候选与图片")
        return bundle

    def resolve_finding(
        self,
        finding_id: str,
        status: FindingStatus,
        method: TransformMethod,
        ignore_reason: str = "",
        replacement: str = "",
    ) -> Finding:
        document, bundle, mode = self._require_task()
        finding = self._finding(finding_id)
        if finding.category is Category.COMBINATION_RISK:
            self._refresh_combination_statuses(bundle.findings)
            if finding.status is FindingStatus.PENDING:
                raise ValueError("请先处理该组合风险的贡献字段")
            return finding
        related_findings = self._related_findings(finding, bundle.findings)
        if status is FindingStatus.KEEP_FALSE_POSITIVE and any(
            bool(item.metadata.get("rule_mandatory")) for item in related_findings
        ):
            raise ValueError("此项命中你的强制规则，必须使用代号或删除")
        if status is FindingStatus.KEEP_FALSE_POSITIVE and not ignore_reason.strip():
            raise ValueError("忽略候选必须填写原因")
        if status is FindingStatus.PENDING:
            raise ValueError("不能将候选回退为未处理状态")
        manual_replacement = replacement.strip()
        if len(manual_replacement) > 512:
            raise ValueError("人工替代值不能超过 512 个字符")
        if (
            status is FindingStatus.TRANSFORM
            and manual_replacement
            and any(bool(item.metadata.get("rule_mandatory")) for item in related_findings)
            and any(
                item.original and contains_normalized_original(item.original, manual_replacement)
                for item in related_findings
            )
        ):
            raise ValueError("强制规则的代号不能继续包含原文")
        for related in related_findings:
            related.status = status
            related.suggested_method = method
            related.ignore_reason = (
                ignore_reason.strip() if status is FindingStatus.KEEP_FALSE_POSITIVE else ""
            )
            if status is FindingStatus.KEEP_FALSE_POSITIVE:
                related.suggested_method = TransformMethod.KEEP
                related.replacement = related.original
            elif status is FindingStatus.REMOVE:
                related.suggested_method = TransformMethod.REMOVE
                related.replacement = ""
            elif manual_replacement:
                related.metadata["manual_replacement"] = manual_replacement
                related.replacement = manual_replacement
            else:
                related.metadata.pop("manual_replacement", None)
                related.replacement = ""
        self._refresh_replacements(document, bundle.findings, mode)
        self._refresh_combination_statuses(bundle.findings)
        bundle.preview = self._preview_for(document, bundle.findings)
        return finding

    def resolve_ordinary_findings(self) -> list[Finding]:
        """Apply safe, deterministic suggestions without bypassing human-only items."""

        document, bundle, mode = self._require_task()
        resolved: list[Finding] = []
        combination_contributor_ids = {
            contributor_id
            for risk in bundle.findings
            if risk.category is Category.COMBINATION_RISK and risk.status is FindingStatus.PENDING
            for contributor_id in risk.metadata.get("contributor_ids", ())
        }
        for finding in bundle.findings:
            if finding.status is not FindingStatus.PENDING:
                continue
            if finding.category is Category.COMBINATION_RISK:
                continue
            if finding.id in combination_contributor_ids:
                continue
            if finding.modality not in {Modality.TEXT, Modality.CELL}:
                continue
            if any(location.image_id for location in finding.locations):
                continue
            deterministic_rule = bool(finding.metadata.get("rule_id"))
            if finding.confidence < 0.8 and not deterministic_rule:
                continue
            finding.status = FindingStatus.TRANSFORM
            finding.ignore_reason = ""
            resolved.append(finding)

        if resolved:
            self._refresh_replacements(document, bundle.findings, mode)
            self._refresh_combination_statuses(bundle.findings)
            bundle.preview = self._preview_for(document, bundle.findings)
        return resolved

    def save_fixed_rule(
        self,
        original: str,
        replacement: str,
        category: Category,
    ) -> RuleDefinition:
        """Persist one reviewed mapping for future tasks without changing this snapshot."""

        source_value = original.strip()
        replacement_value = replacement.strip()
        if not source_value or not replacement_value:
            raise ValueError("原词和代号都不能为空")
        if contains_normalized_original(source_value, replacement_value):
            raise ValueError("代号不能继续包含原词")
        candidate = RuleDefinition.fixed(
            source_value,
            replacement_value,
            name=f"{source_value[:40]} → {replacement_value[:40]}",
            category=category.value,
        )
        library = self._rule_store.load()
        for existing in library.rules:
            if existing.source_signature() != candidate.source_signature():
                continue
            if existing.effect_signature() != candidate.effect_signature():
                raise RuleConflictError("这个原词已有不同代号，请到规则库中选择保留哪一个")
            if not existing.enabled:
                updated = library.set_enabled(existing.id, True)
                self._rule_store.save_if_revision(
                    updated,
                    expected_revision=library.revision,
                )
                return replace(existing, enabled=True)
            return existing
        self._rule_store.save_if_revision(
            library.add(candidate),
            expected_revision=library.revision,
        )
        return candidate

    def apply_rules_incrementally(self) -> int:
        """Apply the latest rules to the in-memory text/OCR snapshot only."""

        document, bundle, mode = self._require_task()
        try:
            latest = self._rule_store.load()
        except RuleLibraryError as exc:
            raise ValueError("本地规则库无法安全读取") from exc
        old_findings = tuple(bundle.findings)
        preserved = {self._finding_identity(item): item for item in old_findings}
        self._rule_snapshot = latest
        self._rule_session = RuleSession(latest)

        detected = self._detector.detect(document)
        time_ids = {item.id for item in detected if item.category is Category.TIME}
        text_findings = [
            item
            for item in detected
            if item.category is not Category.TIME
            and item.modality not in {Modality.METADATA, Modality.HIDDEN, Modality.IMAGE}
            and not any(location.image_id for location in item.locations)
            and not (
                item.category is Category.COMBINATION_RISK
                and time_ids.intersection(
                    str(value) for value in item.metadata.get("contributor_ids", ())
                )
            )
        ]
        for finding in text_findings:
            if finding.category is Category.SECRET:
                finding.status = FindingStatus.REMOVE
                finding.suggested_method = TransformMethod.REMOVE
                finding.replacement = ""
                finding.metadata["auto_handled"] = "secret"
        try:
            text_findings = self._apply_text_rules(document, text_findings)
        except RuleLibraryError as exc:
            raise ValueError("新规则在当前缓存中产生冲突，未改变当前复核") from exc

        try:
            cached_image_findings = [
                item
                for item in self._apply_image_rules(self._cached_image_findings)
                if item.category is not Category.TIME and self._keep_image_finding(item)
            ]
        except RuleLibraryError as exc:
            raise ValueError("新规则在当前图片 OCR 缓存中产生冲突，未改变当前复核") from exc
        prepared, _ = self._prepare_findings(
            document,
            merge_findings([*text_findings, *cached_image_findings]),
            mode,
        )
        self._seed_image_regions(document, prepared)
        old_identities = {self._finding_identity(item) for item in old_findings}
        newly_sensitive_image_ids = {
            location.image_id
            for finding in prepared
            if self._finding_identity(finding) not in old_identities
            for location in finding.locations
            if location.image_id is not None
        }
        for image in document.images:
            if image.id in newly_sensitive_image_ids:
                image.disposition = ImageDisposition.PENDING
        self._auto_keep_clean_images(document, prepared)
        for finding in prepared:
            previous = preserved.get(self._finding_identity(finding))
            if previous is None:
                continue
            finding.status = previous.status
            finding.suggested_method = previous.suggested_method
            finding.replacement = previous.replacement
            finding.ignore_reason = previous.ignore_reason
            if "manual_replacement" in previous.metadata:
                finding.metadata["manual_replacement"] = previous.metadata["manual_replacement"]
        self._refresh_replacements(document, prepared, mode)
        self._refresh_combination_statuses(prepared)
        bundle.findings = prepared
        bundle.images = self._image_rows(document, prepared)
        bundle.preview = self._preview_for(document, prepared)
        bundle.inventory = self._inventory_rows(
            document,
            prepared,
            capability_warnings=bundle.capability_warnings,
            blocking_issues=bundle.blocking_issues,
        )
        return sum(self._finding_identity(item) not in old_identities for item in prepared)

    @staticmethod
    def _finding_identity(finding: Finding) -> tuple[object, ...]:
        locations = tuple(
            sorted(
                (
                    location.part,
                    location.block_id or "",
                    location.image_id or "",
                    location.start if location.start is not None else -1,
                    location.end if location.end is not None else -1,
                )
                for location in finding.locations
            )
        )
        return finding.category, finding.original, locations

    def change_finding_category(
        self,
        finding_id: str,
        category: Category,
    ) -> Finding:
        document, bundle, mode = self._require_task()
        finding = self._finding(finding_id)
        if finding.category is Category.COMBINATION_RISK:
            raise ValueError("组合识别风险类别由系统根据贡献字段生成")
        for related in self._related_findings(finding, bundle.findings):
            related.category = category
            related.status = FindingStatus.PENDING
            related.ignore_reason = ""
            related.replacement = ""
            related.metadata["manual_category"] = True
            related.metadata.pop("manual_replacement", None)
        self._refresh_replacements(document, bundle.findings, mode)
        self._refresh_combination_statuses(bundle.findings)
        bundle.preview = self._preview_for(document, bundle.findings)
        return finding

    def add_manual_finding(
        self,
        original: str,
        category: Category,
        method: TransformMethod,
    ) -> Finding:
        document, bundle, mode = self._require_task()
        value = original.strip().replace("\u2029", "\n")
        if not value:
            raise ValueError("请先选择或输入需要补充的文字")
        if len(value) > 256:
            raise ValueError("人工补充的文字不能超过 256 个字符")
        existing = next(
            (
                item
                for item in bundle.findings
                if item.original == value and item.category is category
            ),
            None,
        )
        if existing is not None:
            return existing

        locations = []
        modality = None
        for block in document.blocks:
            start = 0
            while True:
                start = block.text.find(value, start)
                if start < 0:
                    break
                locations.append(
                    clone_location(
                        block.location,
                        start=start,
                        end=start + len(value),
                    )
                )
                modality = modality or modality_for_block(block)
                start += len(value)
        if not locations or modality is None:
            raise ValueError("所选文字不在当前文档的可复核内容中")

        finding = Finding(
            category=category,
            modality=modality,
            original=value,
            locations=locations,
            detector="manual:text-selection",
            confidence=1.0,
            suggested_method=method,
            preserved_semantics="按人工确认的类别和策略处理",
            context="由用户在当前任务中手动补充。",
            metadata={"manual": True},
        )
        bundle.findings.append(finding)
        self._refresh_replacements(document, bundle.findings, mode)
        self._refresh_combination_statuses(bundle.findings)
        bundle.preview = self._preview_for(document, bundle.findings)
        return finding

    def resolve_image(
        self,
        image_id: str,
        disposition: ImageDisposition,
    ) -> None:
        document, bundle, _mode = self._require_task()
        image = next((item for item in document.images if item.id == image_id), None)
        review = next((item for item in bundle.images if item.id == image_id), None)
        if image is None or review is None:
            raise KeyError("图片复核项不存在")
        image.disposition = disposition
        review.disposition = disposition

    def set_image_regions(
        self,
        image_id: str,
        boxes: Sequence[tuple[int, int, int, int]],
    ) -> None:
        document, bundle, _mode = self._require_task()
        image = next((item for item in document.images if item.id == image_id), None)
        review = next((item for item in bundle.images if item.id == image_id), None)
        if image is None or review is None:
            raise KeyError("图片复核项不存在")
        left, top, right, bottom = self._image_bounds(image.content)
        normalized: list[tuple[int, int, int, int]] = []
        for box in boxes:
            x1, y1, x2, y2 = (int(value) for value in box)
            if x1 < left or y1 < top or x2 <= x1 or y2 <= y1 or x2 > right or y2 > bottom:
                raise ValueError("图片框选区域超出原图范围")
            normalized.append((x1, y1, x2, y2))
        self._image_region_overrides[image_id] = normalized
        review.regions = list(normalized)

    def resolve_hidden(self, item_id: str, action: str) -> None:
        _document, bundle, _mode = self._require_task()
        package_item = self._hidden_items.get(item_id)
        review_item = next(
            (item for item in bundle.hidden_items if item.id == item_id),
            None,
        )
        if package_item is None or review_item is None:
            raise KeyError("隐藏内容复核项不存在")
        if action == "pending":
            package_item.disposition = ObjectDisposition.PENDING
            review_item.action = action
            return
        try:
            disposition = ObjectDisposition(action)
        except ValueError as exc:
            raise ValueError("不支持的对象处理方式") from exc
        if action not in review_item.allowed_actions:
            raise ValueError("该对象不允许使用此处理方式")
        package_item.disposition = disposition
        review_item.action = action

    def is_review_complete(self) -> bool:
        if self._document is None or self._bundle is None:
            return False
        if self._bundle.blocking_issues:
            return False
        if self._image_recognition_degraded(self._bundle.capability_warnings):
            safe_image_decisions = all(
                image.disposition in {ImageDisposition.PIXEL_REDACT, ImageDisposition.REMOVE}
                for image in self._document.images
            )
            if not safe_image_decisions:
                return False
        return (
            all(finding.status is not FindingStatus.PENDING for finding in self._bundle.findings)
            and all(
                image.disposition is not ImageDisposition.PENDING for image in self._document.images
            )
            and not self._document.inventory.unresolved_items
        )

    def preview(self) -> PreviewContent:
        document, bundle, _mode = self._require_task()
        bundle.preview = self._preview_for(document, bundle.findings)
        return bundle.preview

    def export(
        self,
        result_root: Path,
        mapping_password: str,
        progress: ProgressCallback | None = None,
    ) -> ExportArtifacts:
        document, bundle, mode = self._require_task()
        self._require_current_rule_snapshot()
        if not self.is_review_complete():
            if bundle.blocking_issues:
                codes = "、".join(self._warning_code(item) for item in bundle.blocking_issues)
                raise ValueError(f"本地识别组件异常，任务已阻断：{codes}")
            if self._image_recognition_degraded(bundle.capability_warnings):
                raise ValueError("图片识别能力异常时，只允许遮住整张图片或删除整张图片")
            raise ValueError("仍有未完成人工决定的项目")
        self._validate_image_decisions(document, bundle.findings)
        self._synchronize_image_regions(document, bundle.findings)
        self._refresh_replacements(document, bundle.findings, mode)
        prepared, mappings = self._prepare_findings(
            document,
            bundle.findings,
            mode,
        )
        self._copy_prepared_values(bundle.findings, prepared)
        self._progress(progress, 12, "正在原格式结构中安全替换已确认内容")
        writer = self._artifact_writer
        if writer is None:
            from .artifacts import ArtifactWriter

            adapter = self._adapter
            if adapter is None:
                raise RuntimeError("当前没有可用的 Office 文档适配器")
            writer = ArtifactWriter(adapter)
        self._progress(progress, 38, "正在生成本地脱敏映射表")
        try:
            artifacts = writer.export_task(
                document=document,
                findings=bundle.findings,
                mappings=mappings,
                result_root=Path(result_root),
                mapping_password=mapping_password,
            )
        except Exception:
            self._record_history(document, bundle.findings, "failed", "")
            raise
        self._progress(progress, 90, "正在复查实际落盘文件和目录隔离")
        self._progress(progress, 100, "实际导出文件复扫完成")
        self._record_history(
            document,
            bundle.findings,
            "completed",
            str(artifacts.result_root),
        )
        return artifacts

    def history_entries(self) -> tuple[HistoryEntry, ...]:
        return self._history_store.load()

    def delete_history(self, entry_id: str) -> None:
        self._history_store.delete(entry_id)

    def clear_history(self) -> None:
        self._history_store.clear()

    def record_failed_task(self, source_path: Path) -> None:
        """Record a file that failed before a document model could be created."""

        path = Path(source_path)
        try:
            fingerprint = sha256_file(path) if path.is_file() else ""
        except OSError:
            fingerprint = ""
        self._history_store.append(
            HistoryEntry(
                id=new_history_id(),
                created_at=datetime.now().astimezone().isoformat(timespec="seconds"),
                source_name=path.name,
                source_sha256=fingerprint,
                document_kind=path.suffix.lstrip(".").casefold() or "unknown",
                status="failed",
                finding_count=0,
                transformed_count=0,
                removed_count=0,
            )
        )

    def record_batch_summary(
        self,
        folder_name: str,
        total: int,
        completed: int,
        failed: int,
    ) -> None:
        self._history_store.append(
            HistoryEntry(
                id=new_history_id(),
                created_at=datetime.now().astimezone().isoformat(timespec="seconds"),
                source_name=folder_name or "文件夹批量任务",
                source_sha256="",
                document_kind="batch",
                status="completed" if failed == 0 else "partial",
                finding_count=total,
                transformed_count=completed,
                removed_count=failed,
            )
        )

    def _record_history(
        self,
        document: DocumentModel,
        findings: Sequence[Finding],
        status: str,
        result_path: str,
    ) -> None:
        transformed = sum(item.status is FindingStatus.TRANSFORM for item in findings)
        removed = sum(item.status is FindingStatus.REMOVE for item in findings)
        self._history_store.append(
            HistoryEntry(
                id=new_history_id(),
                created_at=datetime.now().astimezone().isoformat(timespec="seconds"),
                source_name=document.display_name,
                source_sha256=document.source_sha256,
                document_kind=document.kind.value,
                status=status,
                finding_count=len(findings),
                transformed_count=transformed,
                removed_count=removed,
                result_path=result_path,
            )
        )

    def _require_current_rule_snapshot(self) -> None:
        try:
            current = self._rule_store.load()
        except RuleLibraryError as exc:
            raise ValueError(
                "本地规则库无法安全读取。请先修复规则库，再重新检查当前文件。"
            ) from exc
        if current != self._rule_snapshot:
            raise ValueError("规则库已经更新。为保证本次标准一致，请重新检查当前文件。")

    def reset(self) -> None:
        self._document = None
        self._adapter = None
        self._mode = None
        self._bundle = None
        self._hidden_items = {}
        self._image_region_overrides = {}
        self._cached_image_findings = []
        self._rule_snapshot = RuleLibrary()
        self._rule_session = RuleSession(self._rule_snapshot)

    @property
    def rule_store(self) -> Any:
        """Expose the local encrypted store to the dedicated rule-library dialog."""

        return self._rule_store

    @staticmethod
    def default_rule_store_path() -> Path:
        return default_rule_store_path()

    @staticmethod
    def _adapter_for(path: Path) -> Any:
        suffix = path.suffix.casefold()
        if suffix == ".docx":
            return DocxAdapter()
        if suffix == ".xlsx":
            return XlsxAdapter()
        raise ValueError("首版只支持 .docx 和 .xlsx")

    @staticmethod
    def _progress(
        callback: ProgressCallback | None,
        value: int,
        message: str,
    ) -> None:
        if callback is not None:
            callback(value, message)

    def _require_task(self) -> tuple[DocumentModel, ReviewBundle, ProcessingMode]:
        if self._document is None or self._bundle is None or self._mode is None:
            raise RuntimeError("当前没有正在复核的文档")
        return self._document, self._bundle, self._mode

    def _finding(self, finding_id: str) -> Finding:
        if self._bundle is None:
            raise RuntimeError("当前没有正在复核的文档")
        finding = next(
            (item for item in self._bundle.findings if item.id == finding_id),
            None,
        )
        if finding is None:
            raise KeyError("识别项不存在")
        return finding

    def _prepare_findings(
        self,
        document: DocumentModel,
        findings: Sequence[Finding],
        mode: ProcessingMode,
    ) -> tuple[list[Finding], list[MappingEntry]]:
        return self._transformer.prepare(document, findings, mode)

    def _refresh_replacements(
        self,
        document: DocumentModel,
        findings: list[Finding],
        mode: ProcessingMode,
    ) -> None:
        for item in findings:
            if item.status is FindingStatus.KEEP_FALSE_POSITIVE:
                item.replacement = item.original
                item.suggested_method = TransformMethod.KEEP
            elif item.status is FindingStatus.REMOVE:
                item.replacement = ""
                item.suggested_method = TransformMethod.REMOVE
            else:
                item.replacement = str(item.metadata.get("manual_replacement", ""))
        prepared, _ = self._prepare_findings(document, findings, mode)
        self._copy_prepared_values(findings, prepared)

    @staticmethod
    def _copy_prepared_values(
        target: Sequence[Finding],
        prepared: Sequence[Finding],
    ) -> None:
        by_id = {item.id: item for item in prepared}
        for item in target:
            updated = by_id.get(item.id)
            if updated is None:
                continue
            item.replacement = updated.replacement
            item.suggested_method = updated.suggested_method
            item.preserved_semantics = updated.preserved_semantics
            item.metadata = dict(updated.metadata)

    @staticmethod
    def _refresh_combination_statuses(findings: Sequence[Finding]) -> None:
        by_id = {finding.id: finding for finding in findings}
        for risk in findings:
            if risk.category is not Category.COMBINATION_RISK:
                continue
            contributor_ids = tuple(risk.metadata.get("contributor_ids", ()))
            contributors = [by_id[item_id] for item_id in contributor_ids if item_id in by_id]
            if not contributors or any(
                item.status is FindingStatus.PENDING for item in contributors
            ):
                risk.status = FindingStatus.PENDING
                risk.replacement = ""
                continue
            if all(item.status is FindingStatus.KEEP_FALSE_POSITIVE for item in contributors):
                risk.status = FindingStatus.KEEP_FALSE_POSITIVE
                risk.suggested_method = TransformMethod.KEEP
                risk.ignore_reason = "贡献字段均已确认为误报"
            else:
                risk.status = FindingStatus.TRANSFORM
                risk.suggested_method = TransformMethod.GENERALIZE
                risk.ignore_reason = ""
            risk.replacement = ""

    @staticmethod
    def _related_findings(
        selected: Finding,
        findings: Sequence[Finding],
    ) -> list[Finding]:
        if not selected.original:
            return [selected]
        selected_rule_ids = {
            rule_id for rule_id in str(selected.metadata.get("rule_id", "")).split("；") if rule_id
        }
        if selected_rule_ids:
            rule_related = [
                finding
                for finding in findings
                if finding.original == selected.original
                and selected_rule_ids.intersection(
                    rule_id
                    for rule_id in str(finding.metadata.get("rule_id", "")).split("；")
                    if rule_id
                )
            ]
            if rule_related:
                return rule_related
        normalized = normalize_entity(selected.category, selected.original)
        return [
            finding
            for finding in findings
            if finding.category is selected.category
            and normalize_entity(finding.category, finding.original) == normalized
        ]

    def _apply_text_rules(
        self,
        document: DocumentModel,
        findings: Sequence[Finding],
    ) -> list[Finding]:
        existing_risks = [
            finding for finding in findings if finding.category is Category.COMBINATION_RISK
        ]
        ordinary = [
            replace(
                finding,
                locations=list(finding.locations),
                metadata=dict(finding.metadata),
            )
            for finding in findings
            if finding.category is not Category.COMBINATION_RISK
        ]
        rule_findings: list[Finding] = []

        for block in document.blocks:
            scope = self._rule_scope_for_modality(modality_for_block(block))
            matches = self._rule_session.find(block.text, applies_to=scope)
            for match in matches:
                location = clone_location(
                    block.location,
                    start=match.start,
                    end=match.end,
                )
                overlapping = [
                    (finding, candidate)
                    for finding in ordinary
                    for candidate in finding.locations
                    if self._locations_overlap(candidate, location)
                ]
                partially_overlapping = [
                    finding
                    for finding, candidate in overlapping
                    if not self._location_fully_covered(location, candidate)
                ]
                if partially_overlapping:
                    for finding_id in dict.fromkeys(item.id for item, _candidate in overlapping):
                        target = next(item for item in ordinary if item.id == finding_id)
                        self._merge_rule_metadata(target, match)
                    continue
                category = self._rule_category(match.category)
                if category is Category.OTHER:
                    category = self._overlapping_category(location, ordinary)
                rule_finding = self._rule_finding(
                    match,
                    modality=modality_for_block(block),
                    location=location,
                    category=category,
                    context=block.text,
                )
                rule_findings.append(rule_finding)
                for finding in ordinary:
                    finding.locations = [
                        candidate
                        for candidate in finding.locations
                        if not (
                            self._locations_overlap(candidate, location)
                            and self._location_fully_covered(location, candidate)
                        )
                    ]
                ordinary = [item for item in ordinary if item.locations]

        merged = merge_findings([*ordinary, *rule_findings])
        scorer = getattr(self._detector, "combination_scorer", None)
        if scorer is None:
            return [*merged, *existing_risks]
        return [*merged, *scorer.assess(document, merged)]

    def _apply_image_rules(self, findings: Sequence[Finding]) -> list[Finding]:
        prepared: list[Finding] = []
        rule_lookup = {rule.id: rule for rule in self._rule_snapshot.enabled_rules}
        for source in findings:
            application = self._rule_session.apply(source.original, applies_to="ocr")
            if not application.matches:
                prepared.append(source)
                continue
            if contains_normalized_original(
                source.original,
                application.replacement,
            ):
                raise RuleLibraryError("本地规则替换结果仍包含完整原文，不能作为安全处理结果")
            names = tuple(dict.fromkeys(match.rule_name for match in application.matches))
            identifiers = tuple(dict.fromkeys(match.rule_id for match in application.matches))
            kinds = tuple(
                dict.fromkeys(
                    rule_lookup[identifier].kind.value
                    for identifier in identifiers
                    if identifier in rule_lookup
                )
            )
            metadata = dict(source.metadata)
            metadata.update(
                {
                    "manual_replacement": application.replacement,
                    "rule_id": "；".join(identifiers),
                    "rule_name": "；".join(names),
                    "rule_kind": "；".join(kinds),
                    "rule_mandatory": any(match.mandatory for match in application.matches),
                    "rule_action": "；".join(
                        dict.fromkeys(match.action.value for match in application.matches)
                    ),
                }
            )
            status = (
                FindingStatus.REMOVE if not application.replacement else FindingStatus.TRANSFORM
            )
            method = (
                TransformMethod.REMOVE
                if status is FindingStatus.REMOVE
                else source.suggested_method
            )
            prepared.append(
                replace(
                    source,
                    replacement=application.replacement,
                    status=status,
                    suggested_method=method,
                    metadata=metadata,
                    locations=list(source.locations),
                )
            )
        return prepared

    def _rule_finding(
        self,
        match: RuleMatch,
        *,
        modality: Modality,
        location: SourceLocation,
        category: Category,
        context: str,
    ) -> Finding:
        if match.action is not ActionKind.DELETE and contains_normalized_original(
            match.original, match.replacement
        ):
            raise RuleLibraryError(f"规则“{match.rule_name}”替换后仍为原文，不能安全应用")
        remove = match.action is ActionKind.DELETE
        metadata = {
            "rule_id": match.rule_id,
            "rule_name": match.rule_name,
            "rule_kind": match.kind.value,
            "rule_mandatory": match.mandatory,
            "rule_action": match.action.value,
        }
        if not remove:
            metadata["manual_replacement"] = match.replacement
        return Finding(
            category=category,
            modality=modality,
            original=match.original,
            locations=[location],
            detector="local-rule",
            confidence=1.0,
            suggested_method=(TransformMethod.REMOVE if remove else TransformMethod.ALIAS),
            replacement="" if remove else match.replacement,
            preserved_semantics="按本地规则隐藏原词，保留必要业务上下文",
            context=self._rule_context(context, match.start, match.end),
            status=FindingStatus.REMOVE if remove else FindingStatus.TRANSFORM,
            metadata=metadata,
        )

    @staticmethod
    def _rule_scope_for_modality(modality: Modality) -> str:
        return {
            Modality.CELL: "cell",
            Modality.IMAGE: "ocr",
            Modality.METADATA: "metadata",
            Modality.HIDDEN: "hidden",
        }.get(modality, "text")

    @staticmethod
    def _rule_category(value: str) -> Category:
        try:
            return Category(value.strip())
        except ValueError:
            return Category.OTHER

    @staticmethod
    def _overlapping_category(
        location: SourceLocation,
        findings: Sequence[Finding],
    ) -> Category:
        for finding in findings:
            if any(
                LocalDesktopController._locations_overlap(candidate, location)
                for candidate in finding.locations
            ):
                return finding.category
        return Category.OTHER

    @staticmethod
    def _locations_overlap(left: SourceLocation, right: SourceLocation) -> bool:
        if left.block_id != right.block_id or left.block_id is None:
            return False
        if left.start is None or left.end is None or right.start is None or right.end is None:
            return False
        return left.start < right.end and left.end > right.start

    @staticmethod
    def _location_fully_covered(
        rule_location: SourceLocation,
        candidate: SourceLocation,
    ) -> bool:
        if (
            rule_location.block_id != candidate.block_id
            or rule_location.start is None
            or rule_location.end is None
            or candidate.start is None
            or candidate.end is None
        ):
            return False
        return rule_location.start <= candidate.start and rule_location.end >= candidate.end

    @staticmethod
    def _merge_rule_metadata(finding: Finding, match: RuleMatch) -> None:
        def merge_value(key: str, value: str) -> None:
            values = [item for item in str(finding.metadata.get(key, "")).split("；") if item]
            if value not in values:
                values.append(value)
            finding.metadata[key] = "；".join(values)

        merge_value("rule_id", match.rule_id)
        merge_value("rule_name", match.rule_name)
        merge_value("rule_kind", match.kind.value)
        merge_value("rule_action", match.action.value)
        finding.metadata["rule_mandatory"] = (
            bool(finding.metadata.get("rule_mandatory")) or match.mandatory
        )
        finding.metadata["rule_partial_overlap"] = True

    @staticmethod
    def _rule_context(text: str, start: int, end: int, radius: int = 24) -> str:
        left = max(0, start - radius)
        right = min(len(text), end + radius)
        return ("…" if left else "") + text[left:right] + ("…" if right < len(text) else "")

    def _hidden_rows(self, document: DocumentModel) -> list[HiddenReviewItem]:
        rows: list[HiddenReviewItem] = []
        self._hidden_items = {}
        for index, item in enumerate(document.inventory.parts, start=1):
            if not item.requires_decision:
                continue
            item.disposition = ObjectDisposition.REMOVE
            item_id = f"object-{index:04d}"
            self._hidden_items[item_id] = item
            label = _OBJECT_LABELS.get(item.kind, item.kind or "文件对象")
            allowed = ["remove"]
            if item.kind in {"comment", "footnote", "endnote", "header", "footer"}:
                allowed.append("visible_note")
            if item.kind in {"embedded_object", "binary"}:
                allowed.append("separate_task")
            rows.append(
                HiddenReviewItem(
                    id=item_id,
                    title=f"{label} {len(rows) + 1}",
                    location=item.part,
                    kind=label,
                    description=self._object_description(item),
                    allowed_actions=tuple(allowed),
                    action=ObjectDisposition.REMOVE.value,
                )
            )
        return rows

    @staticmethod
    def _object_description(item: PackageItem) -> str:
        if item.external:
            return "发现外部目标；活动关系已自动移除，不会进入分析副本。"
        if item.kind == "embedded_object":
            return "嵌入文件已自动移除，不会复制到分析副本。"
        if item.kind in {"header", "footer", "comment", "footnote", "endnote"}:
            return "该隐藏部件已自动移除，不再要求逐项确认。"
        return "该部件已按安全默认策略自动移除。"

    @staticmethod
    def _keep_image_finding(finding: Finding) -> bool:
        """Keep only faces and information that is sensitive by rule or structure."""

        if finding.category is Category.PHOTO:
            return True
        if finding.category is Category.IMAGE_TEXT:
            return bool(finding.metadata.get("rule_id"))
        return finding.category in {
            Category.NAME,
            Category.PHONE,
            Category.ID_CARD,
            Category.BANK_CARD,
            Category.EMAIL,
            Category.LANDLINE,
            Category.ADDRESS,
            Category.VEHICLE_PLATE,
            Category.ACCOUNT,
            Category.USERNAME,
            Category.SECRET,
            Category.PUBLIC_IP,
            Category.PRIVATE_IP,
            Category.DOMAIN,
            Category.CASE_ID,
            Category.DEVICE_ID,
        } or bool(finding.metadata.get("rule_id"))

    @staticmethod
    def _auto_keep_clean_images(
        document: DocumentModel,
        findings: Sequence[Finding],
    ) -> None:
        if LocalDesktopController._image_recognition_degraded(
            LocalDesktopController._capability_warnings(document.warnings)
        ):
            return
        sensitive_ids = {
            location.image_id
            for finding in findings
            for location in finding.locations
            if location.image_id is not None
        }
        for image in document.images:
            if image.id not in sensitive_ids:
                image.disposition = ImageDisposition.KEEP_REENCODED
                image.regions.clear()

    @staticmethod
    def _image_rows(
        document: DocumentModel,
        findings: Sequence[Finding],
    ) -> list[ImageReviewItem]:
        degraded = LocalDesktopController._image_recognition_degraded(
            LocalDesktopController._capability_warnings(document.warnings)
        )
        grouped: dict[str, list[Finding]] = defaultdict(list)
        for finding in findings:
            for location in finding.locations:
                if location.image_id:
                    grouped[location.image_id].append(finding)
        rows: list[ImageReviewItem] = []
        for index, image in enumerate(document.images, start=1):
            image_findings = grouped.get(image.id, [])
            if image.disposition is ImageDisposition.KEEP_REENCODED and not image_findings:
                continue
            categories = tuple(
                dict.fromkeys(
                    _CATEGORY_LABELS.get(item.category, item.category.value)
                    for item in image_findings
                )
            )
            if not categories:
                categories = ("图片识别能力异常，需人工检查",)
            rows.append(
                ImageReviewItem(
                    id=image.id,
                    title=f"图片 {index}",
                    location=image.location.display,
                    candidates=categories,
                    original_summary=(f"本机识别到 {len(image_findings)} 个人脸或敏感信息候选。"),
                    processed_summary=(
                        "本地图片识别能力异常；为避免漏检，只能遮住整张图片或删除整张图片。"
                        if degraded
                        else "只需确认人脸和敏感信息区域；其他图片已自动去元数据并重新编码。"
                    ),
                    preview_png=LocalDesktopController._preview_png(image.content),
                    regions=[region.bbox for region in image.regions],
                    disposition=image.disposition,
                )
            )
        return rows

    @staticmethod
    def _inventory_rows(
        document: DocumentModel,
        findings: Sequence[Finding],
        *,
        capability_warnings: Sequence[str] = (),
        blocking_issues: Sequence[str] = (),
    ) -> list[ScanInventoryItem]:
        categories = Counter(finding.category for finding in findings)
        hidden = sum(item.requires_decision for item in document.inventory.parts)
        external = sum(item.external for item in document.inventory.parts)
        rows = [
            ScanInventoryItem(
                "文字与表格",
                len(document.blocks),
                "已识别",
                f"共形成 {len(findings)} 个候选，必须逐项复核。",
            ),
            ScanInventoryItem(
                "图片与二维码",
                len(document.images),
                "待人工决定"
                if any(image.disposition is ImageDisposition.PENDING for image in document.images)
                else ("已自动净化" if document.images else "未发现"),
                "只有人脸、敏感信息和强制规则命中需人工确认。",
            ),
            ScanInventoryItem(
                "隐藏内容与文件对象",
                hidden,
                "待人工决定" if hidden else "已清理",
                f"另发现 {external} 个外部目标；重建时不复制活动关系。",
            ),
            ScanInventoryItem(
                "组合识别风险",
                categories[Category.COMBINATION_RISK],
                ("待人工复核" if categories[Category.COMBINATION_RISK] else "未触发高风险阈值"),
                "按段落、表格行和文档整体计算组合可识别风险。",
            ),
        ]
        codes = tuple(
            dict.fromkeys(
                LocalDesktopController._warning_code(item) for item in capability_warnings
            )
        )
        if not codes:
            rows.append(
                ScanInventoryItem(
                    "本地识别能力",
                    0,
                    "正常",
                    "必需的本地识别组件已完成本次扫描。",
                )
            )
        elif blocking_issues:
            rows.append(
                ScanInventoryItem(
                    "本地识别能力",
                    len(codes),
                    "已阻断",
                    f"识别组件异常：{'、'.join(codes)}。本次任务不能导出。",
                )
            )
        else:
            rows.append(
                ScanInventoryItem(
                    "本地识别能力",
                    len(codes),
                    "需整图安全处理",
                    f"图片识别能力异常：{'、'.join(codes)}。所有图片只能整图处理或移除。",
                )
            )
        return rows

    @staticmethod
    def _preview_for(
        document: DocumentModel,
        findings: Sequence[Finding],
    ) -> PreviewContent:
        blocks = [block for block in document.blocks if not block.hidden and block.text]
        chosen = blocks[:12]
        chosen_ids = {block.id for block in chosen}
        referenced_ids = {
            location.block_id
            for finding in findings
            for location in finding.locations
            if location.block_id
        }
        chosen.extend(
            block for block in blocks if block.id in referenced_ids and block.id not in chosen_ids
        )
        original = "\n".join(block.text for block in chosen)
        transformed = "\n".join(apply_findings_to_text(block, findings) for block in chosen)
        if not original:
            original = "（文档没有可直接预览的正文文字）"
            transformed = original
        statuses = Counter(item.status for item in findings)
        summary = (
            f"已确认替换 {statuses[FindingStatus.TRANSFORM]} 项、"
            f"移除 {statuses[FindingStatus.REMOVE]} 项、"
            f"保留并注明原因 {statuses[FindingStatus.KEEP_FALSE_POSITIVE]} 项；"
            "保留文档顺序、实体同一性和可理解的业务关系。"
        )
        return PreviewContent(
            original=original[:4000],
            replacement=transformed[:4000],
            preserved_summary=summary,
            blocks=tuple(
                {
                    "id": block.id,
                    "text": block.text,
                    "kind": block.block_kind,
                    "style": {
                        "styleId": str(block.style.get("style_id", "")),
                        "alignment": str(block.style.get("alignment", "")),
                        "numbered": bool(block.style.get("numbered", False)),
                        "level": str(block.style.get("level", "")),
                        "bold": bool(block.style.get("bold", False)),
                    },
                }
                for block in chosen
            ),
        )

    @staticmethod
    def _seed_image_regions(
        document: DocumentModel,
        findings: Sequence[Finding],
    ) -> None:
        by_id = {image.id: image for image in document.images}
        for image in document.images:
            image.regions.clear()
        for finding in findings:
            for location in finding.locations:
                if location.image_id is None or location.bbox is None:
                    continue
                target_image = by_id.get(location.image_id)
                if target_image is None:
                    continue
                region = ImageRegion(
                    bbox=location.bbox,
                    category=finding.category,
                    replacement_label=finding.replacement,
                )
                if region not in target_image.regions:
                    target_image.regions.append(region)

    @staticmethod
    def _validate_image_decisions(
        document: DocumentModel,
        findings: Sequence[Finding],
    ) -> None:
        active_by_image: Counter[str] = Counter()
        for finding in findings:
            if finding.status not in {FindingStatus.TRANSFORM, FindingStatus.REMOVE}:
                continue
            for location in finding.locations:
                if location.image_id:
                    active_by_image[location.image_id] += 1
        for image in document.images:
            if image.disposition is ImageDisposition.KEEP_REENCODED and active_by_image[image.id]:
                raise ValueError(
                    "图片仍有已确认敏感候选，不能选择“保留并重新编码”；"
                    "请改为像素遮挡/整图移除，或逐项注明为误报。"
                )

    def _synchronize_image_regions(
        self,
        document: DocumentModel,
        findings: Sequence[Finding],
    ) -> None:
        by_id = {image.id: image for image in document.images}
        degraded = self._bundle is not None and self._image_recognition_degraded(
            self._bundle.capability_warnings
        )
        for image in document.images:
            image.regions.clear()
        needs_full_image: set[str] = set()
        for finding in findings:
            if finding.status not in {FindingStatus.TRANSFORM, FindingStatus.REMOVE}:
                continue
            for location in finding.locations:
                if not location.image_id:
                    continue
                target_image = by_id.get(location.image_id)
                if target_image is None:
                    continue
                if target_image.id in self._image_region_overrides:
                    continue
                if location.bbox is None:
                    needs_full_image.add(target_image.id)
                    continue
                region = ImageRegion(
                    bbox=location.bbox,
                    category=finding.category,
                    replacement_label=finding.replacement,
                )
                if region not in target_image.regions:
                    target_image.regions.append(region)
        for image in document.images:
            if image.disposition is not ImageDisposition.PIXEL_REDACT:
                continue
            if degraded:
                image.regions = [
                    ImageRegion(
                        bbox=LocalDesktopController._image_bounds(image.content),
                        category=Category.PHOTO,
                        replacement_label="[整图像素已处理]",
                    )
                ]
                continue
            if image.id in self._image_region_overrides:
                image.regions = [
                    ImageRegion(
                        bbox=box,
                        category=Category.OTHER,
                        replacement_label="[人工框选区域已处理]",
                    )
                    for box in self._image_region_overrides[image.id]
                ]
            if image.id in needs_full_image or not image.regions:
                image.regions = [
                    ImageRegion(
                        bbox=LocalDesktopController._image_bounds(image.content),
                        category=Category.PHOTO,
                        replacement_label="[整图像素已处理]",
                    )
                ]

    @staticmethod
    def _warning_code(warning: str) -> str:
        return warning.partition(":")[0].strip()

    @staticmethod
    def _capability_warnings(warnings: Sequence[str]) -> list[str]:
        return [
            warning
            for warning in warnings
            if LocalDesktopController._warning_code(warning).startswith(("NER_", "IMAGE_"))
        ]

    @staticmethod
    def _image_recognition_degraded(warnings: Sequence[str]) -> bool:
        return any(
            LocalDesktopController._warning_code(warning).startswith(_IMAGE_DEGRADED_PREFIX)
            for warning in warnings
        )

    @staticmethod
    def _image_bounds(content: bytes) -> tuple[int, int, int, int]:
        try:
            with Image.open(BytesIO(content)) as image:
                image.load()
                normalized = ImageOps.exif_transpose(image)
                if normalized.width <= 0 or normalized.height <= 0:
                    raise ValueError("图片尺寸无效")
                return (0, 0, normalized.width, normalized.height)
        except OSError as exc:
            raise ValueError("图片无法安全解码，不能执行像素遮挡") from exc

    @staticmethod
    def _preview_png(content: bytes) -> bytes:
        try:
            with Image.open(BytesIO(content)) as image:
                image.load()
                normalized = ImageOps.exif_transpose(image)
                if normalized.width * normalized.height > 80_000_000:
                    return b""
                rgb = normalized.convert("RGBA" if "A" in normalized.getbands() else "RGB")
                output = BytesIO()
                rgb.save(output, format="PNG", optimize=False, compress_level=6)
                return output.getvalue()
        except (OSError, ValueError):
            return b""


__all__ = ["LocalDesktopController"]
