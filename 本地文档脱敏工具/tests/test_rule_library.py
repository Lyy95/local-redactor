from __future__ import annotations

import csv
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from openpyxl import Workbook

from local_redactor.rule_library import (
    ActionKind,
    MatchMode,
    RuleConflictError,
    RuleDefinition,
    RuleImportConflictError,
    RuleImportError,
    RuleKind,
    RuleLibrary,
    RuleLibraryError,
    RuleSession,
    RuleStore,
    RuleValidationError,
    WindowsDpapiProtector,
    default_industry_rules,
    default_rule_store_path,
    default_standard_rules,
    import_rules,
    is_preset_rule,
    restore_default_rules,
)


class _TestProtector:
    def protect(self, plaintext: bytes) -> bytes:
        return b"test-v1:" + bytes(value ^ 0xA5 for value in plaintext)

    def unprotect(self, ciphertext: bytes) -> bytes:
        if not ciphertext.startswith(b"test-v1:"):
            raise ValueError("damaged")
        return bytes(value ^ 0xA5 for value in ciphertext.removeprefix(b"test-v1:"))


def test_fixed_mask_sequence_and_no_second_pass() -> None:
    library = RuleLibrary(
        (
            RuleDefinition.fixed("公安", "GA"),
            RuleDefinition.fixed("GA", "SECOND"),
            RuleDefinition.standard(
                "网络名称",
                match_mode=MatchMode.CONTAINS,
                patterns=("530网",),
                action=ActionKind.MASK_MIDDLE,
                keep_prefix=1,
                keep_suffix=1,
                positive_examples=("530网",),
            ),
            RuleDefinition.standard(
                "案件代号",
                match_mode=MatchMode.ANY_KEYWORD,
                patterns=("案件甲", "案件乙"),
                action=ActionKind.SEQUENCE_CODE,
                replacement="jz",
                code_width=2,
                positive_examples=("案件甲",),
            ),
        )
    )
    session = RuleSession(library)

    first = session.apply("公安使用530网处理案件甲，公安复核案件甲和案件乙。")

    assert first.replacement == "GA使用5**网处理jz01，GA复核jz01和jz02。"
    assert "SECOND" not in first.replacement
    assert [match.original for match in first.matches].count("公安") == 2
    assert all(match.mandatory for match in first.matches)


def test_match_modes_examples_scope_enabled_and_manual() -> None:
    exact = RuleDefinition.standard(
        "整字段规则",
        match_mode=MatchMode.EXACT,
        patterns=("机密字段",),
        action=ActionKind.DELETE,
        positive_examples=("机密字段",),
        negative_examples=("前缀机密字段",),
        applies_to=("cell",),
    )
    all_keywords = RuleDefinition.standard(
        "共同出现",
        match_mode=MatchMode.ALL_KEYWORDS,
        patterns=("项目甲", "专网"),
        action=ActionKind.FIXED_REPLACEMENT,
        replacement="项目代号",
        positive_examples=("项目甲使用专网",),
    )
    manual = RuleDefinition.standard(
        "人工判断标准",
        match_mode=MatchMode.MANUAL,
        action=ActionKind.SEQUENCE_CODE,
        replacement="qb",
        positive_examples=("人工选中的内容",),
    )
    disabled = RuleDefinition.fixed("不应命中", "X", enabled=False)
    ocr_only = RuleDefinition.fixed(
        "图片敏感词",
        "IMG",
        applies_to=("ocr",),
    )
    session = RuleSession(
        RuleLibrary((exact, all_keywords, manual, disabled, ocr_only))
    )

    assert not session.find("机密字段", applies_to="text")
    assert session.apply("机密字段", applies_to="cell").replacement == ""
    assert not session.find("只出现项目甲")
    all_result = session.apply("项目甲使用专网")
    assert all_result.replacement == "项目代号使用项目代号"
    assert not session.find("人工选中的内容")
    manual_result = session.apply(
        "人工选中的内容",
        manual_rule_ids=(manual.id,),
    )
    assert manual_result.replacement == "qb01"
    assert manual_result.matches[0].kind is RuleKind.STANDARD
    with pytest.raises(RuleValidationError):
        session.find("人工选中的内容", manual_rule_ids=("missing",))
    assert session.apply("不应命中").replacement == "不应命中"
    assert session.apply("图片敏感词").replacement == "图片敏感词"
    assert session.apply("图片敏感词", applies_to="ocr").replacement == "IMG"


