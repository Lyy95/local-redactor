from __future__ import annotations

import ipaddress
import math
import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from decimal import ROUND_FLOOR, Decimal, InvalidOperation

from local_redactor.models import (
    Category,
    DocumentModel,
    Finding,
    FindingStatus,
    MappingEntry,
    ProcessingMode,
    TransformMethod,
)

from .common import location_label, normalize_entity

_ALIAS_MARKERS = (
    "甲",
    "乙",
    "丙",
    "丁",
    "戊",
    "己",
    "庚",
    "辛",
    "壬",
    "癸",
)

_COMPOUND_SURNAMES = frozenset(
    {
        "欧阳",
        "司马",
        "上官",
        "诸葛",
        "东方",
        "皇甫",
        "尉迟",
        "公孙",
        "慕容",
        "令狐",
        "钟离",
        "宇文",
        "长孙",
        "司徒",
        "司空",
        "夏侯",
        "独孤",
        "南宫",
        "万俟",
        "闻人",
        "赫连",
        "澹台",
        "宗政",
        "濮阳",
        "淳于",
        "单于",
        "太史",
        "申屠",
        "公冶",
        "轩辕",
        "百里",
        "呼延",
        "东郭",
        "南门",
        "东门",
        "西门",
    }
)

_MAPPING_PREFIX: dict[Category, str] = {
    Category.NAME: "PERSON",
    Category.ID_CARD: "ID",
    Category.PHONE: "PHONE",
    Category.ADDRESS: "ADDRESS",
    Category.VEHICLE_PLATE: "VEHICLE",
    Category.ACCOUNT: "ACCOUNT",
    Category.ORGANIZATION: "ORG",
    Category.DEPARTMENT: "DEPT",
    Category.PROJECT: "PROJECT",
    Category.SYSTEM: "SYSTEM",
    Category.LOCATION: "LOCATION",
    Category.TIME: "TIME",
    Category.MONEY: "MONEY",
    Category.CASE_ID: "CASE",
    Category.DEVICE_ID: "DEVICE",
    Category.PUBLIC_IP: "PUBLIC-IP",
    Category.PRIVATE_IP: "PRIVATE-IP",
    Category.DOMAIN: "DOMAIN",
    Category.EMAIL: "EMAIL",
    Category.USERNAME: "USER",
    Category.SECRET: "SECRET",
    Category.IMAGE_TEXT: "IMAGE-TEXT",
    Category.SEAL: "SEAL",
    Category.SIGNATURE: "SIGNATURE",
    Category.QR_CODE: "QR",
    Category.PHOTO: "PHOTO",
    Category.FILE_PROPERTY: "PROPERTY",
    Category.REVISION: "REVISION",
    Category.COMMENT: "COMMENT",
    Category.HIDDEN_CONTENT: "HIDDEN",
    Category.HEADER_FOOTER: "HEADER",
    Category.WATERMARK: "WATERMARK",
    Category.ATTACHMENT: "ATTACHMENT",
    Category.EMBEDDED_OBJECT: "OBJECT",
    Category.HYPERLINK: "LINK",
    Category.OTHER: "OTHER",
}


@dataclass(slots=True)
class _MappingAccumulator:
    mapping_id: str
    category: Category
    originals: list[str]
    replacement: str
    method: TransformMethod
    occurrence_count: int = 0
    locations: list[str] = field(default_factory=list)
    restore_note: str = ""
    rule_sources: list[str] = field(default_factory=list)

    def add(self, finding: Finding) -> None:
        if finding.original and finding.original not in self.originals:
            self.originals.append(finding.original)
        self.occurrence_count += finding.occurrence_count
        for location in finding.locations:
            label = location_label(location)
            if label not in self.locations:
                self.locations.append(label)
        rule_source = str(finding.metadata.get("rule_name", "")).strip()
        if rule_source and rule_source not in self.rule_sources:
            self.rule_sources.append(rule_source)

    def to_entry(self) -> MappingEntry:
        return MappingEntry(
            mapping_id=self.mapping_id,
            category=self.category,
            original="；".join(self.originals),
            replacement=self.replacement,
            method=self.method,
            occurrence_count=self.occurrence_count,
            locations=list(self.locations),
            restore_note=self.restore_note,
            rule_source="；".join(self.rule_sources),
        )


