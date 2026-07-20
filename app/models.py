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
        occurrence: Which occurrence of `text` to target (1-indexed).
    """

    text: str
    occurrence: int = 1


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
            with `range`).
        range: Position-based location for the change (mutually exclusive
            with `target`).
        new_text: The new content. Used as the replacement for "replace",
            the inserted text for "insert", and left as "" for "delete".
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