def test_controlled_regex_accepts_bounded_patterns_and_rejects_risky_ones() -> None:
    rule = RuleDefinition.standard(
        "网络编号",
        match_mode=MatchMode.REGEX,
        patterns=(r"\d{3}网",),
        action=ActionKind.MASK_MIDDLE,
        positive_examples=("530网",),
    )

    assert RuleSession(RuleLibrary((rule,))).apply("使用530网").replacement == "使用5**网"

    for pattern in (
        r"(a+)+",
        r".*",
        r"(abc|def)",
        r"([A-Z])\1",
        r"\d{1,99}",
        r"a?",
        r"a{0}",
        r"a{0,10}",
        r"a{1,10}b{1,10}",
        r"\b公安",
    ):
        with pytest.raises(RuleValidationError):
            RuleDefinition.standard(
                "危险表达式",
                match_mode=MatchMode.REGEX,
                patterns=(pattern,),
                action=ActionKind.DELETE,
            )


def test_longest_match_priority_and_equal_rank_conflict() -> None:
    short = RuleDefinition.fixed("公安", "GA", priority=100)
    longest = RuleDefinition.fixed("公安网", "专网", priority=0)
    result = RuleSession(RuleLibrary((short, longest))).apply("公安网")
    assert result.replacement == "专网"
    assert [match.rule_id for match in result.matches] == [longest.id]

    exact = RuleDefinition.fixed(
        "网警",
        "WJ",
        match_mode=MatchMode.EXACT,
        priority=10,
    )
    contains = RuleDefinition.fixed(
        "网警",
        "OTHER",
        match_mode=MatchMode.CONTAINS,
        priority=1,
    )
    assert RuleSession(RuleLibrary((exact, contains))).apply("网警").replacement == "WJ"

    conflicting = RuleDefinition.fixed(
        "网警",
        "CONFLICT",
        match_mode=MatchMode.CONTAINS,
        priority=10,
    )
    with pytest.raises(RuleConflictError):
        RuleSession(RuleLibrary((exact, conflicting))).apply("网警")


def test_library_crud_and_same_source_conflict() -> None:
    rule = RuleDefinition.fixed("公安", "GA")
    library = RuleLibrary().add(rule)
    assert library.revision == 1
    assert library.enabled_rules == (rule,)

    disabled = library.set_enabled(rule.id, False)
    assert disabled.revision == 2
    assert not disabled.enabled_rules
    assert disabled.delete(rule.id).rules == ()

    with pytest.raises(RuleConflictError):
        RuleLibrary((rule, RuleDefinition.fixed("公安", "OTHER")))


def test_rule_kinds_enforce_fixed_mapping_and_standard_example() -> None:
    with pytest.raises(RuleValidationError, match="固定替换只允许"):
        RuleDefinition(
            name="错误固定规则",
            kind=RuleKind.FIXED,
            match_mode=MatchMode.REGEX,
            patterns=(r"\d{3}网",),
            action=ActionKind.FIXED_REPLACEMENT,
            replacement="GA",
        )
    with pytest.raises(RuleValidationError, match="固定替换只能"):
        RuleDefinition(
            name="错误固定动作",
            kind=RuleKind.FIXED,
            match_mode=MatchMode.CONTAINS,
            patterns=("公安",),
            action=ActionKind.DELETE,
        )
    with pytest.raises(RuleValidationError, match="正确示例"):
        RuleDefinition.standard(
            "缺少示例",
            match_mode=MatchMode.CONTAINS,
            patterns=("530网",),
            action=ActionKind.MASK_MIDDLE,
        )
    for source, replacement in (
        ("SecretProject", "secretproject"),
        ("AB", "ABX"),
    ):
        with pytest.raises(RuleValidationError, match="完整原词"):
            RuleDefinition.fixed(source, replacement)


def test_encrypted_store_round_trip_and_corruption_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "rules.dat"
    store = RuleStore(path, _TestProtector())
    library = RuleLibrary((RuleDefinition.fixed("虚构敏感词", "CODE"),), revision=7)

    store.save(library)

    stored = path.read_bytes()
    assert "虚构敏感词".encode() not in stored
    assert store.load() == library
    assert not list(tmp_path.glob("*.tmp"))

    path.write_bytes(b"damaged")
    with pytest.raises(RuleLibraryError):
        store.load()


