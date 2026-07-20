# sandstone

A document store service: documents live in SQLite, every edit is recorded
as a new row in an `edits` history table, and full-text search is powered by
SQLite's FTS5 extension.

This is currently a **scaffold**: routes, models, and service functions are
all defined with real signatures and docstrings, but business logic is not
yet implemented (see `NotImplementedError` in `app/services/`).

## Layout

- `app/main.py` — FastAPI app factory, router registration
- `app/db.py` — SQLite connection + schema bootstrap
- `app/schema.sql` — `docs`, `edits`, `docs_fts` DDL
- `app/models.py` — Pydantic request/response models
- `app/routers/documents.py` — all `/documents*` endpoints
- `app/services/document_service.py` — CRUD + patch logic
- `app/services/search_service.py` — FTS5 query logic
- `tests/` — endpoint test stubs

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/documents` | Create a new document |
| `GET` | `/documents` | List all documents |
| `GET` | `/documents/{id}` | Get a single document |
| `DELETE` | `/documents/{id}` | Delete a document |
| `PATCH` | `/documents/{id}` | Apply changes (insert/replace/delete, by text-match or position range) |
| `GET` | `/documents/search` | Full-text search across all documents |
| `GET` | `/documents/{id}/search` | Full-text search within one document |

## Running

```bash
pip install -e ".[dev]"
uvicorn app.main:app --reload
```
