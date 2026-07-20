"""Stub tests for /documents/search endpoints."""


def test_search_all_documents():
    """GET /documents/search returns matches ranked by relevance."""


def test_search_all_documents_pagination():
    """GET /documents/search respects limit and offset."""


def test_search_single_document():
    """GET /documents/{id}/search restricts matches to one document."""


def test_search_single_document_not_found():
    """GET /documents/{id}/search returns 404 for an unknown doc_id."""
