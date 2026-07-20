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


class PatchRequest(BaseModel):
    """Request body for PATCH /documents/{id}.

    Args:
        changes: Ordered list of changes to apply to the document.
    """

    changes: list[DocumentChange]


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
