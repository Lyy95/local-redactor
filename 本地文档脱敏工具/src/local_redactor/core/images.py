from __future__ import annotations

import importlib
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

from local_redactor.models import (
    Category,
    DocumentModel,
    Finding,
    ImageObject,
    Modality,
    SourceLocation,
    TextBlock,
    TransformMethod,
)

from .common import merge_findings
from .detectors import StructuredDetector

ImageDecoder = Callable[[bytes], Any]


@dataclass(slots=True)
class ImageAnalysisResult:
    findings: list[Finding] = field(default_factory=list)
    mandatory_review_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def requires_manual_review(self) -> bool:
        return bool(self.mandatory_review_ids)


@dataclass(frozen=True, slots=True)
class _OcrLine:
    text: str
    bbox: tuple[int, int, int, int]
    confidence: float


class LocalImageAnalyzer:
    """Offline image candidate adapter with a mandatory human-review gate.

    OCR and face engines must be supplied by the application from verified
    local assets. Missing components never turn an image into an automatic
    pass: every image ID is returned in ``mandatory_review_ids`` and its
    ``ImageObject.disposition`` remains ``PENDING``.
    """

    def __init__(
        self,
        *,
        ocr_engine: Any | None = None,
        face_detector: Any | None = None,
        text_detectors: Sequence[Any] | None = None,
        image_decoder: ImageDecoder | None = None,
        auto_load_qr: bool = True,
        enable_seal_heuristic: bool = True,
        enable_signature_heuristic: bool = True,
    ) -> None:
        self.ocr_engine = ocr_engine
        self.face_detector = face_detector
        self.text_detectors = tuple(text_detectors or (StructuredDetector(),))
        self.image_decoder = image_decoder
        self.auto_load_qr = auto_load_qr
        self.enable_seal_heuristic = enable_seal_heuristic
        self.enable_signature_heuristic = enable_signature_heuristic
        self._cv2: Any | None = None
        self._cv2_attempted = False

    def analyze(self, document: DocumentModel) -> ImageAnalysisResult:
        result = ImageAnalysisResult(mandatory_review_ids=[image.id for image in document.images])
        if document.images and self.ocr_engine is None:
            self._warning(
                document,
                result,
                "IMAGE_OCR_UNAVAILABLE: 本地OCR组件不可用；所有图片仍须逐张人工复核。",
            )
        if document.images and self.face_detector is None:
            self._warning(
                document,
                result,
                "IMAGE_FACE_MODEL_UNAVAILABLE: 本地人脸候选模型不可用；所有图片仍须逐张人工复核。",
            )

        cv2 = self._load_cv2()
        if document.images and cv2 is None:
            self._warning(
                document,
                result,
                "IMAGE_QR_UNAVAILABLE: 本地二维码组件不可用；所有图片仍须逐张人工复核。",
            )

        for image in document.images:
            decoded = self._decode_image(image, document, result, cv2)
            result.findings.extend(self._alt_text_findings(document, image))
            if decoded is None:
                continue

            if self.ocr_engine is not None:
                ocr_lines = self._run_ocr(decoded, document, result)
                result.findings.extend(self._ocr_findings(document, image, ocr_lines))
            if cv2 is not None:
                result.findings.extend(self._qr_findings(image, decoded, cv2, document, result))
            if self.face_detector is not None:
                result.findings.extend(
                    self._face_findings(
                        image,
                        decoded,
                        document,
                        result,
                    )
                )
            if self.enable_seal_heuristic:
                seal_bbox = self._red_seal_bbox(decoded)
                if seal_bbox is not None:
                    result.findings.append(
                        self._visual_finding(
                            image,
                            category=Category.SEAL,
                            bbox=seal_bbox,
                            detector="vision:red-seal-heuristic",
                            confidence=0.55,
                            metadata={"candidate_only": True},
                        )
                    )
            if self.enable_signature_heuristic and cv2 is not None:
                for signature_bbox in self._signature_bboxes(decoded, cv2):
                    result.findings.append(
                        self._visual_finding(
                            image,
                            category=Category.SIGNATURE,
                            bbox=signature_bbox,
                            detector="vision:handwriting-heuristic",
                            confidence=0.42,
                            metadata={
                                "candidate_only": True,
                                "mandatory_manual_review": True,
                                "heuristic": "conservative-handwriting",
                            },
                        )
                    )

        result.findings = merge_findings(result.findings)
        return result

    def _alt_text_findings(
        self,
        document: DocumentModel,
        image: ImageObject,
    ) -> list[Finding]:
        text = image.alt_text.strip()
        if not text or re.fullmatch(
            r"(?:(?:Picture|Image)\s*\d+(?:\s*(?:Picture|Image))?|"
            r"(?:图片|图像)\s*\d+)",
            text,
            flags=re.IGNORECASE,
        ):
            return []
        location = SourceLocation(
            part=image.source_part,
            display=f"{image.location.display} / 替代文字",
            block_id=image.id,
            image_id=image.id,
        )
        base = Finding(
            category=Category.IMAGE_TEXT,
            modality=Modality.IMAGE,
            original=text,
            locations=[location],
            detector="image:alt-text",
            confidence=1.0,
            suggested_method=TransformMethod.PIXEL_REDACT,
            preserved_semantics="替代文字不得未经复核进入副本",
            context=text,
            metadata={"mandatory_manual_review": True, "alt_text": True},
        )
        return [base, *self._detect_image_text(document, text, location)]

    def _ocr_findings(
        self,
        document: DocumentModel,
        image: ImageObject,
        lines: Iterable[_OcrLine],
    ) -> list[Finding]:
        findings: list[Finding] = []
        for line in lines:
            location = SourceLocation(
                part=image.source_part,
                display=f"{image.location.display} / OCR文字",
                block_id=image.id,
                image_id=image.id,
                bbox=line.bbox,
            )
            findings.append(
                Finding(
                    category=Category.IMAGE_TEXT,
                    modality=Modality.IMAGE,
                    original=line.text,
                    locations=[location],
                    detector="ocr:local",
                    confidence=line.confidence,
                    suggested_method=TransformMethod.PIXEL_REDACT,
                    preserved_semantics="按正文同类规则处理并重写真实像素",
                    context=line.text,
                    metadata={
                        "mandatory_manual_review": True,
                        "ocr_confidence": line.confidence,
                    },
                )
            )
            if re.search(r"(?:手写)?签名|签字|手签|签章", line.text):
                findings.append(
                    self._visual_finding(
                        image,
                        category=Category.SIGNATURE,
                        bbox=line.bbox,
                        detector="vision:signature-label-heuristic",
                        confidence=max(0.5, min(line.confidence, 0.75)),
                        metadata={
                            "candidate_only": True,
                            "mandatory_manual_review": True,
                            "trigger": "ocr-signature-label",
                        },
                    )
                )
            findings.extend(self._detect_image_text(document, line.text, location))
        return findings

    def _detect_image_text(
        self,
        document: DocumentModel,
        text: str,
        location: SourceLocation,
    ) -> list[Finding]:
        image_document = DocumentModel(
            kind=document.kind,
            source_path=document.source_path,
            source_sha256=document.source_sha256,
            display_name=document.display_name,
            blocks=[
                TextBlock(
                    text=text,
                    location=location,
                    block_kind="image-text",
                )
            ],
        )
        findings: list[Finding] = []
        for detector in self.text_detectors:
            try:
                findings.extend(detector.detect(image_document))
            except Exception:
                if (
                    "IMAGE_TEXT_DETECTOR_FAILED: 图片文字实体识别失败；"
                    "该图片仍须人工复核。" not in document.warnings
                ):
                    document.warnings.append(
                        "IMAGE_TEXT_DETECTOR_FAILED: 图片文字实体识别失败；该图片仍须人工复核。"
                    )
        for finding in findings:
            finding.modality = Modality.IMAGE
            finding.metadata["from_image_text"] = True
        return findings

    def _decode_image(
        self,
        image: ImageObject,
        document: DocumentModel,
        result: ImageAnalysisResult,
        cv2: Any | None,
    ) -> Any | None:
        if self.image_decoder is not None:
            try:
                return self.image_decoder(image.content)
            except Exception:
                self._warning(
                    document,
                    result,
                    "IMAGE_DECODE_FAILED: 图片解码失败；必须移除或另行处理。",
                )
                return None
        try:
            pil_image_module = importlib.import_module("PIL.Image")
            pil_image_ops_module = importlib.import_module("PIL.ImageOps")
            numpy = importlib.import_module("numpy")
            with pil_image_module.open(BytesIO(image.content)) as opened:
                oriented = pil_image_ops_module.exif_transpose(opened)
                oriented.load()
                rgb = oriented.convert("RGB")
                return numpy.asarray(rgb)
        except (ImportError, ModuleNotFoundError, OSError, ValueError):
            if cv2 is not None:
                try:
                    numpy = importlib.import_module("numpy")
                    raw = numpy.frombuffer(image.content, dtype=numpy.uint8)
                    decoded_bgr = cv2.imdecode(raw, cv2.IMREAD_COLOR)
                    if decoded_bgr is not None:
                        return cv2.cvtColor(decoded_bgr, cv2.COLOR_BGR2RGB)
                except Exception:
                    pass
            self._warning(
                document,
                result,
                "IMAGE_DECODE_FAILED: 图片解码失败；必须移除或另行处理。",
            )
            return None

    def _run_ocr(
        self,
        decoded: Any,
        document: DocumentModel,
        result: ImageAnalysisResult,
    ) -> list[_OcrLine]:
        engine = self.ocr_engine
        if engine is None:
            return []
        try:
            raw = engine(decoded)
            return _parse_ocr_result(raw)
        except Exception:
            self._warning(
                document,
                result,
                "IMAGE_OCR_FAILED: 本地OCR执行失败；该图片仍须人工复核。",
            )
            return []

    def _qr_findings(
        self,
        image: ImageObject,
        decoded: Any,
        cv2: Any,
        document: DocumentModel,
        result: ImageAnalysisResult,
    ) -> list[Finding]:
        try:
            detector = cv2.QRCodeDetector()
            values: list[str] = []
            boxes: list[tuple[int, int, int, int]] = []
            if hasattr(detector, "detectAndDecodeMulti"):
                multi = detector.detectAndDecodeMulti(decoded)
                if isinstance(multi, tuple) and len(multi) >= 3 and bool(multi[0]):
                    values = [str(value) for value in multi[1]]
                    boxes = _boxes_from_points(multi[2])
            if not boxes:
                value, points, _ = detector.detectAndDecode(decoded)
                if points is not None:
                    values = [str(value)]
                    boxes = _boxes_from_points(points)
            findings = []
            for index, bbox in enumerate(boxes):
                payload = values[index] if index < len(values) else ""
                findings.append(
                    self._visual_finding(
                        image,
                        category=Category.QR_CODE,
                        bbox=bbox,
                        detector="qr:opencv-local",
                        confidence=1.0 if payload else 0.85,
                        original=payload,
                        metadata={
                            "payload_decoded": bool(payload),
                            "mandatory_manual_review": True,
                        },
                    )
                )
            return findings
        except Exception:
            self._warning(
                document,
                result,
                "IMAGE_QR_FAILED: 本地二维码识别失败；该图片仍须人工复核。",
            )
            return []

    def _face_findings(
        self,
        image: ImageObject,
        decoded: Any,
        document: DocumentModel,
        result: ImageAnalysisResult,
    ) -> list[Finding]:
        detector = self.face_detector
        if detector is None:
            return []
        try:
            raw = detector(decoded) if callable(detector) else detector.detect(decoded)
            boxes = _parse_face_boxes(raw)
            return [
                self._visual_finding(
                    image,
                    category=Category.PHOTO,
                    bbox=bbox,
                    detector="vision:face-local",
                    confidence=confidence,
                    metadata={
                        "candidate_only": True,
                        "mandatory_manual_review": True,
                    },
                )
                for bbox, confidence in boxes
            ]
        except Exception:
            self._warning(
                document,
                result,
                "IMAGE_FACE_FAILED: 本地人脸候选识别失败；该图片仍须人工复核。",
            )
            return []

    @staticmethod
    def _visual_finding(
        image: ImageObject,
        *,
        category: Category,
        bbox: tuple[int, int, int, int],
        detector: str,
        confidence: float,
        original: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Finding:
        return Finding(
            category=category,
            modality=Modality.IMAGE,
            original=original,
            locations=[
                SourceLocation(
                    part=image.source_part,
                    display=image.location.display,
                    block_id=image.id,
                    image_id=image.id,
                    bbox=bbox,
                )
            ],
            detector=detector,
            confidence=max(0.0, min(1.0, confidence)),
            suggested_method=TransformMethod.PIXEL_REDACT,
            preserved_semantics="只保留经人工确认的必要场景信息",
            context="视觉候选区域，必须人工确认。",
            metadata=metadata or {"mandatory_manual_review": True},
        )

    def _load_cv2(self) -> Any | None:
        if self._cv2_attempted:
            return self._cv2
        self._cv2_attempted = True
        if not self.auto_load_qr:
            return None
        try:
            self._cv2 = importlib.import_module("cv2")
        except (ImportError, ModuleNotFoundError):
            self._cv2 = None
        return self._cv2

    @staticmethod
    def _red_seal_bbox(decoded: Any) -> tuple[int, int, int, int] | None:
        try:
            shape = decoded.shape
            if len(shape) < 3 or int(shape[2]) < 3:
                return None
            red = decoded[:, :, 0].astype("int32")
            green = decoded[:, :, 1].astype("int32")
            blue = decoded[:, :, 2].astype("int32")
            mask = (red >= 140) & (red >= (green * 135 // 100)) & (red >= (blue * 135 // 100))
            ys, xs = mask.nonzero()
            if len(xs) < 24:
                return None
            x1 = int(xs.min())
            y1 = int(ys.min())
            x2 = int(xs.max()) + 1
            y2 = int(ys.max()) + 1
            area = (x2 - x1) * (y2 - y1)
            if area < 64 or len(xs) / area < 0.035:
                return None
            return (x1, y1, x2, y2)
        except (AttributeError, IndexError, TypeError, ValueError):
            return None

    @staticmethod
    def _signature_bboxes(
        decoded: Any,
        cv2: Any,
    ) -> list[tuple[int, int, int, int]]:
        """Find isolated handwriting-like strokes as low-confidence candidates.

        This is deliberately conservative: it rejects dense printed blocks,
        whole text rows, tiny marks and regions covering a large page area.
        The result is never treated as an automatic signature decision.
        """

        try:
            height, width = (int(decoded.shape[0]), int(decoded.shape[1]))
            if height < 32 or width < 64:
                return []
            gray = cv2.cvtColor(decoded, cv2.COLOR_RGB2GRAY)
            dark = (gray < 105).astype("uint8")
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            joined = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, kernel)
            count, _, stats, _ = cv2.connectedComponentsWithStats(
                joined,
                connectivity=8,
            )
            candidates: list[tuple[int, int, int, int]] = []
            numpy = importlib.import_module("numpy")
            for label in range(1, int(count)):
                x = int(stats[label, cv2.CC_STAT_LEFT])
                y = int(stats[label, cv2.CC_STAT_TOP])
                region_width = int(stats[label, cv2.CC_STAT_WIDTH])
                region_height = int(stats[label, cv2.CC_STAT_HEIGHT])
                if (
                    region_width < 40
                    or region_height < 12
                    or region_width > width * 0.68
                    or region_height > height * 0.38
                ):
                    continue
                aspect = region_width / max(region_height, 1)
                if not 1.4 <= aspect <= 8.0:
                    continue
                region = dark[
                    y : y + region_height,
                    x : x + region_width,
                ]
                ink_count = int(region.sum())
                density = ink_count / max(region_width * region_height, 1)
                if ink_count < 45 or not 0.015 <= density <= 0.18:
                    continue
                active_columns = region.any(axis=0)
                column_indices = active_columns.nonzero()[0]
                if len(column_indices) < region_width * 0.28:
                    continue
                centerline = []
                for column in column_indices:
                    rows = region[:, column].nonzero()[0]
                    if len(rows):
                        centerline.append(float(rows.mean()))
                if len(centerline) < 12:
                    continue
                if float(numpy.std(centerline)) < max(
                    2.2,
                    region_height * 0.11,
                ):
                    continue
                candidates.append((x, y, x + region_width, y + region_height))
            return candidates
        except (
            AttributeError,
            ImportError,
            IndexError,
            ModuleNotFoundError,
            TypeError,
            ValueError,
        ):
            return []

    @staticmethod
    def _warning(
        document: DocumentModel,
        result: ImageAnalysisResult,
        warning: str,
    ) -> None:
        if warning not in result.warnings:
            result.warnings.append(warning)
        if warning not in document.warnings:
            document.warnings.append(warning)


def _parse_ocr_result(raw: Any) -> list[_OcrLine]:
    if raw is None:
        return []
    if hasattr(raw, "txts") and hasattr(raw, "boxes"):
        raw_texts = raw.txts
        raw_boxes = raw.boxes
        raw_scores = getattr(raw, "scores", None)
        texts = [] if raw_texts is None else list(raw_texts)
        boxes = [] if raw_boxes is None else list(raw_boxes)
        scores = [] if raw_scores is None else list(raw_scores)
        return [
            _OcrLine(
                text=str(text),
                bbox=_bbox_from_points(boxes[index]),
                confidence=float(scores[index]) if index < len(scores) else 0.5,
            )
            for index, text in enumerate(texts)
            if str(text).strip() and index < len(boxes)
        ]

    candidates = raw
    if isinstance(raw, tuple) and raw:
        candidates = raw[0]
    lines: list[_OcrLine] = []
    if not isinstance(candidates, (list, tuple)):
        return lines
    for item in candidates:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        points = item[0]
        text = str(item[1]).strip()
        score = float(item[2]) if len(item) >= 3 else 0.5
        if text:
            lines.append(
                _OcrLine(
                    text=text,
                    bbox=_bbox_from_points(points),
                    confidence=score,
                )
            )
    return lines


def _bbox_from_points(points: Any) -> tuple[int, int, int, int]:
    flat = list(points)
    if len(flat) == 4 and all(isinstance(value, (int, float)) for value in flat):
        x, y, width, height = (int(float(value)) for value in flat)
        return (x, y, x + width, y + height)
    xy = [(float(point[0]), float(point[1])) for point in flat]
    xs = [point[0] for point in xy]
    ys = [point[1] for point in xy]
    return (
        int(min(xs)),
        int(min(ys)),
        int(max(xs)) + 1,
        int(max(ys)) + 1,
    )


def _boxes_from_points(points: Any) -> list[tuple[int, int, int, int]]:
    try:
        shape = getattr(points, "shape", ())
        if len(shape) == 2:
            return [_bbox_from_points(points)]
        return [_bbox_from_points(item) for item in points]
    except (TypeError, ValueError, IndexError):
        return []


def _parse_face_boxes(raw: Any) -> list[tuple[tuple[int, int, int, int], float]]:
    if isinstance(raw, tuple) and len(raw) >= 2:
        raw = raw[1]
    if raw is None:
        return []
    boxes: list[tuple[tuple[int, int, int, int], float]] = []
    for item in raw:
        values = list(item)
        if len(values) < 4:
            continue
        x, y, width, height = (int(float(value)) for value in values[:4])
        confidence = float(values[-1]) if len(values) >= 5 else 0.5
        boxes.append(((x, y, x + width, y + height), confidence))
    return boxes


__all__ = ["ImageAnalysisResult", "LocalImageAnalyzer"]
