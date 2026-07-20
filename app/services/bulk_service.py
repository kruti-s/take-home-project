"""Bulk-change orchestration: applies one set of PATCH changes across many documents.

This module resolves *which* documents a request targets and loops over
them; the actual per-document patch/preview logic all lives in
`document_service` and is reused as-is (see `apply_bulk_changes` below).
"""

import sqlite3

from app.models import BulkChangeFilter, BulkChangeResult, DocumentChange
from app.services import document_service, search_service


def is_filter_empty(filter: BulkChangeFilter) -> bool:
    """Check whether a bulk-change filter specifies no selection criteria.

    Args:
        filter: The filter to check.

    Returns:
        True if neither a non-empty `ids` list nor a non-empty `query`
        string is set — i.e. the request gave nothing to select
        documents by.
    """
    has_ids = bool(filter.ids)
    has_query = bool(filter.query) and filter.query.strip() != ""
    return not (has_ids or has_query)


def resolve_filter_doc_ids(conn: sqlite3.Connection, filter: BulkChangeFilter) -> list[int]:
    """Resolve a bulk-change filter to the document ids it selects.

    - `ids` only: those ids, as given.
    - `query` only: every document matching `query` (full-text search
      across all documents).
    - Both: documents matching `query`, restricted to `ids` — i.e. `ids`
      scopes the search rather than overriding it (the intersection of the
      query matches with `ids`).

    When a query is present this is a direct, in-process call to
    `search_service.search_document_ids` — the same MATCH/sanitization
    logic behind GET /documents/search, never an HTTP self-call.

    Args:
        conn: Open SQLite connection.
        filter: The filter to resolve.

    Returns:
        Document ids to target, in processing order. Empty if `query`
        (scoped or not) matches nothing — a valid, non-error outcome,
        distinct from the filter being empty in the first place.
    """
    if filter.query:
        return search_service.search_document_ids(conn, filter.query, ids=filter.ids)
    if filter.ids:
        return list(dict.fromkeys(filter.ids))
    return []


def apply_bulk_changes(
    conn: sqlite3.Connection,
    doc_ids: list[int],
    changes: list[DocumentChange],
    preview: bool,
) -> list[BulkChangeResult]:
    """Apply the same changes to each document independently.

    Each document is processed on its own connection-level statement
    sequence — there is no transaction spanning documents, and a failure
    on one document is recorded and does not stop the rest from being
    processed. This calls `document_service.preview_patch` and
    `document_service.apply_patch_with_diff` directly: the exact same
    functions PATCH /documents/{id} uses, so patch logic is never
    duplicated here.

    Args:
        conn: Open SQLite connection.
        doc_ids: Document ids to apply the changes to.
        changes: The change list to apply to every document.
        preview: If true, compute diffs without writing anything.

    Returns:
        One result per doc_id, in the same order: an "ok" outcome (diff,
        plus version if written) or an "error" outcome (message) for
        documents where a change couldn't be resolved or applied, or that
        don't exist.
    """
    results: list[BulkChangeResult] = []
    for doc_id in doc_ids:
        try:
            if preview:
                preview_out = document_service.preview_patch(conn, doc_id, changes)
                results.append(
                    BulkChangeResult(
                        id=doc_id, status="ok", diff=preview_out.diff.splitlines()
                    )
                )
            else:
                _doc, diff, version = document_service.apply_patch_with_diff(
                    conn, doc_id, changes
                )
                results.append(
                    BulkChangeResult(
                        id=doc_id, status="ok", diff=diff.splitlines(), version=version
                    )
                )
        except (KeyError, document_service.ChangeError) as exc:
            results.append(BulkChangeResult(id=doc_id, status="error", message=str(exc)))
    return results
