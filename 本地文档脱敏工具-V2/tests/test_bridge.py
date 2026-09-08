import json
from pathlib import Path

from local_redactor_v2.bridge import DesktopBridge
from local_redactor.rule_library import FernetFileProtector, RuleStore
from local_redactor.service import LocalDesktopController


def test_bridge_reports_local_runtime() -> None:
    bridge = DesktopBridge(Path.cwd())
    runtime = json.loads(bridge.get_runtime_info())
    assert runtime["runtime"] == "native-windows-desktop"
    assert runtime["offline"] is True
    assert runtime["demoMode"] is False


def test_demo_mode_requires_explicit_bridge_configuration() -> None:
    runtime = json.loads(DesktopBridge(Path.cwd(), demo_mode=True).get_runtime_info())
    assert runtime["demoMode"] is True


def test_bridge_self_test_reports_ui_presence() -> None:
    result = json.loads(DesktopBridge(Path.cwd()).self_test())
    assert result == {"ok": True, "network": "disabled"}


def test_bridge_persists_rule_library(tmp_path: Path) -> None:
    store = RuleStore(
        tmp_path / "rules.dat",
        protector=FernetFileProtector(tmp_path / "key"),
        include_presets=False,
    )

    def factory():
        return LocalDesktopController(rule_store=store)

    bridge = DesktopBridge(tmp_path, controller_factory=factory)
    listed = json.loads(bridge.list_rules())
    assert listed["ok"] is True
    assert listed["data"]["rules"] == []

    saved = json.loads(
        bridge.save_rule(
            json.dumps(
                {
                    "id": "rule-ga",
                    "type": "fixed",
                    "name": "公安简称统一代号",
                    "matchMode": "包含",
                    "pattern": "公安",
                    "action": "换成固定代号",
                    "replacement": "GA",
                    "scope": "正文、表格",
                    "mandatory": True,
                    "enabled": True,
                },
                ensure_ascii=False,
            )
        )
    )
    assert saved["ok"] is True, saved
    assert any(rule["replacement"] == "GA" for rule in saved["data"]["rules"])

    disabled = json.loads(bridge.set_rule_enabled("rule-ga", False))
    assert disabled["ok"] is True
    assert disabled["data"]["rules"][0]["enabled"] is False

    deleted = json.loads(bridge.delete_rule("rule-ga"))
    assert deleted["ok"] is True
    assert deleted["data"]["rules"] == []

def _write_rules_csv(path: Path, rows: list[dict[str, str]]) -> Path:
    headers = ["规则类型", "规则名称", "匹配方式", "关键词", "处理方式", "替换内容", "必须处理", "启用", "适用范围"]
    lines = [",".join(headers)]
    for row in rows:
        lines.append(",".join(row.get(header, "") for header in headers))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    return path


