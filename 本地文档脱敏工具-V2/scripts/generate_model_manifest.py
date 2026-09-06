from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
from pathlib import Path
from typing import Any


def _package_root(package: str) -> Path:
    module = importlib.import_module(package)
    return Path(module.__file__ or "").resolve(strict=True).parent


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _asset(package: str, root: Path, path: Path) -> dict[str, str | int]:
    return {
        "package": package,
        "relative": path.relative_to(root).as_posix(),
        "sha256": _sha256(path),
        "bytes": path.stat().st_size,
    }


def build_manifest(output_path: Path) -> Path:
    """Build an integrity manifest from components already installed on this machine."""

    rapid_root = _package_root("rapidocr")
    zh_root = _package_root("zh_core_web_sm")
    cv2_root = _package_root("cv2")

    selected: list[tuple[str, Path, Path]] = []
    for name in ("config.yaml", "default_models.yaml"):
        selected.append(("rapidocr", rapid_root, rapid_root / name))
    selected.extend(
        ("rapidocr", rapid_root, path) for path in sorted((rapid_root / "models").glob("*.onnx"))
    )

    model_roots = sorted(zh_root.glob("zh_core_web_sm-*"))
    if len(model_roots) != 1:
        raise RuntimeError("无法唯一定位本地中文实体模型目录")
    selected.extend(
        ("zh_core_web_sm", zh_root, path)
        for path in sorted(model_roots[0].rglob("*"))
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix.casefold() not in {".py", ".pyc"}
    )

    selected.append(
        (
            "cv2",
            cv2_root,
            cv2_root / "data" / "haarcascade_frontalface_default.xml",
        )
    )
    missing = [path for _package, _root, path in selected if not path.is_file()]
    if missing:
        names = "、".join(path.name for path in missing)
        raise RuntimeError(f"离线识别组件不完整，不能生成发布清单：{names}")

    assets = [
        _asset(package, root, path)
        for package, root, path in sorted(
            selected,
            key=lambda item: (item[0], item[2].as_posix()),
        )
    ]
    manifest: dict[str, Any] = {
        "schema": 1,
        "runtime_policy": "offline-only; no runtime model download",
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("rapidocr", "onnxruntime", "spacy", "zh-core-web-sm")
        },
        "assets": assets,
    }
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return destination


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    generated = build_manifest(project_root / "build" / "generated" / "model-manifest.json")
    print(generated)
