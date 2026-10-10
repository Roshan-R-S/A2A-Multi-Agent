import pytest

from memory.store import ConversationMemory


def test_history_persists_across_instances(tmp_path):
    db = tmp_path / "memory.db"
    a = ConversationMemory(db)
    a.add_message("sprint", "user", "Build RAG")
    a.add_message("sprint", "assistant", "Start with SQLite")
    b = ConversationMemory(db)
    assert [(x.role, x.content) for x in b.history("sprint")] == [
        ("user", "Build RAG"), ("assistant", "Start with SQLite")
    ]


def test_exchanges_are_ordered(tmp_path):
    memory = ConversationMemory(tmp_path / "db.sqlite3")
    memory.add_exchange("sprint", "question one", "answer one")
    memory.add_exchange("sprint", "question two", "answer two")
    assert [m.content for m in memory.history("sprint")] == [
        "question one", "answer one", "question two", "answer two"
    ]


def test_history_limit_returns_last_n(tmp_path):
    memory = ConversationMemory(tmp_path / "db.sqlite3")
    memory.add_exchange("sprint", "one", "two")
    memory.add_exchange("sprint", "three", "four")
    assert [m.content for m in memory.history("sprint", limit=2)] == [
        "three", "four"
    ]


def test_conversations_are_isolated(tmp_path):
    memory = ConversationMemory(tmp_path / "db.sqlite3")
    memory.add_message("one", "user", "private one")
    memory.add_message("two", "user", "private two")
    assert [m.content for m in memory.history("one")] == ["private one"]


def test_delete_conversation(tmp_path):
    memory = ConversationMemory(tmp_path / "db.sqlite3")
    memory.add_exchange("one", "hello", "hi")
    assert memory.delete_conversation("one")
    assert not memory.delete_conversation("one")
    assert memory.history("one") == []


@pytest.mark.parametrize("name", ["", "../escape", "hello world", "a" * 65])
def test_invalid_conversation_ids(tmp_path, name):
    memory = ConversationMemory(tmp_path / "db.sqlite3")
    with pytest.raises(ValueError):
        memory.add_message(name, "user", "test")


@pytest.mark.parametrize("role,content", [("tool", "hello"), ("user", ""),
                                            ("assistant", "x" * 20001)])
def test_invalid_messages(tmp_path, role, content):
    memory = ConversationMemory(tmp_path / "db.sqlite3")
    with pytest.raises(ValueError):
        memory.add_message("sprint", role, content)


def test_exchange_rejected_atomically(tmp_path):
    memory = ConversationMemory(tmp_path / "db.sqlite3")
    with pytest.raises(ValueError):
        memory.add_exchange("sprint", "hello", " ")
    assert memory.history("sprint") == []
