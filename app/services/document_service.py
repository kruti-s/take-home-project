"""CRUD and patch logic for documents."""

import difflib
import sqlite3
from datetime import datetime, timezone
from typing import Literal

from app.models import DocumentChange, DocumentOut, PatchPreviewOut


def apply_range_operation(
    text: str,
    operation: Literal["insert", "replace", "delete"],
    start: int,
    end: int,
    replacement: str = "",
) -> str:
    """Pure function that inserts, replaces, or deletes a range of text.

    Args:
        text: The original text.
        operation: One of "insert", "replace", "delete".
        start: Start offset (inclusive) of the range.
        end: End offset (exclusive) of the range. Ignored for "insert" —
            the replacement is inserted at `start` with nothing removed.
        replacement: Text to insert, or to substitute in for "replace".
            Ignored for "delete".

    Returns:
        The resulting text after applying the operation. `text` itself is
        left unmodified.

    Raises:
        ValueError: If `start`/`end` are out of bounds for `text`, or
            `operation` is not one of the supported values.
    """
    if not (0 <= start <= len(text)):
        raise ValueError(f"start {start} out of bounds for text of length {len(text)}")

    if operation == "insert":
        return text[:start] + replacement + text[start:]

    if not (start <= end <= len(text)):
        raise ValueError(f"end {end} out of bounds for text of length {len(text)}")

    if operation == "delete":
        return text[:start] + text[end:]
    if operation == "replace":
        return text[:start] + replacement + text[end:]

    raise ValueError(f"unknown operation: {operation}")


def _resolve_change_location(text: str, change: DocumentChange) -> tuple[int, int]:
    """Resolve a change's `target` or `range` locator into a (start, end) offset pair.

    Args:
        text: The document text the change will be applied against.
        change: The change to resolve. Exactly one of `change.target` or
            `change.range` is expected to be set.

    Returns:
        A `(start, end)` offset pair into `text`.

    Raises:
        ValueError: If neither `target` nor `range` is set, or if `target`
            is set but the requested occurrence of its text isn't found.
    """
    if change.range is not None:
        return change.range.start, change.range.end

    if change.target is not None:
        if change.target.occurrence < 1:
            raise ValueError("target.occurrence must be >= 1")
        idx = -1
        search_from = 0
        for _ in range(change.target.occurrence):
            idx = text.find(change.target.text, search_from)
            if idx == -1:
                raise ValueError(
                    f"occurrence {change.target.occurrence} of "
                    f"{change.target.text!r} not found"
                )
            search_from = idx + 1
        return idx, idx + len(change.target.text)

    raise ValueError("change must specify either 'target' or 'range'")


def apply_changes(text: str, changes: list[DocumentChange]) -> str:
    """Pure function that applies an ordered list of changes to text.

    Each change is resolved and applied against the text produced by the
    previous change. No I/O — this only computes the resulting string.

    Args:
        text: The starting text.
        changes: Ordered list of insert/replace/delete operations to apply.

    Returns:
        The text after all changes have been applied.

    Raises:
        ValueError: If a change is malformed or its target/range cannot be
            resolved against the text at that point in the sequence.
    """
    for change in changes:
        start, end = _resolve_change_location(text, change)
        text = apply_range_operation(text, change.operation, start, end, change.new_text)
    return text


def diff_text(old_text: str, new_text: str) -> str:
    """Pure function that computes a unified diff between two texts.

    Args:
        old_text: The "before" text.
        new_text: The "after" text.

    Returns:
        A unified diff (as produced by `difflib.unified_diff`) from
        `old_text` to `new_text`.
    """
    return "".join(
        difflib.unified_diff(
            old_text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile="before",
            tofile="after",
        )
    )


def create_document(conn: sqlite3.Connection, title: str, content: str) -> DocumentOut:
    """Insert a new document and its initial edit-history entry.

    The FTS5 index is kept in sync automatically by the `edits_sync_fts`
    trigger (see schema.sql), which fires when `record_edit` inserts the
    initial edits row below.

    Args:
        conn: Open SQLite connection.
        title: Title of the new document.
        content: Full text content of the new document.

    Returns:
        The newly created document.
    """
    cur = conn.execute(
        "INSERT INTO docs (title, content) VALUES (?, ?)", (title, content)
    )
    doc_id = cur.lastrowid
    record_edit(conn, doc_id, content)
    conn.commit()
    return DocumentOut(doc_id=doc_id, title=title, content=content)


