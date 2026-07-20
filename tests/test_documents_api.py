"""Tests for /documents CRUD and patch endpoints."""


def _create(client, title="Contract", content="the quick brown fox"):
    resp = client.post("/documents", json={"title": title, "content": content})
    assert resp.status_code == 201
    return resp.json()


def test_create_document(client):
    body = _create(client, title="My Doc", content="hello world")
    assert body["title"] == "My Doc"
    assert body["content"] == "hello world"
    assert isinstance(body["doc_id"], int)


def test_list_documents(client):
    _create(client, title="A", content="one")
    _create(client, title="B", content="two")
    resp = client.get("/documents")
    assert resp.status_code == 200
    titles = [d["title"] for d in resp.json()["documents"]]
    assert titles == ["A", "B"]


def test_get_document(client):
    created = _create(client)
    resp = client.get(f"/documents/{created['doc_id']}")
    assert resp.status_code == 200
    assert resp.json() == created


def test_get_document_not_found(client):
    resp = client.get("/documents/999")
    assert resp.status_code == 404


def test_delete_document(client):
    created = _create(client)
    resp = client.delete(f"/documents/{created['doc_id']}")
    assert resp.status_code == 204
    assert client.get(f"/documents/{created['doc_id']}").status_code == 404


def test_delete_document_not_found(client):
    resp = client.delete("/documents/999")
    assert resp.status_code == 404


def test_delete_document_excluded_from_list(client):
    kept = _create(client, title="Kept", content="one")
    deleted = _create(client, title="Deleted", content="two")
    client.delete(f"/documents/{deleted['doc_id']}")
    resp = client.get("/documents")
    assert resp.status_code == 200
    doc_ids = [d["doc_id"] for d in resp.json()["documents"]]
    assert doc_ids == [kept["doc_id"]]


def test_delete_document_excluded_from_search(client):
    doc = _create(client, title="Lease", content="a rental contract for an apartment")
    client.delete(f"/documents/{doc['doc_id']}")
    resp = client.get("/documents/search", params={"q": "contract"})
    assert resp.status_code == 200
    assert resp.json()["results"] == []


def test_delete_document_single_search_returns_404(client):
    doc = _create(client, title="Lease", content="a rental contract")
    client.delete(f"/documents/{doc['doc_id']}")
    resp = client.get(f"/documents/{doc['doc_id']}/search", params={"q": "contract"})
    assert resp.status_code == 404


def test_delete_document_twice_returns_404(client):
    created = _create(client)
    assert client.delete(f"/documents/{created['doc_id']}").status_code == 204
    assert client.delete(f"/documents/{created['doc_id']}").status_code == 404


def test_delete_document_preserves_edit_history(client, conn):
    created = _create(client, content="the quick brown fox")
    doc_id = created["doc_id"]
    client.patch(
        f"/documents/{doc_id}",
        json={
            "changes": [
                {"operation": "delete", "range": {"start": 0, "end": 4}, "new_text": ""}
            ]
        },
    )
    client.delete(f"/documents/{doc_id}")

    row = conn.execute(
        "SELECT deleted_at, content FROM docs WHERE doc_id = ?", (doc_id,)
    ).fetchone()
    assert row["deleted_at"] is not None
    assert row["content"] == "quick brown fox"

    edits = conn.execute(
        "SELECT change_id FROM edits WHERE doc_id = ? ORDER BY change_id", (doc_id,)
    ).fetchall()
    assert [r["change_id"] for r in edits] == [1, 2]


