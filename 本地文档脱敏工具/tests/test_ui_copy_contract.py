from __future__ import annotations

import json
from pathlib import Path


def test_approved_copy_contract_matches_desktop_source() -> None:
    root = Path(__file__).resolve().parents[1]
    contract = json.loads((root / "src" / "ui-copy-contract.json").read_text(encoding="utf-8"))
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in (root / "src" / "local_redactor").rglob("*.py")
    )

    for phrase in contract["requiredPhrases"]:
        assert phrase in source
