"""Pydantic request/response models for the documents API."""

from typing import Literal

from pydantic import BaseModel, model_validator


class DocumentCreate(BaseModel):
    """Request body for creating a new document.

    Args:
        title: The document's title.
        content: The full text content of the document.
    """

    title: str
    content: str


class DocumentOut(BaseModel):
    """A document as returned by the API.

    Args:
        doc_id: Unique identifier of the document.
        title: The document's title.
        content: The document's current full text content.
    """

    doc_id: int
    title: str
    content: str


class DocumentListOut(BaseModel):
    """Response body for listing documents.

    Args:
        documents: All documents in the store.
    """

    documents: list[DocumentOut]


class ChangeTarget(BaseModel):
    """Identifies where a text-match based change should be applied.

    Args:
        text: The exact substring to locate within the document.
        occurrence: Which occurrence of `text` to target — a 1-indexed
            integer, or the string "all" to target every (non-overlapping)
            occurrence in the document. "all" is only meaningful for
            replace/delete (insert is position-only).
    """

    text: str
    occurrence: int | Literal["all"] = 1


class ChangeRange(BaseModel):
    """Identifies where a position-based change should be applied.

    Args:
        start: Start offset (inclusive) into the document text.
        end: End offset (exclusive) into the document text.
    """

    start: int
    end: int


class DocumentChange(BaseModel):
    """A single edit operation to apply to a document.

    Exactly one of `target` (text-match based) or `range` (position based)
    must be provided to locate the edit.

    Args:
        operation: One of "replace", "insert", or "delete".
        target: Text-match location for the change (mutually exclusive
            with `range`). Not allowed for "insert" — see below.
        range: Position-based location for the change (mutually exclusive
            with `target`).
        new_text: The new content. Used as the replacement for "replace",
            the inserted text for "insert", and left as "" for "delete".

    "insert" must be located by a position `range` (a single point,
    `start == end`); it cannot use a text-match `target`, because an
    occurrence-based locator doesn't define where relative to the match the
    new text lands. "replace" and "delete" accept either locator.
    """

    operation: Literal["replace", "insert", "delete"]
    target: ChangeTarget | None = None
    range: ChangeRange | None = None
    new_text: str = ""

    @model_validator(mode="after")
    def _check_exactly_one_locator(self) -> "DocumentChange":
        if (self.target is None) == (self.range is None):
            raise ValueError("exactly one of 'target' or 'range' must be set")
        return self

    @model_validator(mode="after")
    def _check_insert_uses_range(self) -> "DocumentChange":
        if self.operation == "insert" and self.target is not None:
            raise ValueError(
                "'insert' must be located by a position range, not a text-match occurrence"
            )
        return self

    @model_validator(mode="after")
    def _check_insert_range_is_a_point(self) -> "DocumentChange":
        if self.operation == "insert" and self.range is not None:
            if self.range.start != self.range.end:
                raise ValueError("'insert' requires range.start == range.end")
        return self

    @model_validator(mode="after")
    def _check_new_text_matches_operation(self) -> "DocumentChange":
        if self.operation == "delete" and self.new_text != "":
            raise ValueError("'delete' requires new_text to be empty")
        if self.operation == "replace" and self.new_text == "":
            raise ValueError("'replace' requires a non-empty new_text")
        return self


class PatchRequest(BaseModel):
    """Request body for PATCH /documents/{id}.

    Args:
        changes: Ordered list of changes to apply to the document.
        preview: If true, compute and return the resulting diff without
            writing anything — no document update, no new edits row.
    """

    changes: list[DocumentChange]
    preview: bool = False


class PatchPreviewOut(BaseModel):
    """Response body for PATCH /documents/{id} when `preview` is true.

    Args:
        doc_id: Identifier of the document that would be patched.
        old_content: The document's content before the patch.
        new_content: The content the patch would produce, if applied.
        diff: A unified diff from `old_content` to `new_content`.
    """

    doc_id: int
    old_content: str
    new_content: str
    diff: str


class BulkChangeFilter(BaseModel):
    """Selects which documents a bulk change applies to.

    `ids` alone targets exactly those documents. `query` alone targets
    every document matching it (full-text search across all documents,
    resolved via the same search used by GET /documents/search). Given
    together, `query` finds matches restricted to `ids` — `ids` scopes
    the search rather than overriding it.

    Args:
        ids: Document ids to target, or to scope a `query` search to.
        query: Full-text search query.
    """

    ids: list[int] | None = None
    query: str | None = None


class BulkChangeRequest(BaseModel):
    """Request body for POST /documents/bulk-changes.

    Args:
        filter: Selects target documents. Required: a non-empty `ids` or
            a non-empty `query` must be given — there is no "apply to
            all documents" default.
        changes: The same change list shape PATCH /documents/{id} takes,
            applied independently to each targeted document.
        preview: If true, compute diffs for every targeted document
            without writing anything.
    """

    filter: BulkChangeFilter
    changes: list[DocumentChange]
    preview: bool = False


class BulkChangeResult(BaseModel):
    """Per-document outcome of a bulk change.

    Args:
        id: The document's id.
        status: "ok" (change applied/previewed), "skipped" (the edit target
            wasn't present in this document — nothing to change), or "error"
            (a genuine failure: malformed change, bad range, missing document).
        old_content: The document's content before the change; set when
            status is "ok". Paired with `new_content` so the client renders
            the same word-level diff a single-document preview does.
        new_content: The content the change produced; set when status is "ok".
        version: The new change_id recorded for this edit; set when
            status is "ok" and the change was actually written (not a
            preview).
        message: Human-readable reason; set when status is "skipped" or "error".
    """

    id: int
    status: Literal["ok", "skipped", "error"]
    old_content: str | None = None
    new_content: str | None = None
    version: int | None = None
    message: str | None = None


class BulkChangeResponse(BaseModel):
    """Response body for POST /documents/bulk-changes.

    Args:
        results: One outcome per document the filter resolved to.
    """

    results: list[BulkChangeResult]


class SearchResultItem(BaseModel):
    """A single search hit.

    Args:
        doc_id: Identifier of the matching document.
        snippet: A highlighted excerpt of the match in context.
        rank: FTS5 relevance rank for this match (lower is more relevant).
    """

    doc_id: int
    snippet: str
    rank: float


class SearchResponse(BaseModel):
    """Response body for document search endpoints.

    Args:
        results: Matching documents, ordered by relevance.
        limit: The page size that was applied.
        offset: The page offset that was applied.
    """

    results: list[SearchResultItem]
    limit: int
    offset: int
