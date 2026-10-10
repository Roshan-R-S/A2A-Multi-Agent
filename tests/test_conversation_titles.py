"""Phase 4 frontend-polish SQLite title migration and API regression tests."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from knowledge.db import connect
from memory.store import ConversationMemory
from web_api.app import create_app


def test_first_user_question_becomes_persistent_title(tmp_path):
    path = tmp_path / "test.db"
    memory = ConversationMemory(path)
    memory.add_exchange("chat_a", "  What is   RAG?\n  ", "Retrieval-augmented generation")
    memory.add_exchange("chat_a", "What are its limits?", "Some limitations")
    with connect(path) as con:
        title = con.execute("SELECT title FROM memory_conversations WHERE id='chat_a'").fetchone()[0]
    assert title == "What is RAG?"
    assert ConversationMemory(path).history("chat_a")[0].content.strip() == "What is   RAG?"


def test_add_message_sets_title_only_for_first_user(tmp_path):
    path = tmp_path / "test.db"
    mem = ConversationMemory(path)
    mem.add_message("c", "assistant", "Welcome")
    mem.add_message("c", "user", "How do A2A agents work?")
    mem.add_message("c", "user", "Another question")
    with connect(path) as con:
        assert con.execute("SELECT title FROM memory_conversations WHERE id='c'").fetchone()[0] == "How do A2A agents work?"


def test_upgrade_existing_database_backfills_first_question(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as con:
        con.executescript("""
            CREATE TABLE memory_conversations (id TEXT PRIMARY KEY);
            CREATE TABLE memory_messages (
                id INTEGER PRIMARY KEY, conversation_id TEXT, role TEXT,
                content TEXT, created_at TEXT
            );
            INSERT INTO memory_conversations VALUES ('old');
            INSERT INTO memory_messages VALUES (1,'old','user','  First  topic  ', '2026-01-01');
            INSERT INTO memory_messages VALUES (2,'old','assistant','answer', '2026-01-02');
            INSERT INTO memory_messages VALUES (3,'old','user','Second topic', '2026-01-03');
        """)
    m = ConversationMemory(path)
    with connect(path) as con:
        title = con.execute("SELECT title FROM memory_conversations WHERE id='old'").fetchone()[0]
    assert title == "First topic"
    assert len(m.history("old")) == 3
    assert ConversationMemory(path).history("old")[0].content.strip() == "First  topic"


def test_titles_are_isolated_renamed_and_deleted(tmp_path):
    path = tmp_path / "db.sqlite"
    mem = ConversationMemory(path)
    mem.add_exchange("alpha", "One question", "answer")
    mem.add_exchange("beta", "Different question", "answer")
    assert mem.rename_conversation("alpha", "  Custom   name\nhere  ")
    assert not mem.rename_conversation("unknown", "Test")
    with connect(path) as con:
        assert con.execute("SELECT title FROM memory_conversations WHERE id='alpha'").fetchone()[0] == "Custom name here"
        assert con.execute("SELECT title FROM memory_conversations WHERE id='beta'").fetchone()[0] == "Different question"
    assert mem.delete_conversation("alpha")
    assert mem.history("alpha") == []


@pytest.mark.parametrize("bad", ["", "  \n ", "x"*81])
def test_rename_rejects_invalid_titles(tmp_path, bad):
    mem = ConversationMemory(tmp_path / "db.sqlite")
    mem.add_exchange("chat", "Hi", "Hello")
    with pytest.raises(ValueError):
        mem.rename_conversation("chat", bad)


def test_api_lists_friendly_titles_without_exposing_ids_in_title(tmp_path):
    path = tmp_path / "api.db"
    app = create_app(db_path=path)
    with TestClient(app) as client:
        # History is created through the same store used by the API.
        memory = ConversationMemory(path)
        memory.add_exchange("chat_sensitive_internal_id", "Explain Python decorators", "Functions wrap functions")
        conversations = client.get("/api/conversations")
        assert conversations.status_code == 200
        result = conversations.json()[0]
        assert result["id"] == "chat_sensitive_internal_id" # API still needs stable routing IDs.
        assert result["title"] == "Explain Python decorators"
        renamed = client.patch("/api/conversations/chat_sensitive_internal_id", json={"title":"My Python research"})
        assert renamed.status_code == 200
        assert renamed.json()["title"] == "My Python research"
        assert client.get("/api/conversations").json()[0]["title"] == "My Python research"
        assert client.patch("/api/conversations/missing", json={"title":"Ignore"}).status_code == 404
        assert client.patch("/api/conversations/chat_sensitive_internal_id", json={"title":"  "}).status_code == 422
        assert client.get("/api/conversations/chat_sensitive_internal_id").status_code == 200
        assert client.delete("/api/conversations/chat_sensitive_internal_id").json()["deleted"]
        assert client.get("/api/conversations").json() == []
