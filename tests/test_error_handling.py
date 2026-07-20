"""Tests for the API's error contract.

4xx client errors use FastAPI's standard `{"detail": ...}` shape (covered
throughout the endpoint tests); genuinely unhandled server errors must come
back as a JSON `{"error": str, "code": 500}` body rather than an opaque 500.
"""

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.services import document_service


def test_unhandled_server_error_returns_json_error_body(conn, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("simulated storage failure")

    monkeypatch.setattr(document_service, "list_documents", boom)
    app.dependency_overrides[get_db] = lambda: iter([conn])
    try:
        # raise_server_exceptions=False lets the response (and our handler)
        # come back instead of the test re-raising the RuntimeError.
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/documents")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 500
    body = resp.json()
    assert body == {"error": "internal server error", "code": 500}
    # the underlying exception text must not leak to the client
    assert "simulated storage failure" not in resp.text


def test_unicode_content_replace_roundtrip(client):
    # Documents aren't guaranteed to be clean ASCII — offsets and matching
    # must behave on multi-byte text (accents, emoji, smart quotes).
    content = "Ce contrat (« l'Accord ») couvre l'indemnité — §4.2 ⚖️ applies."
    resp = client.post("/documents", json={"title": "Accord", "content": content})
    doc_id = resp.json()["doc_id"]

    patched = client.patch(
        f"/documents/{doc_id}",
        json={
            "changes": [
                {
                    "operation": "replace",
                    "target": {"text": "l'indemnité", "occurrence": 1},
                    "new_text": "la responsabilité",
                }
            ]
        },
    )
    assert patched.status_code == 200
    assert "la responsabilité" in patched.json()["content"]
    assert "⚖️" in patched.json()["content"]
