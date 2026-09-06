from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from local_redactor.artifacts.validation import (
    ArtifactValidationError,
    _rescan_visual_media,
)
from local_redactor.models import (
    Category,
    DocumentKind,
    DocumentModel,
    Finding,
    FindingStatus,
    ImageObject,
    Modality,
    SourceLocation,
    TransformMethod,
)


def document_with_image() -> DocumentModel:
    return DocumentModel(
        kind=DocumentKind.DOCX,
        source_path=Path("fictional.docx"),
        source_sha256="0" * 64,
        display_name="fictional.docx",
        images=[
            ImageObject(
                id="output-image",
                source_part="word/media/image1.png",
                location=SourceLocation(
                    part="word/document.xml",
                    display="图片 1",
                    image_id="output-image",
                ),
                content=b"fake-output-bytes",
            )
        ],
    )


def finding(
    category: Category,
    original: str,
    *,
    detector: str,
) -> Finding:
    return Finding(
        category=category,
        modality=Modality.IMAGE,
        original=original,
        locations=[
            SourceLocation(
                part="word/media/image1.png",
                display="图片 1",
                image_id="output-image",
                bbox=(1, 1, 5, 5),
            )
        ],
        detector=detector,
        confidence=1.0,
        suggested_method=TransformMethod.PIXEL_REDACT,
        status=FindingStatus.TRANSFORM,
    )


class FakeAnalyzer:
    def __init__(self, findings: list[Finding], warnings: list[str] | None = None) -> None:
        self.findings = findings
        self.warnings = warnings or []

    def analyze(self, _document: DocumentModel) -> Any:
        return SimpleNamespace(findings=self.findings, warnings=self.warnings)


def install_analyzer(monkeypatch: pytest.MonkeyPatch, analyzer: FakeAnalyzer) -> None:
    monkeypatch.setattr(
        "local_redactor.runtime.create_local_image_analyzer",
        lambda: analyzer,
    )


def test_visual_rescan_rejects_ocr_original_after_normalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = finding(
        Category.IMAGE_TEXT,
        "联系人 林青河 13800000000",
        detector="ocr:local",
    )
    install_analyzer(monkeypatch, FakeAnalyzer([output]))

    with pytest.raises(ArtifactValidationError, match="OCR"):
        _rescan_visual_media(
            document_with_image(),
            [],
            ("林青河",),
        )


def test_visual_rescan_rejects_numeric_original_with_ocr_spacing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = finding(
        Category.IMAGE_TEXT,
        "屏幕号码 138 1234 5678",
        detector="ocr:local",
    )
    install_analyzer(monkeypatch, FakeAnalyzer([output]))

    with pytest.raises(ArtifactValidationError, match="OCR"):
        _rescan_visual_media(
            document_with_image(),
            [],
            ("13812345678",),
        )


def test_visual_rescan_rejects_remaining_qr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = finding(
        Category.QR_CODE,
        "https://demo.example.invalid",
        detector="qr:opencv-local",
    )
    output = finding(
        Category.QR_CODE,
        "https://demo.example.invalid",
        detector="qr:opencv-local",
    )
    install_analyzer(monkeypatch, FakeAnalyzer([output]))

    with pytest.raises(ArtifactValidationError, match="二维码"):
        _rescan_visual_media(
            document_with_image(),
            [source],
            (),
        )


def test_visual_rescan_fails_closed_when_ocr_cannot_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_analyzer(
        monkeypatch,
        FakeAnalyzer(
            [],
            ["IMAGE_OCR_FAILED: 本地OCR执行失败；该图片仍须人工复核。"],
        ),
    )

    with pytest.raises(ArtifactValidationError, match="复扫"):
        _rescan_visual_media(document_with_image(), [], ())


def test_visual_rescan_rejects_one_character_mandatory_original(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = finding(Category.IMAGE_TEXT, "A", detector="ocr:local")
    source.metadata["rule_mandatory"] = True
    output = finding(Category.IMAGE_TEXT, "a", detector="ocr:local")
    install_analyzer(monkeypatch, FakeAnalyzer([output]))

    with pytest.raises(ArtifactValidationError, match="OCR"):
        _rescan_visual_media(
            document_with_image(),
            [source],
            ("A",),
        )
