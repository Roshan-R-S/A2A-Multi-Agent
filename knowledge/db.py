"""Connection helpers for the opt-in local SQLite knowledge/memory store."""

from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
from typing import Iterator

ROOT_DIR = Path(__file__).resolve().parents[1]


def default_db_path() -> Path:
    base = os.environ.get("A2A_DATA_DIR", "").strip()
    directory = Path(base).expanduser() if base else ROOT_DIR / ".a2a_data"
    return directory / "assistant.sqlite3"


@contextmanager
def connect(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    path = Path(db_path) if db_path is not None else default_db_path()
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), timeout=5.0)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 5000")
    try:
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()
