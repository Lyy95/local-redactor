from __future__ import annotations

from pathlib import Path

from local_redactor.core import (
    CombinationRiskScorer,
    CompositeFindingDetector,
    LocalNerDetector,
    StructuredDetector,
    TaskTerm,
)
from local_redactor.models import (
    Category,
    DocumentKind,
    DocumentModel,
    Finding,
    Modality,
    SourceLocation,
    TextBlock,
    TransformMethod,
)


def _fictional_id(prefix17: str) -> str:
    weights = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
    check_codes = "10X98765432"
    total = sum(int(digit) * weight for digit, weight in zip(prefix17, weights, strict=True))
    return prefix17 + check_codes[total % 11]


def _document(text: str, *, properties: dict[str, str] | None = None) -> DocumentModel:
    return DocumentModel(
        kind=DocumentKind.DOCX,
        source_path=Path("fictional.docx"),
        source_sha256="0" * 64,
        display_name="虚构测试.docx",
        blocks=[
            TextBlock(
                text=text,
                location=SourceLocation(
                    part="word/document.xml",
                    display="正文第1段",
                    block_id="paragraph-1",
                ),
            )
        ],
        document_properties=properties or {},
    )


def test_structured_detector_covers_confirmed_fields() -> None:
    valid_id = _fictional_id("44010019900101001")
    text = (
        f"姓名：林澄，身份证号{valid_id}，手机号13812345678，"
        "邮箱lincheng@nebula.example，公网IP 203.0.113.25，"
        "内网IP 10.23.8.17，域名api.nebula.example，"
        "车牌粤B12345，平台账号：ACCT-2026-0008，"
        "案件编号：AJ-20260712-0048，设备编号：DEV-GZ-2391，"
        "预算137.6万元，时间2026年7月12日14:36，"
        "地址：广州市天河区星云路18号，"
        "机构：海川科技有限公司，部门：研发部，"
        "星河项目，案件协同系统，地点：广州市天河区。"
    )
    document = _document(text, properties={"creator": "虚构作者甲"})

    findings = StructuredDetector().detect(document)
    categories = {finding.category for finding in findings}

    assert {
        Category.NAME,
        Category.ID_CARD,
        Category.PHONE,
        Category.EMAIL,
        Category.PUBLIC_IP,
        Category.PRIVATE_IP,
        Category.DOMAIN,
        Category.VEHICLE_PLATE,
        Category.ACCOUNT,
        Category.CASE_ID,
        Category.DEVICE_ID,
        Category.MONEY,
        Category.TIME,
        Category.ADDRESS,
        Category.ORGANIZATION,
        Category.DEPARTMENT,
        Category.PROJECT,
        Category.SYSTEM,
        Category.LOCATION,
        Category.FILE_PROPERTY,
    } <= categories
    assert (
        next(finding for finding in findings if finding.category is Category.ID_CARD).confidence
        == 1.0
    )
    assert all(
        finding.locations[0].start is not None
        for finding in findings
        if finding.modality is Modality.TEXT
    )


def test_invalid_id_checksum_is_not_reported_as_id_card() -> None:
    valid_id = _fictional_id("44010019900101001")
    wrong_tail = "0" if valid_id[-1] != "0" else "1"
    document = _document(f"编号为{valid_id[:-1]}{wrong_tail}，仅用于虚构测试。")

    findings = StructuredDetector().detect(document)

    assert not any(finding.category is Category.ID_CARD for finding in findings)


def test_structured_detector_marks_landline_for_last_four_masking() -> None:
    findings = StructuredDetector().detect(_document("办公室固定电话：010-88888888。"))

    landline = next(
        finding
        for finding in findings
        if finding.category is Category.PHONE and finding.original == "010-88888888"
    )

    assert landline.metadata["contact_kind"] == "landline"


def test_standalone_bank_card_requires_luhn_validation() -> None:
    valid = "6222020000000007"
    invalid = "6222020000000008"
    findings = StructuredDetector().detect(
        _document(f"虚构有效卡号 {valid}，虚构无效数字 {invalid}。")
    )

    bank_cards = [
        finding
        for finding in findings
        if finding.category is Category.ACCOUNT and finding.metadata.get("account_kind") == "bank"
    ]

    assert [finding.original for finding in bank_cards] == [valid]


