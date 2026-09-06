from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

APP_NAME = "本地文档脱敏工具-V2"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(root: Path) -> dict[str, object]:
    dist = root / "dist"
    app_dir = dist / APP_NAME
    executable = app_dir / f"{APP_NAME}.exe"
    archive = dist / f"{APP_NAME}-Windows-x64.zip"
    manifest = app_dir / "版本与校验.json"
    model_manifests = list(app_dir.rglob("model-manifest.json"))
    required = [executable, archive, manifest]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("发布物不完整：" + "、".join(missing))

    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    executable_hash = _sha256(executable)
    if metadata.get("executable_sha256") != executable_hash:
        raise RuntimeError("EXE SHA-256 与版本清单不一致")
    if len(model_manifests) != 1:
        raise RuntimeError("便携目录必须且只能包含一份离线识别组件清单")
    model_manifest_hash = _sha256(model_manifests[0])
    if metadata.get("model_manifest_sha256") != model_manifest_hash:
        raise RuntimeError("离线识别组件清单 SHA-256 与版本清单不一致")

    model_manifest = json.loads(model_manifests[0].read_text(encoding="utf-8"))
    packages = model_manifest.get("packages", {})
    required_packages = {"rapidocr", "onnxruntime", "spacy", "zh-core-web-sm"}
    if not required_packages.issubset(packages):
        raise RuntimeError("离线识别组件清单缺少 OCR/ONNX/中文模型版本")
    if not model_manifest.get("assets"):
        raise RuntimeError("离线识别组件清单没有资产记录")

    webengine_processes = list(app_dir.rglob("QtWebEngineProcess.exe"))
    ui_pages = list(app_dir.rglob("ui/dist/client/index.html"))
    if not webengine_processes:
        raise RuntimeError("便携目录缺少 QtWebEngineProcess.exe")
    if not ui_pages:
        raise RuntimeError("便携目录缺少本地 UI 构建文件")

    with zipfile.ZipFile(archive) as package:
        names = set(package.namelist())
        exe_name = f"{APP_NAME}/{APP_NAME}.exe"
        if exe_name not in names:
            raise RuntimeError("ZIP 中缺少应用 EXE")
        package.testzip()

    return {
        "ok": True,
        "appDir": str(app_dir),
        "archive": str(archive),
        "executableSha256": executable_hash,
        "archiveSha256": _sha256(archive),
        "modelManifestSha256": model_manifest_hash,
        "modelAssetCount": len(model_manifest["assets"]),
        "qtWebEngineProcessCount": len(webengine_processes),
        "uiPageCount": len(ui_pages),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    arguments = parser.parse_args()
    print(json.dumps(verify(arguments.root.resolve()), ensure_ascii=False, indent=2))
