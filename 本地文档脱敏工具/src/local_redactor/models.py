from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4


class DocumentKind(StrEnum):
    DOCX = "docx"
    XLSX = "xlsx"


class ProcessingMode(StrEnum):
    BALANCED = "balanced"
    STRICT = "strict"


class Modality(StrEnum):
    TEXT = "text"
    CELL = "cell"
    IMAGE = "image"
    METADATA = "metadata"
    HIDDEN = "hidden"
    RELATION = "relation"
    OBJECT = "object"


class Category(StrEnum):
    NAME = "name"
    ID_CARD = "id_card"
    PHONE = "phone"
    BANK_CARD = "bank_card"
    LANDLINE = "landline"
    ADDRESS = "address"
    VEHICLE_PLATE = "vehicle_plate"
    ACCOUNT = "account"
    ORGANIZATION = "organization"
    DEPARTMENT = "department"
    PROJECT = "project"
    SYSTEM = "system"
    LOCATION = "location"
    TIME = "time"
    MONEY = "money"
    CASE_ID = "case_id"
    DEVICE_ID = "device_id"
    PUBLIC_IP = "public_ip"
    PRIVATE_IP = "private_ip"
    DOMAIN = "domain"
    EMAIL = "email"
    USERNAME = "username"
    SECRET = "secret"
    IMAGE_TEXT = "image_text"
    SEAL = "seal"
    SIGNATURE = "signature"
    QR_CODE = "qr_code"
    PHOTO = "photo"
    FILE_PROPERTY = "file_property"
    REVISION = "revision"
    COMMENT = "comment"
    HIDDEN_CONTENT = "hidden_content"
    HEADER_FOOTER = "header_footer"
    WATERMARK = "watermark"
    ATTACHMENT = "attachment"
    EMBEDDED_OBJECT = "embedded_object"
    HYPERLINK = "hyperlink"
    COMBINATION_RISK = "combination_risk"
    OTHER = "other"


class FindingStatus(StrEnum):
    PENDING = "pending"
    TRANSFORM = "transform"
    KEEP_FALSE_POSITIVE = "keep_false_positive"
    REMOVE = "remove"


class TransformMethod(StrEnum):
    ALIAS = "alias"
    SIMULATE = "simulate"
    GENERALIZE = "generalize"
    RANGE = "range"
    SHIFT = "shift"
    SCALE = "scale"
    PIXEL_REDACT = "pixel_redact"
    VISIBLE_NOTE = "visible_note"
    REMOVE = "remove"
    KEEP = "keep"


class ImageDisposition(StrEnum):
    PENDING = "pending"
    KEEP_REENCODED = "keep_reencoded"
    PIXEL_REDACT = "pixel_redact"
    REMOVE = "remove"


class ObjectDisposition(StrEnum):
    PENDING = "pending"
    REMOVE = "remove"
    VISIBLE_NOTE = "visible_note"
    SEPARATE_TASK = "separate_task"


@dataclass(slots=True)
class SourceLocation:
    part: str
    display: str
    block_id: str | None = None
    sheet: str | None = None
    cell: str | None = None
    image_id: str | None = None
    start: int | None = None
    end: int | None = None
    bbox: tuple[int, int, int, int] | None = None


@dataclass(slots=True)
class TextBlock:
    text: str
    location: SourceLocation
    block_kind: str = "paragraph"
    style: dict[str, Any] = field(default_factory=dict)
    hidden: bool = False
    id: str = field(default_factory=lambda: uuid4().hex)


@dataclass(slots=True)
class ImageRegion:
    bbox: tuple[int, int, int, int]
    category: Category
    replacement_label: str


@dataclass(slots=True)
class ImageObject:
    source_part: str
    location: SourceLocation
    content: bytes = field(repr=False)
    media_type: str = "image/png"
    width: int | None = None
    height: int | None = None
    alt_text: str = ""
    disposition: ImageDisposition = ImageDisposition.PENDING
    regions: list[ImageRegion] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid4().hex)


@dataclass(slots=True)
class PackageItem:
    part: str
    kind: str
    relationship_target: str | None = None
    external: bool = False
    hidden: bool = False
    requires_decision: bool = False
    disposition: ObjectDisposition = ObjectDisposition.PENDING
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PackageInventory:
    parts: list[PackageItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)

    @property
    def unresolved_items(self) -> list[PackageItem]:
        return [
            item
            for item in self.parts
            if item.requires_decision and item.disposition is ObjectDisposition.PENDING
        ]


@dataclass(slots=True)
class DocumentModel:
    kind: DocumentKind
    source_path: Path
    source_sha256: str
    display_name: str
    blocks: list[TextBlock] = field(default_factory=list)
    images: list[ImageObject] = field(default_factory=list)
    inventory: PackageInventory = field(default_factory=PackageInventory)
    document_properties: dict[str, str] = field(default_factory=dict)
    structure: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Finding:
    category: Category
    modality: Modality
    original: str
    locations: list[SourceLocation]
    detector: str
    confidence: float
    suggested_method: TransformMethod
    replacement: str = ""
    preserved_semantics: str = ""
    context: str = ""
    combination_score: int = 0
    status: FindingStatus = FindingStatus.PENDING
    ignore_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid4().hex)

    @property
    def occurrence_count(self) -> int:
        return len(self.locations)


@dataclass(slots=True)
class MappingEntry:
    mapping_id: str
    category: Category
    original: str
    replacement: str
    method: TransformMethod
    occurrence_count: int
    locations: list[str]
    restore_note: str = ""
    rule_source: str = ""


@dataclass(slots=True)
class ExportArtifacts:
    result_root: Path
    ai_copy: Path
    encrypted_mapping: Path
    report: Path
    hashes: dict[str, str]
    warnings: list[str] = field(default_factory=list)
