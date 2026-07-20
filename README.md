# assessment

A document store service: documents live in SQLite, every edit is recorded
as a new row in an `edits` history table, and full-text search is powered by
SQLite's FTS5 extension.

## Layout

- `app/main.py` — FastAPI app factory, router registration, schema init on startup
- `app/db.py` — SQLite connection + schema bootstrap
- `app/schema.sql` — `docs`, `edits`, `docs_fts` DDL
- `app/models.py` — Pydantic request/response models
- `app/routers/documents.py` — all `/documents*` endpoints
- `app/services/document_service.py` — CRUD + patch logic, including the pure
  `apply_range_operation` insert/replace/delete function
- `app/services/search_service.py` — FTS5 query logic
- `seed.py` — generates sample contracts for local testing
- `tests/` — endpoint and unit tests

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/documents` | Create a new document |
| `GET` | `/documents` | List all documents |
| `GET` | `/documents/{id}` | Get a single document |
| `DELETE` | `/documents/{id}` | Delete a document |
| `PATCH` | `/documents/{id}` | Apply changes (insert/replace/delete, by text-match or position range), or preview them |
| `GET` | `/documents/search` | Full-text search, optionally restricted to specific document ids |

### PATCH /documents/{id}

Each change locates its edit with **exactly one** of `target` (text-match)
or `range` (position offsets) — not both. `new_text` holds the new content;
leave it `""` for `"delete"`. Set `"preview": true` to get back a diff
without writing anything.

Text-match based:

```json
{
  "changes": [
    {
      "operation": "replace",
      "target": { "text": "old text", "occurrence": 1 },
      "new_text": "new text"
    }
  ]
}
```

Position based:

```json
{
  "changes": [
    {
      "operation": "replace",
      "range": { "start": 100, "end": 108 },
      "new_text": "new text"
    }
  ]
}
```

### GET /documents/search

`q` is required; `ids` (repeatable, e.g. `?ids=1&ids=2`) optionally
restricts the search to specific documents; `limit`/`offset` paginate.
Results are ranked by FTS5's `bm25` rank, with a `<mark>`-highlighted
snippet per match. `q` is always bound as a parameter and quoted as a
single FTS5 phrase literal before being sent to `MATCH`, so it can never
be interpreted as FTS5 query syntax.

## Running

```bash
pip install -e ".[dev]"
uvicorn app.main:app --reload
```