class _TaskTransformState:
    def __init__(self, mode: ProcessingMode, date_shift_days: int) -> None:
        self.mode = mode
        self.date_shift_days = date_shift_days
        self.replacements: dict[tuple[Category, str], str] = {}
        self.sequences: dict[Category, int] = defaultdict(int)
        self.mapping_sequences: dict[Category, int] = defaultdict(int)
        self.user_indices: dict[str, int] = {}
        self.domain_indices: dict[str, int] = {}
        self.private_network_indices: dict[str, int] = {}

    def next_index(self, category: Category) -> int:
        self.sequences[category] += 1
        return self.sequences[category]

    def next_mapping_id(self, category: Category) -> str:
        self.mapping_sequences[category] += 1
        prefix = _MAPPING_PREFIX.get(category, category.value.upper())
        return f"{prefix}-{self.mapping_sequences[category]:03d}"

    def alias(self, index: int) -> str:
        if index <= len(_ALIAS_MARKERS):
            return _ALIAS_MARKERS[index - 1]
        return f"{index:02d}"

    def user_index(self, value: str) -> int:
        key = value.casefold()
        if key not in self.user_indices:
            self.user_indices[key] = len(self.user_indices) + 1
        return self.user_indices[key]

    def domain_index(self, value: str) -> int:
        key = value.casefold().rstrip(".")
        if key not in self.domain_indices:
            self.domain_indices[key] = len(self.domain_indices) + 1
        return self.domain_indices[key]

    def private_network_index(self, value: str) -> int:
        if value not in self.private_network_indices:
            self.private_network_indices[value] = len(self.private_network_indices) + 1
        return self.private_network_indices[value]


