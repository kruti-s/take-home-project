"""FTS5-backed search logic. Not yet implemented."""

import sqlite3

from app.models import SearchResponse


def search_all(
    conn: sqlite3.Connection, query: str, limit: int, offset: int
) -> SearchResponse:
    """Full-text search across all documents.

    Args:
        conn: Open SQLite connection.
        query: FTS5 match expression to search for.
        limit: Maximum number of results to return.
        offset: Number of results to skip, for pagination.

    Returns:
        Matching documents ranked by relevance.
    """
    raise NotImplementedError


def search_document(
    conn: sqlite3.Connection, doc_id: int, query: str, limit: int, offset: int
) -> SearchResponse:
    """Full-text search restricted to a single document.

    Args:
        conn: Open SQLite connection.
        doc_id: Identifier of the document to search within.
        query: FTS5 match expression to search for.
        limit: Maximum number of results to return.
        offset: Number of results to skip, for pagination.

    Returns:
        Matching passages within the document, ranked by relevance.

    Raises:
        KeyError: If no document with `doc_id` exists.
    """
    raise NotImplementedError
