"""FTS5-backed search logic."""

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
    sql = [
        "SELECT docs_fts.rowid AS doc_id,",
        f"       snippet(docs_fts, {_CONTENT_COLUMN}, '<mark>', '</mark>', '…', 30) AS snippet,",
        "       bm25(docs_fts) AS rank",
        "FROM docs_fts",
        "WHERE docs_fts MATCH ?",
    ]
    params: list[str | int] = [_quote_fts5_query(query)]

    if ids:
        placeholders = ", ".join("?" for _ in ids)
        sql.append(f"AND docs_fts.rowid IN ({placeholders})")
        params.extend(ids)

    sql.append("ORDER BY rank")
    sql.append("LIMIT ? OFFSET ?")
    params.extend([limit, offset])

    try:
        rows = conn.execute("\n".join(sql), params).fetchall()
    except sqlite3.OperationalError as exc:
        raise ValueError(f"invalid search query: {query!r}") from exc

    results = [
        SearchResultItem(doc_id=row["doc_id"], snippet=row["snippet"], rank=row["rank"])
        for row in rows
    ]
    return SearchResponse(results=results, limit=limit, offset=offset)