class SemanticTransformationEngine:
    """Prepare task-local, consistent replacements without persisting state."""

    def __init__(self, *, date_shift_days: int = 53) -> None:
        if date_shift_days == 0:
            raise ValueError("date_shift_days must not be zero")
        self.date_shift_days = date_shift_days

    def prepare(
        self,
        document: DocumentModel,
        findings: Sequence[Finding],
        mode: ProcessingMode,
    ) -> tuple[list[Finding], list[MappingEntry]]:
        del document  # Transformations use reviewed findings, never the source path.
        state = _TaskTransformState(mode, self.date_shift_days)
        self._register_relationships(findings, state)

        prepared: list[Finding] = []
        mappings: dict[tuple[Category, str], _MappingAccumulator] = {}
        mapping_order: list[tuple[Category, str]] = []

        for source in findings:
            finding = replace(
                source,
                locations=list(source.locations),
                metadata=dict(source.metadata),
            )
            if finding.status is FindingStatus.KEEP_FALSE_POSITIVE:
                finding.suggested_method = TransformMethod.KEEP
                finding.replacement = finding.original
                prepared.append(finding)
                continue

            if finding.category is Category.COMBINATION_RISK:
                finding.replacement = ""
                finding.suggested_method = TransformMethod.GENERALIZE
                prepared.append(finding)
                continue

            normalized = normalize_entity(finding.category, finding.original)
            key = (finding.category, normalized)
            method = (
                TransformMethod.REMOVE
                if finding.status is FindingStatus.REMOVE
                else finding.suggested_method
            )

            if finding.replacement:
                cached = state.replacements.get(key)
                if cached is None:
                    state.replacements[key] = finding.replacement
                elif cached != finding.replacement:
                    finding.replacement = cached
                    finding.metadata["replacement_conflict_resolved"] = True
            else:
                replacement_value = state.replacements.get(key)
                if replacement_value is None:
                    replacement_value = self._replacement_for(
                        finding,
                        method,
                        state,
                    )
                    state.replacements[key] = replacement_value
                finding.replacement = replacement_value

            finding.suggested_method = method
            prepared.append(finding)
            if (
                not finding.original
                or method is TransformMethod.KEEP
                or finding.category is Category.SECRET
            ):
                continue

            accumulator = mappings.get(key)
            if accumulator is None:
                accumulator = _MappingAccumulator(
                    mapping_id=state.next_mapping_id(finding.category),
                    category=finding.category,
                    originals=[],
                    replacement=finding.replacement,
                    method=method,
                    restore_note=self._restore_note(finding, method, state),
                )
                mappings[key] = accumulator
                mapping_order.append(key)
            accumulator.add(finding)

        return prepared, [mappings[key].to_entry() for key in mapping_order]

    @staticmethod
    def _register_relationships(
        findings: Iterable[Finding],
        state: _TaskTransformState,
    ) -> None:
        for finding in findings:
            if finding.category is not Category.EMAIL or "@" not in finding.original:
                continue
            local, domain = finding.original.rsplit("@", 1)
            state.user_index(local)
            state.domain_index(domain)

    def _replacement_for(
        self,
        finding: Finding,
        method: TransformMethod,
        state: _TaskTransformState,
    ) -> str:
        if method is TransformMethod.REMOVE:
            return ""
        category = finding.category
        index = state.next_index(category)
        marker = state.alias(index)
        strict = state.mode is ProcessingMode.STRICT
        original = finding.original

        if category is Category.NAME:
            return _mask_chinese_name(original)
        if category is Category.ID_CARD:
            return _mask_identifier(original, keep_prefix=6, keep_suffix=4)
        if category is Category.PHONE:
            if finding.metadata.get("contact_kind") == "landline":
                return _mask_landline(original)
            return _mask_mobile(original)
        if category is Category.ADDRESS:
            return "某地区" if strict else _generalize_address(original)
        if category is Category.VEHICLE_PLATE:
            if strict:
                return f"车辆{index:02d}"
            compact = re.sub(r"[\s·-]", "", original)
            vehicle_type = "新能源汽车" if len(compact) == 8 else "小型汽车"
            return f"车辆{marker}（{vehicle_type}）"
        if category is Category.ACCOUNT:
            if finding.metadata.get("account_kind") == "bank":
                return _mask_identifier(original, keep_prefix=6, keep_suffix=4)
            if strict:
                return f"账号{index:02d}"
            kind = str(finding.metadata.get("account_kind", "platform"))
            label = "对公账户" if kind == "bank" else "平台账号"
            return f"{label}{marker}"
        if category is Category.ORGANIZATION:
            if strict:
                return f"机构{index:02d}"
            suffix = _organization_suffix(original)
            role = str(finding.metadata.get("organization_role", "")).strip()
            return f"{marker}{suffix}" + (f"（{role}）" if role else "")
        if category is Category.DEPARTMENT:
            if strict:
                return f"部门{index:02d}"
            return f"{_department_function(original)}部门{marker}"
        if category is Category.PROJECT:
            if strict:
                return f"项目{index:02d}"
            return f"{_project_type(original)}项目{marker}"
        if category is Category.SYSTEM:
            if strict:
                return f"系统{index:02d}"
            return f"{_system_type(original)}系统{marker}"
        if category is Category.LOCATION:
            return "某地区" if strict else _generalize_location(original)
        if category is Category.TIME:
            return _transform_time(original, finding.metadata, state)
        if category is Category.MONEY:
            return _transform_money(finding.metadata, strict)
        if category is Category.CASE_ID:
            if strict:
                return f"案件{index:02d}"
            year_match = re.search(r"(?:19|20)\d{2}", original)
            year = year_match.group(0) if year_match else "2026"
            return f"CASE-{year}-{index:04d}"
        if category is Category.DEVICE_ID:
            return f"设备{index:02d}" if strict else f"DEVICE-{index:04d}"
        if category is Category.PUBLIC_IP:
            if strict:
                return f"网络地址{index:02d}"
            networks = ("192.0.2", "198.51.100", "203.0.113")
            network = networks[(index - 1) % len(networks)]
            host = 10 + ((index - 1) % 235)
            return f"{network}.{host}"
        if category is Category.PRIVATE_IP:
            if strict:
                return f"内网地址{index:02d}"
            return _simulate_private_ip(original, index, state)
        if category is Category.DOMAIN:
            if strict:
                return f"域名{index:02d}"
            return _simulate_domain(original, state)
        if category is Category.EMAIL:
            return _mask_email(original)
        if category is Category.USERNAME:
            user_index = state.user_index(original)
            return f"用户{user_index:02d}" if strict else f"user{user_index:02d}"
        if category is Category.SECRET:
            return ""
        if category is Category.IMAGE_TEXT:
            return f"[图片文字{index:02d}]" if strict else f"[图片文字{marker}]"
        if category is Category.SEAL:
            return f"[印章{index:02d}]" if strict else f"[印章{marker}·候选]"
        if category is Category.SIGNATURE:
            return f"[签名{index:02d}]" if strict else f"[签名{marker}]"
        if category is Category.QR_CODE:
            return "[二维码已移除]"
        if category is Category.PHOTO:
            return "[图片已移除]" if strict else "[图片已处理]"
        if category is Category.HEADER_FOOTER:
            return "" if strict else f"[页眉页脚内容{marker}]"
        if category is Category.HYPERLINK:
            return f"[链接用途{index:02d}]"
        if category in {
            Category.FILE_PROPERTY,
            Category.REVISION,
            Category.COMMENT,
            Category.HIDDEN_CONTENT,
            Category.WATERMARK,
            Category.ATTACHMENT,
            Category.EMBEDDED_OBJECT,
        }:
            return ""
        return f"[信息{index:02d}]"

    @staticmethod
    def _restore_note(
        finding: Finding,
        method: TransformMethod,
        state: _TaskTransformState,
    ) -> str:
        if finding.category is Category.TIME and method is TransformMethod.SHIFT:
            sign = "+" if state.date_shift_days > 0 else ""
            inverse = -state.date_shift_days
            inverse_sign = "+" if inverse > 0 else ""
            return (
                f"所有日期按同样天数调整{sign}{state.date_shift_days}天；"
                f"需要还原时平移{inverse_sign}{inverse}天。"
            )
        if finding.category is Category.MONEY:
            return "金额只保留大致范围，不能从范围反推；还原以本行原始值为准。"
        if method is TransformMethod.REMOVE:
            return "副本中已移除；还原以本行原始值和位置为准。"
        if method in {
            TransformMethod.GENERALIZE,
            TransformMethod.RANGE,
        }:
            return "替代值经过泛化；精确还原以本行原始值和位置为准。"
        return "按映射编号、替代值和位置对应还原。"


