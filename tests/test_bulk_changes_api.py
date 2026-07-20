"""Tests for POST /documents/bulk-changes."""


def _create(client, title="Contract", content="the quick brown fox"):
    resp = client.post("/documents", json={"title": title, "content": content})
    assert resp.status_code == 201
    return resp.json()


def _replace_change(text, replacement, occurrence=1):
    return {
        "operation": "replace",
        "target": {"text": text, "occurrence": occurrence},
        "new_text": replacement,
    }


def test_filter_by_ids_applies_to_exactly_those_documents(client):
    a = _create(client, "A", "the quick brown fox")
    b = _create(client, "B", "the quick brown fox")
    c = _create(client, "C", "the quick brown fox")

    resp = client.post(
        "/documents/bulk-changes",
        json={
            "filter": {"ids": [a["doc_id"], b["doc_id"]]},
            "changes": [_replace_change("quick", "slow")],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    result_ids = {r["id"] for r in body["results"]}
    assert result_ids == {a["doc_id"], b["doc_id"]}

    assert client.get(f"/documents/{a['doc_id']}").json()["content"] == "the slow brown fox"
    assert client.get(f"/documents/{b['doc_id']}").json()["content"] == "the slow brown fox"
    assert client.get(f"/documents/{c['doc_id']}").json()["content"] == "the quick brown fox"


def test_bulk_result_returns_before_and_after_content(client):
    # each ok result carries old/new content so the client renders a precise
    # (word-level) diff — replacing exactly the target, nothing more.
    doc = _create(client, "A", "the quick brown fox")
    resp = client.post(
        "/documents/bulk-changes",
        json={
            "filter": {"ids": [doc["doc_id"]]},
            "changes": [_replace_change("quick", "slow")],
        },
    )
    r = resp.json()["results"][0]
    assert r["old_content"] == "the quick brown fox"
    assert r["new_content"] == "the slow brown fox"


def test_bulk_replace_all_occurrences_in_one_call(client):
    # occurrence "all" is a single change the backend expands per document —
    # no per-document orchestration, and documents with different match counts
    # each get all of theirs replaced.
    a = _create(client, "A", "cat cat cat")
    b = _create(client, "B", "cat cat")
    resp = client.post(
        "/documents/bulk-changes",
        json={
            "filter": {"ids": [a["doc_id"], b["doc_id"]]},
            "changes": [
                {"operation": "replace", "target": {"text": "cat", "occurrence": "all"}, "new_text": "dog"}
            ],
        },
    )
    assert resp.status_code == 200
    assert client.get(f"/documents/{a['doc_id']}").json()["content"] == "dog dog dog"
    assert client.get(f"/documents/{b['doc_id']}").json()["content"] == "dog dog"


def test_filter_by_query_resolves_via_search_and_applies_to_matches(client):
    a = _create(client, "Lease", "a rental contract about apples")
    b = _create(client, "Sublease", "a rental contract about bananas")
    _create(client, "Recipe", "mix flour, sugar, and eggs")

    resp = client.post(
        "/documents/bulk-changes",
        json={
            "filter": {"query": "contract"},
            "changes": [_replace_change("rental", "commercial")],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    result_ids = {r["id"] for r in body["results"]}
    assert result_ids == {a["doc_id"], b["doc_id"]}
    assert all(r["status"] == "ok" for r in body["results"])

    assert "commercial" in client.get(f"/documents/{a['doc_id']}").json()["content"]
    assert "commercial" in client.get(f"/documents/{b['doc_id']}").json()["content"]


def test_filter_with_ids_and_query_scopes_search_to_ids(client):
    a = _create(client, "Lease", "a rental contract about apples")
    b = _create(client, "Sublease", "a rental contract about bananas")

    resp = client.post(
        "/documents/bulk-changes",
        json={
            "filter": {"ids": [a["doc_id"]], "query": "contract"},
            "changes": [_replace_change("rental", "commercial")],
        },
    )
    assert resp.status_code == 200
    result_ids = {r["id"] for r in resp.json()["results"]}
    assert result_ids == {a["doc_id"]}

    assert "commercial" in client.get(f"/documents/{a['doc_id']}").json()["content"]
    assert "commercial" not in client.get(f"/documents/{b['doc_id']}").json()["content"]


def test_filter_with_ids_and_query_no_match_within_scope(client):
    a = _create(client, "Lease", "a rental contract about apples")
    _create(client, "Sublease", "a rental contract about bananas")

    resp = client.post(
        "/documents/bulk-changes",
        json={
            "filter": {"ids": [a["doc_id"]], "query": "bananas"},
            "changes": [_replace_change("rental", "commercial")],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["results"] == []


def test_missing_filter_returns_400(client):
    resp = client.post(
        "/documents/bulk-changes",
        json={"filter": {}, "changes": [_replace_change("quick", "slow")]},
    )
    assert resp.status_code == 400


def test_empty_ids_list_returns_400(client):
    resp = client.post(
        "/documents/bulk-changes",
        json={"filter": {"ids": []}, "changes": [_replace_change("quick", "slow")]},
    )
    assert resp.status_code == 400


def test_empty_query_returns_400(client):
    resp = client.post(
        "/documents/bulk-changes",
        json={"filter": {"query": ""}, "changes": [_replace_change("quick", "slow")]},
    )
    assert resp.status_code == 400


def test_bulk_insert_with_target_rejected(client):
    # insert is position-only; an occurrence-based target is a 422 for
    # bulk-changes just as it is for a single-document PATCH.
    doc = _create(client, "A", "the quick fox")
    resp = client.post(
        "/documents/bulk-changes",
        json={
            "filter": {"ids": [doc["doc_id"]]},
            "changes": [
                {
                    "operation": "insert",
                    "target": {"text": "quick", "occurrence": 1},
                    "new_text": "very ",
                }
            ],
        },
    )
    assert resp.status_code == 422


def test_query_matching_nothing_returns_empty_results_not_400(client):
    _create(client, "Doc", "nothing relevant here")
    resp = client.post(
        "/documents/bulk-changes",
        json={
            "filter": {"query": "nonexistentxyz"},
            "changes": [_replace_change("quick", "slow")],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["results"] == []


def test_missing_target_text_skips_that_doc_others_still_succeed(client):
    # A document that doesn't contain the edit target is "skipped" (nothing to
    # change there), not "error" — the batch still applies to the others. This
    # is what makes a broad filter query usable: FTS5 matches case-
    # insensitively/by token, so it selects docs that don't contain the exact
    # find text, and those must not show up as failures.
    ok_doc = _create(client, "OK", "the quick brown fox")
    skip_doc = _create(client, "Skip", "no matching phrase here")

    resp = client.post(
        "/documents/bulk-changes",
        json={
            "filter": {"ids": [ok_doc["doc_id"], skip_doc["doc_id"]]},
            "changes": [_replace_change("quick", "slow")],
        },
    )
    assert resp.status_code == 200
    results = {r["id"]: r for r in resp.json()["results"]}

    assert results[ok_doc["doc_id"]]["status"] == "ok"
    assert results[ok_doc["doc_id"]]["version"] == 2
    assert results[skip_doc["doc_id"]]["status"] == "skipped"
    assert "not found" in results[skip_doc["doc_id"]]["message"]

    assert client.get(f"/documents/{ok_doc['doc_id']}").json()["content"] == "the slow brown fox"
    assert client.get(f"/documents/{skip_doc['doc_id']}").json()["content"] == "no matching phrase here"


def test_query_filter_case_mismatch_skips_not_errors(client):
    # Regression test for the reported bug: filter query 'COMPANY' + find
    # 'COMPANY' against docs that contain 'Company' (title case). FTS5 matches
    # the docs case-insensitively; the exact find doesn't. Those docs must be
    # skipped, not reported as errors.
    a = _create(client, "A", "the Company shall indemnify")
    b = _create(client, "B", "the COMPANY shall indemnify")

    resp = client.post(
        "/documents/bulk-changes",
        json={
            "filter": {"query": "COMPANY"},
            "changes": [_replace_change("COMPANY", "VENDOR")],
        },
    )
    assert resp.status_code == 200
    by_id = {r["id"]: r for r in resp.json()["results"]}
    # both docs matched the query; only the exact-case one is changed
    assert by_id[a["doc_id"]]["status"] == "skipped"
    assert by_id[b["doc_id"]]["status"] == "ok"
    # no "error" outcomes at all
    assert all(r["status"] != "error" for r in resp.json()["results"])


def test_preview_true_produces_diffs_without_writing_new_versions(client, conn):
    a = _create(client, "A", "the quick brown fox")
    b = _create(client, "B", "the quick brown fox")

    resp = client.post(
        "/documents/bulk-changes",
        json={
            "filter": {"ids": [a["doc_id"], b["doc_id"]]},
            "changes": [_replace_change("quick", "slow")],
            "preview": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    for result in body["results"]:
        assert result["status"] == "ok"
        # before/after content is returned so the client can render a diff…
        assert result["old_content"] == "the quick brown fox"
        assert result["new_content"] == "the slow brown fox"
        # …but nothing was committed, so no version was assigned (None is
        # omitted from the response by response_model_exclude_none)
        assert "version" not in result

    # nothing was written
    assert client.get(f"/documents/{a['doc_id']}").json()["content"] == "the quick brown fox"
    assert client.get(f"/documents/{b['doc_id']}").json()["content"] == "the quick brown fox"
    for doc_id in (a["doc_id"], b["doc_id"]):
        edits = conn.execute(
            "SELECT change_id FROM edits WHERE doc_id = ?", (doc_id,)
        ).fetchall()
        assert [r["change_id"] for r in edits] == [1]


def test_result_for_nonexistent_doc_id_is_an_error(client):
    ok_doc = _create(client, "OK", "the quick brown fox")

    resp = client.post(
        "/documents/bulk-changes",
        json={
            "filter": {"ids": [ok_doc["doc_id"], 999999]},
            "changes": [_replace_change("quick", "slow")],
        },
    )
    assert resp.status_code == 200
    results = {r["id"]: r for r in resp.json()["results"]}
    assert results[ok_doc["doc_id"]]["status"] == "ok"
    assert results[999999]["status"] == "error"


def test_bulk_change_does_not_apply_to_unfiltered_documents(client):
    target = _create(client, "Target", "the quick brown fox")
    untouched = _create(client, "Untouched", "the quick brown fox")

    client.post(
        "/documents/bulk-changes",
        json={
            "filter": {"ids": [target["doc_id"]]},
            "changes": [_replace_change("quick", "slow")],
        },
    )
    assert client.get(f"/documents/{untouched['doc_id']}").json()["content"] == "the quick brown fox"