def test_patch_document_text_replace(client):
    created = _create(client, content="the quick brown fox")
    resp = client.patch(
        f"/documents/{created['doc_id']}",
        json={
            "changes": [
                {
                    "operation": "replace",
                    "target": {"text": "quick", "occurrence": 1},
                    "new_text": "slow",
                }
            ]
        },
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "the slow brown fox"


def test_patch_document_range_replace(client):
    created = _create(client, content="the quick brown fox")
    resp = client.patch(
        f"/documents/{created['doc_id']}",
        json={
            "changes": [
                {"operation": "replace", "range": {"start": 4, "end": 9}, "new_text": "slow"}
            ]
        },
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "the slow brown fox"


def test_patch_document_insert(client):
    created = _create(client, content="the fox")
    resp = client.patch(
        f"/documents/{created['doc_id']}",
        json={
            "changes": [
                {"operation": "insert", "range": {"start": 4, "end": 4}, "new_text": "quick "}
            ]
        },
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "the quick fox"


def test_patch_document_delete(client):
    created = _create(client, content="the quick brown fox")
    resp = client.patch(
        f"/documents/{created['doc_id']}",
        json={"changes": [{"operation": "delete", "range": {"start": 3, "end": 9}}]},
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "the brown fox"


def test_patch_document_multiple_changes_applied_in_order(client):
    created = _create(client, content="the quick brown fox")
    resp = client.patch(
        f"/documents/{created['doc_id']}",
        json={
            "changes": [
                {
                    "operation": "replace",
                    "target": {"text": "quick", "occurrence": 1},
                    "new_text": "slow",
                },
                {
                    "operation": "delete",
                    "target": {"text": "brown ", "occurrence": 1},
                },
            ]
        },
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "the slow fox"


def test_patch_document_bad_target_returns_400(client):
    created = _create(client, content="the quick brown fox")
    resp = client.patch(
        f"/documents/{created['doc_id']}",
        json={
            "changes": [
                {
                    "operation": "replace",
                    "target": {"text": "nonexistent", "occurrence": 1},
                    "new_text": "x",
                }
            ]
        },
    )
    assert resp.status_code == 400


def test_patch_document_requires_exactly_one_locator(client):
    created = _create(client, content="the quick brown fox")
    resp = client.patch(
        f"/documents/{created['doc_id']}",
        json={"changes": [{"operation": "delete", "new_text": ""}]},
    )
    assert resp.status_code == 422


def test_patch_document_rejects_both_locators(client):
    created = _create(client, content="the quick brown fox")
    resp = client.patch(
        f"/documents/{created['doc_id']}",
        json={
            "changes": [
                {
                    "operation": "replace",
                    "target": {"text": "quick", "occurrence": 1},
                    "range": {"start": 0, "end": 3},
                    "new_text": "slow",
                }
            ]
        },
    )
    assert resp.status_code == 422


def test_patch_document_insert_requires_start_equals_end(client):
    created = _create(client, content="the fox")
    resp = client.patch(
        f"/documents/{created['doc_id']}",
        json={
            "changes": [
                {"operation": "insert", "range": {"start": 4, "end": 5}, "new_text": "quick "}
            ]
        },
    )
    assert resp.status_code == 422


def test_patch_document_delete_rejects_nonempty_new_text(client):
    created = _create(client, content="the quick brown fox")
    resp = client.patch(
        f"/documents/{created['doc_id']}",
        json={
            "changes": [
                {"operation": "delete", "range": {"start": 3, "end": 9}, "new_text": "oops"}
            ]
        },
    )
    assert resp.status_code == 422


def test_patch_document_replace_rejects_empty_new_text(client):
    created = _create(client, content="the quick brown fox")
    resp = client.patch(
        f"/documents/{created['doc_id']}",
        json={
            "changes": [
                {"operation": "replace", "range": {"start": 4, "end": 9}, "new_text": ""}
            ]
        },
    )
    assert resp.status_code == 422


def test_patch_document_not_found(client):
    resp = client.patch(
        "/documents/999",
        json={"changes": [{"operation": "delete", "range": {"start": 0, "end": 1}}]},
    )
    assert resp.status_code == 404


def test_patch_document_records_edit_history(client, conn):
    created = _create(client, content="the quick brown fox")
    doc_id = created["doc_id"]
    client.patch(
        f"/documents/{doc_id}",
        json={"changes": [{"operation": "delete", "range": {"start": 0, "end": 4}}]},
    )
    client.patch(
        f"/documents/{doc_id}",
        json={"changes": [{"operation": "delete", "range": {"start": 0, "end": 6}}]},
    )
    rows = conn.execute(
        "SELECT change_id, current_text FROM edits WHERE doc_id = ? ORDER BY change_id",
        (doc_id,),
    ).fetchall()
    assert [r["change_id"] for r in rows] == [1, 2, 3]
    assert rows[0]["current_text"] == "the quick brown fox"
    assert rows[1]["current_text"] == "quick brown fox"
    assert rows[2]["current_text"] == "brown fox"
