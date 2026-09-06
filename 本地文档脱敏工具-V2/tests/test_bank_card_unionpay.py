from __future__ import annotations

from pathlib import Path

from local_redactor.core.detectors import StructuredDetector, _luhn_valid
from local_redactor.models import Category, DocumentKind, DocumentModel, SourceLocation, TextBlock


def _document(text: str) -> DocumentModel:
    return DocumentModel(
        kind=DocumentKind.XLSX,
        source_path=Path("sample.xlsx"),
        source_sha256="0" * 64,
        display_name="sample.xlsx",
        blocks=[
            TextBlock(
                text=text,
                location=SourceLocation(part="xl/sharedStrings.xml", display="单元格", block_id="c1", cell="B2"),
                id="c1",
                block_kind="cell",
            )
        ],
    )


def test_sample_unionpay_number_detected_without_luhn() -> None:
    sample = "6222020200066288888"
    assert not _luhn_valid(sample)
    findings = StructuredDetector().detect(_document(f"卡号 {sample}"))
    cards = [item for item in findings if "6222020200066288888" in item.original.replace(" ", "")]
    assert cards
    assert cards[0].category is Category.ACCOUNT
    assert cards[0].confidence >= 0.8
    assert cards[0].metadata.get("unionpay_bin") is True
    assert cards[0].metadata.get("luhn_valid") is False


def test_luhn_valid_card_still_detected() -> None:
    valid = "4111111111111111"
    assert _luhn_valid(valid)
    findings = StructuredDetector().detect(_document(valid))
    cards = [item for item in findings if "".join(ch for ch in item.original if ch.isdigit()) == valid]
    assert cards
    assert cards[0].confidence >= 0.99 or cards[0].metadata.get("luhn_valid") is True
