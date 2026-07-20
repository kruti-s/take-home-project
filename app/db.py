"""SQLite connection management and schema bootstrap."""

import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
DEFAULT_DB_PATH = Path(__file__).parent.parent / "sandstone.db"


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open a SQLite connection to the document store.

    Args:
        db_path: Filesystem path to the SQLite database file. Defaults to
            `sandstone.db` in the project root.

    Returns:
        A `sqlite3.Connection` with foreign key enforcement enabled and
        `row_factory` set to `sqlite3.Row` so query results are accessible
        by column name.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create the docs, edits, and docs_fts tables if they don't exist.

    Args:
        conn: An open SQLite connection to initialize.
    """
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()
