from __future__ import annotations

import hashlib
import re
import zipfile
from collections.abc import Iterable, Sequence
from pathlib import Path

from local_redactor.core.common import contains_normalized_original
from local_redactor.interfaces import DocumentAdapter
from local_redactor.models import (
    Category,
    DocumentKind,
    DocumentModel,
    Finding,
    FindingStatus,
    Modality,
)
from local_redactor.office import OoxmlSecurityError, preflight_ooxml

_ACTIVE_PART_MARKERS = (
    "vbaproject",
    "activex",
    "/embeddings/",
)
_ACTIVE_CONTENT_TYPE_MARKERS = (
    "macroenabled",
    "vbaproject",
    "activex",
    "oleobject",
)
_ACTIVE_RELATION_MARKERS = (
    "oleobject",
    "attachedtemplate",
    "externallink",
)
_DIRECT_NUMERIC_CATEGORIES = {
    Category.ID_CARD,
    Category.PHONE,
    Category.ACCOUNT,
    Category.CASE_ID,
    Category.DEVICE_ID,
}
_MIN_DIRECT_NUMERIC_LENGTH = 6
_MIN_GENERIC_NUMERIC_LENGTH = 8


class ArtifactValidationError(RuntimeError):
    """Raised when actual staged output bytes fail an independent rescan."""


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def forbidden_originals(findings: Sequence[Finding]) -> tuple[str, ...]:
    values = {
        finding.original
        for finding in findings
        if finding.status in {FindingStatus.TRANSFORM, FindingStatus.REMOVE}
        and finding.original
        and _is_scannable_original(finding)
    }
    return tuple(sorted(values, key=len, reverse=True))


def _is_scannable_original(finding: Finding) -> bool:
    value = finding.original.strip()
    if not value:
        return False
    if finding.modality in {Modality.METADATA, Modality.HIDDEN} or (
        finding.locations
        and all(location.part.startswith("docProps/") for location in finding.locations)
    ):
        return False
    if bool(finding.metadata.get("rule_mandatory")):
        return True
    compact_digits = re.sub(r"[\s‐‑‒–—―_-]+", "", value)
    if compact_digits.isdecimal():
        minimum = (
            _MIN_DIRECT_NUMERIC_LENGTH
            if finding.category in _DIRECT_NUMERIC_CATEGORIES
            else _MIN_GENERIC_NUMERIC_LENGTH
        )
        return len(compact_digits) >= minimum
    return len(value) >= 3 or re.search(r"[\u4e00-\u9fff]", value) is not None


def rescan_ai_copy(
    path: Path,
    kind: DocumentKind,
    findings: Sequence[Finding],
    adapter: DocumentAdapter,
) -> None:
    """Re-open the actual AI copy and reject content or package leakage."""

    target = Path(path)
    expected_suffix = ".docx" if kind is DocumentKind.DOCX else ".xlsx"
    if target.suffix.casefold() != expected_suffix or not target.is_file():
        raise ArtifactValidationError("AI 分析副本格式或路径不正确")
    if not zipfile.is_zipfile(target):
        raise ArtifactValidationError("AI 分析副本不是有效的现代 Office 文件")

    try:
        preflight = preflight_ooxml(target, kind)
    except OoxmlSecurityError as exc:
        raise ArtifactValidationError("AI 分析副本未通过 OOXML 安全复检") from exc
    if any(relationship.external for relationship in preflight.relationships):
        raise ArtifactValidationError("AI 分析副本仍包含外部关系")
    if any(
        marker in name.casefold()
        for name in preflight.part_names
        for marker in _ACTIVE_PART_MARKERS
    ):
        raise ArtifactValidationError("AI 分析副本仍包含宏、ActiveX 或 OLE 部件")
    if any(
        marker in content_type.casefold()
        for content_type in preflight.content_types.values()
        for marker in _ACTIVE_CONTENT_TYPE_MARKERS
    ):
        raise ArtifactValidationError("AI 分析副本仍包含活动内容类型")
    if any(
        marker in relationship.relationship_type.casefold()
        for relationship in preflight.relationships
        for marker in _ACTIVE_RELATION_MARKERS
    ):
        raise ArtifactValidationError("AI 分析副本仍包含活动或嵌入对象关系")

    try:
        rescanned = adapter.scan(target)
    except Exception as exc:
        raise ArtifactValidationError("AI 分析副本无法重新打开并建立文档模型") from exc
    visible_text = "\n".join(
        [
            *(block.text for block in rescanned.blocks),
            *(image.alt_text for image in rescanned.images),
            *(str(value) for value in rescanned.document_properties.values()),
        ]
    )
    originals = forbidden_originals(findings)
    for original in originals:
        if contains_normalized_original(original, visible_text):
            fingerprint = hashlib.sha256(original.encode("utf-8")).hexdigest()[:12]
            raise ArtifactValidationError(
                f"AI 分析副本仍包含已确认处理的原值（指纹：{fingerprint}）"
            )

    _scan_package_bytes(target, originals)
    _rescan_visual_media(rescanned, findings, originals)


