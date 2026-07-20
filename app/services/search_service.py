"""FTS5-backed search logic."""

import sqlite3

from app.models import SearchResponse, SearchResultItem

# docs_fts columns: 0 = title, 1 = content. MATCH with no column filter
# searches both; snippet() targets content (column 1).
_SEARCH_ALL_SQL = """
    SELECT docs_fts.rowid AS doc_id,
           snippet(docs_fts, 1, '[', ']', '...', 8) AS snippet,
           bm25(docs_fts) AS rank
    FROM docs_fts
    WHERE docs_fts MATCH ?
    ORDER BY rank
    LIMIT ? OFFSET ?
"""

_SEARCH_ONE_SQL = """
    SELECT docs_fts.rowid AS doc_id,
           snippet(docs_fts, 1, '[', ']', '...', 8) AS snippet,
           bm25(docs_fts) AS rank
    FROM docs_fts
    WHERE docs_fts MATCH ? AND docs_fts.rowid = ?
    ORDER BY rank
    LIMIT ? OFFSET ?
"""


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
        Matching documents ranked by relevance (best first).
    """
    rows = conn.execute(_SEARCH_ALL_SQL, (query, limit, offset)).fetchall()
    results = [
        SearchResultItem(doc_id=row["doc_id"], snippet=row["snippet"], rank=row["rank"])
        for row in rows
    ]
    return SearchResponse(results=results, limit=limit, offset=offset)


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
        KeyError: If no live (non-deleted) document with `doc_id` exists.
    """
    exists = conn.execute(
        "SELECT 1 FROM docs WHERE doc_id = ? AND deleted_at IS NULL", (doc_id,)
    ).fetchone()
    if exists is None:
        raise KeyError(f"no document with doc_id={doc_id}")

    rows = conn.execute(_SEARCH_ONE_SQL, (query, doc_id, limit, offset)).fetchall()
    results = [
        SearchResultItem(doc_id=row["doc_id"], snippet=row["snippet"], rank=row["rank"])
        for row in rows
    ]
    return SearchResponse(results=results, limit=limit, offset=offset)
