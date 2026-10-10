"""Persistent local messages. Storage is not encrypted at rest."""

from dataclasses import dataclass
from pathlib import Path
import re

from knowledge.db import connect

_CONVERSATION_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_ROLES = {"user", "assistant"}
_MAX_CONTENT = 20000


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
                    id TEXT PRIMARY KEY
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
