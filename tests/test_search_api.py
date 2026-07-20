"""Tests for GET /documents/search."""

import pytest


def _create(client, title, content):
    resp = client.post("/documents", json={"title": title, "content": content})
    assert resp.status_code == 201
    return resp.json()


def test_search_all_documents(client):
    _create(client, "Lease", "this is a rental contract for an apartment")
    _create(client, "Recipe", "mix flour, sugar, and eggs")
    resp = client.get("/documents/search", params={"q": "contract"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["doc_id"] == 1


def test_search_all_documents_pagination(client):
    for i in range(5):
        _create(client, f"Doc {i}", "contract terms and conditions")
    resp = client.get("/documents/search", params={"q": "contract", "limit": 2, "offset": 0})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) == 2
    assert body["limit"] == 2
    assert body["offset"] == 0


def test_search_matches_on_title(client):
    doc = _create(client, "Master Service Agreement", "no matching keyword in body")
    resp = client.get("/documents/search", params={"q": "Master"})
    assert resp.status_code == 200
    doc_ids = [r["doc_id"] for r in resp.json()["results"]]
    assert doc["doc_id"] in doc_ids


def test_search_snippet_uses_mark_tags(client):
    _create(client, "Lease", "this is a rental contract for an apartment")
    resp = client.get("/documents/search", params={"q": "contract"})
    snippet = resp.json()["results"][0]["snippet"]
    assert "<mark>contract</mark>" in snippet


def test_search_orders_by_rank(client):
    _create(client, "A", "contract contract contract about apples")
    _create(client, "B", "a single mention of contract")
    resp = client.get("/documents/search", params={"q": "contract"})
    doc_ids = [r["doc_id"] for r in resp.json()["results"]]
    assert doc_ids == [1, 2]


def test_search_with_ids_filters_to_specified_documents(client):
    doc_a = _create(client, "A", "a contract about apples")
    _create(client, "B", "a contract about bananas")
    resp = client.get(
        "/documents/search", params={"q": "contract", "ids": [doc_a["doc_id"]]}
    )
    assert resp.status_code == 200
    doc_ids = [r["doc_id"] for r in resp.json()["results"]]
    assert doc_ids == [doc_a["doc_id"]]


def test_search_with_ids_excludes_unlisted_matches(client):
    doc_a = _create(client, "A", "a contract about apples")
    doc_b = _create(client, "B", "a contract about bananas")
    resp = client.get(
        "/documents/search", params={"q": "contract", "ids": [doc_a["doc_id"]]}
    )
    doc_ids = [r["doc_id"] for r in resp.json()["results"]]
    assert doc_b["doc_id"] not in doc_ids


def test_search_with_ids_multiple_values(client):
    doc_a = _create(client, "A", "a contract about apples")
    doc_b = _create(client, "B", "a contract about bananas")
    _create(client, "C", "a contract about cherries")
    resp = client.get(
        "/documents/search",
        params={"q": "contract", "ids": [doc_a["doc_id"], doc_b["doc_id"]]},
    )
    doc_ids = {r["doc_id"] for r in resp.json()["results"]}
    assert doc_ids == {doc_a["doc_id"], doc_b["doc_id"]}


def test_search_with_ids_no_match_in_scope(client):
    doc_a = _create(client, "A", "a contract about apples")
    _create(client, "B", "a contract about bananas that also mentions apples")
    resp = client.get(
        "/documents/search", params={"q": "bananas", "ids": [doc_a["doc_id"]]}
    )
    assert resp.status_code == 200
    assert resp.json()["results"] == []


@pytest.mark.parametrize(
    "query",
    [
        '"',
        "*",
        "-",
        "^",
        'foo"bar',
        "foo OR bar",
        "foo AND NOT bar",
        "col:val",
        "NEAR(a b)",
        "'; DROP TABLE docs; --",
        "",
    ],
)
def test_search_special_characters_never_500(client, query):
    _create(client, "Doc", "some ordinary content")
    resp = client.get("/documents/search", params={"q": query})
    assert resp.status_code in (200, 400)
