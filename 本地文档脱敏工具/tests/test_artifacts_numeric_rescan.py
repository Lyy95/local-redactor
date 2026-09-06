from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from docx import Document

from local_redactor.artifacts.validation import (
    ArtifactValidationError,
    _scan_package_bytes,
    rescan_ai_copy,
)
from local_redactor.artifacts.validation import (
    forbidden_originals as artifact_forbidden_originals,
)
from local_redactor.models import (
    Category,
    DocumentKind,
    DocumentModel,
    Finding,
    FindingStatus,
    Modality,
    SourceLocation,
    TextBlock,
    TransformMethod,
)
from local_redactor.office.common import (
    forbidden_originals as office_forbidden_originals,
)


def _finding(category: Category, original: str) -> Finding:
    return Finding(
        category=category,
        modality=Modality.TEXT,
        original=original,
        locations=[
            SourceLocation(
                part="word/document.xml",
                display="正文第1段",
                block_id="paragraph-1",
            )
        ],
        detector="fictional-fixture",
        confidence=1.0,
        suggested_method=TransformMethod.SIMULATE,
        status=FindingStatus.TRANSFORM,
        replacement="[虚构替代值]",
    )


def test_numeric_sensitive_originals_are_not_filtered_out() -> None:
    findings = [
        _finding(Category.PHONE, "13812345678"),
        _finding(Category.ID_CARD, "440100199001010017"),
        _finding(Category.ACCOUNT, "6222000012345678"),
        _finding(Category.ACCOUNT, "12345"),
        _finding(Category.MONEY, "123456"),
    ]

    expected = {
        "13812345678",
        "440100199001010017",
        "6222000012345678",
    }
    assert set(artifact_forbidden_originals(findings)) == expected
    assert set(office_forbidden_originals(findings)) == expected


def test_mandatory_short_original_is_never_filtered_out() -> None:
    mandatory = _finding(Category.SYSTEM, "AB")
    mandatory.metadata["rule_mandatory"] = True

    assert artifact_forbidden_originals([mandatory]) == ("AB",)
    assert office_forbidden_originals([mandatory]) == ("AB",)


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16le", "utf-16be"])
def test_ooxml_package_byte_scan_rejects_numeric_original(
    tmp_path: Path,
    encoding: str,
) -> None:
    original = "13812345678"
    package = tmp_path / f"numeric-{encoding}.zip"
    with zipfile.ZipFile(package, mode="w") as archive:
        archive.writestr("word/custom-part.bin", original.encode(encoding))

    with pytest.raises(ArtifactValidationError, match="OOXML"):
        _scan_package_bytes(package, (original,))


def test_visible_rescan_rejects_pure_numeric_phone(tmp_path: Path) -> None:
    original = "13812345678"
    path = tmp_path / "AI分析副本.docx"
    document = Document()
    document.add_paragraph("虚构联系人号码：" + original)
    document.save(path)

    rescanned = DocumentModel(
        kind=DocumentKind.DOCX,
        source_path=path,
        source_sha256="0" * 64,
        display_name=path.name,
        blocks=[
            TextBlock(
                text="虚构联系人号码：" + original,
                location=SourceLocation(
                    part="word/document.xml",
                    display="正文第1段",
                    block_id="paragraph-1",
                ),
            )
        ],
    )

    class StaticAdapter:
        def scan(self, _path: Path) -> DocumentModel:
            return rescanned

        def export(
            self,
            document: DocumentModel,
            findings: list[Finding],
            target_path: Path,
        ) -> None:
            del document, findings, target_path

    with pytest.raises(ArtifactValidationError, match="仍包含"):
        rescan_ai_copy(
            path,
            DocumentKind.DOCX,
            [_finding(Category.PHONE, original)],
            StaticAdapter(),
        )
