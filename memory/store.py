"""Persistent local messages. Storage is not encrypted at rest."""

from dataclasses import dataclass
from pathlib import Path
import re

from knowledge.db import connect

_CONVERSATION_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_ROLES = {"user", "assistant"}
_MAX_CONTENT = 20000
_MAX_TITLE = 80


def _clean_title(value: str, *, truncate: bool = False) -> str:
    """Only user-provided text. No external title-generation requests."""
    if not isinstance(value, str):
        raise ValueError("Conversation title must be text.")
    clean = " ".join(value.split())
    if not clean:
        if truncate:
            return "Untitled conversation"
        raise ValueError("Conversation title cannot be empty.")
    if len(clean) > _MAX_TITLE:
        if not truncate:
            raise ValueError("Conversation title must be 80 characters or less.")
        clean = clean[:_MAX_TITLE].rstrip()
    return clean


@dataclass(frozen=True)
class MemoryMessage:
    role: str
    content: str
    created_at: str


def _validate_conversation_id(conversation_id: str) -> str:
    if not _CONVERSATION_RE.fullmatch(conversation_id):
        raise ValueError("Conversation ID: use 1-64 letters, numbers, _ or -.")
    return conversation_id


def _validate_message(role: str, content: str) -> None:
    if role not in _ROLES:
        raise ValueError("Role must be user or assistant.")
    if not isinstance(content, str) or not content.strip() or len(content) > _MAX_CONTENT:
        raise ValueError("Message must have 1-20000 nonempty characters.")


class ConversationMemory:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = db_path
        with connect(self.db_path) as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS memory_conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT
                );
                CREATE TABLE IF NOT EXISTS memory_messages (
                    id INTEGER PRIMARY KEY,
                    conversation_id TEXT NOT NULL
                        REFERENCES memory_conversations(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK(role IN ('user','assistant')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                        DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                );
                CREATE INDEX IF NOT EXISTS memory_messages_by_conversation
                    ON memory_messages(conversation_id, id);
            """)
            # Upgrade existing databases without losing any saved conversations.
            columns = {row["name"] for row in con.execute(
                "PRAGMA table_info(memory_conversations)"
            )}
            if "title" not in columns:
                con.execute("ALTER TABLE memory_conversations ADD COLUMN title TEXT")
            missing = con.execute("""
                SELECT c.id, (
                    SELECT m.content FROM memory_messages AS m
                    WHERE m.conversation_id=c.id AND m.role='user'
                    ORDER BY m.id LIMIT 1
                ) AS first_question
                FROM memory_conversations AS c
                WHERE c.title IS NULL OR c.title=''
            """).fetchall()
            for row in missing:
                if row["first_question"] is None:
                    continue
                con.execute(
                    "UPDATE memory_conversations SET title=? WHERE id=?",
                    (_clean_title(row["first_question"] or "", truncate=True), row["id"]),
                )

    def rename_conversation(self, conversation_id: str, title: str) -> bool:
        _validate_conversation_id(conversation_id)
        name = _clean_title(title)
        with connect(self.db_path) as con:
            result = con.execute(
                "UPDATE memory_conversations SET title=? WHERE id=?",
                (name, conversation_id),
            )
            return result.rowcount > 0

    def add_message(self, conversation_id: str, role: str, content: str) -> None:
        _validate_conversation_id(conversation_id)
        _validate_message(role, content)
        with connect(self.db_path) as con:
            con.execute(
                "INSERT OR IGNORE INTO memory_conversations(id) VALUES (?)",
                (conversation_id,),
            )
            con.execute(
                "INSERT INTO memory_messages(conversation_id,role,content) "
                "VALUES (?,?,?)", (conversation_id, role, content),
            )
            if role == "user":
                con.execute(
                    "UPDATE memory_conversations SET title=? "
                    "WHERE id=? AND title IS NULL",
                    (_clean_title(content, truncate=True), conversation_id),
                )

    def add_exchange(self, conversation_id: str, question: str, answer: str) -> None:
        _validate_conversation_id(conversation_id)
        _validate_message("user", question)
        _validate_message("assistant", answer)
        with connect(self.db_path) as con:
            con.execute(
                "INSERT OR IGNORE INTO memory_conversations(id) VALUES (?)",
                (conversation_id,),
            )
            con.executemany(
                "INSERT INTO memory_messages(conversation_id,role,content) "
                "VALUES (?,?,?)",
                [(conversation_id, "user", question),
                 (conversation_id, "assistant", answer)],
            )
            con.execute(
                "UPDATE memory_conversations SET title=? "
                "WHERE id=? AND title IS NULL",
                (_clean_title(question, truncate=True), conversation_id),
            )

    def history(self, conversation_id: str, limit: int = 50) -> list[MemoryMessage]:
        _validate_conversation_id(conversation_id)
        if limit < 1 or limit > 500:
            raise ValueError("History limit must be between 1 and 500.")
        with connect(self.db_path) as con:
            rows = con.execute(
                """SELECT role, content, created_at FROM (
                    SELECT id, role, content, created_at FROM memory_messages
                    WHERE conversation_id=? ORDER BY id DESC LIMIT ?
                   ) ORDER BY id ASC""",
                (conversation_id, limit),
            ).fetchall()
        return [MemoryMessage(r["role"], r["content"], r["created_at"])
                for r in rows]

    def delete_conversation(self, conversation_id: str) -> bool:
        _validate_conversation_id(conversation_id)
        with connect(self.db_path) as con:
            result = con.execute(
                "DELETE FROM memory_conversations WHERE id=?", (conversation_id,)
            )
            return result.rowcount > 0
