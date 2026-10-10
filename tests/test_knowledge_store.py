from pathlib import Path

import pytest

from knowledge.store import KnowledgeStore, chunk_text


def test_index_and_search(tmp_path):
    doc = tmp_path / "notes.md"
    doc.write_text("RAG retrieves evidence from external knowledge.", encoding="utf-8")
    kb = KnowledgeStore(tmp_path / "db.sqlite3")
    result = kb.ingest_file(doc)
    matches = kb.search("How does RAG retrieve evidence?")
    assert result.chunk_count == 1
    assert matches and matches[0].title == "notes.md"
    assert "external knowledge" in matches[0].body


def test_index_unchanged_and_persistent(tmp_path):
    doc = tmp_path / "notes.txt"
    doc.write_text("Vector databases can store embeddings.", encoding="utf-8")
    db = tmp_path / "db.sqlite3"
    kb = KnowledgeStore(db)
    first = kb.ingest_file(doc)
    second = kb.ingest_file(doc)
    other = KnowledgeStore(db)
    assert not first.unchanged
    assert second.unchanged
    assert first.document_id == second.document_id
    assert len(other.search("embeddings")) == 1


def test_reindex_deletes_stale_fts_rows(tmp_path):
    doc = tmp_path / "notes.txt"
    doc.write_text("alpha previous information", encoding="utf-8")
    kb = KnowledgeStore(tmp_path / "db.sqlite3")
    original = kb.ingest_file(doc)
    doc.write_text("beta changed information", encoding="utf-8")
    updated = kb.ingest_file(doc)
    assert updated.document_id == original.document_id
    assert not kb.search("alpha")
    assert len(kb.search("beta")) == 1


def test_query_syntax_injection_cannot_bypass_match(tmp_path):
    doc = tmp_path / "notes.md"
    doc.write_text("project conductor orchestration", encoding="utf-8")
    kb = KnowledgeStore(tmp_path / "db.sqlite3")
    kb.ingest_file(doc)
    # Tokens are quoted, not interpreted as FTS5 query operators.
    assert kb.search('project" OR (unknown)')
    assert kb.search('""(((***   ' ) == []


def test_reject_non_text_type(tmp_path):
    doc = tmp_path / "file.pdf"
    doc.write_bytes(b"PDF")
    with pytest.raises(ValueError, match="Only"):
        KnowledgeStore(tmp_path / "db.sqlite3").ingest_file(doc)


def test_reject_empty_file(tmp_path):
    doc = tmp_path / "blank.md"
    doc.write_text("\n\n", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        KnowledgeStore(tmp_path / "db.sqlite3").ingest_file(doc)


def test_reject_binary_file(tmp_path):
    doc = tmp_path / "invalid.txt"
    doc.write_bytes(b"hello\x00world")
    with pytest.raises(ValueError, match="Binary"):
        KnowledgeStore(tmp_path / "db.sqlite3").ingest_file(doc)


def test_reject_non_utf8(tmp_path):
    doc = tmp_path / "invalid.txt"
    doc.write_bytes(b"\xff\xfe\xfd")
    with pytest.raises(ValueError, match="UTF-8"):
        KnowledgeStore(tmp_path / "db.sqlite3").ingest_file(doc)


def test_reject_over_2mb(tmp_path):
    doc = tmp_path / "large.txt"
    doc.write_bytes(b"a" * (2 * 1024 * 1024 + 1))
    with pytest.raises(ValueError, match="2 MiB"):
        KnowledgeStore(tmp_path / "db.sqlite3").ingest_file(doc)


def test_delete_document_cleans_index(tmp_path):
    doc = tmp_path / "notes.md"
    doc.write_text("confidentialflower research", encoding="utf-8")
    kb = KnowledgeStore(tmp_path / "db.sqlite3")
    item = kb.ingest_file(doc)
    assert kb.delete_document(item.document_id)
    assert not kb.search("confidentialflower")
    assert kb.list_documents() == []
    assert not kb.delete_document(item.document_id)


def test_search_limit_validation(tmp_path):
    kb = KnowledgeStore(tmp_path / "db.sqlite3")
    with pytest.raises(ValueError):
        kb.search("test", limit=0)
    with pytest.raises(ValueError):
        kb.search("test", limit=21)


def test_chunk_overlap():
    text = " ".join(f"word{i}" for i in range(20))
    chunks = chunk_text(text, words_per_chunk=10, overlap=3)
    assert len(chunks) == 3
    assert chunks[0].split()[-3:] == chunks[1].split()[:3]
    assert chunks[1].split()[-3:] == chunks[2].split()[:3]


def test_chunk_invalid_overlap():
    with pytest.raises(ValueError):
        chunk_text("a b", words_per_chunk=4, overlap=4)


def test_symlink_rejected_if_supported(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("secret", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation unavailable on this platform")
    with pytest.raises(ValueError, match="Symlink"):
        KnowledgeStore(tmp_path / "db.sqlite3").ingest_file(link)
