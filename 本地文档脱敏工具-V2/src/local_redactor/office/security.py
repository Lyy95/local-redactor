from __future__ import annotations

import hashlib
import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from lxml import etree  # type: ignore[import-untyped]

from ..models import (
    DocumentKind,
    ObjectDisposition,
    PackageInventory,
    PackageItem,
)

CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
RELATIONSHIPS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_DOCUMENT_REL = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
)

_DRIVE_PATH = re.compile(r"^[A-Za-z]:")
_FORBIDDEN_XML_DECLARATIONS = (b"<!doctype", b"<!entity")
_MACRO_MARKERS = (
    "vbaproject",
    "vbaProject",
    "macroenabled",
    "macroEnabled",
    "activex",
    "activeX",
)


class OoxmlSecurityError(ValueError):
    """Raised when an OOXML package cannot be handled safely."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ExportSafetyError(ValueError):
    """Raised when a reviewed document cannot be rebuilt safely."""


@dataclass(frozen=True, slots=True)
class OoxmlLimits:
    max_archive_bytes: int = 256 * 1024 * 1024
    max_parts: int = 20_000
    max_uncompressed_bytes: int = 1024 * 1024 * 1024
    max_single_part_bytes: int = 256 * 1024 * 1024
    max_xml_part_bytes: int = 24 * 1024 * 1024
    max_total_xml_bytes: int = 256 * 1024 * 1024
    max_compression_ratio: float = 150.0


@dataclass(frozen=True, slots=True)
class RelationshipRecord:
    relationship_part: str
    source_part: str
    relationship_id: str
    relationship_type: str
    target: str
    target_mode: str
    resolved_target: str | None

    @property
    def external(self) -> bool:
        return self.target_mode.casefold() == "external"


@dataclass(slots=True)
class OoxmlPreflight:
    path: Path
    kind: DocumentKind
    source_sha256: str
    inventory: PackageInventory
    part_names: frozenset[str]
    content_types: dict[str, str] = field(default_factory=dict)
    relationships: list[RelationshipRecord] = field(default_factory=list)
    compressed_bytes: int = 0
    uncompressed_bytes: int = 0


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def safe_xml_root(data: bytes, *, part_name: str) -> etree._Element:
    lowered = data[: min(len(data), 1_048_576)].lower()
    if any(marker in lowered for marker in _FORBIDDEN_XML_DECLARATIONS):
        raise OoxmlSecurityError(
            "xml-external-entity",
            f"OOXML XML 部件包含被禁止的 DTD/实体声明：{part_name}",
        )
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        huge_tree=False,
        recover=False,
        remove_comments=False,
    )
    try:
        return etree.fromstring(data, parser=parser)
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise OoxmlSecurityError(
            "invalid-xml",
            f"OOXML XML 部件无法安全解析：{part_name}",
        ) from exc


def _safe_member_name(raw_name: str) -> str:
    if "\x00" in raw_name:
        raise OoxmlSecurityError("unsafe-part-name", "OOXML 部件名包含空字符")
    candidate = raw_name.replace("\\", "/")
    if candidate.startswith(("/", "//")) or _DRIVE_PATH.match(candidate):
        raise OoxmlSecurityError(
            "zip-path-traversal",
            f"OOXML 部件使用绝对路径：{raw_name}",
        )
    path = PurePosixPath(candidate)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise OoxmlSecurityError(
            "zip-path-traversal",
            f"OOXML 部件路径不安全：{raw_name}",
        )
    normalized = str(path)
    if normalized != candidate.rstrip("/"):
        raise OoxmlSecurityError(
            "zip-path-traversal",
            f"OOXML 部件路径无法规范化：{raw_name}",
        )
    return normalized


def _relationship_source(rels_name: str) -> str:
    if rels_name == "_rels/.rels":
        return ""
    marker = "/_rels/"
    if marker not in rels_name or not rels_name.endswith(".rels"):
        raise OoxmlSecurityError(
            "invalid-relationship-part",
            f"关系部件路径不符合 OOXML 约定：{rels_name}",
        )
    parent, filename = rels_name.split(marker, maxsplit=1)
    return f"{parent}/{filename[:-5]}"


def _resolve_internal_target(source_part: str, target: str) -> str:
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        raise OoxmlSecurityError(
            "disguised-external-relationship",
            "内部关系包含网络或 URI scheme 目标",
        )
    decoded = unquote(parsed.path).replace("\\", "/")
    if "\x00" in decoded or _DRIVE_PATH.match(decoded):
        raise OoxmlSecurityError(
            "unsafe-relationship-target",
            "内部关系包含不安全路径",
        )
    if decoded.startswith("/"):
        combined = decoded.lstrip("/")
    else:
        base = posixpath.dirname(source_part)
        combined = posixpath.join(base, decoded)
    normalized = posixpath.normpath(combined)
    if normalized in {"", "."} or normalized == ".." or normalized.startswith("../"):
        raise OoxmlSecurityError(
            "relationship-path-traversal",
            "内部关系目标逃逸 OOXML 包",
        )
    return _safe_member_name(normalized)


def _read_content_types(
    archive: zipfile.ZipFile,
    names: set[str],
    limits: OoxmlLimits,
) -> dict[str, str]:
    content_types_name = "[Content_Types].xml"
    if content_types_name not in names:
        raise OoxmlSecurityError(
            "missing-content-types",
            "OOXML 包缺少 [Content_Types].xml",
        )
    info = archive.getinfo(content_types_name)
    if info.file_size > limits.max_xml_part_bytes:
        raise OoxmlSecurityError(
            "xml-part-too-large",
            "OOXML 内容类型部件超过安全上限",
        )
    root = safe_xml_root(archive.read(info), part_name=content_types_name)
    result: dict[str, str] = {}
    defaults: dict[str, str] = {}
    for child in root:
        local_name = etree.QName(child).localname
        if local_name == "Default":
            extension = child.get("Extension", "").casefold()
            content_type = child.get("ContentType", "")
            if extension:
                defaults[extension] = content_type
        elif local_name == "Override":
            part_name = child.get("PartName", "").lstrip("/")
            content_type = child.get("ContentType", "")
            if part_name:
                result[part_name] = content_type
    for name in names:
        if name in result:
            continue
        extension = PurePosixPath(name).suffix.lstrip(".").casefold()
        if extension in defaults:
            result[name] = defaults[extension]
    return result


def _relationship_kind(record: RelationshipRecord) -> str:
    relation = record.relationship_type.casefold()
    if relation.endswith("/hyperlink"):
        return "hyperlink"
    if "attachedtemplate" in relation:
        return "remote_template"
    if "externallink" in relation:
        return "external_link"
    if "oleobject" in relation or relation.endswith("/package"):
        return "embedded_object"
    if "image" in relation:
        return "image_relation"
    if "comments" in relation:
        return "comment_relation"
    known_internal_suffixes = {
        "/calculationchain",
        "/core-properties",
        "/custom-properties",
        "/drawing",
        "/endnotes",
        "/extended-properties",
        "/fonttable",
        "/footer",
        "/footnotes",
        "/header",
        "/image",
        "/numbering",
        "/officedocument",
        "/settings",
        "/sharedstrings",
        "/styles",
        "/styleswitheffects",
        "/table",
        "/theme",
        "/thumbnail",
        "/websettings",
        "/worksheet",
    }
    if not record.external and any(relation.endswith(suffix) for suffix in known_internal_suffixes):
        return "relationship"
    return "external_relationship" if record.external else "unknown_relationship"


def _part_kind(name: str, content_type: str, document_kind: DocumentKind) -> str:
    lowered = name.casefold()
    content = content_type.casefold()
    if lowered.startswith("docprops/"):
        return "document_property"
    if "/media/" in lowered or content.startswith("image/"):
        return "image"
    if "/embeddings/" in lowered or "oleobject" in content:
        return "embedded_object"
    if "customxml" in lowered:
        return "custom_xml"
    if "comments" in lowered or "threadedcomments" in lowered:
        return "comment"
    if "footnotes" in lowered:
        return "footnote"
    if "endnotes" in lowered:
        return "endnote"
    if "/header" in lowered:
        return "header"
    if "/footer" in lowered:
        return "footer"
    if "externallinks" in lowered:
        return "external_link"
    if "connections" in lowered:
        return "data_connection"
    if "pivotcache" in lowered:
        return "pivot_cache"
    if "/drawings/" in lowered:
        return "drawing"
    if "/charts/" in lowered:
        return "chart"
    if lowered.endswith(".rels"):
        return "relationships"
    if lowered.endswith(".xml"):
        common_xml = lowered == "[content_types].xml"
        if document_kind is DocumentKind.DOCX:
            known_xml = (
                lowered == "word/document.xml"
                or lowered
                in {
                    "word/fonttable.xml",
                    "word/numbering.xml",
                    "word/settings.xml",
                    "word/styles.xml",
                    "word/styleswitheffects.xml",
                    "word/websettings.xml",
                }
                or lowered.startswith("word/theme/theme")
            )
        else:
            known_xml = (
                lowered
                in {
                    "xl/calcchain.xml",
                    "xl/sharedstrings.xml",
                    "xl/styles.xml",
                    "xl/workbook.xml",
                }
                or lowered.startswith("xl/worksheets/sheet")
                or lowered.startswith("xl/theme/theme")
            )
        return "xml" if common_xml or known_xml else "unknown_xml"
    return "binary"


def _part_requires_decision(kind: str) -> bool:
    return kind in {
        "embedded_object",
        "custom_xml",
        "comment",
        "footnote",
        "endnote",
        "header",
        "footer",
        "external_link",
        "data_connection",
        "pivot_cache",
        "chart",
        "binary",
        "unknown_xml",
        "unknown_relationship",
    }


def _default_disposition(kind: str, requires_decision: bool) -> ObjectDisposition:
    if not requires_decision or kind == "document_property":
        return ObjectDisposition.REMOVE
    return ObjectDisposition.PENDING


def _check_macro_markers(names: set[str], content_types: dict[str, str]) -> None:
    for name in names:
        if any(marker.casefold() in name.casefold() for marker in _MACRO_MARKERS):
            raise OoxmlSecurityError(
                "active-content",
                "检测到宏或 ActiveX 部件，首版不处理",
            )
    for content_type in content_types.values():
        if any(marker.casefold() in content_type.casefold() for marker in _MACRO_MARKERS):
            raise OoxmlSecurityError(
                "macro-enabled-content-type",
                "检测到宏启用的 Office 内容类型，首版不处理",
            )


def _parse_relationships(
    archive: zipfile.ZipFile,
    names: set[str],
    limits: OoxmlLimits,
) -> list[RelationshipRecord]:
    records: list[RelationshipRecord] = []
    for rels_name in sorted(name for name in names if name.endswith(".rels")):
        info = archive.getinfo(rels_name)
        if info.file_size > limits.max_xml_part_bytes:
            raise OoxmlSecurityError(
                "xml-part-too-large",
                f"OOXML 关系部件超过安全上限：{rels_name}",
            )
        root = safe_xml_root(archive.read(info), part_name=rels_name)
        source_part = _relationship_source(rels_name)
        seen_ids: set[str] = set()
        for relation in root:
            if etree.QName(relation).namespace != RELATIONSHIPS_NS:
                continue
            relationship_id = relation.get("Id", "")
            relationship_type = relation.get("Type", "")
            target = relation.get("Target", "")
            target_mode = relation.get("TargetMode", "Internal")
            if not relationship_id or relationship_id in seen_ids:
                raise OoxmlSecurityError(
                    "invalid-relationship-id",
                    f"OOXML 关系 ID 缺失或重复：{rels_name}",
                )
            seen_ids.add(relationship_id)
            if not relationship_type or not target:
                raise OoxmlSecurityError(
                    "invalid-relationship",
                    f"OOXML 关系缺少类型或目标：{rels_name}",
                )
            external = target_mode.casefold() == "external"
            resolved_target = None
            if not external:
                resolved_target = _resolve_internal_target(source_part, target)
                if resolved_target not in names:
                    raise OoxmlSecurityError(
                        "missing-relationship-target",
                        f"OOXML 内部关系目标不存在：{resolved_target}",
                    )
            records.append(
                RelationshipRecord(
                    relationship_part=rels_name,
                    source_part=source_part,
                    relationship_id=relationship_id,
                    relationship_type=relationship_type,
                    target=target,
                    target_mode=target_mode,
                    resolved_target=resolved_target,
                )
            )
    return records


def _validate_main_part(
    kind: DocumentKind,
    names: set[str],
    content_types: dict[str, str],
    relationships: list[RelationshipRecord],
) -> None:
    expected_main = "word/document.xml" if kind is DocumentKind.DOCX else "xl/workbook.xml"
    expected_content_fragment = (
        "wordprocessingml.document.main+xml"
        if kind is DocumentKind.DOCX
        else "spreadsheetml.sheet.main+xml"
    )
    if expected_main not in names:
        raise OoxmlSecurityError(
            "extension-mismatch",
            f"扩展名与 OOXML 主部件不匹配，缺少 {expected_main}",
        )
    content_type = content_types.get(expected_main, "").casefold()
    if expected_content_fragment not in content_type:
        raise OoxmlSecurityError(
            "extension-mismatch",
            "扩展名与 OOXML 主内容类型不匹配",
        )
    root_targets = {
        relation.resolved_target
        for relation in relationships
        if relation.source_part == ""
        and relation.relationship_type == OFFICE_DOCUMENT_REL
        and not relation.external
    }
    if expected_main not in root_targets:
        raise OoxmlSecurityError(
            "missing-office-document-relationship",
            "OOXML 根关系未指向预期主文档",
        )


def preflight_ooxml(
    path: Path,
    expected_kind: DocumentKind | None = None,
    *,
    limits: OoxmlLimits | None = None,
) -> OoxmlPreflight:
    selected_limits = limits or OoxmlLimits()
    path = Path(path)
    suffix = path.suffix.casefold()
    suffix_kind = {
        ".docx": DocumentKind.DOCX,
        ".xlsx": DocumentKind.XLSX,
    }.get(suffix)
    if suffix_kind is None:
        raise OoxmlSecurityError(
            "unsupported-extension",
            "首版只支持 .docx 与 .xlsx",
        )
    if expected_kind is not None and suffix_kind is not expected_kind:
        raise OoxmlSecurityError(
            "extension-mismatch",
            "文件扩展名与所选 Office 适配器不一致",
        )
    if not path.is_file():
        raise OoxmlSecurityError("missing-file", "所选文件不存在或不是普通文件")
    if path.stat().st_size > selected_limits.max_archive_bytes:
        raise OoxmlSecurityError("archive-too-large", "Office 文件超过安全大小上限")
    with path.open("rb") as stream:
        signature = stream.read(8)
    if not signature.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        raise OoxmlSecurityError(
            "not-ooxml-zip",
            "文件不是可识别的现代 Office OOXML 包，可能是旧格式、加密文件或扩展名伪装",
        )
    if not zipfile.is_zipfile(path):
        raise OoxmlSecurityError("invalid-zip", "Office OOXML 压缩包已损坏")

    inventory = PackageInventory()
    with zipfile.ZipFile(path, mode="r") as archive:
        infos = archive.infolist()
        if len(infos) > selected_limits.max_parts:
            raise OoxmlSecurityError("too-many-parts", "OOXML 部件数量超过安全上限")
        names: set[str] = set()
        total_uncompressed = 0
        total_compressed = 0
        total_xml = 0
        for info in infos:
            if info.is_dir():
                _safe_member_name(info.filename)
                continue
            safe_name = _safe_member_name(info.filename)
            if safe_name in names:
                raise OoxmlSecurityError(
                    "duplicate-part",
                    f"OOXML 包含重复部件名：{safe_name}",
                )
            names.add(safe_name)
            if info.flag_bits & 0x1:
                raise OoxmlSecurityError(
                    "encrypted-zip-entry",
                    "OOXML 包含加密 ZIP 部件，首版不处理",
                )
            if info.file_size > selected_limits.max_single_part_bytes:
                raise OoxmlSecurityError(
                    "part-too-large",
                    f"OOXML 单个部件超过安全上限：{safe_name}",
                )
            total_uncompressed += info.file_size
            total_compressed += info.compress_size
            if total_uncompressed > selected_limits.max_uncompressed_bytes:
                raise OoxmlSecurityError(
                    "uncompressed-quota",
                    "OOXML 解压后总量超过安全上限",
                )
            ratio = info.file_size / max(info.compress_size, 1)
            if info.file_size >= 1024 * 1024 and ratio > selected_limits.max_compression_ratio:
                raise OoxmlSecurityError(
                    "compression-ratio",
                    f"OOXML 部件压缩率异常：{safe_name}",
                )
            if safe_name.endswith((".xml", ".rels")):
                total_xml += info.file_size
                if info.file_size > selected_limits.max_xml_part_bytes:
                    raise OoxmlSecurityError(
                        "xml-part-too-large",
                        f"OOXML XML 部件超过安全上限：{safe_name}",
                    )
                if total_xml > selected_limits.max_total_xml_bytes:
                    raise OoxmlSecurityError(
                        "xml-total-too-large",
                        "OOXML XML 总量超过安全上限",
                    )
                safe_xml_root(archive.read(info), part_name=safe_name)

        content_types = _read_content_types(archive, names, selected_limits)
        _check_macro_markers(names, content_types)
        relationships = _parse_relationships(archive, names, selected_limits)
        _validate_main_part(suffix_kind, names, content_types, relationships)

        for name in sorted(names):
            kind = _part_kind(name, content_types.get(name, ""), suffix_kind)
            requires_decision = _part_requires_decision(kind)
            inventory.parts.append(
                PackageItem(
                    part=name,
                    kind=kind,
                    hidden=kind
                    in {
                        "document_property",
                        "custom_xml",
                        "comment",
                        "footnote",
                        "endnote",
                        "external_link",
                        "data_connection",
                        "pivot_cache",
                    },
                    requires_decision=requires_decision,
                    disposition=_default_disposition(kind, requires_decision),
                    details={
                        "content_type": content_types.get(name, ""),
                        "uncompressed_size": archive.getinfo(name).file_size,
                        "compressed_size": archive.getinfo(name).compress_size,
                    },
                )
            )
        for relationship in relationships:
            kind = _relationship_kind(relationship)
            requires_decision = relationship.external or kind in {
                "hyperlink",
                "remote_template",
                "external_link",
                "embedded_object",
                "unknown_relationship",
            }
            inventory.parts.append(
                PackageItem(
                    part=(f"{relationship.relationship_part}#{relationship.relationship_id}"),
                    kind=kind,
                    relationship_target=relationship.target,
                    external=relationship.external,
                    hidden=relationship.external,
                    requires_decision=requires_decision,
                    disposition=_default_disposition(kind, requires_decision),
                    details={
                        "source_part": relationship.source_part,
                        "relationship_type": relationship.relationship_type,
                        "resolved_target": relationship.resolved_target,
                    },
                )
            )

    return OoxmlPreflight(
        path=path,
        kind=suffix_kind,
        source_sha256=sha256_file(path),
        inventory=inventory,
        part_names=frozenset(names),
        content_types=content_types,
        relationships=relationships,
        compressed_bytes=total_compressed,
        uncompressed_bytes=total_uncompressed,
    )
