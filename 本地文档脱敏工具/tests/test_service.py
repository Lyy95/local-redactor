from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from local_redactor.models import (
    Category,
    DocumentKind,
    DocumentModel,
    ExportArtifacts,
    Finding,
    FindingStatus,
    ImageDisposition,
    ImageObject,
    Modality,
    ObjectDisposition,
    PackageInventory,
    PackageItem,
    ProcessingMode,
    SourceLocation,
    TextBlock,
    TransformMethod,
)
from local_redactor.rule_library import (
    ActionKind,
    MatchMode,
    RuleConflictError,
    RuleDefinition,
    RuleLibrary,
    RuleStoreError,
)
from local_redactor.service import LocalDesktopController


def png_bytes() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (24, 18), "white").save(stream, format="PNG")
    return stream.getvalue()


def make_document(source: Path, *, image: bool = False) -> DocumentModel:
    location = SourceLocation(part="word/document.xml", display="正文第 1 段")
    block = TextBlock(
        text="负责人姓名：林青河，联系电话：13800138000。",
        location=location,
    )
    location.block_id = block.id
    images = []
    if image:
        image_id = "image-001"
        images.append(
            ImageObject(
                id=image_id,
                source_part="word/media/image1.png",
                location=SourceLocation(
                    part="word/document.xml",
                    display="正文图片 1",
                    image_id=image_id,
                ),
                content=png_bytes(),
            )
        )
    return DocumentModel(
        kind=DocumentKind.DOCX,
        source_path=source,
        source_sha256="0" * 64,
        display_name=source.name,
        blocks=[block],
        images=images,
        inventory=PackageInventory(
            parts=[
                PackageItem(
                    part="word/comments.xml",
                    kind="comment",
                    requires_decision=True,
                    disposition=ObjectDisposition.PENDING,
                )
            ]
        ),
    )


class FakeAdapter:
    def __init__(self, document: DocumentModel) -> None:
        self.document = document

    def scan(self, _path: Path) -> DocumentModel:
        return self.document


class FakeDetector:
    def detect(self, document: DocumentModel) -> list[Finding]:
        block = document.blocks[0]
        start = block.text.index("林青河")
        return [
            Finding(
                id="finding-001",
                category=Category.NAME,
                modality=Modality.TEXT,
                original="林青河",
                locations=[
                    SourceLocation(
                        part=block.location.part,
                        display=block.location.display,
                        block_id=block.id,
                        start=start,
                        end=start + 3,
                    )
                ],
                detector="fake",
                confidence=1.0,
                suggested_method=TransformMethod.ALIAS,
            )
        ]


@dataclass
class FakeImageResult:
    findings: list[Finding] = field(default_factory=list)
    mandatory_review_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class FakeImageAnalyzer:
    def __init__(self, findings: list[Finding] | None = None) -> None:
        self.findings = findings or []

    def analyze(self, document: DocumentModel) -> FakeImageResult:
        return FakeImageResult(
            findings=self.findings,
            mandatory_review_ids=[image.id for image in document.images],
        )


class EmptyDetector:
    combination_scorer = None

    def detect(self, _document: DocumentModel) -> list[Finding]:
        return []


class MemoryRuleStore:
    def __init__(self, library: RuleLibrary) -> None:
        self.library = library

    def load(self) -> RuleLibrary:
        return self.library.snapshot()

    def save(self, library: RuleLibrary) -> None:
        self.library = library.snapshot()

    def save_if_revision(
        self,
        library: RuleLibrary,
        *,
        expected_revision: int,
    ) -> None:
        if self.library.revision != expected_revision:
            raise RuleConflictError("stale")
        self.save(library)


class BrokenRuleStore:
    def load(self) -> RuleLibrary:
        raise RuleStoreError("tampered")


class WarningDetector(FakeDetector):
    def __init__(self, warning: str) -> None:
        self.warning = warning

    def detect(self, document: DocumentModel) -> list[Finding]:
        document.warnings.append(self.warning)
        return super().detect(document)


class WarningImageAnalyzer(FakeImageAnalyzer):
    def __init__(self, warning: str) -> None:
        super().__init__()
        self.warning = warning

    def analyze(self, document: DocumentModel) -> FakeImageResult:
        document.warnings.append(self.warning)
        result = super().analyze(document)
        result.warnings.append(self.warning)
        return result


