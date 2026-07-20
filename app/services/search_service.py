"""FTS5-backed search logic.

`_run_match_query` is the single place the FTS5 MATCH query, its parameter
binding, its query sanitization, and its error handling live. Both the
public entry points build on it and differ only in their SELECT projection
and (for the ranked HTTP response) their ORDER BY / LIMIT / OFFSET tail:

- `search_document_ids` — every matching id, no snippet/rank/pagination;
  used in-process by bulk-changes to resolve a target set.
- `search_documents` — ranked, snippeted, paginated response for the
  GET /documents/search endpoint.
"""

import sqlite3

from app.models import SearchResponse, SearchResultItem

# docs_fts columns: 0 = title, 1 = content. Snippets are drawn from
# content (column 1) — MATCH itself still searches both columns.
_CONTENT_COLUMN = 1


def _quote_fts5_query(query: str) -> str:
    """Turn raw user input into a safe FTS5 phrase-query literal.

    FTS5's MATCH syntax treats `"`, `*`, `-`, `^`, `:`, and bareword
    operators (AND/OR/NOT/NEAR) specially. Wrapping the whole input in
    double quotes forces it to be parsed as a single literal phrase, so
    none of those characters are interpreted as query syntax — the query
    is bound as a parameter (never string-concatenated into SQL), and this
    quoting neutralizes FTS5's *own* query-language operators within that
    parameter's value.

    Args:
        query: The raw, untrusted search string from the client.

    Returns:
        `query`, with any embedded `"` doubled (FTS5's escape for a
        literal quote) and the whole string wrapped in `"..."`.
    """
    return '"' + query.replace('"', '""') + '"'


def _run_match_query(
    conn: sqlite3.Connection,
    select_clause: str,
    query: str,
    ids: list[int] | None,
    tail_sql: str = "",
    tail_params: list[int] | None = None,
) -> list[sqlite3.Row]:
    """Run the shared FTS5 MATCH query and return the raw rows.

    This is the one place the MATCH clause, its parameter binding, the
    optional `ids` scoping, the query sanitization, and the malformed-query
    error handling are defined. Callers vary only `select_clause` (the
    projection) and the optional `tail_sql`/`tail_params` (e.g. ORDER BY /
    LIMIT / OFFSET) — the matching logic itself is never duplicated.

    Args:
        conn: Open SQLite connection.
        select_clause: The columns to select (everything between SELECT and
            FROM), e.g. "docs_fts.rowid AS doc_id".
        query: Raw, untrusted search string; sanitized here before binding.
        ids: If given, restrict matches to these document ids (an
            intersection of the MATCH results with `ids`).
        tail_sql: Optional trailing clause appended after the WHERE, e.g.
            "ORDER BY rank\\nLIMIT ? OFFSET ?".
        tail_params: Parameters for placeholders in `tail_sql`, in order.

    Returns:
        The raw result rows.

    Raises:
        ValueError: If `query` can't be parsed as an FTS5 query.
    """
    sql = [
        f"SELECT {select_clause}",
        "FROM docs_fts",
        "WHERE docs_fts MATCH ?",
    ]
    params: list[str | int] = [_quote_fts5_query(query)]

    if ids:
        placeholders = ", ".join("?" for _ in ids)
        sql.append(f"AND docs_fts.rowid IN ({placeholders})")
        params.extend(ids)

    if tail_sql:
        sql.append(tail_sql)
        params.extend(tail_params or [])

    try:
        return conn.execute("\n".join(sql), params).fetchall()
    except sqlite3.OperationalError as exc:
        raise ValueError(f"invalid search query: {query!r}") from exc


def search_document_ids(
    conn: sqlite3.Connection, query: str, ids: list[int] | None = None
) -> list[int]:
    """Return ALL matching document ids (no pagination, no snippet, no rank).

    Used internally — as a plain in-process function call, never over
    HTTP — by bulk-changes to resolve a target set. Shares the exact same
    MATCH query, parameter binding, sanitization, and error handling as the
    search endpoint (see `_run_match_query`).

    Args:
        conn: Open SQLite connection.
        query: Raw search string to look for.
        ids: If given, restrict matches to these document ids — the result
            is the intersection of the query matches with `ids`.

    Returns:
        Every matching document id, ordered best-match-first (same
        relevance order the search endpoint uses).

    Raises:
        ValueError: If `query` can't be parsed as an FTS5 query.
    """
    rows = _run_match_query(
        conn,
        "docs_fts.rowid AS doc_id",
        query,
        ids,
        tail_sql="ORDER BY bm25(docs_fts)",
    )
    return [row["doc_id"] for row in rows]


def search_documents(
    conn: sqlite3.Connection,
    query: str,
    limit: int,
    offset: int,
    ids: list[int] | None = None,
) -> SearchResponse:
    """Full-text search across documents, optionally restricted to specific ids.

    Args:
        conn: Open SQLite connection.
        query: Raw search string to look for.
        limit: Maximum number of results to return.
        offset: Number of results to skip, for pagination.
        ids: If given, only search within these document ids.

    Returns:
        Matching documents ranked by relevance (best first).

    Raises:
        ValueError: If `query` can't be parsed as an FTS5 query.
    """
    rows = _run_match_query(
        conn,
        "docs_fts.rowid AS doc_id, "
        f"snippet(docs_fts, {_CONTENT_COLUMN}, '<mark>', '</mark>', '…', 30) AS snippet, "
        "bm25(docs_fts) AS rank",
        query,
        ids,
        tail_sql="ORDER BY rank\nLIMIT ? OFFSET ?",
        tail_params=[limit, offset],
    )
    results = [
        SearchResultItem(doc_id=row["doc_id"], snippet=row["snippet"], rank=row["rank"])
        for row in rows
    ]
    return SearchResponse(results=results, limit=limit, offset=offset)
