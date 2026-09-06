"""Offline semantic-preserving redaction for modern Office documents."""

from .models import (
    Category,
    DocumentKind,
    DocumentModel,
    Finding,
    FindingStatus,
    MappingEntry,
    Modality,
    ProcessingMode,
    TransformMethod,
)

__all__ = [
    "Category",
    "DocumentKind",
    "DocumentModel",
    "Finding",
    "FindingStatus",
    "MappingEntry",
    "Modality",
    "ProcessingMode",
    "TransformMethod",
]

__version__ = "0.4.0"
