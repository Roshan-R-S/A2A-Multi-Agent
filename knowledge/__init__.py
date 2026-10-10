"""Local document indexing and retrieval (SQLite FTS5, no cloud dependencies)."""

from .store import KnowledgeStore, SearchHit, IndexedDocument

__all__ = ["KnowledgeStore", "SearchHit", "IndexedDocument"]
