"""CRUD and patch logic for documents."""

import difflib
import sqlite3
from datetime import datetime, timezone
from typing import Literal

from app.models import DocumentChange, DocumentOut, PatchPreviewOut


class ChangeError(ValueError):
    """Raised when a change can't be resolved or applied against document text.

    Subclasses ValueError so existing `except ValueError` handling (e.g.
    the PATCH route) keeps working unchanged; callers that need to
    distinguish "bad change" from other ValueErrors (e.g. bulk-changes,
    which must keep processing the rest of a batch) can catch this
    specifically.
    """


class TargetNotFoundError(ChangeError):
    """Raised when a text-match target simply isn't present in the document.

    A subclass of ChangeError (so a single-document PATCH still treats it as
    a 400 client error), but distinguished so bulk-changes can report it as a
    "skipped" outcome rather than an "error": when a broad filter (e.g. an
    FTS5 query, which matches case-insensitively and by token) selects a
    document that doesn't contain the exact edit target, there is simply
    nothing to change there — that's not a failure of the batch.
    """


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
        ChangeError: If `start`/`end` are out of bounds for `text`, or
            `operation` is not one of the supported values.
    """
    if not (0 <= start <= len(text)):
        raise ChangeError(f"start {start} out of bounds for text of length {len(text)}")

    if operation == "insert":
        return text[:start] + replacement + text[start:]

    if not (start <= end <= len(text)):
        raise ChangeError(f"end {end} out of bounds for text of length {len(text)}")

    if operation == "delete":
        return text[:start] + text[end:]
    if operation == "replace":
        return text[:start] + replacement + text[end:]

    raise ChangeError(f"unknown operation: {operation}")


def _resolve_change_location(text: str, change: DocumentChange) -> tuple[int, int]:
    """Resolve a change's `target` or `range` locator into a (start, end) offset pair.

    Args:
        text: The document text the change will be applied against.
        change: The change to resolve. Exactly one of `change.target` or
            `change.range` is expected to be set.

    Returns:
        A `(start, end)` offset pair into `text`.

    Raises:
        ChangeError: If neither `target` nor `range` is set, or if
            `target` is set but the requested occurrence of its text
            isn't found.
    """
    if change.range is not None:
        return change.range.start, change.range.end

    if change.target is not None:
        # occurrence == "all" is expanded in _apply_one_change, never here.
        if change.target.occurrence < 1:
            raise ChangeError("target.occurrence must be >= 1")
        idx = -1
        search_from = 0
        for _ in range(change.target.occurrence):
            idx = text.find(change.target.text, search_from)
            if idx == -1:
                raise TargetNotFoundError(
                    f"{change.target.text!r} not found "
                    f"(occurrence {change.target.occurrence})"
                )
            search_from = idx + 1
        return idx, idx + len(change.target.text)

    raise ChangeError("change must specify either 'target' or 'range'")


def _find_all_occurrences(text: str, target: str) -> list[int]:
    """Return the start offset of every non-overlapping occurrence of `target`.

    Non-overlapping (advance past each match), matching `str.replace`
    semantics — the natural meaning of "replace/delete all occurrences."

    Args:
        text: The text to search.
        target: The substring to find.

    Returns:
        Start offsets, left to right. Empty if `target` never occurs (or is
        empty).
    """
    if not target:
        return []
    positions: list[int] = []
    i = text.find(target)
    while i != -1:
        positions.append(i)
        i = text.find(target, i + len(target))
    return positions


def _apply_one_change(text: str, change: DocumentChange) -> str:
    """Apply a single change to `text`, handling occurrence "all".

    For a text target with `occurrence == "all"`, the operation is applied
    to every non-overlapping occurrence, right-to-left so earlier offsets
    don't shift as the text changes. Otherwise it's a single located edit.

    Args:
        text: The current text.
        change: The change to apply.

    Returns:
        The text after applying the change.

    Raises:
        TargetNotFoundError: If a text target isn't present.
        ChangeError: If the change is otherwise malformed.
    """
    if change.target is not None and change.target.occurrence == "all":
        positions = _find_all_occurrences(text, change.target.text)
        if not positions:
            raise TargetNotFoundError(f"{change.target.text!r} not found")
        span = len(change.target.text)
        for start in reversed(positions):
            text = apply_range_operation(
                text, change.operation, start, start + span, change.new_text
            )
        return text

    start, end = _resolve_change_location(text, change)
    return apply_range_operation(text, change.operation, start, end, change.new_text)


def apply_changes(text: str, changes: list[DocumentChange]) -> str:
    """Pure function that applies an ordered list of changes to text.

    Each change is resolved and applied against the text produced by the
    previous change. No I/O — this only computes the resulting string. This
    is the single edit engine behind both PATCH /documents/{id} and
    POST /documents/bulk-changes (via `apply_patch_with_diff` /
    `preview_patch`), so a bulk edit and a single-document edit resolve and
    apply text identically — including `occurrence == "all"`.

    Args:
        text: The starting text.
        changes: Ordered list of insert/replace/delete operations to apply.

    Returns:
        The text after all changes have been applied.

    Raises:
        ChangeError: If a change is malformed or its target/range cannot
            be resolved against the text at that point in the sequence.
    """
    for change in changes:
        text = _apply_one_change(text, change)
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


def apply_patch_with_diff(
    conn: sqlite3.Connection, doc_id: int, changes: list[DocumentChange]
) -> tuple[DocumentOut, str, int]:
    """Apply changes to a document, write them, and report the before-text and version.

    This is the single shared core behind both PATCH /documents/{id} and
    POST /documents/bulk-changes — both call this function rather than
    reimplementing the fetch/apply/write sequence, so a bulk edit and a
    single-document edit are byte-for-byte the same operation.

    Changes are applied sequentially via `apply_changes` (including
    `occurrence == "all"`), all within a single document.

    The FTS5 index is kept in sync automatically by the `edits_sync_fts`
    trigger (see schema.sql), which fires when `record_edit` inserts the
    new edits row below.

    Args:
        conn: Open SQLite connection.
        doc_id: Identifier of the document to patch.
        changes: Ordered list of insert/replace/delete operations to apply.

    Returns:
        A `(document, old_content, version)` tuple: the document after all
        changes have been applied, the content *before* the edit (so the
        caller can render a diff the same way a preview does), and the new
        change_id recorded for this edit.

    Raises:
        KeyError: If no document with `doc_id` exists.
        ChangeError: If a change is malformed or its target/range cannot
            be resolved against the current document text.
    """
    doc = get_document(conn, doc_id)
    old_content = doc.content
    new_text = apply_changes(old_content, changes)

    conn.execute("UPDATE docs SET content = ? WHERE doc_id = ?", (new_text, doc_id))
    version = record_edit(conn, doc_id, new_text)
    conn.commit()

    return DocumentOut(doc_id=doc_id, title=doc.title, content=new_text), old_content, version


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
        ChangeError: If a change is malformed or its target/range cannot
            be resolved against the current document text.
    """
    doc, _old_content, _version = apply_patch_with_diff(conn, doc_id, changes)
    return doc


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
        ChangeError: If a change is malformed or its target/range cannot
            be resolved against the current document text.
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
