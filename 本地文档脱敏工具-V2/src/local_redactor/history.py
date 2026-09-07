from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from .rule_library import Protector, default_app_data_dir, default_protector


class HistoryError(RuntimeError):
    """Encrypted history could not be read or written safely."""


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    id: str
    created_at: str
    source_name: str
    source_sha256: str
    document_kind: str
    status: str
    finding_count: int
    transformed_count: int
    removed_count: int
    result_path: str = ""


class HistoryStoreProtocol(Protocol):
    def load(self) -> tuple[HistoryEntry, ...]: ...
    def append(self, entry: HistoryEntry) -> None: ...
    def delete(self, entry_id: str) -> None: ...
    def clear(self) -> None: ...


def default_history_store_path() -> Path:
    return default_app_data_dir() / "history.dat"


class HistoryStore:
    """Small DPAPI-encrypted task index; it never stores originals or mappings."""

    def __init__(
        self,
        path: Path | None = None,
        protector: Protector | None = None,
    ) -> None:
        self.path = Path(path) if path is not None else default_history_store_path()
        self.protector = protector or default_protector()

    def load(self) -> tuple[HistoryEntry, ...]:
        if not self.path.exists():
            return ()
        try:
            encrypted = self.path.read_bytes()
            decoded = json.loads(self.protector.unprotect(encrypted).decode("utf-8"))
            rows = decoded.get("entries", [])
            if not isinstance(rows, list):
                raise ValueError("entries")
            return tuple(HistoryEntry(**row) for row in rows if isinstance(row, dict))
        except Exception as exc:
            raise HistoryError("本地加密历史无法读取或已损坏") from exc

    def append(self, entry: HistoryEntry) -> None:
        entries = [entry, *(item for item in self.load() if item.id != entry.id)]
        self._save(tuple(entries[:500]))

    def delete(self, entry_id: str) -> None:
        self._save(tuple(item for item in self.load() if item.id != entry_id))

    def clear(self) -> None:
        self._save(())

    def _save(self, entries: tuple[HistoryEntry, ...]) -> None:
        plaintext = json.dumps(
            {"schema_version": 1, "entries": [asdict(item) for item in entries]},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        try:
            encrypted = self.protector.protect(plaintext)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                dir=self.path.parent,
            )
            os.close(descriptor)
            temporary = Path(temporary_name)
            try:
                temporary.write_bytes(encrypted)
                os.replace(temporary, self.path)
            finally:
                if temporary.exists():
                    temporary.unlink()
        except Exception as exc:
            raise HistoryError("本地加密历史写入失败") from exc


def new_history_id() -> str:
    return uuid4().hex


__all__ = [
    "HistoryEntry",
    "HistoryError",
    "HistoryStore",
    "HistoryStoreProtocol",
    "default_history_store_path",
    "new_history_id",
]