def _mask_chinese_name(value: str) -> str:
    name = value.strip()
    if not name:
        return ""
    surname_length = 2 if name[:2] in _COMPOUND_SURNAMES else 1
    surname = name[:surname_length]
    given_length = max(1, len(name) - surname_length)
    return surname + "*" * given_length


def _mask_identifier(value: str, *, keep_prefix: int, keep_suffix: int) -> str:
    compact = re.sub(r"[\s-]+", "", value)
    if len(compact) <= keep_prefix + keep_suffix:
        return "*" * len(compact)
    return (
        compact[:keep_prefix]
        + "*" * (len(compact) - keep_prefix - keep_suffix)
        + compact[-keep_suffix:]
    )


def _mask_mobile(value: str) -> str:
    compact = re.sub(r"[\s-]+", "", value)
    compact = re.sub(r"^\+?86", "", compact)
    return _mask_identifier(compact, keep_prefix=3, keep_suffix=4)


def _mask_landline(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return "*" * 4 + digits[-4:]


def _mask_email(value: str) -> str:
    local, separator, domain = value.rpartition("@")
    if not separator:
        return "*" * len(value)
    visible = local[:2]
    hidden_count = max(1, len(local) - len(visible))
    return f"{visible}{'*' * hidden_count}@{domain}"


def _generalize_address(value: str) -> str:
    province = re.search(r"([\u4e00-\u9fff]{2,8}(?:省|自治区|特别行政区))", value)
    city = re.search(r"([\u4e00-\u9fff]{2,8}(?:市|州|盟))", value)
    district = re.search(r"([\u4e00-\u9fff]{1,8}(?:区|县|旗))", value)
    if province and city:
        return f"{province.group(1)}{city.group(1)}某区"
    if city:
        return f"{city.group(1)}某区"
    if province:
        return f"{province.group(1)}某市"
    if district:
        return "某市某区"
    return "某市某区"


def _generalize_location(value: str) -> str:
    province = re.search(r"([\u4e00-\u9fff]{2,8}(?:省|自治区|特别行政区))", value)
    city = re.search(r"([\u4e00-\u9fff]{2,8}(?:市|州|盟))", value)
    district = re.search(r"([\u4e00-\u9fff]{1,8}(?:区|县|旗))", value)
    if province and city:
        return f"{province.group(1)}某市"
    if city and district:
        return f"{city.group(1)}某区"
    if province:
        return f"{province.group(1)}某市"
    if city:
        return "某市"
    if district:
        return "某区"
    return "某地区"


def _organization_suffix(value: str) -> str:
    suffixes = (
        ("银行", "银行"),
        ("医院", "医院"),
        ("学校", "学校"),
        ("研究院", "研究机构"),
        ("研究所", "研究机构"),
        ("协会", "协会"),
        ("委员会", "委员会"),
        ("集团", "集团"),
        ("公司", "公司"),
        ("局", "市级单位"),
        ("厅", "省级单位"),
    )
    for token, replacement in suffixes:
        if token in value:
            return replacement
    return "机构"


def _department_function(value: str) -> str:
    rules = (
        (("研发", "技术", "信息"), "技术"),
        (("业务", "运营"), "业务"),
        (("财务", "审计"), "财务"),
        (("人事", "人力"), "人力"),
        (("法务", "合规"), "法务"),
        (("办公室", "综合"), "综合"),
    )
    for tokens, label in rules:
        if any(token in value for token in tokens):
            return label
    return "业务"


def _project_type(value: str) -> str:
    rules = (
        (("数据", "治理"), "数据治理类"),
        (("安全", "风控"), "安全类"),
        (("升级", "改造"), "升级改造类"),
        (("建设", "工程"), "建设类"),
    )
    for tokens, label in rules:
        if any(token in value for token in tokens):
            return label
    return "业务类"


def _system_type(value: str) -> str:
    rules = (
        (("案件", "案管"), "案件管理类"),
        (("数据", "治理"), "数据治理类"),
        (("办公", "OA"), "办公类"),
        (("运维", "监控"), "运维类"),
    )
    for tokens, label in rules:
        if any(token in value for token in tokens):
            return label
    return "业务类"


def _transform_time(
    original: str,
    metadata: dict[str, object],
    state: _TaskTransformState,
) -> str:
    iso = metadata.get("iso")
    if isinstance(iso, str):
        try:
            parsed = datetime.fromisoformat(iso)
        except ValueError:
            parsed = None
        if parsed is not None:
            shifted = parsed + timedelta(days=state.date_shift_days)
            if state.mode is ProcessingMode.STRICT:
                if len(original) <= 5 and "年" not in original:
                    return f"第{((shifted.month - 1) // 3) + 1}季度"
                return f"{shifted.year}年{shifted.month}月"
            if ":" in original or "时" in original:
                return f"{shifted.year}年{shifted.month}月{shifted.day}日{shifted.hour}时左右"
            if "年" in original or re.match(r"(?:19|20)\d{2}", original):
                return f"{shifted.year}年{shifted.month}月{shifted.day}日"
            return f"{shifted.month}月{shifted.day}日"

    if re.fullmatch(r"\d{1,2}:\d{2}", original):
        hour = int(original.split(":", 1)[0])
        if state.mode is ProcessingMode.STRICT:
            return "上午" if hour < 12 else "下午"
        return f"{hour}时左右"
    return "某时间段" if state.mode is ProcessingMode.STRICT else "某日"


def _transform_money(metadata: dict[str, object], strict: bool) -> str:
    try:
        amount = Decimal(str(metadata.get("amount_yuan", "0")))
    except InvalidOperation:
        amount = Decimal("0")
    if amount <= 0:
        return "某金额区间"

    power = int(math.floor(math.log10(float(amount))))
    step = Decimal(10) ** power if strict else Decimal(5) * (Decimal(10) ** max(power - 1, 0))
    lower = (amount / step).to_integral_value(rounding=ROUND_FLOOR) * step
    if lower <= 0:
        lower = step
    upper = lower + step
    unit_value, unit_label = _display_money_unit(upper)
    lower_display = lower / unit_value
    upper_display = upper / unit_value
    return f"{_decimal_text(lower_display)}{unit_label}—{_decimal_text(upper_display)}{unit_label}"


def _display_money_unit(value: Decimal) -> tuple[Decimal, str]:
    if value >= Decimal("100000000"):
        return Decimal("100000000"), "亿元"
    if value >= Decimal("10000"):
        return Decimal("10000"), "万元"
    return Decimal("1"), "元"


def _decimal_text(value: Decimal) -> str:
    normalized = value.normalize()
    text = format(normalized, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _simulate_private_ip(
    original: str,
    fallback_index: int,
    state: _TaskTransformState,
) -> str:
    try:
        address = ipaddress.ip_address(original)
    except ValueError:
        return f"10.254.1.{10 + fallback_index}"
    if address.version == 6:
        return f"fd00:254::{fallback_index:x}"
    network = ipaddress.ip_network(f"{address}/24", strict=False)
    network_index = state.private_network_index(str(network.network_address))
    host = 10 + ((fallback_index - 1) % 235)
    return f"10.254.{network_index}.{host}"


def _simulate_domain(original: str, state: _TaskTransformState) -> str:
    normalized = original.casefold().rstrip(".")
    parts = normalized.split(".")
    role = (
        parts[0]
        if len(parts) >= 3
        and parts[0]
        in {
            "api",
            "app",
            "mail",
            "oa",
            "vpn",
            "www",
        }
        else ""
    )
    index = state.domain_index(normalized)
    prefix = f"{role}." if role else ""
    return f"{prefix}org{index:02d}.example.invalid"


def _simulate_email(original: str, state: _TaskTransformState) -> str:
    if "@" not in original:
        index = state.user_index(original)
        return f"user{index:02d}@org01.example.invalid"
    local, domain = original.rsplit("@", 1)
    user_index = state.user_index(local)
    domain_index = state.domain_index(domain)
    return f"user{user_index:02d}@org{domain_index:02d}.example.invalid"


__all__ = ["SemanticTransformationEngine"]
