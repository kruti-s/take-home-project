"""Unit tests for search_service.search_document_ids and its reuse by bulk-changes.

These exercise the plain in-process function directly (via the `conn`
fixture), confirming it returns the correct id set — not snippets, ranks,
or a paginated response — and that bulk-changes combines it with an `ids`
filter by intersection.
"""

from app.services import document_service, search_service


def _create(conn, title, content):
    return document_service.create_document(conn, title, content)


def test_search_document_ids_returns_all_matching_ids(conn):
    a = _create(conn, "A", "a rental contract about apples")
    b = _create(conn, "B", "a rental contract about bananas")
    _create(conn, "C", "mix flour, sugar, and eggs")

    ids = search_service.search_document_ids(conn, "contract")

    assert isinstance(ids, list)
    assert all(isinstance(i, int) for i in ids)
    assert set(ids) == {a.doc_id, b.doc_id}


def test_search_document_ids_not_paginated(conn):
    # search_documents defaults to a page of results; search_document_ids
    # must return EVERY match regardless of any page size.
    created = [_create(conn, f"Doc {i}", "contract terms").doc_id for i in range(25)]

    ids = search_service.search_document_ids(conn, "contract")

    assert set(ids) == set(created)
    assert len(ids) == 25


def test_search_document_ids_no_match_returns_empty(conn):
    _create(conn, "A", "a rental contract")
    assert search_service.search_document_ids(conn, "nonexistentxyz") == []


def test_search_document_ids_scoped_by_ids_is_intersection(conn):
    a = _create(conn, "A", "a contract about apples")
    b = _create(conn, "B", "a contract about bananas")
    c = _create(conn, "C", "a contract about cherries")

    # query matches {a, b, c}; ids scope is {b, c, <nonexistent>} ->
    # intersection is {b, c}.
    ids = search_service.search_document_ids(conn, "contract", ids=[b.doc_id, c.doc_id, 9999])

    assert set(ids) == {b.doc_id, c.doc_id}
    assert a.doc_id not in ids


def test_search_document_ids_shares_query_sanitization(conn):
    _create(conn, "A", "some ordinary content")
    # A bare FTS5 column-filter operator (`col:val`) would be a syntax error
    # against the raw MATCH grammar; because search_document_ids goes through
    # the same _quote_fts5_query sanitization as the endpoint, it's treated as
    # a literal phrase and simply matches nothing instead of raising. This
    # confirms the shared sanitization path is in effect (no separate query).
    assert search_service.search_document_ids(conn, "col:val") == []


def test_bulk_changes_intersects_query_with_ids(client):
    # End-to-end through the HTTP handler: filter provides BOTH query and
    # ids, and bulk-changes must apply only to their intersection.
    def create(title, content):
        resp = client.post("/documents", json={"title": title, "content": content})
        assert resp.status_code == 201
        return resp.json()

    a = create("A", "a rental contract about apples")
    b = create("B", "a rental contract about bananas")
    c = create("C", "a rental contract about cherries")

    resp = client.post(
        "/documents/bulk-changes",
        json={
            # query matches all three; ids restricts to {a, b} ->
            # intersection {a, b}.
            "filter": {"query": "contract", "ids": [a["doc_id"], b["doc_id"]]},
            "changes": [
                {
                    "operation": "replace",
                    "target": {"text": "rental", "occurrence": 1},
                    "new_text": "commercial",
                }
            ],
        },
    )
    assert resp.status_code == 200
    result_ids = {r["id"] for r in resp.json()["results"]}
    assert result_ids == {a["doc_id"], b["doc_id"]}

    assert "commercial" in client.get(f"/documents/{a['doc_id']}").json()["content"]
    assert "commercial" in client.get(f"/documents/{b['doc_id']}").json()["content"]
    # c matched the query but was outside the ids scope -> untouched.
    assert "commercial" not in client.get(f"/documents/{c['doc_id']}").json()["content"]