def get_document(conn: sqlite3.Connection, doc_id: int) -> DocumentOut:
    """Fetch a single document by id.

    Args:
        conn: Open SQLite connection.
        doc_id: Identifier of the document to fetch.

    Returns:
        The requested document.

    Raises:
        KeyError: If no live (non-deleted) document with `doc_id` exists.
    """
    row = conn.execute(
        "SELECT doc_id, title, content FROM docs WHERE doc_id = ? AND deleted_at IS NULL",
        (doc_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"no document with doc_id={doc_id}")
    return DocumentOut(doc_id=row["doc_id"], title=row["title"], content=row["content"])


def list_documents(conn: sqlite3.Connection) -> list[DocumentOut]:
    """Fetch all non-deleted documents in the store.

    Args:
        conn: Open SQLite connection.

    Returns:
        All live documents, ordered by doc_id. Soft-deleted documents are
        excluded.
    """
    rows = conn.execute(
        "SELECT doc_id, title, content FROM docs WHERE deleted_at IS NULL ORDER BY doc_id"
    ).fetchall()
    return [
        DocumentOut(doc_id=row["doc_id"], title=row["title"], content=row["content"])
        for row in rows
    ]


def delete_document(conn: sqlite3.Connection, doc_id: int) -> None:
    """Soft-delete a document: hide it from reads/search, but keep its row
    and edit history intact so the deletion can be reverted.

    The FTS5 index is kept in sync automatically by the
    `docs_soft_delete_sync_fts` trigger (see schema.sql), which removes
    the document from the index when `deleted_at` is set below.

    Args:
        conn: Open SQLite connection.
        doc_id: Identifier of the document to delete.

    Raises:
        KeyError: If no live (non-deleted) document with `doc_id` exists.
    """
    deleted_at = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "UPDATE docs SET deleted_at = ? WHERE doc_id = ? AND deleted_at IS NULL",
        (deleted_at, doc_id),
    )
    if cur.rowcount == 0:
        raise KeyError(f"no document with doc_id={doc_id}")
    conn.commit()


def apply_patch(
    conn: sqlite3.Connection, doc_id: int, changes: list[DocumentChange]
) -> DocumentOut:
    """Apply an ordered list of changes to a document and record the edit.

    Changes are applied sequentially: each change is resolved and applied
    against the text produced by the previous change, all within a single
    document (cross-document patches are not supported).

    The FTS5 index is kept in sync automatically by the `edits_sync_fts`
    trigger (see schema.sql), which fires when `record_edit` inserts the
    new edits row below.

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
    doc = get_document(conn, doc_id)
    text = apply_changes(doc.content, changes)

    conn.execute("UPDATE docs SET content = ? WHERE doc_id = ?", (text, doc_id))
    record_edit(conn, doc_id, text)
    conn.commit()

    return DocumentOut(doc_id=doc_id, title=doc.title, content=text)


def preview_patch(
    conn: sqlite3.Connection, doc_id: int, changes: list[DocumentChange]
) -> PatchPreviewOut:
    """Compute what applying changes to a document would produce, without writing.

    Nothing is persisted: no `docs` update, no new `edits` row, no FTS
    re-index.

    Args:
        conn: Open SQLite connection.
        doc_id: Identifier of the document to preview a patch against.
        changes: Ordered list of insert/replace/delete operations to apply.

    Returns:
        The document's current content, the content the patch would
        produce, and a unified diff between the two.

    Raises:
        KeyError: If no document with `doc_id` exists.
        ValueError: If a change is malformed or its target/range cannot be
            resolved against the current document text.
    """
    doc = get_document(conn, doc_id)
    new_text = apply_changes(doc.content, changes)
    return PatchPreviewOut(
        doc_id=doc_id,
        old_content=doc.content,
        new_content=new_text,
        diff=diff_text(doc.content, new_text),
    )


def record_edit(conn: sqlite3.Connection, doc_id: int, current_text: str) -> int:
    """Append a new row to the edit history for a document.

    Args:
        conn: Open SQLite connection.
        doc_id: Identifier of the document being edited.
        current_text: The document's full text after this edit.

    Returns:
        The newly assigned change_id for this edit.
    """
    row = conn.execute(
        "SELECT COALESCE(MAX(change_id), 0) + 1 AS next_id FROM edits WHERE doc_id = ?",
        (doc_id,),
    ).fetchone()
    change_id = row["next_id"]
    conn.execute(
        "INSERT INTO edits (doc_id, change_id, current_text) VALUES (?, ?, ?)",
        (doc_id, change_id, current_text),
    )
    return change_id
