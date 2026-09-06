from __future__ import annotations

from pathlib import Path

from local_redactor.history import HistoryEntry, HistoryStore


class TestProtector:
    def protect(self, plaintext: bytes) -> bytes:
        return b"encrypted:" + plaintext[::-1]

    def unprotect(self, ciphertext: bytes) -> bytes:
        assert ciphertext.startswith(b"encrypted:")
        return ciphertext[len(b"encrypted:") :][::-1]


def entry(identifier: str, source_name: str = "测试文档.docx") -> HistoryEntry:
    return HistoryEntry(
        id=identifier,
        created_at="2026-08-07T17:00:00+08:00",
        source_name=source_name,
        source_sha256="a" * 64,
        document_kind="docx",
        status="completed",
        finding_count=8,
        transformed_count=7,
        removed_count=1,
        result_path=r"C:\result",
    )


def test_history_is_encrypted_and_supports_delete_and_clear(tmp_path: Path) -> None:
    path = tmp_path / "history.dat"
    store = HistoryStore(path, TestProtector())
    store.append(entry("one"))
    store.append(entry("two", "第二个文档.xlsx"))

    raw = path.read_bytes()
    assert raw.startswith(b"encrypted:")
    assert "测试文档".encode() not in raw
    assert [item.id for item in store.load()] == ["two", "one"]

    store.delete("two")
    assert [item.id for item in store.load()] == ["one"]
    store.clear()
    assert store.load() == ()
