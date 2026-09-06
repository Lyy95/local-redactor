from __future__ import annotations

import ipaddress
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import replace

from local_redactor.models import (
    Category,
    Finding,
    Modality,
    SourceLocation,
    TextBlock,
)

_COMPACT_CATEGORIES = {
    Category.ID_CARD,
    Category.PHONE,
    Category.VEHICLE_PLATE,
    Category.ACCOUNT,
    Category.CASE_ID,
    Category.DEVICE_ID,
}
_LOWERCASE_CATEGORIES = {
    Category.DOMAIN,
    Category.EMAIL,
    Category.USERNAME,
}


def clone_location(
    location: SourceLocation,
    *,
    start: int | None = None,
    end: int | None = None,
    bbox: tuple[int, int, int, int] | None = None,
) -> SourceLocation:
    """Copy a source location without mutating the document model."""

    base = location.start or 0
    return replace(
        location,
        start=None if start is None else base + start,
        end=None if end is None else base + end,
        bbox=location.bbox if bbox is None else bbox,
    )


def modality_for_block(block: TextBlock) -> Modality:
    if block.location.image_id is not None:
        return Modality.IMAGE
    if block.hidden:
        return Modality.HIDDEN
    if block.location.cell is not None or block.location.sheet is not None:
        return Modality.CELL
    return Modality.TEXT


def normalize_entity(category: Category, value: str) -> str:
    """Normalize only enough to keep task-local replacements consistent."""

    normalized = value.strip()
    if category in _COMPACT_CATEGORIES:
        normalized = re.sub(r"[\s‐‑‒–—―_-]+", "", normalized)
        if category is Category.PHONE:
            normalized = re.sub(r"^\+?86", "", normalized)
        return normalized.upper()
    if category in _LOWERCASE_CATEGORIES:
        return normalized.casefold().rstrip(".")
    if category in {Category.PUBLIC_IP, Category.PRIVATE_IP}:
        try:
            return ipaddress.ip_address(normalized).compressed
        except ValueError:
            return normalized.casefold()
    return re.sub(r"\s+", " ", normalized).casefold()


def normalize_for_residual_check(value: str) -> str:
    """Normalize full source text before checking whether it survived.

    NFKC closes full-width/canonical spelling variations, casefold closes
    case-only replacements, and dropping separators prevents a rule from
    preserving an original merely by inserting spaces or punctuation.
    """

    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum())


def contains_normalized_original(original: str, candidate: str) -> bool:
    """Return whether the complete normalized original survives in a result."""

    normalized_original = normalize_for_residual_check(original)
    if not normalized_original:
        return False
    return normalized_original in normalize_for_residual_check(candidate)


def location_label(location: SourceLocation) -> str:
    """Return a non-path task-local location label for the local mapping."""

    pieces = [location.display]
    if location.sheet:
        pieces.append(f"工作表:{location.sheet}")
    if location.cell:
        pieces.append(f"单元格:{location.cell}")
    if location.image_id:
        pieces.append(f"图片:{location.image_id}")
    if location.bbox:
        x1, y1, x2, y2 = location.bbox
        pieces.append(f"区域:{x1},{y1},{x2},{y2}")
    return " / ".join(piece for piece in pieces if piece)


def merge_findings(findings: Iterable[Finding]) -> list[Finding]:
    """Merge exact duplicate entities while retaining every occurrence.

    Near-equivalent variants are deliberately left separate here because the
    document rebuild layer still needs their exact source spelling. The
    transformation engine normalizes those variants to one replacement.
    """

    merged: dict[tuple[Category, str, Modality], Finding] = {}
    order: list[tuple[Category, str, Modality]] = []
    for finding in findings:
        key = (finding.category, finding.original, finding.modality)
        current = merged.get(key)
        if current is None:
            copied = replace(
                finding,
                locations=list(finding.locations),
                metadata=dict(finding.metadata),
            )
            merged[key] = copied
            order.append(key)
            continue

        known_locations = {
            (
                location.part,
                location.display,
                location.block_id,
                location.sheet,
                location.cell,
                location.image_id,
                location.start,
                location.end,
                location.bbox,
            )
            for location in current.locations
        }
        for location in finding.locations:
            location_key = (
                location.part,
                location.display,
                location.block_id,
                location.sheet,
                location.cell,
                location.image_id,
                location.start,
                location.end,
                location.bbox,
            )
            if location_key not in known_locations:
                current.locations.append(location)
                known_locations.add(location_key)
        current.confidence = max(current.confidence, finding.confidence)
        detectors = set(str(current.detector).split("+"))
        detectors.update(str(finding.detector).split("+"))
        current.detector = "+".join(sorted(detectors))
        current.combination_score = max(
            current.combination_score,
            finding.combination_score,
        )
        current.metadata.update(
            {key: value for key, value in finding.metadata.items() if key not in current.metadata}
        )
    return [merged[key] for key in order]
