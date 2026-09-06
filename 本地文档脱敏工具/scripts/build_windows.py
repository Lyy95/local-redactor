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

APP_NAME = "本地文档脱敏工具"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def ensure_generated_target(path: Path, project_root: Path) -> None:
    resolved = path.resolve(strict=False)
    resolved.relative_to(project_root.resolve(strict=True))
    if path.exists():
        raise RuntimeError(f"目标已存在，为避免覆盖请先另存或使用 --replace：{path}")


def remove_generated_target(path: Path, project_root: Path) -> None:
    resolved = path.resolve(strict=False)
    resolved.relative_to(project_root.resolve(strict=True))
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def build(*, replace: bool = False) -> tuple[Path, Path]:
    project_root = Path(__file__).resolve().parents[1]
    dist_root = project_root / "dist"
    app_dir = dist_root / APP_NAME
    zip_path = dist_root / f"{APP_NAME}-Windows-x64.zip"
    work_root = project_root / "build" / "pyinstaller-work"
    spec_root = project_root / "build" / "pyinstaller-spec"
    usage_pdf = project_root / "assets" / "使用说明.pdf"
    logo_path = project_root / "assets" / "logo-glass-transparent-cropped.png"
    if not usage_pdf.is_file():
        raise RuntimeError("缺少 assets/使用说明.pdf，不能生成正式绿色版")
    if not logo_path.is_file():
        raise RuntimeError("缺少应用 Logo，不能生成正式绿色版")

    for target in (app_dir, zip_path):
        if target.exists():
            if not replace:
                ensure_generated_target(target, project_root)
            remove_generated_target(target, project_root)
    manifest = build_manifest(project_root / "build" / "generated" / "model-manifest.json")
    dist_root.mkdir(parents=True, exist_ok=True)
    work_root.mkdir(parents=True, exist_ok=True)
    spec_root.mkdir(parents=True, exist_ok=True)

    add_data = f"{manifest}{os.pathsep}."
    logo_data = f"{logo_path}{os.pathsep}assets"
    PyInstaller.__main__.run(
        [
            str(project_root / "scripts" / "launcher.py"),
            "--noconfirm",
            "--onedir",
            "--windowed",
            "--noupx",
            "--name",
            APP_NAME,
            "--icon",
            str(logo_path),
            "--contents-directory",
            "离线识别组件",
            "--paths",
            str(project_root / "src"),
            "--distpath",
            str(dist_root),
            "--workpath",
            str(work_root),
            "--specpath",
            str(spec_root),
            "--add-data",
            add_data,
            "--add-data",
            logo_data,
            "--collect-all",
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
        ]
    )

    executable = app_dir / f"{APP_NAME}.exe"
    if not executable.is_file():
        raise RuntimeError("PyInstaller 未生成预期可执行文件")
    shutil.copy2(usage_pdf, app_dir / "使用说明.pdf")
    build_info = {
        "product": APP_NAME,
        "version": "0.4.0",
        "built_at_utc": datetime.now(UTC).isoformat(),
        "architecture": "Windows x64",
        "runtime": "fully local; no upload; no runtime download",
        "executable_sha256": sha256_file(executable),
        "model_manifest_sha256": sha256_file(manifest),
    }
    (app_dir / "版本与校验.json").write_text(
        json.dumps(build_info, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    environment = dict(os.environ)
    environment["QT_QPA_PLATFORM"] = "offscreen"
    completed = subprocess.run(
        [str(executable), "--self-test"],
        cwd=app_dir,
        env=environment,
        timeout=120,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"绿色版离屏启动自检失败，退出码 {completed.returncode}")

    with zipfile.ZipFile(
        zip_path,
        mode="x",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in sorted(app_dir.rglob("*")):
            if path.is_file():
                archive.write(
                    path,
                    (Path(APP_NAME) / path.relative_to(app_dir)).as_posix(),
                )
    return app_dir, zip_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--replace",
        action="store_true",
        help="replace only the generated app folder and ZIP under dist",
    )
    arguments = parser.parse_args()
    built_dir, built_zip = build(replace=arguments.replace)
    print(built_dir)
    print(built_zip)