def test_passwords_keys_and_tokens_are_detected_for_removal() -> None:
    findings = StructuredDetector().detect(
        _document("登录密码：Abc#1234；API_KEY=sk-fictional-123456；token: eyJfictional")
    )

    secrets = [finding for finding in findings if finding.category is Category.SECRET]

    assert {finding.original for finding in secrets} == {
        "Abc#1234",
        "sk-fictional-123456",
        "eyJfictional",
    }
    assert all(finding.suggested_method is TransformMethod.REMOVE for finding in secrets)


def test_generic_administrative_phrases_are_not_locations() -> None:
    text = "指导各地市完善流程，并面向各地市开展培训。"
    structured = StructuredDetector().detect(_document(text))
    assert not any(finding.category is Category.LOCATION for finding in structured)

    class Entity:
        label_ = "GPE"
        start_char = 0
        end_char = 6

    class Parsed:
        ents = (Entity(),)

    class FakeNlp:
        pipe_names: tuple[str, ...] = ()

        def __call__(self, _text: str) -> Parsed:
            return Parsed()

    ner = LocalNerDetector(nlp=FakeNlp())
    assert not any(
        finding.category is Category.LOCATION
        for finding in ner.detect(_document("指导各地市完善流程。"))
    )


def test_task_terms_work_when_spacy_model_is_unavailable() -> None:
    document = _document("请在星河协同平台中核对虚构事项。")
    detector = LocalNerDetector(
        model_path=None,
        task_terms=(
            TaskTerm(
                term="星河协同平台",
                category=Category.SYSTEM,
                suggested_method=TransformMethod.ALIAS,
            ),
        ),
    )

    findings = detector.detect(document)

    assert len(findings) == 1
    assert findings[0].category is Category.SYSTEM
    assert findings[0].detector == "task-term"
    assert any("NER_MODEL_UNAVAILABLE" in warning for warning in detector.warnings)
    assert detector.warnings == document.warnings


def test_combination_risk_marks_contributors_and_minimum_generalization() -> None:
    document = _document("虚构组合风险段落")
    location = document.blocks[0].location
    findings = [
        Finding(
            category=Category.LOCATION,
            modality=Modality.TEXT,
            original="星云市云河区",
            locations=[location],
            detector="fixture",
            confidence=0.9,
            suggested_method=TransformMethod.GENERALIZE,
        ),
        Finding(
            category=Category.TIME,
            modality=Modality.TEXT,
            original="2026年7月12日",
            locations=[location],
            detector="fixture",
            confidence=0.9,
            suggested_method=TransformMethod.SHIFT,
        ),
        Finding(
            category=Category.DEPARTMENT,
            modality=Modality.TEXT,
            original="稀有业务处",
            locations=[location],
            detector="fixture",
            confidence=0.9,
            suggested_method=TransformMethod.ALIAS,
        ),
    ]

    risks = CombinationRiskScorer().assess(document, findings)

    assert len(risks) == 1
    assert risks[0].category is Category.COMBINATION_RISK
    assert risks[0].combination_score >= 52
    assert risks[0].original == ""
    assert "location" in risks[0].metadata["recommended_categories"]
    assert all(finding.combination_score == risks[0].combination_score for finding in findings)


def test_composite_detector_merges_rules_terms_and_risk() -> None:
    document = _document("2026年7月12日，星云市云河区的星河项目使用设备编号DEV-0001。")
    detector = CompositeFindingDetector.default(
        task_terms=(TaskTerm("星云市云河区", Category.LOCATION),),
        spacy_model_path=None,
        combination_scorer=CombinationRiskScorer(scope_threshold=35),
    )

    findings = detector.detect(document)

    assert any(finding.category is Category.LOCATION for finding in findings)
    assert any(finding.category is Category.TIME for finding in findings)
    assert any(finding.category is Category.COMBINATION_RISK for finding in findings)
    assert any("NER_MODEL_UNAVAILABLE" in warning for warning in detector.warnings)
