from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import PyInstaller.__main__
from generate_model_manifest import build_manifest

APP_NAME = "本地文档脱敏工具-V2"


def run_pyinstaller(arguments: list[str]) -> None:
    original_path = os.environ.get("PATH", "")
    clean_entries = [
        entry
        for entry in original_path.split(os.pathsep)
        if "codex-runtimes" not in entry.casefold()
    ]
    os.environ["PATH"] = os.pathsep.join(clean_entries)
    try:
        PyInstaller.__main__.run(arguments)
    finally:
        os.environ["PATH"] = original_path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build(*, replace: bool = False) -> tuple[Path, Path]:
    root = Path(__file__).resolve().parents[1]
    ui_root = root / "ui"
    ui_dist = ui_root / "dist" / "client"
    if not (ui_dist / "index.html").is_file():
        raise RuntimeError("UI 尚未构建，请先在 ui 目录执行 npm run build")
    dist = root / "dist"
    app_dir = dist / APP_NAME
    zip_path = dist / f"{APP_NAME}-Windows-x64.zip"
    if not replace and (app_dir.exists() or zip_path.exists()):
        raise RuntimeError("目标已存在；使用 --replace 才允许替换 V2 生成物")
    if app_dir.exists():
        shutil.rmtree(app_dir)
    if zip_path.exists():
        zip_path.unlink()
    dist.mkdir(parents=True, exist_ok=True)
    spec = root / "build" / "pyinstaller-spec"
    work = root / "build" / "pyinstaller-work"
    spec.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    entry = root / "scripts" / "desktop_entry.py"
    model_manifest = build_manifest(root / "build" / "generated" / "model-manifest.json")
    run_pyinstaller(
        [
            str(entry),
            "--noconfirm",
            "--clean",
            "--onedir",
            "--windowed",
            "--disable-windowed-traceback",
            "--name",
            APP_NAME,
            "--paths",
            str(root / "src"),
            "--distpath",
            str(dist),
            "--workpath",
            str(work),
            "--specpath",
            str(spec),
            "--add-data",
            f"{ui_dist}{__import__('os').pathsep}ui/dist/client",
            "--add-data",
            f"{model_manifest}{os.pathsep}.",
            "--hidden-import",
            "PySide6.QtWebChannel",
            "--hidden-import",
            "PySide6.QtWebEngineCore",
            "--hidden-import",
            "PySide6.QtWebEngineWidgets",
            "--collect-data",
            "rapidocr",
            "--collect-all",
            "zh_core_web_sm",
            "--collect-all",
            "spacy_pkuseg",
            "--collect-data",
            "cv2",
            "--hidden-import",
            "onnxruntime",
            "--hidden-import",
            "spacy.lang.zh",
            "--exclude-module",
            "torch",
            "--exclude-module",
            "torchvision",
            "--exclude-module",
            "torchaudio",
            "--exclude-module",
            "tensorflow",
            "--exclude-module",
            "jax",
            "--exclude-module",
            "cupy",
            "--exclude-module",
            "pandas",
            "--exclude-module",
            "scipy",
            "--exclude-module",
            "sklearn",
            "--exclude-module",
            "matplotlib",
            "--exclude-module",
            "pytest",
            "--exclude-module",
            "IPython",
        ]
    )
    polluted_icu = app_dir / "_internal" / "icuuc.dll"
    if polluted_icu.exists():
        raise RuntimeError(
            "构建环境污染：检测到不应随包携带的 icuuc.dll；"
            "Qt 必须使用 Windows 系统 ICU，禁止从 Codex/Poppler PATH 收集"
        )
    executable = app_dir / f"{APP_NAME}.exe"
    if not executable.is_file():
        raise RuntimeError("PyInstaller 未生成 V2 可执行文件")
    info = {
        "product": APP_NAME,
        "built_at_utc": datetime.now(UTC).isoformat(),
        "architecture": "Windows x64",
        "runtime": "fully local; no upload; no runtime download",
        "executable_sha256": sha256_file(executable),
        "model_manifest_sha256": sha256_file(model_manifest),
    }
    (app_dir / "版本与校验.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    env = dict(__import__("os").environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --no-sandbox"
    check = subprocess.run(
        [str(executable), "--self-test"],
        cwd=app_dir,
        env=env,
        timeout=120,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check.returncode != 0:
        details = "\n".join(part.strip() for part in (check.stdout, check.stderr) if part.strip())
        raise RuntimeError(f"V2 EXE 自检失败：{check.returncode}\n{details}")
    with zipfile.ZipFile(zip_path, "x", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(app_dir.rglob("*")):
            if path.is_file():
                archive.write(path, (Path(APP_NAME) / path.relative_to(app_dir)).as_posix())
    return app_dir, zip_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    print(*build(replace=args.replace), sep="\n")
