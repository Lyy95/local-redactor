from __future__ import annotations

from datetime import datetime
from pathlib import Path

from local_redactor.core import SemanticTransformationEngine
from local_redactor.models import (
    Category,
    DocumentKind,
    DocumentModel,
    Finding,
    FindingStatus,
    Modality,
    ProcessingMode,
    SourceLocation,
    TransformMethod,
)


def _document() -> DocumentModel:
    return DocumentModel(
        kind=DocumentKind.XLSX,
        source_path=Path("fictional.xlsx"),
        source_sha256="1" * 64,
        display_name="虚构数据.xlsx",
    )


def _finding(
    category: Category,
    original: str,
    method: TransformMethod,
    *,
    cell: str,
    metadata: dict[str, object] | None = None,
    status: FindingStatus = FindingStatus.PENDING,
) -> Finding:
    return Finding(
        category=category,
        modality=Modality.CELL,
        original=original,
        locations=[
            SourceLocation(
                part="xl/worksheets/sheet1.xml",
                display=f"工作表 数据 / {cell}",
                sheet="数据",
                cell=cell,
            )
        ],
        detector="fictional-fixture",
        confidence=1.0,
        suggested_method=method,
        metadata=metadata or {},
        status=status,
    )


def test_balanced_transform_preserves_semantics_and_consistency() -> None:
    findings = [
        _finding(
            Category.NAME,
            "林澄",
            TransformMethod.ALIAS,
            cell="A2",
            metadata={"role": "项目负责人", "rule_name": "虚构人员固定规则"},
        ),
        _finding(
            Category.NAME,
            "林澄",
            TransformMethod.ALIAS,
            cell="A8",
            metadata={"role": "项目负责人"},
        ),
        _finding(
            Category.TIME,
            "2026年7月12日14:36",
            TransformMethod.SHIFT,
            cell="B2",
            metadata={
                "iso": datetime(2026, 7, 12, 14, 36).isoformat(timespec="minutes"),
                "precision": "minute",
            },
        ),
        _finding(
            Category.MONEY,
            "137.6万元",
            TransformMethod.RANGE,
            cell="C2",
            metadata={"amount_yuan": "1376000", "source_unit": "万元"},
        ),
        _finding(
            Category.PRIVATE_IP,
            "10.23.8.17",
            TransformMethod.SIMULATE,
            cell="D2",
        ),
        _finding(
            Category.PRIVATE_IP,
            "10.23.8.99",
            TransformMethod.SIMULATE,
            cell="D3",
        ),
        _finding(
            Category.EMAIL,
            "lincheng@nebula.example",
            TransformMethod.GENERALIZE,
            cell="E2",
        ),
        _finding(
            Category.DOMAIN,
            "nebula.example",
            TransformMethod.GENERALIZE,
            cell="E3",
        ),
        _finding(
            Category.USERNAME,
            "lincheng",
            TransformMethod.SIMULATE,
            cell="E4",
        ),
    ]

    prepared, mappings = SemanticTransformationEngine().prepare(
        _document(),
        findings,
        ProcessingMode.BALANCED,
    )

    assert prepared[0].replacement == "林*"
    assert prepared[1].replacement == prepared[0].replacement
    assert prepared[2].replacement == "2026年9月3日14时左右"
    assert prepared[3].replacement == "100万元—150万元"
    assert prepared[4].replacement.startswith("10.254.1.")
    assert prepared[5].replacement.startswith("10.254.1.")
    assert prepared[6].replacement == "li******@nebula.example"
    assert prepared[7].replacement == "org01.example.invalid"
    assert prepared[8].replacement == "user01"

    person_mapping = next(mapping for mapping in mappings if mapping.category is Category.NAME)
    assert person_mapping.mapping_id == "PERSON-001"
    assert person_mapping.occurrence_count == 2
    assert len(person_mapping.locations) == 2
    assert person_mapping.rule_source == "虚构人员固定规则"
    assert len([mapping for mapping in mappings if mapping.category is Category.NAME]) == 1
    assert next(
        mapping for mapping in mappings if mapping.category is Category.TIME
    ).restore_note.startswith("所有日期按同样天数调整+53天")


def test_strict_mode_uses_numbered_or_broader_replacements() -> None:
    findings = [
        _finding(Category.NAME, "林澄", TransformMethod.ALIAS, cell="A2"),
        _finding(
            Category.ADDRESS,
            "星云市云河区星光路18号",
            TransformMethod.GENERALIZE,
            cell="B2",
        ),
        _finding(
            Category.MONEY,
            "137.6万元",
            TransformMethod.RANGE,
            cell="C2",
            metadata={"amount_yuan": "1376000"},
        ),
        _finding(
            Category.CASE_ID,
            "AJ-20260712-0048",
            TransformMethod.SIMULATE,
            cell="D2",
        ),
    ]

    prepared, mappings = SemanticTransformationEngine().prepare(
        _document(),
        findings,
        ProcessingMode.STRICT,
    )

    assert [finding.replacement for finding in prepared] == [
        "林*",
        "某地区",
        "100万元—200万元",
        "案件01",
    ]
    assert len(mappings) == 4


def test_false_positive_is_kept_and_excluded_from_mapping() -> None:
    finding = _finding(
        Category.SYSTEM,
        "公开演示系统",
        TransformMethod.ALIAS,
        cell="A1",
        status=FindingStatus.KEEP_FALSE_POSITIVE,
    )

    prepared, mappings = SemanticTransformationEngine().prepare(
        _document(),
        [finding],
        ProcessingMode.BALANCED,
    )

    assert prepared[0].replacement == "公开演示系统"
    assert prepared[0].suggested_method is TransformMethod.KEEP
    assert mappings == []


def test_remove_decision_has_mapping_but_no_output_value() -> None:
    finding = _finding(
        Category.FILE_PROPERTY,
        "虚构作者甲",
        TransformMethod.REMOVE,
        cell="A1",
        status=FindingStatus.REMOVE,
    )

    prepared, mappings = SemanticTransformationEngine().prepare(
        _document(),
        [finding],
        ProcessingMode.BALANCED,
    )

    assert prepared[0].replacement == ""
    assert mappings[0].method is TransformMethod.REMOVE
    assert "已移除" in mappings[0].restore_note


def test_common_personal_fields_use_the_confirmed_star_masks() -> None:
    findings = [
        _finding(Category.NAME, "张三", TransformMethod.ALIAS, cell="A2"),
        _finding(Category.NAME, "欧阳菲菲", TransformMethod.ALIAS, cell="A3"),
        _finding(Category.PHONE, "13812345678", TransformMethod.SIMULATE, cell="B2"),
        _finding(
            Category.PHONE,
            "010-88888888",
            TransformMethod.SIMULATE,
            cell="B3",
            metadata={"contact_kind": "landline"},
        ),
        _finding(
            Category.ID_CARD,
            "420101199003051234",
            TransformMethod.SIMULATE,
            cell="C2",
        ),
        _finding(
            Category.ACCOUNT,
            "6222021234567890",
            TransformMethod.SIMULATE,
            cell="D2",
            metadata={"account_kind": "bank"},
        ),
        _finding(
            Category.EMAIL,
            "abcde@163.com",
            TransformMethod.GENERALIZE,
            cell="E2",
        ),
    ]

    prepared, _ = SemanticTransformationEngine().prepare(
        _document(),
        findings,
        ProcessingMode.BALANCED,
    )

    assert [finding.replacement for finding in prepared] == [
        "张*",
        "欧阳**",
        "138****5678",
        "****8888",
        "420101********1234",
        "622202******7890",
        "ab***@163.com",
    ]
