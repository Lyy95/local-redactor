from __future__ import annotations

from pathlib import Path

from local_redactor.models import ProcessingMode
from local_redactor.rule_library import RuleLibrary
from local_redactor.service import LocalDesktopController


class _RuleStore:
    def load(self):
        return RuleLibrary()


class _HistoryStore:
    def load(self):
        return ()

    def append(self, _entry):
        return None


def test_xlsx_preview_exposes_sheet_grid() -> None:
    source = Path(__file__).resolve().parents[2] / "测试样本" / "青云专项人员名册-脱敏测试样本.xlsx"
    controller = LocalDesktopController(rule_store=_RuleStore(), history_store=_HistoryStore())
    bundle = controller.scan(source, ProcessingMode.BALANCED)
    preview = bundle.preview
    assert preview.kind == "xlsx"
    names = [sheet["name"] for sheet in preview.sheets]
    assert "联系人" in names
    assert "项目" in names