def test_revision_checked_save_and_locked_updates_prevent_lost_rules(
    tmp_path: Path,
) -> None:
    store = RuleStore(tmp_path / "rules.dat", _TestProtector())
    empty = store.load()
    first = empty.add(RuleDefinition.fixed("公安", "GA"))
    stale = empty.add(RuleDefinition.fixed("网警", "WJ"))

    store.save_if_revision(first, expected_revision=empty.revision)
    with pytest.raises(RuleConflictError, match="其他窗口更新"):
        store.save_if_revision(stale, expected_revision=empty.revision)
    assert store.load() == first

    barrier = threading.Barrier(2)

    def add_rule(rule: RuleDefinition) -> None:
        barrier.wait(timeout=3)
        store.update(lambda current: current.add(rule))

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(add_rule, RuleDefinition.fixed("项目甲", "XM-A")),
            pool.submit(add_rule, RuleDefinition.fixed("系统乙", "XT-B")),
        ]
        for future in futures:
            future.result(timeout=5)

    current = store.load()
    assert {rule.patterns[0] for rule in current.rules} == {
        "公安",
        "项目甲",
        "系统乙",
    }
    assert current.revision == 3


def test_default_store_path_is_under_current_user_local_app_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert default_rule_store_path() == (
        tmp_path / "LocalRedactor" / "本地文档脱敏工具" / "rules.dat"
    )
    assert RuleStore(protector=_TestProtector()).path == default_rule_store_path()


def test_industry_and_place_presets_are_deterministic_and_use_longest_match(
    tmp_path: Path,
) -> None:
    store = RuleStore(
        tmp_path / "rules.dat",
        _TestProtector(),
        include_presets=True,
    )

    library = store.load()
    assert library.rules
    assert all(is_preset_rule(rule) for rule in library.rules)
    assert default_industry_rules() == default_industry_rules()

    result = RuleSession(library).apply(
        "海南省公安网警会同福建和广东省技侦开展虚构检查。"
    )
    assert result.replacement == "HNGAWJ会同FJ和GDJZ开展虚构检查。"
    assert "海南省" in [match.original for match in result.matches]
    assert "海南" not in [match.original for match in result.matches]


def test_existing_user_rule_wins_over_same_source_preset(tmp_path: Path) -> None:
    path = tmp_path / "rules.dat"
    plain_store = RuleStore(path, _TestProtector())
    custom = RuleDefinition.fixed("海南", "HNA", name="我的海南规则")
    plain_store.save(RuleLibrary((custom,), revision=3))

    merged = RuleStore(path, _TestProtector(), include_presets=True).load()

    hainan = [rule for rule in merged.rules if rule.patterns == ("海南",)]
    assert hainan == [custom]
    assert RuleSession(merged).apply("海南").replacement == "HNA"


def test_deleted_preset_stays_deleted_until_explicit_restore(tmp_path: Path) -> None:
    path = tmp_path / "rules.dat"
    store = RuleStore(path, _TestProtector(), include_presets=True)
    library = store.load()
    preset = next(rule for rule in library.rules if is_preset_rule(rule))
    assert any(rule.kind is RuleKind.STANDARD for rule in default_standard_rules())

    deleted = library.delete(preset.id)
    store.save_if_revision(deleted, expected_revision=library.revision)
    reloaded = store.load()
    assert all(rule.id != preset.id for rule in reloaded.rules)

    restored = restore_default_rules(reloaded)
    store.save_if_revision(restored, expected_revision=reloaded.revision)
    assert any(rule.id == preset.id for rule in store.load().rules)


@pytest.mark.skipif(os.name != "nt", reason="Windows DPAPI only")
def test_windows_dpapi_current_user_round_trip() -> None:
    protector = WindowsDpapiProtector()
    plaintext = "仅用于虚构测试".encode()

    encrypted = protector.protect(plaintext)

    assert encrypted != plaintext
    assert protector.unprotect(encrypted) == plaintext


