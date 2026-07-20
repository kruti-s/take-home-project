"""Tests for /documents/search endpoints."""


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


def test_search_single_document(client):
    doc_a = _create(client, "A", "a contract about apples")
    _create(client, "B", "a contract about bananas")
    resp = client.get(f"/documents/{doc_a['doc_id']}/search", params={"q": "apples"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["doc_id"] == doc_a["doc_id"]


def test_search_single_document_no_match(client):
    doc_a = _create(client, "A", "a contract about apples")
    resp = client.get(f"/documents/{doc_a['doc_id']}/search", params={"q": "bananas"})
    assert resp.status_code == 200
    assert resp.json()["results"] == []


def test_search_single_document_not_found(client):
    resp = client.get("/documents/999/search", params={"q": "anything"})
    assert resp.status_code == 404


def test_search_matches_on_title(client):
    doc = _create(client, "Master Service Agreement", "no matching keyword in body")
    resp = client.get("/documents/search", params={"q": "Master"})
    assert resp.status_code == 200
    doc_ids = [r["doc_id"] for r in resp.json()["results"]]
    assert doc["doc_id"] in doc_ids
