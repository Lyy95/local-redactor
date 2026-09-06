from __future__ import annotations

from io import BytesIO
from pathlib import Path

import numpy
from PIL import Image

from local_redactor.core import LocalImageAnalyzer
from local_redactor.models import (
    Category,
    DocumentKind,
    DocumentModel,
    ImageDisposition,
    ImageObject,
    Modality,
    SourceLocation,
)


def _document(*, content: bytes = b"not-an-image", alt_text: str = "") -> DocumentModel:
    image = ImageObject(
        source_part="word/media/image1.png",
        location=SourceLocation(
            part="word/document.xml",
            display="正文图片1",
            image_id="source-image-1",
        ),
        content=content,
        alt_text=alt_text,
    )
    return DocumentModel(
        kind=DocumentKind.DOCX,
        source_path=Path("fictional.docx"),
        source_sha256="2" * 64,
        display_name="虚构图片文档.docx",
        images=[image],
    )


def test_missing_image_dependencies_never_auto_approve_an_image() -> None:
    document = _document()
    analyzer = LocalImageAnalyzer(
        auto_load_qr=False,
        enable_seal_heuristic=False,
        enable_signature_heuristic=False,
    )

    result = analyzer.analyze(document)

    assert result.requires_manual_review
    assert result.mandatory_review_ids == [document.images[0].id]
    assert document.images[0].disposition is ImageDisposition.PENDING
    assert any("IMAGE_OCR_UNAVAILABLE" in warning for warning in result.warnings)
    assert any("IMAGE_FACE_MODEL_UNAVAILABLE" in warning for warning in result.warnings)
    assert any("IMAGE_QR_UNAVAILABLE" in warning for warning in result.warnings)
    assert any("IMAGE_DECODE_FAILED" in warning for warning in result.warnings)


def test_ocr_text_enters_the_same_structured_detection_flow() -> None:
    class FakeOcr:
        def __call__(self, image: object) -> tuple[list[list[object]], None]:
            del image
            return (
                [
                    [
                        [[1, 2], [101, 2], [101, 24], [1, 24]],
                        "联系电话13812345678",
                        0.97,
                    ]
                ],
                None,
            )

    document = _document(alt_text="虚构图片说明")
    analyzer = LocalImageAnalyzer(
        ocr_engine=FakeOcr(),
        image_decoder=lambda content: object(),
        auto_load_qr=False,
        enable_seal_heuristic=False,
        enable_signature_heuristic=False,
    )

    result = analyzer.analyze(document)

    assert any(finding.category is Category.IMAGE_TEXT for finding in result.findings)
    phone = next(finding for finding in result.findings if finding.category is Category.PHONE)
    assert phone.original == "13812345678"
    assert phone.modality is Modality.IMAGE
    assert phone.locations[0].bbox == (1, 2, 102, 25)
    assert result.requires_manual_review


def test_injected_face_detector_creates_only_a_candidate() -> None:
    document = _document()
    analyzer = LocalImageAnalyzer(
        face_detector=lambda image: [[10, 20, 30, 40, 0.91]],
        image_decoder=lambda content: object(),
        auto_load_qr=False,
        enable_seal_heuristic=False,
        enable_signature_heuristic=False,
    )

    result = analyzer.analyze(document)

    face = next(finding for finding in result.findings if finding.category is Category.PHOTO)
    assert face.locations[0].bbox == (10, 20, 40, 60)
    assert face.metadata["candidate_only"] is True
    assert document.images[0].disposition is ImageDisposition.PENDING


def test_rapidocr_numpy_arrays_are_parsed_without_truth_value_error() -> None:
    class RapidOutput:
        txts = ("签名：林澄",)
        boxes = numpy.array([[[2.0, 3.0], [82.0, 3.0], [82.0, 28.0], [2.0, 28.0]]])
        scores = numpy.array([0.96])

    document = _document()
    analyzer = LocalImageAnalyzer(
        ocr_engine=lambda image: RapidOutput(),
        image_decoder=lambda content: object(),
        auto_load_qr=False,
        enable_seal_heuristic=False,
        enable_signature_heuristic=False,
    )

    result = analyzer.analyze(document)

    assert not any("IMAGE_OCR_FAILED" in warning for warning in result.warnings)
    image_text = next(
        finding for finding in result.findings if finding.category is Category.IMAGE_TEXT
    )
    assert image_text.original == "签名：林澄"
    assert image_text.locations[0].bbox == (2, 3, 83, 29)
    signature = next(
        finding for finding in result.findings if finding.category is Category.SIGNATURE
    )
    assert signature.metadata["candidate_only"] is True


def test_signature_stroke_heuristic_is_low_confidence_and_conservative() -> None:
    cv2 = __import__("cv2")
    signature = numpy.full((120, 320, 3), 255, dtype="uint8")
    points = numpy.asarray(
        [[70, 72], [85, 45], [100, 78], [118, 42], [135, 76], [180, 55]],
        dtype="int32",
    )
    cv2.polylines(signature, [points], False, (20, 20, 20), 2)
    cv2.line(signature, (82, 67), (170, 62), (20, 20, 20), 2)
    document = _document()

    result = LocalImageAnalyzer(
        image_decoder=lambda content: signature,
        auto_load_qr=True,
        enable_seal_heuristic=False,
    ).analyze(document)

    candidates = [
        finding for finding in result.findings if finding.detector == "vision:handwriting-heuristic"
    ]
    assert candidates
    assert all(candidate.category is Category.SIGNATURE for candidate in candidates)
    assert all(candidate.confidence < 0.5 for candidate in candidates)
    assert all(candidate.metadata["candidate_only"] is True for candidate in candidates)

    printed_grid = numpy.full((120, 320, 3), 255, dtype="uint8")
    for row in range(20, 95, 24):
        for column in range(15, 300, 18):
            cv2.rectangle(
                printed_grid,
                (column, row),
                (column + 10, row + 14),
                (20, 20, 20),
                1,
            )
    grid_result = LocalImageAnalyzer(
        image_decoder=lambda content: printed_grid,
        auto_load_qr=True,
        enable_seal_heuristic=False,
    ).analyze(_document())

    assert not any(
        finding.detector == "vision:handwriting-heuristic" for finding in grid_result.findings
    )


def test_decode_applies_exif_orientation_before_ocr_coordinates() -> None:
    source = Image.new("RGB", (20, 10), "white")
    exif = Image.Exif()
    exif[274] = 6
    buffer = BytesIO()
    source.save(buffer, format="JPEG", exif=exif)
    observed_shapes: list[tuple[int, ...]] = []

    def record_shape(decoded: object) -> list[object]:
        observed_shapes.append(tuple(decoded.shape))
        return []

    analyzer = LocalImageAnalyzer(
        ocr_engine=record_shape,
        auto_load_qr=False,
        enable_seal_heuristic=False,
        enable_signature_heuristic=False,
    )
    analyzer.analyze(_document(content=buffer.getvalue()))

    assert observed_shapes == [(20, 10, 3)]
