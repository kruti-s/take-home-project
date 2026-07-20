"""CRUD and patch logic for documents. Not yet implemented."""

import sqlite3

from app.models import DocumentChange, DocumentOut


def create_document(conn: sqlite3.Connection, content: str) -> DocumentOut:
    """Insert a new document and its matching FTS5 index entry.

    Args:
        conn: Open SQLite connection.
        content: Full text content of the new document.

    Returns:
        The newly created document.
    """
    raise NotImplementedError


def get_document(conn: sqlite3.Connection, doc_id: int) -> DocumentOut:
    """Fetch a single document by id.

    Args:
        conn: Open SQLite connection.
        doc_id: Identifier of the document to fetch.

    Returns:
        The requested document.

    Raises:
        KeyError: If no document with `doc_id` exists.
    """
    raise NotImplementedError


def list_documents(conn: sqlite3.Connection) -> list[DocumentOut]:
    """Fetch all documents in the store.

    Args:
        conn: Open SQLite connection.

    Returns:
        All documents, in an unspecified order.
    """
    raise NotImplementedError


def delete_document(conn: sqlite3.Connection, doc_id: int) -> None:
    """Delete a document, its edit history, and its FTS5 index entry.

    Args:
        conn: Open SQLite connection.
        doc_id: Identifier of the document to delete.

    Raises:
        KeyError: If no document with `doc_id` exists.
    """
    raise NotImplementedError


def apply_patch(
    conn: sqlite3.Connection, doc_id: int, changes: list[DocumentChange]
) -> DocumentOut:
    """Apply an ordered list of changes to a document and record the edit.

    Args:
        conn: Open SQLite connection.
        doc_id: Identifier of the document to patch.
        changes: Ordered list of insert/replace/delete operations to apply.

    Returns:
        The document after all changes have been applied.

    Raises:
        KeyError: If no document with `doc_id` exists.
        ValueError: If a change is malformed or its target/range cannot be
            resolved against the current document text.
    """
    raise NotImplementedError


def _apply_text_change(text: str, change: DocumentChange) -> str:
    """Apply a single text-match (occurrence-based) change to a string.

    Args:
        text: The document text to modify.
        change: A change with a `target` (text + occurrence) locator.

    Returns:
        The text after the change has been applied.

    Raises:
        ValueError: If the target text/occurrence cannot be found.
    """
    raise NotImplementedError


def _apply_range_change(text: str, change: DocumentChange) -> str:
    """Apply a single position-based (start/end offset) change to a string.

    Args:
        text: The document text to modify.
        change: A change with a `range` (start/end offset) locator.

    Returns:
        The text after the change has been applied.

    Raises:
        ValueError: If the range is out of bounds for `text`.
    """
    raise NotImplementedError


def record_edit(conn: sqlite3.Connection, doc_id: int, current_text: str) -> int:
    """Append a new row to the edit history for a document.

    Args:
        conn: Open SQLite connection.
        doc_id: Identifier of the document being edited.
        current_text: The document's full text after this edit.

    Returns:
        The newly assigned change_id for this edit.
    """
    raise NotImplementedError
