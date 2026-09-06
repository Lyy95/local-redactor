import json
from pathlib import Path

from local_redactor_v2.bridge import DesktopBridge


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
