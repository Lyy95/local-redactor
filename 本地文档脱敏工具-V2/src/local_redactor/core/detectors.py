from __future__ import annotations

import importlib
import ipaddress
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from local_redactor.models import (
    Category,
    DocumentModel,
    Finding,
    Modality,
    SourceLocation,
    TransformMethod,
)

from .common import clone_location, expand_duplicate_locations, merge_findings, modality_for_block

Validator = Callable[[re.Match[str]], bool]
MetadataFactory = Callable[[re.Match[str]], dict[str, Any]]


@dataclass(frozen=True, slots=True)
class TaskTerm:
    term: str
    category: Category
    case_sensitive: bool = False
    suggested_method: TransformMethod | None = None
    preserved_semantics: str = ""


@dataclass(frozen=True, slots=True)
class _Rule:
    name: str
    category: Category
    pattern: re.Pattern[str]
    method: TransformMethod
    confidence: float
    group: str | int = 0
    validator: Validator | None = None
    metadata_factory: MetadataFactory | None = None
    suppress_if_overlapped: bool = False


def _default_method(category: Category) -> TransformMethod:
    if category in {
        Category.NAME,
        Category.ORGANIZATION,
        Category.DEPARTMENT,
        Category.PROJECT,
        Category.SYSTEM,
    }:
        return TransformMethod.ALIAS
    if category in {
        Category.ADDRESS,
        Category.LOCATION,
        Category.DOMAIN,
        Category.EMAIL,
        Category.HYPERLINK,
    }:
        return TransformMethod.GENERALIZE
    if category is Category.TIME:
        return TransformMethod.SHIFT
    if category is Category.MONEY:
        return TransformMethod.RANGE
    if category in {
        Category.IMAGE_TEXT,
        Category.SEAL,
        Category.SIGNATURE,
        Category.QR_CODE,
        Category.PHOTO,
    }:
        return TransformMethod.PIXEL_REDACT
    if category in {
        Category.FILE_PROPERTY,
        Category.REVISION,
        Category.COMMENT,
        Category.HIDDEN_CONTENT,
        Category.ATTACHMENT,
        Category.EMBEDDED_OBJECT,
        Category.WATERMARK,
        Category.SECRET,
    }:
        return TransformMethod.REMOVE
    return TransformMethod.SIMULATE


def _valid_chinese_id(match: re.Match[str]) -> bool:
    value = match.group(0).upper()
    if len(value) != 18 or not re.fullmatch(r"\d{17}[\dX]", value):
        return False
    try:
        datetime.strptime(value[6:14], "%Y%m%d")
    except ValueError:
        return False
    if value[:6] == "000000":
        return False
    weights = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
    check_codes = "10X98765432"
    total = sum(int(digit) * weight for digit, weight in zip(value[:17], weights, strict=True))
    return check_codes[total % 11] == value[-1]


def _valid_vehicle_plate(match: re.Match[str]) -> bool:
    value = re.sub(r"[\s·-]", "", match.group(0)).upper()
    return len(value) in {7, 8}


_GENERIC_LOCATION_TERMS = frozenset(
    {
        "各地市",
        "各省市",
        "各市县",
        "相关地市",
        "多个地市",
        "指导各地市",
        "面向各地市",
        "覆盖各地市",
        "全国各地",
        "本市",
        "该市",
        "全市",
        "市内",
    }
)


def _valid_administrative_location(match: re.Match[str]) -> bool:
    value = match.group(0).strip()
    if value in _GENERIC_LOCATION_TERMS:
        return False
    if any(term in value for term in ("各地市", "各省市", "各市县", "相关地市")):
        return False
    return not value.startswith(("指导", "面向", "覆盖", "涉及", "组织", "协调", "通知"))


def _plausible_ner_location(value: str) -> bool:
    stripped = value.strip()
    if stripped in _GENERIC_LOCATION_TERMS:
        return False
    if any(term in stripped for term in ("各地市", "各省市", "各市县", "相关地市")):
        return False
    return not stripped.startswith(("指导", "面向", "覆盖", "涉及", "组织", "协调", "通知"))


def _valid_labeled_name(match: re.Match[str]) -> bool:
    value = match.group("value")
    return value not in {
        "信息",
        "情况",
        "名单",
        "姓名",
        "签名",
        "意见",
        "部门",
        "单位",
    }