def test_csv_import_adds_skips_duplicate_and_rejects_conflict(tmp_path: Path) -> None:
    headers = (
        "规则类型",
        "规则名称",
        "匹配方式",
        "关键词",
        "处理方式",
        "替换内容",
        "必须处理",
        "启用",
        "适用范围",
        "正例",
    )
    csv_path = tmp_path / "rules.csv"
    _write_csv(
        csv_path,
        headers,
        [
            (
                "固定替换",
                "公安代号",
                "包含",
                "公安",
                "固定代号",
                "GA",
                "是",
                "是",
                "all",
                "",
            ),
            (
                "判断标准",
                "网名遮盖",
                "受控正则",
                r"\d{3}网",
                "中间星号",
                "",
                "是",
                "是",
                "text|ocr",
                "530网",
            ),
        ],
    )

    first = import_rules(csv_path, RuleLibrary())
    assert first.added_count == 2
    assert first.skipped_duplicate_count == 0
    second = import_rules(csv_path, first.library)
    assert second.added_count == 0
    assert second.skipped_duplicate_count == 2

    conflict_path = tmp_path / "conflict.csv"
    _write_csv(
        conflict_path,
        headers,
        [
            (
                "固定替换",
                "冲突规则",
                "包含",
                "公安",
                "固定代号",
                "OTHER",
                "是",
                "是",
                "all",
            )
        ],
    )
    with pytest.raises(RuleImportConflictError):
        import_rules(conflict_path, first.library)

    kept = import_rules(
        conflict_path,
        first.library,
        conflict_policy="keep_existing",
    )
    assert kept.library == first.library
    assert kept.kept_existing_count == 1
    assert kept.replaced_existing_count == 0

    replaced = import_rules(
        conflict_path,
        first.library,
        conflict_policy="use_imported",
    )
    replaced_rule = next(
        rule for rule in replaced.library.rules if rule.patterns == ("公安",)
    )
    original_rule = next(
        rule for rule in first.library.rules if rule.patterns == ("公安",)
    )
    assert replaced_rule.id == original_rule.id
    assert replaced_rule.replacement == "OTHER"
    assert replaced.replaced_existing_count == 1
    assert replaced.library.revision == first.library.revision + 1


def test_csv_import_rejects_empty_formula_and_unknown_headers(tmp_path: Path) -> None:
    headers = (
        "规则类型",
        "规则名称",
        "匹配方式",
        "关键词",
        "处理方式",
        "替换内容",
    )
    empty_path = tmp_path / "empty.csv"
    _write_csv(empty_path, headers, [("固定替换", "", "包含", "词", "固定代号", "A")])
    with pytest.raises(RuleImportError, match="缺少必填值"):
        import_rules(empty_path, RuleLibrary())

    formula_path = tmp_path / "formula.csv"
    _write_csv(
        formula_path,
        headers,
        [("固定替换", "公式", "包含", "=A1", "固定代号", "A")],
    )
    with pytest.raises(RuleImportError, match="公式"):
        import_rules(formula_path, RuleLibrary())

    unknown_path = tmp_path / "unknown.csv"
    _write_csv(
        unknown_path,
        (*headers, "未知列"),
        [("固定替换", "规则", "包含", "词", "固定代号", "A", "x")],
    )
    with pytest.raises(RuleImportError, match="未知表头"):
        import_rules(unknown_path, RuleLibrary())


def test_xlsx_import_is_read_only_and_rejects_formulas(tmp_path: Path) -> None:
    path = tmp_path / "rules.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(
        [
            "规则类型",
            "规则名称",
            "匹配方式",
            "关键词",
            "处理方式",
            "替换内容",
            "代号位数",
            "正例",
        ]
    )
    worksheet.append(
        [
            "判断标准",
            "案件代号",
            "任一关键词",
            "案件甲|案件乙",
            "任务内顺序代号",
            "jz",
            2,
            "案件甲",
        ]
    )
    workbook.save(path)
    workbook.close()

    result = import_rules(path, RuleLibrary())

    assert result.added_count == 1
    assert result.library.rules[0].action is ActionKind.SEQUENCE_CODE

    formula_path = tmp_path / "formula.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(
        [
            "规则类型",
            "规则名称",
            "匹配方式",
            "关键词",
            "处理方式",
            "替换内容",
        ]
    )
    worksheet.append(["固定替换", "公式规则", "包含", "=A1", "固定代号", "GA"])
    workbook.save(formula_path)
    workbook.close()
    with pytest.raises(RuleImportError, match="公式"):
        import_rules(formula_path, RuleLibrary())


def _write_csv(
    path: Path,
    headers: tuple[str, ...],
    rows: list[tuple[object, ...]],
) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows(rows)
