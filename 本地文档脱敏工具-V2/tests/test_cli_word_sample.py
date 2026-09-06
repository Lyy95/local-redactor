from __future__ import annotations

import hashlib
from pathlib import Path

from local_redactor_v2.cli import run

SAMPLE = Path(__file__).resolve().parents[2] / "测试样本" / "青云专项工作联系单-脱敏测试样本.docx"


def test_regex_only_cli_exports_sample_docx_with_images(tmp_path: Path) -> None:
    assert SAMPLE.is_file()
    before = hashlib.sha256(SAMPLE.read_bytes()).hexdigest()
    out = tmp_path / "out"
    code = run(
        [
            str(SAMPLE),
            "--out",
            str(out),
            "--apply-all",
            "--keep-rest",
            "--regex-only",
            "--no-persist",
            "--json",
        ]
    )
    assert code == 0
    assert hashlib.sha256(SAMPLE.read_bytes()).hexdigest() == before
    copies = list(out.rglob("*.docx"))
    assert copies
    import zipfile

    with zipfile.ZipFile(copies[0]) as archive:
        media = [name for name in archive.namelist() if name.startswith("word/media/")]
    assert media == []


def test_apply_ordinary_keep_rest_exports_sample_docx(tmp_path: Path) -> None:
    assert SAMPLE.is_file()
    before = hashlib.sha256(SAMPLE.read_bytes()).hexdigest()
    code = run(
        [
            str(SAMPLE),
            "--out",
            str(tmp_path / "out"),
            "--apply-ordinary",
            "--keep-rest",
            "--regex-only",
            "--no-persist",
            "--json",
        ]
    )
    assert code == 0
    assert hashlib.sha256(SAMPLE.read_bytes()).hexdigest() == before


def test_apply_ordinary_alone_still_exports_by_auto_keep_rest(tmp_path: Path) -> None:
    code = run(
        [
            str(SAMPLE),
            "--out",
            str(tmp_path / "out"),
            "--apply-ordinary",
            "--regex-only",
            "--no-persist",
            "--json",
        ]
    )
    assert code == 0
