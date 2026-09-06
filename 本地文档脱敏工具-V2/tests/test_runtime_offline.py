from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from local_redactor.runtime import ModelIntegrityError, verify_bundled_models


def _manifest(root: Path, content: bytes) -> None:
    asset = root / "fake_model" / "models" / "model.onnx"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(content)
    (root / "model-manifest.json").write_text(
        json.dumps(
            {
                "assets": [
                    {
                        "package": "fake_model",
                        "relative": "models/model.onnx",
                        "sha256": hashlib.sha256(content).hexdigest(),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def test_frozen_model_verification_uses_bundled_paths_without_import(
    tmp_path: Path, monkeypatch
) -> None:
    _manifest(tmp_path, b"offline-model")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    verify_bundled_models()


def test_frozen_model_verification_fails_closed_on_hash_change(
    tmp_path: Path, monkeypatch
) -> None:
    _manifest(tmp_path, b"offline-model")
    (tmp_path / "fake_model" / "models" / "model.onnx").write_bytes(b"changed")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    try:
        verify_bundled_models()
    except ModelIntegrityError:
        pass
    else:
        raise AssertionError("tampered bundled model must be rejected")