class RecordingWriter:
    def __init__(self) -> None:
        self.call: dict[str, Any] = {}

    def export_task(self, **kwargs: Any) -> ExportArtifacts:
        self.call = kwargs
        root = Path(kwargs["result_root"]) / "脱敏结果_20260729_120000"
        return ExportArtifacts(
            result_root=root,
            ai_copy=root / "AI交付" / "AI分析副本.docx",
            encrypted_mapping=root / "本地保管" / "脱敏映射表.xlsx",
            report=root / "本地保管" / "脱敏检查报告.html",
            hashes={},
        )


def controller_for(
    document: DocumentModel,
    *,
    image_findings: list[Finding] | None = None,
) -> tuple[LocalDesktopController, RecordingWriter]:
    writer = RecordingWriter()
    controller = LocalDesktopController(
        detector=FakeDetector(),
        image_analyzer_factory=lambda: FakeImageAnalyzer(image_findings),
        artifact_writer=writer,
    )
    controller._adapter_for = lambda _path: FakeAdapter(document)  # type: ignore[method-assign]
    return controller, writer


def test_real_controller_closes_review_and_exports_mapping(tmp_path: Path) -> None:
    source = tmp_path / "fixture.docx"
    source.write_bytes(b"not-used-by-fake-adapter")
    document = make_document(source, image=True)
    controller, writer = controller_for(document)

    bundle = controller.scan(source, ProcessingMode.BALANCED)
    assert bundle.findings[0].replacement
    assert not controller.is_review_complete()

    finding = controller.resolve_finding(
        "finding-001",
        FindingStatus.TRANSFORM,
        TransformMethod.ALIAS,
    )
    assert bundle.images == []
    assert document.images[0].disposition is ImageDisposition.KEEP_REENCODED
    controller.resolve_hidden(bundle.hidden_items[0].id, "remove")
    assert finding.replacement != finding.original
    assert controller.is_review_complete()

    controller.export(tmp_path, "Example#Pass123")
    assert writer.call["mappings"][0].original == "林青河"
    assert document.images[0].regions == []
    assert writer.call["mapping_password"] == "Example#Pass123"


def test_time_findings_are_not_added_to_review_or_combination_risk(tmp_path: Path) -> None:
    source = tmp_path / "fixture.docx"
    source.write_bytes(b"fixture")
    document = make_document(source)
    block = document.blocks[0]
    block.text += " 2026年8月7日10:30完成复核。"
    time_value = "2026年8月7日10:30"

    class RecordingScorer:
        def __init__(self) -> None:
            self.categories: list[Category] = []

        def assess(
            self,
            _document: DocumentModel,
            findings: list[Finding],
        ) -> list[Finding]:
            self.categories = [finding.category for finding in findings]
            return []

    scorer = RecordingScorer()

    class TimeDetector(FakeDetector):
        combination_scorer = scorer

        def detect(self, target: DocumentModel) -> list[Finding]:
            findings = super().detect(target)
            time_start = target.blocks[0].text.index(time_value)
            time_finding = Finding(
                id="time-finding",
                category=Category.TIME,
                modality=Modality.TEXT,
                original=time_value,
                locations=[
                    SourceLocation(
                        part=target.blocks[0].location.part,
                        display=target.blocks[0].location.display,
                        block_id=target.blocks[0].id,
                        start=time_start,
                        end=time_start + len(time_value),
                    )
                ],
                detector="time-fixture",
                confidence=1.0,
                suggested_method=TransformMethod.SHIFT,
            )
            risk = Finding(
                id="time-risk",
                category=Category.COMBINATION_RISK,
                modality=Modality.TEXT,
                original="",
                locations=[],
                detector="risk-fixture",
                confidence=1.0,
                suggested_method=TransformMethod.GENERALIZE,
                metadata={"contributor_ids": (time_finding.id, findings[0].id)},
            )
            return [*findings, time_finding, risk]

    controller = LocalDesktopController(
        detector=TimeDetector(),
        image_analyzer_factory=FakeImageAnalyzer,
        rule_store=MemoryRuleStore(RuleLibrary()),
    )
    controller._adapter_for = lambda _path: FakeAdapter(document)  # type: ignore[method-assign]

    bundle = controller.scan(source, ProcessingMode.BALANCED)

    assert all(finding.category is not Category.TIME for finding in bundle.findings)
    assert all(finding.category is not Category.COMBINATION_RISK for finding in bundle.findings)
    assert Category.TIME not in scorer.categories
    assert time_value in bundle.preview.original
    assert time_value in bundle.preview.replacement


