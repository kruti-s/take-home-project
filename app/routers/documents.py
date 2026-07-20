"""Document CRUD, patch, and search endpoints."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import get_db
from app.models import (
    DocumentCreate,
    DocumentListOut,
    DocumentOut,
    PatchRequest,
    SearchResponse,
)
from app.services import document_service, search_service

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
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    conn: sqlite3.Connection = Depends(get_db),
) -> SearchResponse:
    """Full-text search across all documents.

    Args:
        q: The search query string.
        limit: Maximum number of results to return.
        offset: Number of results to skip, for pagination.
        conn: SQLite connection, injected per-request.

    Returns:
        Matching documents ranked by relevance.
    """
    return search_service.search_all(conn, q, limit, offset)


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
    """Delete a document and its edit history.

    Args:
        doc_id: Identifier of the document to delete.
        conn: SQLite connection, injected per-request.
    """
    try:
        document_service.delete_document(conn, doc_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{doc_id}", response_model=DocumentOut)
def patch_document(
    doc_id: int,
    body: PatchRequest,
    conn: sqlite3.Connection = Depends(get_db),
) -> DocumentOut:
    """Apply one or more changes to a document.

    Each change is either text-match based (`target`: text + occurrence)
    or position based (`range`: start/end offset), and applies an
    "insert", "replace", or "delete" operation. Applying the patch records
    a new entry in the document's edit history.

    Args:
        doc_id: Identifier of the document to patch.
        body: The ordered list of changes to apply.
        conn: SQLite connection, injected per-request.

    Returns:
        The document after all changes have been applied.
    """
    try:
        return document_service.apply_patch(conn, doc_id, body.changes)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{doc_id}/search", response_model=SearchResponse)
def search_document(
    doc_id: int,
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    conn: sqlite3.Connection = Depends(get_db),
) -> SearchResponse:
    """Full-text search restricted to a single document.

    Args:
        doc_id: Identifier of the document to search within.
        q: The search query string.
        limit: Maximum number of results to return.
        offset: Number of results to skip, for pagination.
        conn: SQLite connection, injected per-request.

    Returns:
        Matching passages within the document, ranked by relevance.
    """
    try:
        return search_service.search_document(conn, doc_id, q, limit, offset)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