def validate_report_isolated(
    report_path: Path,
    forbidden_values: Iterable[str],
) -> None:
    data = Path(report_path).read_bytes()
    for value in forbidden_values:
        if not value:
            continue
        if value.encode("utf-8") in data or value.encode("utf-16le") in data:
            raise ArtifactValidationError("技术报告包含原值、映射值或密码")


def validate_delivery_layout(
    staging_root: Path,
    *,
    ai_copy_name: str,
) -> None:
    root = Path(staging_root)
    ai_root = root / "AI交付"
    local_root = root / "本地保管"
    ai_files = {
        path.relative_to(ai_root).as_posix() for path in ai_root.rglob("*") if path.is_file()
    }
    local_files = {
        path.relative_to(local_root).as_posix() for path in local_root.rglob("*") if path.is_file()
    }
    if ai_files != {ai_copy_name}:
        raise ArtifactValidationError("AI交付目录包含未允许的文件")
    if local_files != {"脱敏映射表.xlsx", "脱敏检查报告.html"}:
        raise ArtifactValidationError("本地保管目录文件不完整或包含额外文件")
    if {"脱敏映射表.xlsx", "脱敏检查报告.html"} & ai_files:
        raise ArtifactValidationError("本地保管文件被错误放入 AI交付目录")


def _scan_package_bytes(path: Path, originals: Sequence[str]) -> None:
    if not originals:
        return
    encoded = tuple(
        encoding
        for original in originals
        for encoding in (
            original.encode("utf-8"),
            original.encode("utf-16le"),
            original.encode("utf-16be"),
        )
    )
    with zipfile.ZipFile(path, mode="r") as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            content = archive.read(info)
            for value in encoded:
                if value in content:
                    fingerprint = hashlib.sha256(value).hexdigest()[:12]
                    raise ArtifactValidationError(
                        "AI 分析副本 OOXML 部件仍包含已处理原值"
                        f"（部件：{info.filename}，编码指纹：{fingerprint}）"
                    )


def _rescan_visual_media(
    document: DocumentModel,
    source_findings: Sequence[Finding],
    originals: Sequence[str],
) -> None:
    """Run OCR and QR detection again on the actual rebuilt media bytes."""

    if not document.images:
        return
    from local_redactor.runtime import create_local_image_analyzer

    result = create_local_image_analyzer().analyze(document)
    blocking_warnings = [
        warning
        for warning in result.warnings
        if any(
            code in warning
            for code in (
                "IMAGE_DECODE_FAILED",
                "IMAGE_OCR_FAILED",
                "IMAGE_OCR_UNAVAILABLE",
                "IMAGE_QR_FAILED",
                "IMAGE_QR_UNAVAILABLE",
            )
        )
    ]
    if blocking_warnings:
        raise ArtifactValidationError("AI 分析副本图片未能完成 OCR/二维码复扫")

    output_text = "\n".join(
        finding.original
        for finding in result.findings
        if finding.original
        and (
            finding.category is Category.IMAGE_TEXT
            or finding.detector.startswith(("ocr:", "qr:"))
            or finding.metadata.get("from_image_text")
        )
    )
    normalized_output = _normalize_visual_text(output_text)
    mandatory_visual_originals = {
        _normalize_visual_text(finding.original)
        for finding in source_findings
        if bool(finding.metadata.get("rule_mandatory")) and finding.original
    }
    for original in originals:
        normalized_original = _normalize_visual_text(original)
        minimum_length = 1 if normalized_original in mandatory_visual_originals else 2
        if (
            len(normalized_original) >= minimum_length
            and normalized_original in normalized_output
        ):
            raise ArtifactValidationError("AI 分析副本图片 OCR 仍识别到已处理原值")

    source_qr_removed = any(
        finding.category is Category.QR_CODE
        and finding.status in {FindingStatus.TRANSFORM, FindingStatus.REMOVE}
        for finding in source_findings
    )
    if source_qr_removed and any(
        finding.category is Category.QR_CODE for finding in result.findings
    ):
        raise ArtifactValidationError("AI 分析副本图片仍能识别出二维码")


def _normalize_visual_text(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", value).casefold()
