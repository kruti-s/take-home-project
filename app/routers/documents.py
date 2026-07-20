"""Document CRUD, patch, and search endpoints."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import get_db
from app.models import (
    BulkChangeRequest,
    BulkChangeResponse,
    DocumentCreate,
    DocumentListOut,
    DocumentOut,
    PatchPreviewOut,
    PatchRequest,
    SearchResponse,
)
from app.services import bulk_service, document_service, search_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentOut, status_code=201)
def create_document(
    body: DocumentCreate, conn: sqlite3.Connection = Depends(get_db)
) -> DocumentOut:
    """Create a new document.

    Args:
        body: The document title and content to store.
        conn: SQLite connection, injected per-request.

    Returns:
        The newly created document, including its assigned doc_id.
    """
    return document_service.create_document(conn, body.title, body.content)


@router.post(
    "/bulk-changes", response_model=BulkChangeResponse, response_model_exclude_none=True
)
def bulk_change_documents(
    body: BulkChangeRequest, conn: sqlite3.Connection = Depends(get_db)
) -> BulkChangeResponse:
    """Apply the same set of changes across many documents at once.

    Documents are selected via `body.filter`: `ids` alone targets exactly
    those documents; `query` alone targets every document matching it
    (via the same full-text search GET /documents/search uses); given
    together, `query` matches are restricted to `ids`. A filter is
    required and must not be empty; there is no "apply to all documents"
    default.

    Each document is processed independently (no transaction spans
    documents): a change that fails against one document (e.g. its
    target text isn't found) is recorded as an error result for that
    document without affecting the others.

    Args:
        body: The filter, the changes to apply, and whether to preview.
        conn: SQLite connection, injected per-request.

    Returns:
        One result per document the filter resolved to — "ok" (with a
        diff, plus a version if written) or "error" (with a message).
    """
    if bulk_service.is_filter_empty(body.filter):
        raise HTTPException(
            status_code=400,
            detail="filter is required: provide a non-empty 'ids' list or 'query'",
        )
    doc_ids = bulk_service.resolve_filter_doc_ids(conn, body.filter)
    results = bulk_service.apply_bulk_changes(conn, doc_ids, body.changes, body.preview)
    return BulkChangeResponse(results=results)


@router.get("", response_model=DocumentListOut)
def list_documents(conn: sqlite3.Connection = Depends(get_db)) -> DocumentListOut:
    """List all documents in the store.

    Args:
        conn: SQLite connection, injected per-request.

    Returns:
        All documents currently stored.
    """
    return DocumentListOut(documents=document_service.list_documents(conn))


@router.get("/search", response_model=SearchResponse)
def search_documents(
    q: str = Query(..., description="Search query"),
    ids: list[int] | None = Query(None, description="Restrict search to these document ids"),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    conn: sqlite3.Connection = Depends(get_db),
) -> SearchResponse:
    """Full-text search across documents, ranked by relevance.

    Args:
        q: The search query string. Bound as a parameter and quoted as a
            single FTS5 phrase literal, so user input can never be
            interpreted as FTS5 query syntax (or SQL).
        ids: If given, restrict the search to these document ids (e.g.
            `?ids=1&ids=2`) instead of searching every document.
        limit: Maximum number of results to return.
        offset: Number of results to skip, for pagination.
        conn: SQLite connection, injected per-request.

    Returns:
        Matching documents ranked by relevance.
    """
    try:
        return search_service.search_documents(conn, q, limit, offset, ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: int, conn: sqlite3.Connection = Depends(get_db)) -> DocumentOut:
    """Fetch a single document by id.

    Args:
        doc_id: Identifier of the document to fetch.
        conn: SQLite connection, injected per-request.

    Returns:
        The requested document.
    """
    try:
        return document_service.get_document(conn, doc_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: int, conn: sqlite3.Connection = Depends(get_db)) -> None:
    """Soft-delete a document.

    The document stops appearing in GET /documents, GET /documents/{id},
    and search results, but its row and edit history are preserved (not
    hard-deleted), so the deletion can be reverted.

    Args:
        doc_id: Identifier of the document to delete.
        conn: SQLite connection, injected per-request.
    """
    try:
        document_service.delete_document(conn, doc_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{doc_id}")
def patch_document(
    doc_id: int,
    body: PatchRequest,
    conn: sqlite3.Connection = Depends(get_db),
) -> DocumentOut | PatchPreviewOut:
    """Apply one or more changes to a document, or preview them.

    Each change is either text-match based (`target`: text + occurrence)
    or position based (`range`: start/end offset), and applies an
    "insert", "replace", or "delete" operation. Applying the patch records
    a new entry in the document's edit history.

    If `body.preview` is true, nothing is written — the changes are
    computed and returned as a diff instead.

    Args:
        doc_id: Identifier of the document to patch.
        body: The ordered list of changes to apply, and whether to preview.
        conn: SQLite connection, injected per-request.

    Returns:
        The document after all changes have been applied, or (if
        `body.preview` is true) a diff of what would have changed.
    """
    try:
        if body.preview:
            return document_service.preview_patch(conn, doc_id, body.changes)
        return document_service.apply_patch(conn, doc_id, body.changes)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
