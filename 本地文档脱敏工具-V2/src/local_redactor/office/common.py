from __future__ import annotations

import hashlib
import io
import os
import re
import sys
import uuid
import warnings
import zipfile
from collections.abc import Iterable, Sequence
from contextlib import suppress
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from ..models import (
    Category,
    DocumentKind,
    DocumentModel,
    Finding,
    FindingStatus,
    ImageDisposition,
    ImageObject,
    Modality,
    ObjectDisposition,
    SourceLocation,
    TextBlock,
)
from .security import ExportSafetyError, OoxmlSecurityError, preflight_ooxml, safe_xml_root

_UNSAFE_EXPORTED_KINDS = {
    "embedded_object",
    "custom_xml",
    "comment",
    "external_link",
    "data_connection",
    "pivot_cache",
    "chart",
    "binary",
    "unknown_xml",
    "unknown_relationship",
}
MAX_IMAGE_PIXELS = 80_000_000
ANALYSIS_COPY_TITLE = "AI 分析副本说明"
ANALYSIS_COPY_NOTICE = (
    "本副本中的人员、单位、日期、编号、网络地址和金额可能已替换为别名、"
    "替代值或区间值，不代表真实事实，仅用于经授权的内容分析。"
    "技术处理不改变文件密级，也不替代外发审批。"
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


def ensure_export_ready(document: DocumentModel, findings: Sequence[Finding]) -> None:
    unresolved_findings = [
        finding.id for finding in findings if finding.status is FindingStatus.PENDING
    ]
    if unresolved_findings:
        raise ExportSafetyError("仍有未复核的识别项，不能生成 AI 分析副本")
    if document.inventory.blocked_reasons:
        raise ExportSafetyError("源文件安全预检已阻断，不能生成 AI 分析副本")
    if document.inventory.unresolved_items:
        raise ExportSafetyError("仍有未处理的隐藏内容、链接或文件对象")
    pending_images = [
        image.id for image in document.images if image.disposition is ImageDisposition.PENDING
    ]
    if pending_images:
        raise ExportSafetyError("每张图片都必须完成人工处理决定")


def item_disposition(
    document: DocumentModel,
    part: str,
    *,
    default: ObjectDisposition = ObjectDisposition.REMOVE,
) -> ObjectDisposition:
    exact = [item for item in document.inventory.parts if item.part == part]
    if exact:
        return exact[-1].disposition
    package_part = part.split("#", maxsplit=1)[0]
    matching = [
        item
        for item in document.inventory.parts
        if item.part == package_part or item.part.split("#", maxsplit=1)[0] == package_part
    ]
    if not matching:
        return default
    if any(item.disposition is ObjectDisposition.PENDING for item in matching):
        return ObjectDisposition.PENDING
    if any(item.disposition is ObjectDisposition.VISIBLE_NOTE for item in matching):
        return ObjectDisposition.VISIBLE_NOTE
    if any(item.disposition is ObjectDisposition.SEPARATE_TASK for item in matching):
        return ObjectDisposition.SEPARATE_TASK
    return ObjectDisposition.REMOVE


def _location_matches(block: TextBlock, location: SourceLocation) -> bool:
    if location.block_id is not None:
        return location.block_id == block.id
    if location.part != block.location.part:
        return False
    for attribute in ("sheet", "cell", "image_id"):
        expected = getattr(location, attribute)
        actual = getattr(block.location, attribute)
        if expected is not None and expected != actual:
            return False
    return True


def apply_findings_to_text(
    block: TextBlock,
    findings: Sequence[Finding],
) -> str:
    operations: list[tuple[int, int, str, str]] = []
    fallbacks: list[tuple[str, str]] = []
    for finding in findings:
        if finding.category is Category.COMBINATION_RISK:
            continue
        if finding.status not in {FindingStatus.TRANSFORM, FindingStatus.REMOVE}:
            continue
        replacement = "" if finding.status is FindingStatus.REMOVE else finding.replacement
        if finding.status is FindingStatus.TRANSFORM and not replacement:
            raise ExportSafetyError("已确认替换的识别项缺少替代值")
        if finding.original and replacement == finding.original:
            raise ExportSafetyError("替代值与原值相同，不能生成副本")
        matched_locations = [
            location for location in finding.locations if _location_matches(block, location)
        ]
        if not matched_locations:
            # Same confirmed original may appear in another block (e.g. table cell)
            # that the detector missed (Luhn fail / no label). Still scrub it.
            if finding.original and finding.original in block.text:
                fallbacks.append((finding.original, replacement))
            continue
        for location in matched_locations:
            if location.start is None or location.end is None:
                if finding.original:
                    fallbacks.append((finding.original, replacement))
                continue
            start = location.start
            end = location.end
            if start < 0 or end < start or end > len(block.text):
                raise ExportSafetyError("识别项文字位置超出原文边界")
            expected = block.text[start:end]
            if finding.original and expected != finding.original:
                raise ExportSafetyError("识别项位置与原文快照不一致")
            operations.append((start, end, replacement, finding.id))

    operations.sort(key=lambda operation: (operation[0], operation[1]), reverse=True)
    last_start = len(block.text)
    result = block.text
    for start, end, replacement, _finding_id in operations:
        if end > last_start:
            raise ExportSafetyError("识别项文字范围相互重叠，需重新复核")
        result = f"{result[:start]}{replacement}{result[end:]}"
        last_start = start
    for original, replacement in fallbacks:
        result = result.replace(original, replacement)
    return result


def transformed_blocks(
    document: DocumentModel,
    findings: Sequence[Finding],
) -> dict[str, str]:
    return {block.id: apply_findings_to_text(block, findings) for block in document.blocks}


def sanitize_image(image: ImageObject) -> tuple[bytes, str] | None:
    if image.disposition is ImageDisposition.PENDING:
        raise ExportSafetyError("图片仍未完成人工处理决定")
    if image.disposition is ImageDisposition.REMOVE:
        return None
    if image.disposition is ImageDisposition.PIXEL_REDACT and not image.regions:
        raise ExportSafetyError("图片选择了遮住敏感区域，但没有已确认的区域")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            source = Image.open(io.BytesIO(image.content))
        with source:
            if source.width <= 0 or source.height <= 0:
                raise ExportSafetyError("图片尺寸无效")
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise ExportSafetyError("图片像素数量超过安全处理上限")
            source.load()
            clean = ImageOps.exif_transpose(source)
            clean = clean.convert("RGBA") if "A" in clean.getbands() else clean.convert("RGB")
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ExportSafetyError("图片无法安全解码和重新编码") from exc

    if image.disposition is ImageDisposition.PIXEL_REDACT:
        drawer = ImageDraw.Draw(clean)
        for index, region in enumerate(image.regions, start=1):
            left, top, right, bottom = region.bbox
            if left < 0 or top < 0 or right <= left or bottom <= top:
                raise ExportSafetyError("图片处理区域坐标无效")
            if right > clean.width or bottom > clean.height:
                raise ExportSafetyError("图片处理区域超出图片边界")
            label = region.replacement_label.strip()
            if not label:
                raise ExportSafetyError("图片处理区域缺少可见替代标签")
            fill = (0, 0, 0, 255) if clean.mode == "RGBA" else (0, 0, 0)
            drawer.rectangle((left, top, right - 1, bottom - 1), fill=fill)
            _draw_region_replacement(
                drawer,
                region.bbox,
                index=index,
                replacement_label=label,
                image_mode=clean.mode,
            )

    original_hash = hashlib.sha256(image.content).digest()
    clean_bytes = _encode_clean_png(clean, compress_level=9)
    if hashlib.sha256(clean_bytes).digest() == original_hash:
        clean_bytes = _encode_clean_png(clean, compress_level=1)
    if hashlib.sha256(clean_bytes).digest() == original_hash:
        alternate = clean.convert("RGBA" if clean.mode == "RGB" else "RGB")
        clean_bytes = _encode_clean_png(alternate, compress_level=6)
    if hashlib.sha256(clean_bytes).digest() == original_hash:
        raise ExportSafetyError("图片重新编码结果与原始媒体字节一致")
    return clean_bytes, "image/png"


def prepare_image_for_export(
    image: ImageObject,
    findings: Sequence[Finding],
) -> ImageObject:
    """Bind image regions to the same reviewed replacement used in body text."""

    if image.disposition is ImageDisposition.REMOVE:
        return replace(image, regions=[])
    image_locations = [
        (finding, location)
        for finding in findings
        if finding.category is not Category.COMBINATION_RISK
        and finding.status in {FindingStatus.TRANSFORM, FindingStatus.REMOVE}
        for location in finding.locations
        if location.image_id == image.id
    ]
    if image.disposition is ImageDisposition.KEEP_REENCODED and (image_locations or image.regions):
        raise ExportSafetyError("图片包含已确认处理项，不能仅重新编码后原样保留")
    if image.disposition is ImageDisposition.PIXEL_REDACT:
        for _finding, location in image_locations:
            if location.bbox is None:
                raise ExportSafetyError("图片处理项缺少像素坐标，需整图移除或重新框选")
            if not any(_bbox_contains(region.bbox, location.bbox) for region in image.regions):
                raise ExportSafetyError("图片处理项没有对应的遮挡区域")

    prepared_regions = []
    forbidden = tuple(
        finding.original
        for finding in findings
        if finding.original and finding.status in {FindingStatus.TRANSFORM, FindingStatus.REMOVE}
    )
    for region in image.regions:
        labels: list[str] = []
        for finding in findings:
            if finding.status not in {FindingStatus.TRANSFORM, FindingStatus.REMOVE}:
                continue
            if not any(
                location.image_id == image.id
                and location.bbox is not None
                and _bbox_contains(region.bbox, location.bbox)
                for location in finding.locations
            ):
                continue
            if finding.status is FindingStatus.TRANSFORM:
                if not finding.replacement:
                    raise ExportSafetyError("图片识别项缺少与正文一致的替代值")
                label = finding.replacement
            else:
                label = "[已移除]"
            if label not in labels:
                labels.append(label)
        replacement_label = ("；".join(labels) if labels else region.replacement_label).strip()
        if not replacement_label:
            raise ExportSafetyError("图片处理区域缺少可见替代标签")
        if any(original in replacement_label for original in forbidden):
            raise ExportSafetyError("图片替代标签仍包含已确认处理的原值")
        prepared_regions.append(replace(region, replacement_label=replacement_label))
    return replace(image, regions=prepared_regions)


def _bbox_contains(
    outer: tuple[int, int, int, int],
    inner: tuple[int, int, int, int],
) -> bool:
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and outer[2] >= inner[2]
        and outer[3] >= inner[3]
    )