def _valid_domain(match: re.Match[str]) -> bool:
    suffix = match.group(0).rsplit(".", maxsplit=1)[-1].casefold()
    return suffix not in {
        "doc",
        "docm",
        "docx",
        "dot",
        "dotm",
        "dotx",
        "ppt",
        "pptm",
        "pptx",
        "xls",
        "xlsb",
        "xlsm",
        "xlsx",
        "xlt",
        "xltm",
        "xltx",
    }


def _luhn_valid(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 12:
        return False
    checksum = 0
    parity = len(digits) % 2
    for index, char in enumerate(digits):
        digit = int(char)
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def _account_metadata(match: re.Match[str]) -> dict[str, Any]:
    value = match.group("value")
    context = match.group(0)
    kind = "platform"
    if re.search(r"银行卡|卡号|对公|收款|开户", context):
        kind = "bank"
    return {
        "account_kind": kind,
        "luhn_valid": _luhn_valid(value),
        "label": match.group("label"),
    }


def _bank_card_metadata(match: re.Match[str]) -> dict[str, Any]:
    return {
        "account_kind": "bank",
        "luhn_valid": True,
        "label": "银行卡号",
    }


def _money_metadata(match: re.Match[str]) -> dict[str, Any]:
    raw_number = match.group("number").replace(",", "").replace("，", "")
    unit = match.group("unit") or "元"
    multiplier = {
        "元": Decimal("1"),
        "万元": Decimal("10000"),
        "万": Decimal("10000"),
        "亿元": Decimal("100000000"),
        "亿": Decimal("100000000"),
    }.get(unit, Decimal("1"))
    try:
        yuan = Decimal(raw_number) * multiplier
    except InvalidOperation:
        yuan = Decimal("0")
    return {
        "amount_yuan": str(yuan),
        "source_unit": unit,
        "currency": "CNY",
    }


def _time_metadata(match: re.Match[str]) -> dict[str, Any]:
    value = match.group(0)
    formats = (
        "%Y年%m月%d日%H:%M",
        "%Y年%m月%d日 %H:%M",
        "%Y年%m月%d日",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d",
    )
    normalized = re.sub(r"(\d{1,2})时(\d{1,2})分", r"\1:\2", value)
    parsed: datetime | None = None
    for fmt in formats:
        try:
            parsed = datetime.strptime(normalized, fmt)
            break
        except ValueError:
            continue
    result: dict[str, Any] = {"precision": "date"}
    if parsed is not None:
        result["iso"] = parsed.isoformat(timespec="minutes")
        if ":" in normalized:
            result["precision"] = "minute"
    elif re.fullmatch(r"\d{1,2}:\d{2}", value):
        result["precision"] = "minute-of-day"
    elif re.fullmatch(r"\d{1,2}月\d{1,2}日", value):
        result["precision"] = "month-day"
    return result


def _id_metadata(match: re.Match[str]) -> dict[str, Any]:
    value = match.group(0).upper()
    birth = datetime.strptime(value[6:14], "%Y%m%d")
    return {
        "birth_year": birth.year,
        "sex_code": int(value[16]) % 2,
        "checksum_valid": True,
    }


_PROVINCES = "京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼"
_NON_SENSITIVE_DOCUMENT_PROPERTIES = {
    "application",
    "appversion",
    "characters",
    "characterswithspaces",
    "docsecurity",
    "hyperlinkschanged",
    "i4",
    "lines",
    "linksuptodate",
    "lpstr",
    "pages",
    "paragraphs",
    "revision",
    "scalecrop",
    "shareddoc",
    "template",
    "totaltime",
    "words",
}
_NER_NAME_STOPWORDS = {
    "负责人",
    "联系人",
    "信息",
    "单位",
    "名字",
    "姓名",
    "手机号",
    "手机号码",
    "用户名",
    "用户账号",
    "电话",
    "联系电话",
    "签名",
    "系统名称",
    "项目名称",
    "部门",
}


class StructuredDetector:
    """Deterministic, offline rules for structured identifiers and labels."""

    name = "structured-rules"

    def __init__(self) -> None:
        flags = re.IGNORECASE
        self._rules: tuple[_Rule, ...] = (
            _Rule(
                "id-card-checksum",
                Category.ID_CARD,
                re.compile(r"(?<!\d)\d{17}[\dXx](?![\dA-Za-z])"),
                TransformMethod.SIMULATE,
                1.0,
                validator=_valid_chinese_id,
                metadata_factory=_id_metadata,
            ),
            _Rule(
                "email",
                Category.EMAIL,
                re.compile(
                    r"(?<![A-Z0-9._%+-])[A-Z0-9._%+-]+@"
                    r"(?:[A-Z0-9-]+\.)+[A-Z]{2,63}(?![A-Z0-9_.-])",
                    flags,
                ),
                TransformMethod.GENERALIZE,
                0.99,
            ),
            _Rule(
                "mobile",
                Category.PHONE,
                re.compile(r"(?<!\d)(?:\+?86[\s-]?)?1[3-9]\d{9}(?!\d)"),
                TransformMethod.SIMULATE,
                0.99,
                metadata_factory=lambda _match: {"contact_kind": "mobile"},
            ),
            _Rule(
                "landline",
                Category.PHONE,
                re.compile(r"(?<!\d)0\d{2,3}[\s-]?\d{7,8}(?!\d)"),
                TransformMethod.SIMULATE,
                0.98,
                metadata_factory=lambda _match: {"contact_kind": "landline"},
                suppress_if_overlapped=True,
            ),
            _Rule(
                "password-label",
                Category.SECRET,
                re.compile(
                    r"(?:登录密码|初始密码|访问密码|数据库密码|连接密码|密码|口令|PIN|PWD|PASSWD|PASSWORD)"
                    r"\s*[:：=]\s*(?P<value>[^\s,，;；]{4,128})",
                    flags,
                ),
                TransformMethod.REMOVE,
                1.0,
                group="value",
                metadata_factory=lambda _match: {"secret_kind": "password"},
            ),
            _Rule(
                "secret-token-label",
                Category.SECRET,
                re.compile(
                    r"(?:API[ _-]?KEY|ACCESS[ _-]?KEY|SECRET[ _-]?KEY|CLIENT[ _-]?SECRET|"
                    r"ACCESS[ _-]?TOKEN|REFRESH[ _-]?TOKEN|TOKEN|密钥|令牌)"
                    r"\s*[:：=]\s*(?P<value>[^\s,，;；]{6,256})",
                    flags,
                ),
                TransformMethod.REMOVE,
                1.0,
                group="value",
                metadata_factory=lambda _match: {"secret_kind": "key_or_token"},
            ),
            _Rule(
                "bank-card-luhn",
                Category.ACCOUNT,
                re.compile(r"(?<!\d)(?:\d[\s-]?){15,18}\d(?!\d)"),
                TransformMethod.SIMULATE,
                0.99,
                validator=lambda match: _luhn_valid(match.group(0)),
                metadata_factory=_bank_card_metadata,
                suppress_if_overlapped=True,
            ),
            _Rule(
                "vehicle-plate",
                Category.VEHICLE_PLATE,
                re.compile(
                    rf"(?<![A-Z0-9])[{_PROVINCES}][A-HJ-NP-Z]"
                    r"[\s·-]?[A-HJ-NP-Z0-9]{5,6}(?![A-Z0-9])",
                    flags,
                ),
                TransformMethod.SIMULATE,
                0.98,
                validator=_valid_vehicle_plate,
            ),
            _Rule(
                "case-label",
                Category.CASE_ID,
                re.compile(
                    r"(?:案件编号|案件号|案号)\s*[:：]?\s*"
                    r"(?P<value>[A-Z]{1,12}[-_/]?[A-Z0-9][A-Z0-9_.\-/]{3,39})",
                    flags,
                ),
                TransformMethod.SIMULATE,
                0.99,
                group="value",
            ),
            _Rule(
                "device-label",
                Category.DEVICE_ID,
                re.compile(
                    r"(?:设备编号|设备号|终端编号|序列号|SN)\s*[:：]?\s*"
                    r"(?P<value>[A-Z0-9][A-Z0-9_.\-/]{3,39})",
                    flags,
                ),
                TransformMethod.SIMULATE,
                0.98,
                group="value",
            ),
            _Rule(
                "username-label",
                Category.USERNAME,
                re.compile(
                    r"(?:用户名|登录名|用户ID|用户账号)\s*[:：]?\s*"
                    r"(?P<value>[A-Z][A-Z0-9_.-]{2,31})",
                    flags,
                ),
                TransformMethod.SIMULATE,
                0.98,
                group="value",
            ),
            _Rule(
                "account-label",
                Category.ACCOUNT,
                re.compile(
                    r"(?P<label>对公账户|平台账号|银行账号|银行卡号|收款账号|"
                    r"账户|帐号|账号|卡号)\s*[:：]?\s*"
                    r"(?P<value>[A-Z0-9][A-Z0-9_.\s-]{5,31})",
                    flags,
                ),
                TransformMethod.SIMULATE,
                0.96,
                group="value",
                metadata_factory=_account_metadata,
            ),
            _Rule(
                "money",
                Category.MONEY,
                re.compile(
                    r"(?<![\d.])(?:人民币|RMB|￥|¥)?\s*"
                    r"(?P<number>\d{1,3}(?:[,，]\d{3})+(?:\.\d{1,2})?|"
                    r"\d+(?:\.\d{1,4})?)\s*"
                    r"(?P<unit>亿元|万元|元|亿|万)(?![\u4e00-\u9fff])",
                    flags,
                ),
                TransformMethod.RANGE,
                0.96,
                metadata_factory=_money_metadata,
            ),
            _Rule(
                "datetime",
                Category.TIME,
                re.compile(
                    r"(?<!\d)(?:20\d{2}|19\d{2})年(?:0?[1-9]|1[0-2])月"
                    r"(?:0?[1-9]|[12]\d|3[01])日"
                    r"(?:\s*(?:[01]?\d|2[0-3])(?::|时)"
                    r"(?:[0-5]\d)(?:分)?)?"
                    r"|(?<!\d)(?:20\d{2}|19\d{2})[-/]"
                    r"(?:0?[1-9]|1[0-2])[-/](?:0?[1-9]|[12]\d|3[01])"
                    r"(?:[ T](?:[01]?\d|2[0-3]):[0-5]\d)?"
                    r"|(?<![\d年])(?:0?[1-9]|1[0-2])月"
                    r"(?:0?[1-9]|[12]\d|3[01])日"
                    r"|(?<!\d)(?:[01]?\d|2[0-3]):[0-5]\d(?!\d)"
                ),
                TransformMethod.SHIFT,
                0.94,
                metadata_factory=_time_metadata,
            ),
            _Rule(
                "address-label",
                Category.ADDRESS,
                re.compile(
                    r"(?:详细地址|联系地址|住址|地址)\s*[:：]\s*"
                    r"(?P<value>[\u4e00-\u9fffA-Z0-9（）()·\-]{4,60}"
                    r"(?:号|室|栋|单元))",
                    flags,
                ),
                TransformMethod.GENERALIZE,
                0.96,
                group="value",
            ),
            _Rule(
                "street-address",
                Category.ADDRESS,
                re.compile(
                    r"(?:(?:[\u4e00-\u9fff]{2,8})(?:省|自治区|特别行政区))?"
                    r"(?:(?:[\u4e00-\u9fff]{2,8})(?:市|州|盟))?"
                    r"(?:(?:[\u4e00-\u9fff]{1,8})(?:区|县|旗))?"
                    r"(?:[\u4e00-\u9fffA-Z0-9]{1,20})(?:街道|镇|乡|路|街|巷)"
                    r"\d{1,5}号(?:\d{1,4}(?:室|房))?",
                    flags,
                ),
                TransformMethod.GENERALIZE,
                0.91,
            ),
            _Rule(
                "name-label",
                Category.NAME,
                re.compile(
                    r"(?P<label>姓名|联系人|经办人|申请人|审批人|负责人)"
                    r"\s*[:：]?\s*(?P<value>[\u4e00-\u9fff·]{2,6})"
                    r"(?=\s*(?:在|于|负责|身份证|证件|电话|手机|邮箱|"
                    r"[,，。；;、]|$))"
                ),
                TransformMethod.ALIAS,
                0.95,
                group="value",
                validator=_valid_labeled_name,
                metadata_factory=lambda match: {"role": match.group("label")},
            ),
            _Rule(
                "project-name",
                Category.PROJECT,
                re.compile(
                    r"(?<![\u4e00-\u9fffA-Z0-9])"
                    r"[《“\"]?[\u4e00-\u9fffA-Z0-9·]{2,24}[》”\"]?"
                    r"(?:项目|工程|专项)(?![\u4e00-\u9fff])",
                    flags,
                ),
                TransformMethod.ALIAS,
                0.86,
            ),
            _Rule(
                "system-name",
                Category.SYSTEM,
                re.compile(
                    r"(?<![\u4e00-\u9fffA-Z0-9])"
                    r"[《“\"]?[\u4e00-\u9fffA-Z0-9·]{2,24}[》”\"]?"
                    r"(?:系统|平台)(?![\u4e00-\u9fff])",
                    flags,
                ),
                TransformMethod.ALIAS,
                0.84,
            ),
            _Rule(
                "department-label",
                Category.DEPARTMENT,
                re.compile(
                    r"(?:部门|处室|科室)\s*[:：]\s*"
                    r"(?P<value>[\u4e00-\u9fffA-Z0-9·]{2,20}"
                    r"(?:部|处|科|室|中心|办公室))",
                    flags,
                ),
                TransformMethod.ALIAS,
                0.94,
                group="value",
            ),
            _Rule(
                "organization-suffix",
                Category.ORGANIZATION,
                re.compile(
                    r"(?<![\u4e00-\u9fffA-Z0-9])"
                    r"[\u4e00-\u9fffA-Z0-9（）()·]{2,30}?"
                    r"(?:有限责任公司|股份有限公司|有限公司|集团|委员会|研究院|"
                    r"研究所|事务所|学校|医院|协会|银行|中心)"
                    r"(?![\u4e00-\u9fffA-Z0-9])",
                    flags,
                ),
                TransformMethod.ALIAS,
                0.89,
            ),
            _Rule(
                "administrative-location",
                Category.LOCATION,
                re.compile(
                    r"(?<![\u4e00-\u9fff])"
                    r"(?:(?:[\u4e00-\u9fff]{2,8})(?:省|自治区|特别行政区))?"
                    r"(?:(?:[\u4e00-\u9fff]{2,8})(?:市|州|盟))"
                    r"(?:(?:[\u4e00-\u9fff]{1,8})(?:区|县|旗))?"
                    r"(?![\u4e00-\u9fff])"
                    r"|(?<![\u4e00-\u9fff])"
                    r"(?:[\u4e00-\u9fff]{2,8})(?:省|自治区|特别行政区)"
                    r"(?![\u4e00-\u9fff])",
                ),
                TransformMethod.GENERALIZE,
                0.88,
                validator=_valid_administrative_location,
                suppress_if_overlapped=True,
            ),
            _Rule(
                "domain",
                Category.DOMAIN,
                re.compile(
                    r"(?<![@A-Z0-9_.-])"
                    r"(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+"
                    r"(?:[A-Z]{2,63}|XN--[A-Z0-9-]{2,59})(?![A-Z0-9_.-])",
                    flags,
                ),
                TransformMethod.GENERALIZE,
                0.95,
                validator=_valid_domain,
                suppress_if_overlapped=True,
            ),
        )
        self._ipv4_pattern = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
        self._ipv6_pattern = re.compile(
            r"(?<![\w:])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![\w:])"
        )

    def detect(self, document: DocumentModel) -> list[Finding]:
        findings: list[Finding] = []
        for block in document.blocks:
            if block.block_kind == "metadata":
                continue
            findings.extend(self._detect_block(block.text, block.location, block))

        for key, value in document.document_properties.items():
            if (
                not value.strip()
                or key.split("_", maxsplit=1)[0].casefold() in _NON_SENSITIVE_DOCUMENT_PROPERTIES
            ):
                continue
            findings.append(
                Finding(
                    category=Category.FILE_PROPERTY,
                    modality=Modality.METADATA,
                    original=value,
                    locations=[
                        SourceLocation(
                            part="document-properties",
                            display=f"文件属性：{key}",
                        )
                    ],
                    detector="document-property",
                    confidence=1.0,
                    suggested_method=TransformMethod.REMOVE,
                    preserved_semantics="删除作者与历史身份属性",
                    metadata={"property_name": key},
                )
            )
        return expand_duplicate_locations(document, merge_findings(findings))

    def _detect_block(
        self,
        text: str,
        location: SourceLocation,
        block: Any,
    ) -> list[Finding]:
        modality = modality_for_block(block)
        raw: list[tuple[int, int, Finding, bool]] = []
        protected_spans: list[tuple[int, int]] = []

        for rule in self._rules:
            for match in rule.pattern.finditer(text):
                try:
                    if rule.validator is not None and not rule.validator(match):
                        continue
                    start, end = match.span(rule.group)
                    if start == end:
                        continue
                    if rule.suppress_if_overlapped and any(
                        start < protected_end and end > protected_start
                        for protected_start, protected_end in protected_spans
                    ):
                        continue
                    metadata = (
                        rule.metadata_factory(match) if rule.metadata_factory is not None else {}
                    )
                except (IndexError, ValueError, InvalidOperation):
                    continue
                original = match.group(rule.group)
                raw.append(
                    (
                        start,
                        end,
                        Finding(
                            category=rule.category,
                            modality=modality,
                            original=original,
                            locations=[clone_location(location, start=start, end=end)],
                            detector=f"rule:{rule.name}",
                            confidence=rule.confidence,
                            suggested_method=rule.method,
                            preserved_semantics=_preserved_semantics(rule.category),
                            context=_context(text, start, end),
                            metadata=metadata,
                        ),
                        rule.suppress_if_overlapped,
                    )
                )
                if rule.category in {
                    Category.ID_CARD,
                    Category.EMAIL,
                    Category.PHONE,
                    Category.ADDRESS,
                }:
                    protected_spans.append((start, end))

        for pattern_name, pattern in (
            ("ipv4", self._ipv4_pattern),
            ("ipv6", self._ipv6_pattern),
        ):
            for match in pattern.finditer(text):
                value = match.group(0)
                try:
                    address = ipaddress.ip_address(value)
                except ValueError:
                    continue
                start, end = match.span()
                if any(
                    start < protected_end and end > protected_start
                    for protected_start, protected_end in protected_spans
                ):
                    continue
                private = _is_internal_ip(address)
                category = Category.PRIVATE_IP if private else Category.PUBLIC_IP
                raw.append(
                    (
                        start,
                        end,
                        Finding(
                            category=category,
                            modality=modality,
                            original=value,
                            locations=[clone_location(location, start=start, end=end)],
                            detector=f"rule:{pattern_name}",
                            confidence=0.99,
                            suggested_method=TransformMethod.SIMULATE,
                            preserved_semantics="保留内外网属性与同一地址关系",
                            context=_context(text, start, end),
                            metadata={
                                "ip_version": address.version,
                                "is_private": private,
                            },
                        ),
                        False,
                    )
                )
                protected_spans.append((start, end))

        raw.sort(key=lambda item: (item[0], -(item[1] - item[0])))
        return [finding for _, _, finding, _ in raw]


class LocalNerDetector:
    """Task dictionary plus optional local-only spaCy Chinese NER.

    `spacy.load` is only asked to open an already installed package or local
    path. This class never invokes a downloader or performs a network request.
    """

    name = "local-ner"
    _LABEL_MAP: dict[str, Category] = {
        "PERSON": Category.NAME,
        "PER": Category.NAME,
        "ORG": Category.ORGANIZATION,
        "ORGANIZATION": Category.ORGANIZATION,
        "GPE": Category.LOCATION,
        "LOC": Category.LOCATION,
        "LOCATION": Category.LOCATION,
        "FAC": Category.LOCATION,
        "DEPARTMENT": Category.DEPARTMENT,
        "PROJECT": Category.PROJECT,
        "SYSTEM": Category.SYSTEM,
    }

    def __init__(
        self,
        *,
        model_path: str | Path | None = "zh_core_web_sm",
        task_terms: Sequence[TaskTerm] = (),
        nlp: Any | None = None,
    ) -> None:
        self._model_path = None if model_path is None else str(model_path)
        self._task_terms = tuple(term for term in task_terms if term.term)
        self._nlp = nlp
        self._load_attempted = nlp is not None
        self._ruler_configured = False
        self.warnings: list[str] = []

    def detect(self, document: DocumentModel) -> list[Finding]:
        self.warnings = []
        findings = self._detect_task_terms(document)
        nlp = self._ensure_nlp()
        if nlp is None:
            self._add_warning(
                document,
                "NER_MODEL_UNAVAILABLE: 本地中文实体模型不可用，"
                "已使用规则与任务词典降级；所有结果仍需人工复核。",
            )
            return merge_findings(findings)

        self._configure_entity_ruler(nlp, document)
        try:
            for block in document.blocks:
                parsed = nlp(block.text)
                for entity in getattr(parsed, "ents", ()):
                    category = self._category_for_label(str(entity.label_))
                    if category is None:
                        continue
                    start = int(entity.start_char)
                    end = int(entity.end_char)
                    if start >= end:
                        continue
                    entity_text = block.text[start:end]
                    if (
                        category
                        in {
                            Category.NAME,
                            Category.LOCATION,
                        }
                        and re.search(r"[\u4e00-\u9fff]", entity_text) is None
                    ):
                        continue
                    if category is Category.NAME and entity_text.strip() in _NER_NAME_STOPWORDS:
                        continue
                    if category is Category.LOCATION and not _plausible_ner_location(entity_text):
                        continue
                    findings.append(
                        Finding(
                            category=category,
                            modality=modality_for_block(block),
                            original=entity_text,
                            locations=[
                                clone_location(
                                    block.location,
                                    start=start,
                                    end=end,
                                )
                            ],
                            detector=f"spacy:{entity.label_}",
                            confidence=0.88,
                            suggested_method=_default_method(category),
                            preserved_semantics=_preserved_semantics(category),
                            context=_context(block.text, start, end),
                        )
                    )
        except Exception:
            self._add_warning(
                document,
                "NER_PIPELINE_FAILED: 本地中文实体识别执行失败，"
                "已保留规则与任务词典结果；不得跳过人工复核。",
            )
        return merge_findings(findings)

    def _ensure_nlp(self) -> Any | None:
        if self._load_attempted:
            return self._nlp
        self._load_attempted = True
        if self._model_path is None:
            return None
        try:
            spacy = importlib.import_module("spacy")
            self._nlp = spacy.load(self._model_path)
        except (ImportError, ModuleNotFoundError, OSError):
            self._nlp = None
        return self._nlp

    def _configure_entity_ruler(
        self,
        nlp: Any,
        document: DocumentModel,
    ) -> None:
        if self._ruler_configured or not self._task_terms:
            return
        try:
            pipe_name = "local_redactor_entity_ruler"
            if pipe_name in getattr(nlp, "pipe_names", ()):
                ruler = nlp.get_pipe(pipe_name)
            else:
                ruler = nlp.add_pipe(
                    "entity_ruler",
                    name=pipe_name,
                    config={"overwrite_ents": True},
                    last=True,
                )
            patterns = [
                {
                    "label": f"LOCAL_REDACTOR_{term.category.value.upper()}",
                    "pattern": term.term,
                }
                for term in self._task_terms
                if term.case_sensitive
            ]
            if patterns:
                ruler.add_patterns(patterns)
            self._ruler_configured = True
        except Exception:
            self._add_warning(
                document,
                "NER_RULER_UNAVAILABLE: 本地实体规则管线不可用，任务词典仍由确定性匹配执行。",
            )

    def _detect_task_terms(self, document: DocumentModel) -> list[Finding]:
        findings: list[Finding] = []
        for block in document.blocks:
            for term in self._task_terms:
                flags = 0 if term.case_sensitive else re.IGNORECASE
                pattern = re.compile(re.escape(term.term), flags)
                for match in pattern.finditer(block.text):
                    start, end = match.span()
                    findings.append(
                        Finding(
                            category=term.category,
                            modality=modality_for_block(block),
                            original=match.group(0),
                            locations=[
                                clone_location(
                                    block.location,
                                    start=start,
                                    end=end,
                                )
                            ],
                            detector="task-term",
                            confidence=1.0,
                            suggested_method=(
                                term.suggested_method or _default_method(term.category)
                            ),
                            preserved_semantics=(
                                term.preserved_semantics or _preserved_semantics(term.category)
                            ),
                            context=_context(block.text, start, end),
                            metadata={"task_term": True},
                        )
                    )
        return findings

    def _category_for_label(self, label: str) -> Category | None:
        prefix = "LOCAL_REDACTOR_"
        if label.startswith(prefix):
            value = label[len(prefix) :].lower()
            try:
                return Category(value)
            except ValueError:
                return None
        return self._LABEL_MAP.get(label.upper())

    def _add_warning(self, document: DocumentModel, warning: str) -> None:
        if warning not in self.warnings:
            self.warnings.append(warning)
        if warning not in document.warnings:
            document.warnings.append(warning)


class CompositeFindingDetector:
    """Combine local detectors and optionally append combination-risk findings."""

    name = "composite-offline"

    def __init__(
        self,
        detectors: Sequence[Any] | None = None,
        *,
        combination_scorer: Any | None = None,
    ) -> None:
        self.detectors = tuple(detectors or (StructuredDetector(), LocalNerDetector()))
        self.combination_scorer = combination_scorer
        self.warnings: list[str] = []

    @classmethod
    def default(
        cls,
        *,
        task_terms: Sequence[TaskTerm] = (),
        spacy_model_path: str | Path | None = "zh_core_web_sm",
        combination_scorer: Any | None = None,
    ) -> CompositeFindingDetector:
        return cls(
            (
                StructuredDetector(),
                LocalNerDetector(
                    model_path=spacy_model_path,
                    task_terms=task_terms,
                ),
            ),
            combination_scorer=combination_scorer,
        )

    def detect(self, document: DocumentModel) -> list[Finding]:
        findings: list[Finding] = []
        self.warnings = []
        for detector in self.detectors:
            findings.extend(detector.detect(document))
            for warning in getattr(detector, "warnings", ()):
                if warning not in self.warnings:
                    self.warnings.append(warning)
        merged = merge_findings(findings)
        if self.combination_scorer is None:
            return merged
        risks = self.combination_scorer.assess(document, merged)
        return [*merged, *risks]


def _context(text: str, start: int, end: int, radius: int = 24) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    prefix = "…" if left else ""
    suffix = "…" if right < len(text) else ""
    return f"{prefix}{text[left:right]}{suffix}"


def _is_internal_ip(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> bool:
    """Classify topology, keeping RFC documentation ranges as public examples."""

    internal_networks = (
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("127.0.0.0/8"),
        ipaddress.ip_network("169.254.0.0/16"),
        ipaddress.ip_network("0.0.0.0/8"),
        ipaddress.ip_network("fc00::/7"),
        ipaddress.ip_network("fe80::/10"),
        ipaddress.ip_network("::1/128"),
        ipaddress.ip_network("::/128"),
    )
    return any(
        address.version == network.version and address in network for network in internal_networks
    )


def _preserved_semantics(category: Category) -> str:
    semantics = {
        Category.NAME: "保留角色与同一人员关系",
        Category.ID_CARD: "保留证件类型",
        Category.PHONE: "保留同一联系方式关系",
        Category.ADDRESS: "保留经确认的行政层级",
        Category.VEHICLE_PLATE: "保留车辆类别与同一车辆关系",
        Category.ACCOUNT: "保留账号类别与同一性",
        Category.ORGANIZATION: "保留机构类型、层级与业务关系",
        Category.DEPARTMENT: "保留通用职能",
        Category.PROJECT: "保留项目类别",
        Category.SYSTEM: "保留系统用途",
        Category.LOCATION: "保留区域层级",
        Category.TIME: "保留先后顺序与相对间隔",
        Category.MONEY: "保留数量级与大小关系",
        Category.CASE_ID: "保留案件类型、年份与同一性",
        Category.DEVICE_ID: "保留设备类型与同一性",
        Category.PUBLIC_IP: "保留公网属性与同一地址关系",
        Category.PRIVATE_IP: "保留私网属性与同网段关系",
        Category.DOMAIN: "保留服务角色与层级",
        Category.EMAIL: "保留用户与机构关系",
        Category.USERNAME: "保留同一用户关系",
        Category.SECRET: "删除密码、密钥和令牌，不保留可恢复值",
    }
    return semantics.get(category, "保留经人工确认的最低必要业务语义")


__all__ = [
    "CompositeFindingDetector",
    "LocalNerDetector",
    "StructuredDetector",
    "TaskTerm",
]
