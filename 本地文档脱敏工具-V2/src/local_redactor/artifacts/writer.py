from __future__ import annotations

import os
import shutil
import uuid
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path

from local_redactor.core.common import contains_normalized_original
from local_redactor.interfaces import DocumentAdapter
from local_redactor.models import (
    DocumentKind,
    DocumentModel,
    ExportArtifacts,
    Finding,
    FindingStatus,
    MappingEntry,
)

from .encryption import create_encrypted_mapping, create_local_mapping
from .report import render_technical_report
from .validation import (
    ArtifactValidationError,
    rescan_ai_copy,
    sha256_file,
    validate_delivery_layout,
    validate_report_isolated,
)


class ArtifactExportError(RuntimeError):
    """Raised when a complete, verified delivery package cannot be published."""


class ArtifactWriter:
    """Build and atomically publish one local document-delivery package."""

    def __init__(
        self,
        adapter: DocumentAdapter,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._adapter = adapter
        self._clock = clock or datetime.now

    def export_task(
        self,
        document: DocumentModel,
        findings: Sequence[Finding],
        mappings: Sequence[MappingEntry],
        result_root: Path,
        mapping_password: str,
    ) -> ExportArtifacts:
        finding_snapshot = list(findings)
        mapping_snapshot = list(mappings)
        self._validate_request(
            document,
            finding_snapshot,
            mapping_snapshot,
            mapping_password,
        )

        destination_parent = Path(result_root)
        if destination_parent.exists() and not destination_parent.is_dir():
            raise ArtifactExportError("结果位置不是文件夹")
        destination_parent.mkdir(parents=True, exist_ok=True)

        task_name = f"脱敏结果_{self._clock().strftime('%Y%m%d_%H%M%S')}"
        final_root = destination_parent / task_name
        if final_root.exists():
            raise ArtifactExportError("同一时间标识的结果目录已存在，请稍后重试")
        staging_root = destination_parent / f".{task_name}.staging-{uuid.uuid4().hex}"
        ai_dir = staging_root / "AI交付"
        local_dir = staging_root / "本地保管"
        suffix = ".docx" if document.kind is DocumentKind.DOCX else ".xlsx"
        ai_copy_name = f"AI分析副本{suffix}"
        ai_copy = ai_dir / ai_copy_name
        encrypted_mapping = local_dir / "脱敏映射表.xlsx"
        report = local_dir / "脱敏检查报告.html"

        published = False
        try:
            ai_dir.mkdir(parents=True)
            local_dir.mkdir(parents=True)

            self._adapter.export(document, finding_snapshot, ai_copy)
            rescan_ai_copy(
                ai_copy,
                document.kind,
                finding_snapshot,
                self._adapter,
            )

            if mapping_password:
                create_encrypted_mapping(
                    mapping_snapshot,
                    encrypted_mapping,
                    mapping_password,
                )
            else:
                create_local_mapping(mapping_snapshot, encrypted_mapping)
            hashes = {
                "AI分析副本": sha256_file(ai_copy),
                "脱敏映射表": sha256_file(encrypted_mapping),
            }
            report.write_text(
                render_technical_report(
                    finding_snapshot,
                    document=document,
                    hashes=hashes,
                ),
                encoding="utf-8",
                newline="\n",
            )
            forbidden_report_values = {
                mapping_password,
                *(finding.original for finding in finding_snapshot),
                *(finding.replacement for finding in finding_snapshot),
                *(mapping.original for mapping in mapping_snapshot),
                *(mapping.replacement for mapping in mapping_snapshot),
                *(mapping.rule_source for mapping in mapping_snapshot),
            }
            validate_report_isolated(report, forbidden_report_values)
            validate_delivery_layout(staging_root, ai_copy_name=ai_copy_name)
            report_hash = sha256_file(report)

            os.replace(staging_root, final_root)
            published = True
            final_ai = final_root / "AI交付" / ai_copy_name
            final_mapping = final_root / "本地保管" / "脱敏映射表.xlsx"
            final_report = final_root / "本地保管" / "脱敏检查报告.html"
            return ExportArtifacts(
                result_root=final_root,
                ai_copy=final_ai,
                encrypted_mapping=final_mapping,
                report=final_report,
                hashes={
                    "ai_copy": hashes["AI分析副本"],
                    "encrypted_mapping": hashes["脱敏映射表"],
                    "report": report_hash,
                },
            )
        except (ArtifactExportError, ArtifactValidationError):
            raise
        except Exception as exc:
            raise ArtifactExportError("交付物生成未完成，未发布结果目录") from exc
        finally:
            if not published:
                _remove_staging(staging_root)

    @staticmethod
    def _validate_request(
        document: DocumentModel,
        findings: Sequence[Finding],
        mappings: Sequence[MappingEntry],
        password: str,
    ) -> None:
        if document.kind not in {DocumentKind.DOCX, DocumentKind.XLSX}:
            raise ArtifactExportError("只支持 DOCX 或 XLSX 交付物")
        if any(finding.status is FindingStatus.PENDING for finding in findings):
            raise ArtifactExportError("仍有候选未完成复核")
        if any(
            bool(finding.metadata.get("rule_mandatory"))
            and finding.status is FindingStatus.KEEP_FALSE_POSITIVE
            for finding in findings
        ):
            raise ArtifactExportError("命中强制规则的内容不能保留原文")
        if any(
            finding.status is FindingStatus.TRANSFORM
            and contains_normalized_original(
                finding.original,
                finding.replacement,
            )
            for finding in findings
        ):
            raise ArtifactExportError("处理后的内容仍保留完整原文，不能生成文件")
        if any(image.disposition.value == "pending" for image in document.images):
            raise ArtifactExportError("仍有图片未作出处理决定")
        if document.inventory.unresolved_items:
            raise ArtifactExportError("仍有隐藏内容或对象未作出处理决定")
        if password and (len(password) < 12 or _password_groups(password) < 3):
            raise ArtifactExportError("映射表密码不符合强度要求")
        mapping_ids = [mapping.mapping_id for mapping in mappings]
        if len(mapping_ids) != len(set(mapping_ids)):
            raise ArtifactExportError("脱敏映射编号重复")
        if any(
            not mapping.mapping_id.strip() or not mapping.original or mapping.occurrence_count < 1
            for mapping in mappings
        ):
            raise ArtifactExportError("脱敏映射表存在不完整记录")


def _password_groups(password: str) -> int:
    return sum(
        (
            any(character.islower() for character in password),
            any(character.isupper() for character in password),
            any(character.isdigit() for character in password),
            any(not character.isalnum() for character in password),
        )
    )


def _remove_staging(path: Path) -> None:
    if not path.exists():
        return
    try:
        shutil.rmtree(path)
    except OSError as exc:
        raise ArtifactExportError("未完成任务目录无法清理") from exc