def image_replacement_legend(image: ImageObject) -> str:
    if image.disposition is not ImageDisposition.PIXEL_REDACT:
        return ""
    return "；".join(
        f"[{index}] {region.replacement_label}"
        for index, region in enumerate(image.regions, start=1)
    )


def validate_source_image(
    content: bytes,
    *,
    source_part: str,
) -> tuple[int, int]:
    """Inspect dimensions before decode and fail closed on invalid image bytes."""

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            source = Image.open(io.BytesIO(content))
        with source:
            width, height = source.size
            if width <= 0 or height <= 0:
                raise OoxmlSecurityError(
                    "invalid-image-size",
                    f"Office 图片尺寸无效：{source_part}",
                )
            if width * height > MAX_IMAGE_PIXELS:
                raise OoxmlSecurityError(
                    "image-pixel-quota",
                    f"Office 图片像素数量超过安全上限：{source_part}",
                )
            source.verify()
            return width, height
    except OoxmlSecurityError:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise OoxmlSecurityError(
            "unsafe-image",
            f"Office 图片无法安全验证：{source_part}",
        ) from exc


def _draw_region_replacement(
    drawer: ImageDraw.ImageDraw,
    bbox: tuple[int, int, int, int],
    *,
    index: int,
    replacement_label: str,
    image_mode: str,
) -> None:
    left, top, right, bottom = bbox
    width = right - left
    height = bottom - top
    color = (255, 255, 255, 255) if image_mode == "RGBA" else (255, 255, 255)
    font_size = max(8, min(28, height - 4))
    full_font = _replacement_font(font_size)
    full_text = f"[{index}] {replacement_label}"
    if _text_fits(drawer, full_text, full_font, width, height):
        text = full_text
        font = full_font
    else:
        text = f"[{index}]"
        font = ImageFont.load_default()
        if not _text_fits(drawer, text, font, width, height):
            text = str(index)
        if not _text_fits(drawer, text, font, width, height):
            raise ExportSafetyError("图片处理区域过小，无法写入可见替代编号")
    text_box = drawer.textbbox((0, 0), text, font=font)
    text_width = text_box[2] - text_box[0]
    text_height = text_box[3] - text_box[1]
    x = left + max(0, (width - text_width) // 2)
    y = top + max(0, (height - text_height) // 2) - text_box[1]
    drawer.text((x, y), text, font=font, fill=color)


def _text_fits(
    drawer: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
    width: int,
    height: int,
) -> bool:
    try:
        box = drawer.textbbox((0, 0), text, font=font)
    except (OSError, UnicodeError):
        return False
    return box[2] - box[0] <= width - 2 and box[3] - box[1] <= height - 2


@lru_cache(maxsize=32)
def _replacement_font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    windows_root = Path(os.environ.get("WINDIR", r"C:\Windows"))
    package_root = Path(__file__).resolve().parents[3]
    executable_root = Path(sys.executable).resolve().parent
    candidates = (
        package_root / "assets" / "fonts" / "NotoSansCJKsc-Regular.otf",
        executable_root / "assets" / "fonts" / "NotoSansCJKsc-Regular.otf",
        windows_root / "Fonts" / "msyh.ttc",
        windows_root / "Fonts" / "simhei.ttf",
        windows_root / "Fonts" / "Deng.ttf",
        windows_root / "Fonts" / "arial.ttf",
    )
    for candidate in candidates:
        try:
            if candidate.is_file():
                return ImageFont.truetype(str(candidate), size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _encode_clean_png(image: Image.Image, *, compress_level: int) -> bytes:
    output = io.BytesIO()
    image.save(
        output,
        format="PNG",
        optimize=False,
        compress_level=compress_level,
    )
    return output.getvalue()


def secure_target_path(source_path: Path, target_path: Path, suffix: str) -> Path:
    source_resolved = source_path.resolve(strict=True)
    target = Path(target_path)
    if target.suffix.casefold() != suffix:
        raise ExportSafetyError(f"输出文件必须使用 {suffix} 扩展名")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ExportSafetyError("输出目标已存在；为避免覆盖，请选择新的结果目录")
    target_resolved = target.resolve(strict=False)
    if source_resolved == target_resolved:
        raise ExportSafetyError("不得覆盖原始文件")
    return target


def temporary_export_path(target_path: Path) -> Path:
    return target_path.with_name(f".{target_path.stem}.{uuid.uuid4().hex}.tmp{target_path.suffix}")


def finalize_export(temp_path: Path, target_path: Path) -> None:
    if target_path.exists():
        raise ExportSafetyError("输出目标在生成期间已被占用")
    try:
        os.replace(temp_path, target_path)
    except OSError as exc:
        raise ExportSafetyError("无法将已验证的临时副本放入目标位置") from exc


def cleanup_temp(path: Path) -> None:
    with suppress(OSError):
        path.unlink(missing_ok=True)


def verify_rebuilt_ooxml(
    path: Path,
    kind: DocumentKind,
    *,
    forbidden_values: Iterable[str] = (),
    original_image_hashes: Iterable[str] = (),
) -> None:
    try:
        result = preflight_ooxml(path, kind)
    except OoxmlSecurityError as exc:
        raise ExportSafetyError("重建副本未通过 OOXML 重新打开检查") from exc
    if any(relationship.external for relationship in result.relationships):
        raise ExportSafetyError("重建副本仍包含外部关系")
    unsafe_parts = [
        item.part for item in result.inventory.parts if item.kind in _UNSAFE_EXPORTED_KINDS
    ]
    if unsafe_parts:
        raise ExportSafetyError("重建副本仍包含不允许复制的 Office 部件")

    forbidden = tuple(value for value in forbidden_values if value)
    encoded_forbidden = tuple(
        (value, encoded)
        for value in forbidden
        for encoded in (
            value.encode("utf-8"),
            value.encode("utf-16le"),
            value.encode("utf-16be"),
        )
    )
    source_image_hashes = set(original_image_hashes)
    with zipfile.ZipFile(path, mode="r") as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            data = archive.read(info)
            if info.filename.endswith((".xml", ".rels")):
                safe_xml_root(data, part_name=info.filename)
            for value, encoded in encoded_forbidden:
                if encoded in data:
                    fingerprint = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
                    raise ExportSafetyError(
                        "重建副本复扫发现已确认原值残留"
                        f"（部件：{info.filename}，指纹：{fingerprint}）"
                    )
            if "/media/" in info.filename.casefold():
                media_hash = hashlib.sha256(data).hexdigest()
                if media_hash in source_image_hashes:
                    raise ExportSafetyError("重建副本复制了原始图片字节")


def forbidden_originals(findings: Sequence[Finding]) -> tuple[str, ...]:
    values = {
        finding.original
        for finding in findings
        if finding.original
        and finding.status in {FindingStatus.TRANSFORM, FindingStatus.REMOVE}
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
        # Package metadata is removed and verified structurally. Treating a
        # one-character author surname as globally forbidden would otherwise
        # create false failures when the same common character appears in an
        # unrelated picture.
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
