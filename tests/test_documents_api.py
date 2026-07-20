"""Stub tests for /documents CRUD and patch endpoints."""


def test_create_document():
    """POST /documents creates a document and returns its doc_id."""


def test_list_documents():
    """GET /documents returns all stored documents."""


def test_get_document():
    """GET /documents/{id} returns the requested document."""


def test_get_document_not_found():
    """GET /documents/{id} returns 404 for an unknown doc_id."""


def test_delete_document():
    """DELETE /documents/{id} removes the document and its edit history."""


def test_patch_document_text_replace():
    """PATCH /documents/{id} applies a text-match replace operation."""


def test_patch_document_range_replace():
    """PATCH /documents/{id} applies a position-based replace operation."""


def test_patch_document_insert():
    """PATCH /documents/{id} applies an insert operation."""


def test_patch_document_delete():
    """PATCH /documents/{id} applies a delete operation."""


def test_patch_document_records_edit_history():
    """PATCH /documents/{id} appends a new row to the edits table."""