def test_pixel_redaction_without_boxes_falls_back_to_whole_image(
    tmp_path: Path,
) -> None:
    source = tmp_path / "fixture.docx"
    source.write_bytes(b"fixture")
    document = make_document(source, image=True)
    image_finding = Finding(
        id="image-phone",
        category=Category.PHONE,
        modality=Modality.IMAGE,
        original="13800138000",
        locations=[
            SourceLocation(
                part="word/media/image1.png",
                display="正文图片 1",
                image_id="image-001",
                bbox=(2, 2, 12, 12),
            )
        ],
        detector="fake-phone",
        confidence=1.0,
        suggested_method=TransformMethod.PIXEL_REDACT,
    )
    controller, _writer = controller_for(document, image_findings=[image_finding])
    bundle = controller.scan(source, ProcessingMode.BALANCED)
    controller.resolve_finding(
        "finding-001",
        FindingStatus.TRANSFORM,
        TransformMethod.ALIAS,
    )
    controller.resolve_finding(
        "image-phone",
        FindingStatus.TRANSFORM,
        TransformMethod.PIXEL_REDACT,
    )
    controller.set_image_regions("image-001", [])
    controller.resolve_image("image-001", ImageDisposition.PIXEL_REDACT)
    controller.resolve_hidden(bundle.hidden_items[0].id, "remove")

    controller.export(tmp_path, "Example#Pass123")
    assert [region.bbox for region in document.images[0].regions] == [(0, 0, 24, 18)]


def test_image_cannot_be_kept_when_confirmed_candidate_remains(
    tmp_path: Path,
) -> None:
    source = tmp_path / "fixture.docx"
    source.write_bytes(b"fixture")
    document = make_document(source, image=True)
    image_finding = Finding(
        id="image-finding",
        category=Category.PHONE,
        modality=Modality.IMAGE,
        original="13800138000",
        locations=[
            SourceLocation(
                part="word/media/image1.png",
                display="正文图片 1",
                image_id="image-001",
                bbox=(2, 2, 12, 12),
            )
        ],
        detector="fake-qr",
        confidence=1.0,
        suggested_method=TransformMethod.PIXEL_REDACT,
    )
    controller, _writer = controller_for(
        document,
        image_findings=[image_finding],
    )
    bundle = controller.scan(source, ProcessingMode.BALANCED)
    for finding in bundle.findings:
        controller.resolve_finding(
            finding.id,
            FindingStatus.TRANSFORM,
            finding.suggested_method,
        )
    controller.resolve_image("image-001", ImageDisposition.KEEP_REENCODED)
    controller.resolve_hidden(bundle.hidden_items[0].id, "remove")

    with pytest.raises(ValueError, match="不能选择"):
        controller.export(tmp_path, "Example#Pass123")


def test_reset_removes_task_state(tmp_path: Path) -> None:
    source = tmp_path / "fixture.docx"
    source.write_bytes(b"fixture")
    controller, _writer = controller_for(make_document(source))
    controller.scan(source, ProcessingMode.STRICT)
    controller.reset()
    assert not controller.is_review_complete()
    with pytest.raises(RuntimeError):
        controller.preview()


def test_rule_change_is_incremental_and_preserves_existing_decisions(tmp_path: Path) -> None:
    source = tmp_path / "fixture.docx"
    source.write_bytes(b"fixture")
    document = make_document(source)
    store = MemoryRuleStore(RuleLibrary())
    image_calls = 0

    def image_factory() -> FakeImageAnalyzer:
        nonlocal image_calls
        image_calls += 1
        return FakeImageAnalyzer()

    controller = LocalDesktopController(
        detector=FakeDetector(),
        image_analyzer_factory=image_factory,
        rule_store=store,
    )
    controller._adapter_for = lambda _path: FakeAdapter(document)  # type: ignore[method-assign]
    bundle = controller.scan(source, ProcessingMode.BALANCED)
    controller.resolve_finding(
        "finding-001",
        FindingStatus.TRANSFORM,
        TransformMethod.ALIAS,
    )
    store.library = store.library.add(
        RuleDefinition.fixed("13800138000", "138****8000", category="phone")
    )

    added = controller.apply_rules_incrementally()

    assert added == 1
    assert image_calls == 1
    original = next(item for item in bundle.findings if item.id == "finding-001")
    assert original.status is FindingStatus.TRANSFORM
    phone = next(item for item in bundle.findings if item.original == "13800138000")
    assert phone.metadata["rule_id"]


