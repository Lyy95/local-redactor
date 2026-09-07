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
