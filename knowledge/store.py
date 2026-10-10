"""Bounded TXT/Markdown ingestion and parameterized SQLite FTS5 retrieval.

Only explicitly supplied files are indexed. Does not access the internet.
"""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re

from .db import connect

_ALLOWED_SUFFIXES = {".md", ".markdown", ".txt"}
_MAX_BYTES = 2 * 1024 * 1024
_CHUNK_WORDS = 220
_OVERLAP_WORDS = 35
_STOPWORDS = {
    "a", "about", "an", "and", "are", "as", "at", "be", "by", "can",
    "do", "does", "for", "from", "how", "i", "in", "is", "it", "its",
    "me", "my", "of", "on", "or", "our", "the", "their", "this", "to",
    "was", "were", "what", "when", "where", "which", "who", "why", "with",
}


@dataclass(frozen=True)
class IndexedDocument:
    document_id: int
    title: str
    chunk_count: int
    unchanged: bool


class SummaryLimitError(ValueError):
    """Indexed document exceeds the safe full-summary processing limit."""


# Lower than the ingestion limit on purpose: large uploads can still be searched.
MAX_SUMMARY_CHARACTERS = 48_000
MAX_SUMMARY_CHUNKS = 80


@dataclass(frozen=True)
class SummaryChunk:
    position: int
    body: str


@dataclass(frozen=True)
class SummaryDocument:
    document_id: int
    title: str
    chunks: tuple[SummaryChunk, ...]


@dataclass(frozen=True)
class SearchHit:
    document_id: int
    title: str
    chunk_id: int
    body: str
    score: float


def chunk_text(text: str, words_per_chunk: int = _CHUNK_WORDS,
               overlap: int = _OVERLAP_WORDS) -> list[str]:
    if words_per_chunk < 1 or overlap < 0 or overlap >= words_per_chunk:
        raise ValueError("Chunk overlap must be smaller than chunk size.")
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + words_per_chunk, len(words))
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start = end - overlap
    return chunks


def _match_expression(question: str) -> str:
    # Never pass raw user input into FTS5 MATCH syntax. Each word is quoted,
    # and all query operators are supplied here instead of by the user.
    words = re.findall(r"\w+", question, flags=re.UNICODE)
    tokens = []
    for word in words:
        normalized = word.casefold()
        if normalized in _STOPWORDS or len(word) > 48 or not normalized:
            continue
        if normalized not in tokens:
            tokens.append(normalized)
        if len(tokens) >= 12:
            break
    if not tokens:
        return ""
    return " OR ".join('"' + token + '"' for token in tokens)