def test_incremental_rule_reuses_raw_image_ocr_cache(tmp_path: Path) -> None:
    source = tmp_path / "fixture.docx"
    source.write_bytes(b"fixture")
    document = make_document(source, image=True)
    ocr_finding = Finding(
        id="ocr-generic",
        category=Category.IMAGE_TEXT,
        modality=Modality.IMAGE,
        original="公安",
        locations=[
            SourceLocation(
                part="word/media/image1.png",
                display="正文图片 1",
                image_id="image-001",
            )
        ],
        detector="ocr",
        confidence=0.99,
        suggested_method=TransformMethod.PIXEL_REDACT,
    )
    store = MemoryRuleStore(RuleLibrary())
    image_calls = 0

    def image_factory() -> FakeImageAnalyzer:
        nonlocal image_calls
        image_calls += 1
        return FakeImageAnalyzer([ocr_finding])

    controller = LocalDesktopController(
        detector=EmptyDetector(),
        image_analyzer_factory=image_factory,
        rule_store=store,
    )
    controller._adapter_for = lambda _path: FakeAdapter(document)  # type: ignore[method-assign]
    bundle = controller.scan(source, ProcessingMode.BALANCED)
    assert not bundle.findings
    assert not bundle.images

    store.library = store.library.add(RuleDefinition.fixed("公安", "GA"))
    added = controller.apply_rules_incrementally()

    assert added == 1
    assert image_calls == 1
    assert len(bundle.images) == 1
    assert bundle.images[0].disposition is ImageDisposition.PENDING
    assert document.images[0].disposition is ImageDisposition.PENDING
    assert not controller.is_review_complete()
    assert bundle.findings[0].metadata["rule_id"]
    assert bundle.findings[0].replacement == "GA"

def test_manual_text_category_and_replacement_are_kept_in_mapping(
    tmp_path: Path,
) -> None:
    source = tmp_path / "fixture.docx"
    source.write_bytes(b"fixture")
    controller, writer = controller_for(make_document(source))
    bundle = controller.scan(source, ProcessingMode.BALANCED)

    manual = controller.add_manual_finding(
        "13800138000",
        Category.PHONE,
        TransformMethod.SIMULATE,
    )
    assert manual.detector == "manual:text-selection"
    assert manual.occurrence_count == 1
    changed = controller.change_finding_category(
        "finding-001",
        Category.USERNAME,
    )
    assert changed.status is FindingStatus.PENDING
    controller.resolve_finding(
        changed.id,
        FindingStatus.TRANSFORM,
        TransformMethod.SIMULATE,
        replacement="负责人账号甲",
    )
    controller.resolve_finding(
        manual.id,
        FindingStatus.TRANSFORM,
        TransformMethod.SIMULATE,
    )
    controller.resolve_hidden(bundle.hidden_items[0].id, "remove")

    controller.export(tmp_path, "Example#Pass123")
    mappings = writer.call["mappings"]
    changed_mapping = next(item for item in mappings if item.original == "林青河")
    assert changed_mapping.category is Category.USERNAME
    assert changed_mapping.replacement == "负责人账号甲"


def test_combination_risk_is_closed_only_by_contributor_decisions(
    tmp_path: Path,
) -> None:
    source = tmp_path / "fixture.docx"
    source.write_bytes(b"fixture")
    controller, _writer = controller_for(make_document(source))
    bundle = controller.scan(source, ProcessingMode.BALANCED)
    risk = Finding(
        category=Category.COMBINATION_RISK,
        modality=Modality.RELATION,
        original="",
        locations=[bundle.findings[0].locations[0]],
        detector="combination-risk",
        confidence=0.8,
        suggested_method=TransformMethod.GENERALIZE,
        metadata={"contributor_ids": ("finding-001",)},
    )
    bundle.findings.append(risk)

    with pytest.raises(ValueError, match="贡献字段"):
        controller.resolve_finding(
            risk.id,
            FindingStatus.TRANSFORM,
            TransformMethod.GENERALIZE,
        )
    controller.resolve_finding(
        "finding-001",
        FindingStatus.TRANSFORM,
        TransformMethod.ALIAS,
    )
    assert risk.status is FindingStatus.TRANSFORM


