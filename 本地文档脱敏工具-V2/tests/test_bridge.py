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