def test_bridge_preview_and_commit_rule_import(tmp_path: Path) -> None:
    store = RuleStore(
        tmp_path / "rules.dat",
        protector=FernetFileProtector(tmp_path / "key"),
        include_presets=False,
    )

    def factory():
        return LocalDesktopController(rule_store=store)

    bridge = DesktopBridge(tmp_path, controller_factory=factory)
    seeded = json.loads(
        bridge.save_rule(
            json.dumps(
                {
                    "id": "rule-org",
                    "type": "fixed",
                    "name": "合作机构统一代号",
                    "matchMode": "包含",
                    "pattern": "星河合作机构",
                    "action": "换成固定代号",
                    "replacement": "机构甲",
                    "scope": "正文、表格",
                    "mandatory": True,
                    "enabled": True,
                },
                ensure_ascii=False,
            )
        )
    )
    assert seeded["ok"] is True, seeded

    conflict_csv = _write_rules_csv(
        tmp_path / "import-conflict.csv",
        [
            {
                "规则类型": "固定替换",
                "规则名称": "合作机构统一代号",
                "匹配方式": "包含",
                "关键词": "星河合作机构",
                "处理方式": "固定代号",
                "替换内容": "机构乙",
                "必须处理": "是",
                "启用": "是",
                "适用范围": "text|cell",
            },
            {
                "规则类型": "固定替换",
                "规则名称": "项目名称统一代号",
                "匹配方式": "包含",
                "关键词": "星河协同建设项目",
                "处理方式": "固定代号",
                "替换内容": "项目 A",
                "必须处理": "否",
                "启用": "是",
                "适用范围": "text|cell",
            },
        ],
    )

    preview = json.loads(bridge.preview_rule_import(str(conflict_csv)))
    assert preview["ok"] is True, preview
    assert preview["data"]["newCount"] == 1
    assert preview["data"]["conflictCount"] == 1
    assert preview["data"]["duplicateCount"] == 0
    assert preview["data"]["newRules"][0]["replacement"] == "项目 A"
    assert preview["data"]["conflicts"][0]["existing"]["replacement"] == "机构甲"
    assert preview["data"]["conflicts"][0]["imported"]["replacement"] == "机构乙"

    blocked = json.loads(bridge.commit_rule_import(str(conflict_csv), "error"))
    assert blocked["ok"] is False
    assert blocked["error"]["code"] == "RULE_IMPORT_CONFLICT"
    assert blocked["data"]["conflictCount"] == 1

    kept = json.loads(bridge.commit_rule_import(str(conflict_csv), "keep_existing"))
    assert kept["ok"] is True, kept
    assert kept["data"]["addedCount"] == 1
    assert kept["data"]["keptExistingCount"] == 1
    assert kept["data"]["skippedDuplicateCount"] == 0
    assert any(rule["replacement"] == "机构甲" for rule in kept["data"]["rules"])
    assert any(rule["replacement"] == "项目 A" for rule in kept["data"]["rules"])
    assert not any(rule["replacement"] == "机构乙" for rule in kept["data"]["rules"])

    duplicate_csv = _write_rules_csv(
        tmp_path / "import-duplicate.csv",
        [
            {
                "规则类型": "固定替换",
                "规则名称": "合作机构统一代号",
                "匹配方式": "包含",
                "关键词": "星河合作机构",
                "处理方式": "固定代号",
                "替换内容": "机构甲",
                "必须处理": "是",
                "启用": "是",
                "适用范围": "text|cell",
            }
        ],
    )
    dup_preview = json.loads(bridge.preview_rule_import(str(duplicate_csv)))
    assert dup_preview["ok"] is True, dup_preview
    assert dup_preview["data"]["duplicateCount"] == 1
    assert dup_preview["data"]["newCount"] == 0
    assert dup_preview["data"]["conflictCount"] == 0

    dup_commit = json.loads(bridge.commit_rule_import(str(duplicate_csv), "keep_existing"))
    assert dup_commit["ok"] is True, dup_commit
    assert dup_commit["data"]["skippedDuplicateCount"] == 1
    assert dup_commit["data"]["addedCount"] == 0

    replace_csv = _write_rules_csv(
        tmp_path / "import-replace.csv",
        [
            {
                "规则类型": "固定替换",
                "规则名称": "合作机构统一代号",
                "匹配方式": "包含",
                "关键词": "星河合作机构",
                "处理方式": "固定代号",
                "替换内容": "机构乙",
                "必须处理": "是",
                "启用": "是",
                "适用范围": "text|cell",
            }
        ],
    )
    replaced = json.loads(bridge.commit_rule_import(str(replace_csv), "use_imported"))
    assert replaced["ok"] is True, replaced
    assert replaced["data"]["replacedExistingCount"] == 1
    org = next(rule for rule in replaced["data"]["rules"] if rule["pattern"] == "星河合作机构")
    assert org["replacement"] == "机构乙"
    assert org["id"] == "rule-org"