def test_ner_failure_blocks_export_and_is_visible_in_inventory(tmp_path: Path) -> None:
    source = tmp_path / "fixture.docx"
    source.write_bytes(b"fixture")
    document = make_document(source)
    writer = RecordingWriter()
    controller = LocalDesktopController(
        detector=WarningDetector(
            "NER_PIPELINE_FAILED: 本地中文实体识别执行失败，本次任务不能导出。"
        ),
        image_analyzer_factory=FakeImageAnalyzer,
        artifact_writer=writer,
    )
    controller._adapter_for = lambda _path: FakeAdapter(document)  # type: ignore[method-assign]

    bundle = controller.scan(source, ProcessingMode.BALANCED)
    controller.resolve_finding(
        "finding-001",
        FindingStatus.TRANSFORM,
        TransformMethod.ALIAS,
    )
    controller.resolve_hidden(bundle.hidden_items[0].id, "remove")

    assert bundle.blocking_issues
    assert any(item.status == "已阻断" for item in bundle.inventory)
    assert not controller.is_review_complete()
    with pytest.raises(ValueError, match="NER_PIPELINE_FAILED"):
        controller.export(tmp_path, "Example#Pass123")


def test_batch_confirmation_only_resolves_safe_ordinary_text(tmp_path: Path) -> None:
    source = tmp_path / "fixture.docx"
    source.write_bytes(b"fixture")
    document = make_document(source)
    controller, _writer = controller_for(document)
    bundle = controller.scan(source, ProcessingMode.BALANCED)
    ordinary = bundle.findings[0]
    low_confidence = Finding(
        id="finding-low",
        category=Category.OTHER,
        modality=Modality.TEXT,
        original="待判断",
        locations=[
            SourceLocation(
                part="word/document.xml",
                display="正文第 1 段",
                block_id=document.blocks[0].id,
                start=0,
                end=2,
            )
        ],
        detector="unknown",
        confidence=0.5,
        suggested_method=TransformMethod.GENERALIZE,
    )
    image_text = Finding(
        id="finding-image",
        category=Category.IMAGE_TEXT,
        modality=Modality.IMAGE,
        original="图片文字",
        locations=[
            SourceLocation(
                part="word/media/image1.png",
                display="图片 1",
                image_id="image-001",
            )
        ],
        detector="ocr",
        confidence=0.99,
        suggested_method=TransformMethod.PIXEL_REDACT,
    )
    combination = Finding(
        id="finding-combination",
        category=Category.COMBINATION_RISK,
        modality=Modality.TEXT,
        original="",
        locations=[],
        detector="combination",
        confidence=1.0,
        suggested_method=TransformMethod.GENERALIZE,
        metadata={"contributor_ids": [ordinary.id, low_confidence.id]},
    )
    safe_ordinary = Finding(
        id="finding-safe",
        category=Category.NAME,
        modality=Modality.TEXT,
        original="负责人",
        locations=[
            SourceLocation(
                part="word/document.xml",
                display="正文第 1 段",
                block_id=document.blocks[0].id,
                start=0,
                end=3,
            )
        ],
        detector="safe-fixture",
        confidence=0.99,
        suggested_method=TransformMethod.ALIAS,
    )
    bundle.findings.extend([low_confidence, image_text, combination, safe_ordinary])

    resolved = controller.resolve_ordinary_findings()

    assert [item.id for item in resolved] == [safe_ordinary.id]
    assert ordinary.status is FindingStatus.PENDING
    assert safe_ordinary.status is FindingStatus.TRANSFORM
    assert low_confidence.status is FindingStatus.PENDING
    assert image_text.status is FindingStatus.PENDING
    assert combination.status is FindingStatus.PENDING


