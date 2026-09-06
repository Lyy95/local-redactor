from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from .models import (
    DocumentModel,
    ExportArtifacts,
    Finding,
    MappingEntry,
    ProcessingMode,
)


class DocumentAdapter(Protocol):
    def scan(self, path: Path) -> DocumentModel: ...

    def export(
        self,
        document: DocumentModel,
        findings: Sequence[Finding],
        target_path: Path,
    ) -> None: ...


class FindingDetector(Protocol):
    name: str

    def detect(self, document: DocumentModel) -> list[Finding]: ...


class TransformationEngine(Protocol):
    def prepare(
        self,
        document: DocumentModel,
        findings: Sequence[Finding],
        mode: ProcessingMode,
    ) -> tuple[list[Finding], list[MappingEntry]]: ...


class ArtifactExporter(Protocol):
    def export_task(
        self,
        document: DocumentModel,
        findings: Sequence[Finding],
        mappings: Sequence[MappingEntry],
        result_root: Path,
        mapping_password: str,
    ) -> ExportArtifacts: ...