class KnowledgeStore:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = db_path
        with connect(self.db_path) as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS knowledge_documents (
                    id INTEGER PRIMARY KEY,
                    path TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    digest TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    id INTEGER PRIMARY KEY,
                    document_id INTEGER NOT NULL
                        REFERENCES knowledge_documents(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL,
                    body TEXT NOT NULL,
                    UNIQUE(document_id, position)
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts
                    USING fts5(body, tokenize='unicode61');
            """)

    def ingest_file(self, filename: Path | str) -> IndexedDocument:
        requested = Path(filename).expanduser()
        if requested.is_symlink():
            raise ValueError("Symlink files are not supported for ingestion.")
        path = requested.resolve(strict=True)
        if not path.is_file():
            raise ValueError("Provide a regular file, not a directory.")
        if path.suffix.lower() not in _ALLOWED_SUFFIXES:
            raise ValueError("Only .txt, .md, and .markdown files are supported.")
        with path.open("rb") as stream:
            raw = stream.read(_MAX_BYTES + 1)
        if len(raw) > _MAX_BYTES:
            raise ValueError("Document exceeds the 2 MiB limit.")
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Document must be valid UTF-8 text.") from exc
        if "\x00" in text:
            raise ValueError("Binary or NUL-containing documents are not supported.")
        if not text.strip():
            raise ValueError("Cannot index an empty document.")

        digest = sha256(raw).hexdigest()
        chunks = chunk_text(text)
        with connect(self.db_path) as con:
            old = con.execute(
                "SELECT id, digest FROM knowledge_documents WHERE path=?",
                (str(path),),
            ).fetchone()
            if old and old["digest"] == digest:
                count = con.execute(
                    "SELECT COUNT(*) FROM knowledge_chunks WHERE document_id=?",
                    (old["id"],),
                ).fetchone()[0]
                return IndexedDocument(old["id"], path.name, count, True)

            if old:
                doc_id = old["id"]
                ids = con.execute(
                    "SELECT id FROM knowledge_chunks WHERE document_id=?",
                    (doc_id,),
                ).fetchall()
                for record in ids:
                    con.execute("DELETE FROM knowledge_fts WHERE rowid=?", (record["id"],))
                con.execute("DELETE FROM knowledge_chunks WHERE document_id=?", (doc_id,))
                con.execute(
                    "UPDATE knowledge_documents SET digest=?, title=? WHERE id=?",
                    (digest, path.name, doc_id),
                )
            else:
                cursor = con.execute(
                    "INSERT INTO knowledge_documents(path,title,digest) VALUES(?,?,?)",
                    (str(path), path.name, digest),
                )
                doc_id = cursor.lastrowid

            for position, body in enumerate(chunks):
                cursor = con.execute(
                    "INSERT INTO knowledge_chunks(document_id,position,body) "
                    "VALUES(?,?,?)", (doc_id, position, body),
                )
                con.execute(
                    "INSERT INTO knowledge_fts(rowid,body) VALUES(?,?)",
                    (cursor.lastrowid, body),
                )
            return IndexedDocument(doc_id, path.name, len(chunks), False)

    def search(self, question: str, limit: int = 5) -> list[SearchHit]:
        if limit < 1 or limit > 20:
            raise ValueError("Search limit must be between 1 and 20.")
        expression = _match_expression(question)
        if not expression:
            return []
        with connect(self.db_path) as con:
            rows = con.execute(
                """SELECT d.id AS document_id, d.title, c.id AS chunk_id,
                          c.body, bm25(knowledge_fts) AS rank
                   FROM knowledge_fts
                   JOIN knowledge_chunks AS c ON c.id=knowledge_fts.rowid
                   JOIN knowledge_documents AS d ON d.id=c.document_id
                   WHERE knowledge_fts MATCH ?
                   ORDER BY rank ASC, c.id ASC LIMIT ?""",
                (expression, limit),
            ).fetchall()
        return [
            SearchHit(r["document_id"], r["title"], r["chunk_id"],
                      r["body"], float(r["rank"]))
            for r in rows
        ]

    def list_documents(self) -> list[IndexedDocument]:
        with connect(self.db_path) as con:
            rows = con.execute(
                """SELECT d.id, d.title, COUNT(c.id) AS chunks
                   FROM knowledge_documents d LEFT JOIN knowledge_chunks c
                     ON d.id=c.document_id
                   GROUP BY d.id ORDER BY d.id"""
            ).fetchall()
        return [IndexedDocument(r["id"], r["title"], r["chunks"], False)
                for r in rows]

    def read_document_for_summary(self, document_id: int) -> SummaryDocument | None:
        """Return every indexed chunk in order, or reject excessive input.

        Uses indexed content only; never reads arbitrary paths from the DB.
        """
        if document_id <= 0:
            return None
        with connect(self.db_path) as con:
            row = con.execute(
                """SELECT d.id, d.title, COUNT(c.id) AS chunks,
                          COALESCE(SUM(LENGTH(c.body)), 0) AS characters
                   FROM knowledge_documents d
                   LEFT JOIN knowledge_chunks c ON c.document_id=d.id
                   WHERE d.id=? GROUP BY d.id""", (document_id,)
            ).fetchone()
            if row is None:
                return None
            if row["chunks"] > MAX_SUMMARY_CHUNKS or row["characters"] > MAX_SUMMARY_CHARACTERS:
                raise SummaryLimitError(
                    "Document is too large for full summarization (limit: "
                    f"{MAX_SUMMARY_CHARACTERS} indexed characters and "
                    f"{MAX_SUMMARY_CHUNKS} chunks). Search remains available."
                )
            chunks = con.execute(
                """SELECT position, body FROM knowledge_chunks
                   WHERE document_id=? ORDER BY position ASC""", (document_id,)
            ).fetchall()
        return SummaryDocument(document_id, row["title"], tuple(
            SummaryChunk(chunk["position"], chunk["body"]) for chunk in chunks
        ))

    def delete_document(self, document_id: int) -> bool:
        with connect(self.db_path) as con:
            row = con.execute(
                "SELECT id FROM knowledge_documents WHERE id=?", (document_id,)
            ).fetchone()
            if row is None:
                return False
            ids = con.execute(
                "SELECT id FROM knowledge_chunks WHERE document_id=?", (document_id,)
            ).fetchall()
            for r in ids:
                con.execute("DELETE FROM knowledge_fts WHERE rowid=?", (r["id"],))
            con.execute("DELETE FROM knowledge_documents WHERE id=?", (document_id,))
            return True
