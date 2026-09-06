from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from local_redactor.core import CombinationRiskScorer, CompositeFindingDetector, StructuredDetector
from local_redactor.history import HistoryStore
from local_redactor.models import Category, FindingStatus, ImageDisposition, Modality, ProcessingMode
from local_redactor.rule_library import RuleLibrary, RuleStore
from local_redactor.service import LocalDesktopController


class _PlainProtector:
    prefix = b"plain-v1:"

    def protect(self, plaintext: bytes) -> bytes:
        return self.prefix + plaintext

    def unprotect(self, ciphertext: bytes) -> bytes:
        if not ciphertext.startswith(self.prefix):
            raise ValueError("unsupported local store encoding")
        return ciphertext[len(self.prefix) :]


class _EmptyImageAnalyzer:
    def analyze(self, _document):
        return SimpleNamespace(findings=[], warnings=[])


@dataclass
class _MemoryRuleStore:
    library: RuleLibrary

    def load(self) -> RuleLibrary:
        return self.library


class _MemoryHistory:
    def __init__(self) -> None:
        self.entries: list = []

    def load(self):
        return tuple(self.entries)

    def append(self, entry) -> None:
        self.entries = [entry, *(item for item in self.entries if item.id != entry.id)]

    def delete(self, entry_id: str) -> None:
        self.entries = [item for item in self.entries if item.id != entry_id]

    def clear(self) -> None:
        self.entries = []


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _state_dir() -> Path:
    local_app = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app:
        root = Path(local_app)
    else:
        root = Path.home() / ".local" / "share"
    path = root / "LocalRedactor" / "本地文档脱敏工具"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _controller(*, regex_only: bool, persist: bool) -> LocalDesktopController:
    detector = (
        CompositeFindingDetector(
            (StructuredDetector(),),
            combination_scorer=CombinationRiskScorer(),
        )
        if regex_only
        else None
    )
    if persist:
        state = _state_dir()
        protector = None if os.name == "nt" else _PlainProtector()
        rule_store = RuleStore(state / "rules.dat", protector=protector, include_presets=True)
        history_store = HistoryStore(state / "history.dat", protector=protector)
    else:
        rule_store = _MemoryRuleStore(RuleLibrary())
        history_store = _MemoryHistory()

    def images():
        try:
            from local_redactor.runtime import create_local_image_analyzer
            return create_local_image_analyzer()
        except Exception:
            return _EmptyImageAnalyzer()

    return LocalDesktopController(
        detector=detector,
        image_analyzer_factory=images,
        rule_store=rule_store,
        history_store=history_store,
    )


def _print_findings(bundle) -> None:
    print(f"文件：{bundle.source_name}")
    print(f"识别项：{len(bundle.findings)}")
    if bundle.blocking_issues:
        print("阻断：")
        for item in bundle.blocking_issues:
            print(f"  - {item}")
    for finding in bundle.findings:
        print(
            f"  [{finding.status.value}] {finding.category.value} "
            f"{finding.original!r} → {finding.replacement or finding.suggested_method.value}"
        )


_OFFICE_SUFFIXES = {".docx", ".xlsx"}


def _collect_sources(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.casefold() in _OFFICE_SUFFIXES else []
    if path.is_dir():
        return sorted(
            item
            for item in path.rglob("*")
            if item.is_file()
            and item.suffix.casefold() in _OFFICE_SUFFIXES
            and not item.name.startswith("~$")
        )
    return []


def _finding_is_visual(finding) -> bool:
    if finding.modality is Modality.IMAGE:
        return True
    return any(location.image_id for location in finding.locations)


def _remove_all_images(controller) -> None:
    document = controller._document
    bundle = controller._bundle
    if document is None:
        return
    for image in document.images:
        image.disposition = ImageDisposition.REMOVE
        image.regions.clear()
    if bundle is not None:
        for review in bundle.images:
            review.disposition = ImageDisposition.REMOVE


def _close_cli_review(controller, bundle, args) -> None:
    if args.apply_ordinary:
        controller.resolve_ordinary_findings()
    if args.apply_all:
        for finding in list(bundle.findings):
            if finding.status is not FindingStatus.PENDING:
                continue
            if finding.category is Category.COMBINATION_RISK:
                continue
            if _finding_is_visual(finding):
                continue
            controller.resolve_finding(
                finding.id,
                FindingStatus.TRANSFORM,
                finding.suggested_method,
            )
    if args.keep_rest:
        for finding in list(bundle.findings):
            if finding.status is not FindingStatus.PENDING:
                continue
            if finding.category is Category.COMBINATION_RISK:
                continue
            if _finding_is_visual(finding):
                continue
            controller.resolve_finding(
                finding.id,
                FindingStatus.KEEP_FALSE_POSITIVE,
                finding.suggested_method,
                ignore_reason="命令行未逐项确认，保留原文",
            )
    if args.apply_all or args.keep_rest:
        _remove_all_images(controller)
        if controller._bundle is not None:
            controller._refresh_combination_statuses(controller._bundle.findings)


def _process_one(controller, source: Path, out: Path, args) -> dict:
    original_hash = _sha256(source)
    mode = ProcessingMode.BALANCED if args.mode == "balanced" else ProcessingMode.STRICT
    bundle = controller.scan(source, mode)
    _close_cli_review(controller, bundle, args)
    if not args.json:
        _print_findings(bundle)
    artifacts = controller.export(out, mapping_password="")
    after_hash = _sha256(source)
    return {
        "ok": True,
        "source": str(source),
        "sourceSha256": original_hash,
        "unchangedSource": original_hash == after_hash,
        "resultRoot": str(artifacts.result_root),
        "aiCopy": str(artifacts.ai_copy),
        "mapping": str(artifacts.encrypted_mapping),
        "report": str(artifacts.report),
        "findings": len(bundle.findings),
    }


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="本地文档脱敏工具命令行")
    parser.add_argument("source", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mode", choices=["balanced", "strict"], default="balanced")
    parser.add_argument("--apply-ordinary", action="store_true")
    parser.add_argument("--apply-all", action="store_true")
    parser.add_argument("--keep-rest", action="store_true")
    parser.add_argument("--regex-only", action="store_true")
    parser.add_argument("--no-persist", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    source = args.source.expanduser().resolve()
    files = _collect_sources(source)
    if not files:
        print("请提供 .docx / .xlsx", file=sys.stderr)
        return 2
    controller = _controller(regex_only=args.regex_only, persist=not args.no_persist)
    out = args.out.expanduser().resolve()
    results, failures = [], 0
    for path in files:
        try:
            payload = _process_one(controller, path, out, args)
            results.append(payload)
            if not args.json:
                print("原件哈希未变" if payload["unchangedSource"] else "警告：原件哈希变化")
                print(f"AI交付：{payload['aiCopy']}")
        except Exception as exc:
            failures += 1
            results.append({"ok": False, "source": str(path), "error": str(exc)})
            detail = str(exc)
            cause = exc.__cause__ or exc.__context__
            if cause and str(cause) not in detail:
                detail = f"{detail}（{cause}）"
            print(f"导出未完成：{path.name}：{detail}", file=sys.stderr)
    if args.json:
        print(json.dumps({"ok": failures == 0, "results": results}, ensure_ascii=False, indent=2))
    elif failures:
        print(f"完成 {len(results) - failures} 个，失败 {failures} 个。", file=sys.stderr)
        return 3
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