def test_mandatory_rule_cannot_keep_original(tmp_path: Path) -> None:
    source = tmp_path / "fixture.docx"
    source.write_bytes(b"fixture")
    document = make_document(source)
    controller, _writer = controller_for(document)
    bundle = controller.scan(source, ProcessingMode.BALANCED)
    finding = bundle.findings[0]
    finding.metadata.update(
        {
            "rule_id": "rule-001",
            "rule_name": "必须使用代号",
            "rule_mandatory": True,
        }
    )

    with pytest.raises(ValueError, match="必须使用代号或删除"):
        controller.resolve_finding(
            finding.id,
            FindingStatus.KEEP_FALSE_POSITIVE,
            TransformMethod.KEEP,
            "人工判断",
        )
    with pytest.raises(ValueError, match="不能继续包含原文"):
        controller.resolve_finding(
            finding.id,
            FindingStatus.TRANSFORM,
            TransformMethod.ALIAS,
            replacement=f"{finding.original}-GA",
        )


def test_rules_apply_consistently_to_body_and_image_ocr(tmp_path: Path) -> None:
    source = tmp_path / "fixture.docx"
    source.write_bytes(b"fixture")
    document = make_document(source, image=True)
    document.blocks[0].text = "公安使用530网。"
    fixed = RuleDefinition.fixed(
        "公安",
        "GA",
        name="公安固定代号",
        category=Category.ORGANIZATION.value,
    )
    masked = RuleDefinition.standard(
        "网络名称中间隐藏",
        match_mode=MatchMode.CONTAINS,
        patterns=("530网",),
        action=ActionKind.MASK_MIDDLE,
        keep_prefix=1,
        keep_suffix=1,
        positive_examples=("530网",),
        category=Category.SYSTEM.value,
    )
    image_finding = Finding(
        id="ocr-rule",
        category=Category.IMAGE_TEXT,
        modality=Modality.IMAGE,
        original="公安",
        locations=[
            SourceLocation(
                part="word/media/image1.png",
                display="正文图片 1",
                image_id="image-001",
                bbox=(1, 1, 18, 12),
            )
        ],
        detector="ocr",
        confidence=0.95,
        suggested_method=TransformMethod.PIXEL_REDACT,
    )
    controller = LocalDesktopController(
        detector=EmptyDetector(),
        image_analyzer_factory=lambda: FakeImageAnalyzer([image_finding]),
        rule_store=MemoryRuleStore(RuleLibrary((fixed, masked))),
    )
    controller._adapter_for = lambda _path: FakeAdapter(document)  # type: ignore[method-assign]

    bundle = controller.scan(source, ProcessingMode.BALANCED)

    body_ga = next(
        item
        for item in bundle.findings
        if item.original == "公安" and item.modality is Modality.TEXT
    )
    image_ga = next(
        item
        for item in bundle.findings
        if item.original == "公安" and item.modality is Modality.IMAGE
    )
    network = next(item for item in bundle.findings if item.original == "530网")
    assert body_ga.replacement == image_ga.replacement == "GA"
    assert network.replacement == "5**网"
    assert body_ga.status is FindingStatus.TRANSFORM
    assert network.metadata["rule_name"] == "网络名称中间隐藏"
    assert network.metadata["rule_mandatory"] is True

    controller.resolve_finding(
        body_ga.id,
        FindingStatus.TRANSFORM,
        TransformMethod.ALIAS,
        replacement="GA-本次",
    )

    assert body_ga.replacement == image_ga.replacement == "GA-本次"


def test_rule_store_failure_blocks_scan_before_reading_document(tmp_path: Path) -> None:
    source = tmp_path / "fixture.docx"
    source.write_bytes(b"fixture")
    document = make_document(source)
    adapter = FakeAdapter(document)
    controller = LocalDesktopController(
        detector=EmptyDetector(),
        image_analyzer_factory=FakeImageAnalyzer,
        rule_store=BrokenRuleStore(),
    )
    controller._adapter_for = lambda _path: adapter  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="规则库无法安全读取"):
        controller.scan(source, ProcessingMode.BALANCED)


def test_reviewed_mapping_can_be_saved_for_future_tasks() -> None:
    store = MemoryRuleStore(RuleLibrary())
    controller = LocalDesktopController(
        detector=EmptyDetector(),
        image_analyzer_factory=FakeImageAnalyzer,
        rule_store=store,
    )

    saved = controller.save_fixed_rule("公安", "GA", Category.ORGANIZATION)
    duplicate = controller.save_fixed_rule("公安", "GA", Category.ORGANIZATION)

    assert duplicate.id == saved.id
    assert store.library.rules == (saved,)
    with pytest.raises(RuleConflictError, match="已有不同代号"):
        controller.save_fixed_rule("公安", "代号乙", Category.ORGANIZATION)


