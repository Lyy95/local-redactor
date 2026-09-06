from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from local_redactor.artifacts import verify_encrypted_mapping
from local_redactor.models import (
    FindingStatus,
    ImageDisposition,
    ProcessingMode,
    TransformMethod,
)
from local_redactor.rule_library import RuleStore
from local_redactor.runtime import enforce_offline_runtime
from local_redactor.service import LocalDesktopController

PASSWORD = "Acceptance#Pass2026"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def complete_fixture(source: Path, output_parent: Path) -> None:
    before = sha256(source)
    controller = LocalDesktopController(
        rule_store=RuleStore(output_parent / "acceptance-rules.dat")
    )
    bundle = controller.scan(source, ProcessingMode.BALANCED)
    for finding in bundle.findings:
        status = (
            FindingStatus.REMOVE
            if finding.suggested_method is TransformMethod.REMOVE
            else FindingStatus.TRANSFORM
        )
        controller.resolve_finding(
            finding.id,
            status,
            finding.suggested_method,
        )
    for image in bundle.images:
        controller.resolve_image(image.id, ImageDisposition.PIXEL_REDACT)
    for item in bundle.hidden_items:
        controller.resolve_hidden(item.id, "remove")
    if not controller.is_review_complete():
        raise RuntimeError("虚构资料仍有未决复核项")
    artifacts = controller.export(output_parent, PASSWORD)
    for path in (
        artifacts.ai_copy,
        artifacts.encrypted_mapping,
        artifacts.report,
    ):
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError("端到端验收缺少交付文件")
    verify_encrypted_mapping(
        artifacts.encrypted_mapping,
        PASSWORD,
    )
    if sha256(source) != before:
        raise RuntimeError("端到端验收发现原文件发生变化")
    ai_files = [
        path.name for path in (artifacts.result_root / "AI交付").iterdir() if path.is_file()
    ]
    if ai_files != [artifacts.ai_copy.name]:
        raise RuntimeError("AI交付目录包含额外文件")
    controller.reset()
    print(f"accepted: {source.name}")


def main() -> None:
    enforce_offline_runtime()
    root = Path(__file__).resolve().parents[1]
    fixtures = (
        root / "fixtures" / "虚构项目方案.docx",
        root / "fixtures" / "虚构项目台账.xlsx",
    )
    with tempfile.TemporaryDirectory(prefix="local-redactor-acceptance-") as directory:
        output_parent = Path(directory)
        for fixture in fixtures:
            complete_fixture(fixture, output_parent)


if __name__ == "__main__":
    main()