def test_bridge_restores_missing_default_presets(tmp_path: Path) -> None:
    store = RuleStore(
        tmp_path / "rules.dat",
        protector=FernetFileProtector(tmp_path / "key"),
        include_presets=False,
    )

    def factory():
        return LocalDesktopController(rule_store=store)

    bridge = DesktopBridge(tmp_path, controller_factory=factory)

    custom = json.loads(
        bridge.save_rule(
            json.dumps(
                {
                    "id": "rule-custom-org",
                    "type": "fixed",
                    "name": "我的机构代号",
                    "matchMode": "包含",
                    "pattern": "星河自定义机构",
                    "action": "换成固定代号",
                    "replacement": "机构自定",
                    "scope": "正文、表格",
                    "mandatory": False,
                    "enabled": True,
                },
                ensure_ascii=False,
            )
        )
    )
    assert custom["ok"] is True, custom
    assert len(custom["data"]["rules"]) == 1

    first = json.loads(bridge.restore_default_rules())
    assert first["ok"] is True, first
    assert first["data"]["restoredCount"] > 0
    rules = first["data"]["rules"]
    assert any(rule["id"] == "rule-custom-org" for rule in rules)
    presets = [rule for rule in rules if rule.get("preset")]
    assert len(presets) == first["data"]["restoredCount"]
    assert all(rule["id"].startswith("preset-") for rule in presets)

    noop = json.loads(bridge.restore_default_rules())
    assert noop["ok"] is True, noop
    assert noop["data"]["restoredCount"] == 0
    assert len(noop["data"]["rules"]) == len(rules)

    target = next(rule for rule in presets if rule["id"].startswith("preset-v1-police-"))
    deleted = json.loads(bridge.delete_rule(target["id"]))
    assert deleted["ok"] is True, deleted
    assert not any(rule["id"] == target["id"] for rule in deleted["data"]["rules"])

    edited = json.loads(
        bridge.save_rule(
            json.dumps(
                {
                    **target,
                    "id": next(
                        rule["id"]
                        for rule in deleted["data"]["rules"]
                        if rule.get("preset") and rule["id"] != target["id"]
                    ),
                    "replacement": "USER_EDITED_PRESET",
                    "name": "用户改过的预置",
                },
                ensure_ascii=False,
            )
        )
    )
    assert edited["ok"] is True, edited
    edited_rule = next(rule for rule in edited["data"]["rules"] if rule["replacement"] == "USER_EDITED_PRESET")

    second = json.loads(bridge.restore_default_rules())
    assert second["ok"] is True, second
    assert second["data"]["restoredCount"] == 1
    assert any(rule["id"] == target["id"] for rule in second["data"]["rules"])
    untouched = next(rule for rule in second["data"]["rules"] if rule["id"] == edited_rule["id"])
    assert untouched["replacement"] == "USER_EDITED_PRESET"
    assert any(rule["id"] == "rule-custom-org" and rule["replacement"] == "机构自定" for rule in second["data"]["rules"])

def test_bridge_dry_runs_rule_against_sample_text(tmp_path: Path) -> None:
    store = RuleStore(
        tmp_path / "rules.dat",
        protector=FernetFileProtector(tmp_path / "key"),
        include_presets=False,
    )

    def factory():
        return LocalDesktopController(rule_store=store)

    bridge = DesktopBridge(tmp_path, controller_factory=factory)
    payload = {
        "sample": "联系人来自公安厅，电话 13812345678。",
        "rule": {
            "id": "rule-ga-dry",
            "type": "fixed",
            "name": "公安简称统一代号",
            "matchMode": "包含",
            "pattern": "公安",
            "action": "换成固定代号",
            "replacement": "GA",
            "scope": "正文、表格",
            "mandatory": True,
            "enabled": True,
        },
    }
    hit = json.loads(bridge.test_rule(json.dumps(payload, ensure_ascii=False)))
    assert hit["ok"] is True, hit
    assert hit["data"]["hit"] is True
    assert hit["data"]["matchCount"] == 1
    assert hit["data"]["matches"][0]["original"] == "公安"
    assert hit["data"]["matches"][0]["replacement"] == "GA"
    assert "GA" in hit["data"]["replacement"]
    assert "公安" not in hit["data"]["replacement"]

    miss = json.loads(
        bridge.test_rule(
            json.dumps(
                {
                    **payload,
                    "sample": "本文仅讨论普通业务协作。",
                },
                ensure_ascii=False,
            )
        )
    )
    assert miss["ok"] is True, miss
    assert miss["data"]["hit"] is False
    assert miss["data"]["matchCount"] == 0
    assert miss["data"]["replacement"] == "本文仅讨论普通业务协作。"

    empty = json.loads(bridge.test_rule(json.dumps({"sample": "   ", "rule": payload["rule"]})))
    assert empty["ok"] is False
    assert empty["error"]["code"] == "RULE_TEST_EMPTY"

    mask = json.loads(
        bridge.test_rule(
            json.dumps(
                {
                    "sample": "手机号 13812345678 已登记",
                    "rule": {
                        "id": "rule-phone-dry",
                        "type": "standard",
                        "name": "手机号掩码试跑",
                        "matchMode": "符合格式",
                        "pattern": r"1[3-9]\d{9}",
                        "action": "保留首尾并加星号",
                        "replacement": "",
                        "scope": "正文",
                        "mandatory": False,
                        "enabled": True,
                        "positiveExample": "",
                    },
                },
                ensure_ascii=False,
            )
        )
    )
    assert mask["ok"] is True, mask
    assert mask["data"]["hit"] is True
    assert mask["data"]["matches"][0]["original"] == "13812345678"
    assert mask["data"]["matches"][0]["replacement"].startswith("1")
    assert "*" in mask["data"]["matches"][0]["replacement"]
    assert mask["data"]["matches"][0]["replacement"].endswith("8")