def test_partial_rule_overlap_keeps_broader_candidate_for_safe_review(
    tmp_path: Path,
) -> None:
    source = tmp_path / "fixture.docx"
    source.write_bytes(b"fixture")
    document = make_document(source)
    block = document.blocks[0]
    start = block.text.index("林青河")
    end = block.text.index("。")
    broad_original = block.text[start:end]

    class BroadDetector:
        combination_scorer = None

        def detect(self, _document: DocumentModel) -> list[Finding]:
            return [
                Finding(
                    id="broad-sensitive-value",
                    category=Category.NAME,
                    modality=Modality.TEXT,
                    original=broad_original,
                    locations=[
                        SourceLocation(
                            part=block.location.part,
                            display=block.location.display,
                            block_id=block.id,
                            start=start,
                            end=end,
                        )
                    ],
                    detector="broad-fixture",
                    confidence=1.0,
                    suggested_method=TransformMethod.ALIAS,
                )
            ]

    store = MemoryRuleStore(
        RuleLibrary((RuleDefinition.fixed("林青河", "人员甲", name="姓名固定代号"),))
    )
    controller = LocalDesktopController(
        detector=BroadDetector(),
        image_analyzer_factory=FakeImageAnalyzer,
        rule_store=store,
    )
    controller._adapter_for = lambda _path: FakeAdapter(document)  # type: ignore[method-assign]

    bundle = controller.scan(source, ProcessingMode.BALANCED)
    broad = next(item for item in bundle.findings if item.id == "broad-sensitive-value")

    assert broad.status is FindingStatus.PENDING
    assert broad.metadata["rule_mandatory"] is True
    assert broad.metadata["rule_partial_overlap"] is True
    assert "13800138000" in broad.original

    resolved = controller.resolve_ordinary_findings()

    assert [item.id for item in resolved] == [broad.id]
    assert broad.status is FindingStatus.TRANSFORM
    assert "林青河" not in broad.replacement
    assert "13800138000" not in broad.replacement
    assert "13800138000" not in controller.preview().replacement


def test_export_blocks_when_rule_library_changed_after_scan(tmp_path: Path) -> None:
    source = tmp_path / "fixture.docx"
    source.write_bytes(b"fixture")
    document = make_document(source)
    store = MemoryRuleStore(RuleLibrary())
    writer = RecordingWriter()
    controller = LocalDesktopController(
        detector=FakeDetector(),
        image_analyzer_factory=FakeImageAnalyzer,
        artifact_writer=writer,
        rule_store=store,
    )
    controller._adapter_for = lambda _path: FakeAdapter(document)  # type: ignore[method-assign]
    controller.scan(source, ProcessingMode.BALANCED)
    store.library = store.library.add(RuleDefinition.fixed("林青河", "人员甲"))

    with pytest.raises(ValueError, match="重新检查"):
        controller.export(tmp_path, "Example#Pass123")

    assert writer.call == {}


def test_image_recognition_failure_requires_whole_image_safe_action(
    tmp_path: Path,
) -> None:
    source = tmp_path / "fixture.docx"
    source.write_bytes(b"fixture")
    document = make_document(source, image=True)
    writer = RecordingWriter()
    controller = LocalDesktopController(
        detector=FakeDetector(),
        image_analyzer_factory=lambda: WarningImageAnalyzer(
            "IMAGE_OCR_FAILED: 本地OCR执行失败；该图片必须整图安全处理。"
        ),
        artifact_writer=writer,
    )
    controller._adapter_for = lambda _path: FakeAdapter(document)  # type: ignore[method-assign]

    bundle = controller.scan(source, ProcessingMode.BALANCED)
    controller.resolve_finding(
        "finding-001",
        FindingStatus.TRANSFORM,
        TransformMethod.ALIAS,
    )
    controller.resolve_hidden(bundle.hidden_items[0].id, "remove")
    controller.resolve_image("image-001", ImageDisposition.KEEP_REENCODED)
    assert not controller.is_review_complete()

    controller.set_image_regions("image-001", [(1, 2, 10, 12)])
    controller.resolve_image("image-001", ImageDisposition.PIXEL_REDACT)
    assert controller.is_review_complete()
    controller.export(tmp_path, "Example#Pass123")

    assert bundle.capability_warnings
    assert [region.bbox for region in document.images[0].regions] == [(0, 0, 24, 18)]
