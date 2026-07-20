"""Document CRUD, patch, and search endpoints."""

import sqlite3

from fastapi import APIRouter, Depends, Query

from app.db import get_connection
from app.models import (
    DocumentCreate,
    DocumentListOut,
    DocumentOut,
    PatchRequest,
    SearchResponse,
)
router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentOut)
def create_document(
    body: DocumentCreate, conn: sqlite3.Connection = Depends(get_connection)
) -> DocumentOut:
    """Create a new document.

    Args:
        body: The document content to store.
        conn: SQLite connection, injected per-request.

    Returns:
        The newly created document, including its assigned doc_id.
    """
    raise NotImplementedError


@router.get("", response_model=DocumentListOut)
def list_documents(
    conn: sqlite3.Connection = Depends(get_connection),
) -> DocumentListOut:
    """List all documents in the store.

    Args:
        conn: SQLite connection, injected per-request.

    Returns:
        All documents currently stored.
    """
    raise NotImplementedError


@router.get("/search", response_model=SearchResponse)
def search_documents(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    conn: sqlite3.Connection = Depends(get_connection),
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
    raise NotImplementedError


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(
    doc_id: int, conn: sqlite3.Connection = Depends(get_connection)
) -> DocumentOut:
    """Fetch a single document by id.

    Args:
        doc_id: Identifier of the document to fetch.
        conn: SQLite connection, injected per-request.

    Returns:
        The requested document.
    """
    raise NotImplementedError


@router.delete("/{doc_id}", status_code=204)
def delete_document(
    doc_id: int, conn: sqlite3.Connection = Depends(get_connection)
) -> None:
    """Delete a document and its edit history.

    Args:
        doc_id: Identifier of the document to delete.
        conn: SQLite connection, injected per-request.
    """
    raise NotImplementedError


@router.patch("/{doc_id}", response_model=DocumentOut)
def patch_document(
    doc_id: int,
    body: PatchRequest,
    conn: sqlite3.Connection = Depends(get_connection),
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
    raise NotImplementedError


@router.get("/{doc_id}/search", response_model=SearchResponse)
def search_document(
    doc_id: int,
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    conn: sqlite3.Connection = Depends(get_connection),
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
    raise NotImplementedError
