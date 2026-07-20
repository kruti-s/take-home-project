"""Large-file and performance tests for core change and search logic.

Time budgets here are deliberately generous (they guard against accidental
quadratic behavior, not micro-regressions) so the suite stays reliable on
slow CI machines. The pure-function tests exercise ~10MB of text; the
API-level test keeps the document a bit smaller to stay fast end-to-end.
"""

import time

from app.models import ChangeRange, ChangeTarget, DocumentChange
from app.services.document_service import apply_changes, diff_text

# ~10MB of realistic prose-like text with a unique needle near the end.
_PARAGRAPH = (
    "This Agreement shall be governed by the laws of the State of Delaware. "
    "Each party shall indemnify the other against third-party claims. "
) * 40  # ~5KB
_BIG_TEXT = _PARAGRAPH * 2000  # ~10MB
_NEEDLE = "the laws of the State of Delaware"


def test_apply_changes_replace_on_10mb_document():
    assert len(_BIG_TEXT) > 10_000_000
    changes = [
        DocumentChange(
            operation="replace",
            target=ChangeTarget(text=_NEEDLE, occurrence=1),
            new_text="the laws of the State of New York",
        )
    ]
    start = time.perf_counter()
    result = apply_changes(_BIG_TEXT, changes)
    elapsed = time.perf_counter() - start

    assert "New York" in result[:6000]
    assert len(result) == len(_BIG_TEXT)  # equal-length replacement
    assert elapsed < 2.0, f"replace on 10MB took {elapsed:.2f}s"


def test_apply_changes_late_occurrence_on_10mb_document():
    # Resolving a high occurrence number requires scanning deep into the
    # text — this stays linear, not quadratic.
    changes = [
        DocumentChange(
            operation="delete",
            target=ChangeTarget(text=_NEEDLE, occurrence=50_000),
            new_text="",
        )
    ]
    start = time.perf_counter()
    result = apply_changes(_BIG_TEXT, changes)
    elapsed = time.perf_counter() - start

    assert len(result) == len(_BIG_TEXT) - len(_NEEDLE)
    assert elapsed < 2.0, f"late-occurrence delete on 10MB took {elapsed:.2f}s"


def test_range_replace_on_10mb_document():
    changes = [
        DocumentChange(
            operation="replace",
            range=ChangeRange(start=len(_BIG_TEXT) - 20, end=len(_BIG_TEXT)),
            new_text="THE END.",
        )
    ]
    start = time.perf_counter()
    result = apply_changes(_BIG_TEXT, changes)
    elapsed = time.perf_counter() - start

    assert result.endswith("THE END.")
    assert elapsed < 2.0, f"range replace on 10MB took {elapsed:.2f}s"


def test_diff_text_on_large_document_with_small_change():
    # diff_text is line-based; a small edit in a large doc must not blow up.
    big = ("line about indemnification\n" * 20_000) + "the unique closing line\n"
    changed = big.replace("the unique closing line", "the amended closing line")
    start = time.perf_counter()
    diff = diff_text(big, changed)
    elapsed = time.perf_counter() - start

    assert "-the unique closing line" in diff
    assert "+the amended closing line" in diff
    assert elapsed < 5.0, f"diff on large doc took {elapsed:.2f}s"


def test_api_patch_and_search_on_large_document(client):
    # End-to-end: create a ~2MB document over HTTP, patch it, then find the
    # edit via FTS5 search. Budget covers the whole round trip.
    body = _PARAGRAPH * 400  # ~2MB
    content = body + " The zebrafish clause appears exactly once here."
    resp = client.post("/documents", json={"title": "Big Contract", "content": content})
    assert resp.status_code == 201
    doc_id = resp.json()["doc_id"]

    start = time.perf_counter()
    patch = client.patch(
        f"/documents/{doc_id}",
        json={
            "changes": [
                {
                    "operation": "replace",
                    "target": {"text": "zebrafish clause", "occurrence": 1},
                    "new_text": "axolotl clause",
                }
            ]
        },
    )
    search = client.get("/documents/search", params={"q": "axolotl"})
    elapsed = time.perf_counter() - start

    assert patch.status_code == 200
    assert search.status_code == 200
    assert [r["doc_id"] for r in search.json()["results"]] == [doc_id]
    assert elapsed < 10.0, f"patch+search on 2MB doc took {elapsed:.2f}s"
