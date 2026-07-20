# Contract Redlining & Search

Find/replace ("redline") edits across template contracts — by matching text
(with an occurrence number for repeated terms) or by character position;
replace, insert, or delete; single-document or in bulk; previewable before
commit — plus full-text search across document content. FastAPI + SQLite
(FTS5) backend, minimal React frontend, no external services.

[Setup](#setup) · [API reference](#api-reference) ·
[Performance](#performance) · [Design rationale](#design-rationale)

## Setup

Requires Python 3.11+ and Node 18+.

```bash
# backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python seed.py --count 300          # optional: 300 sample contracts
uvicorn app.main:app --reload       # http://127.0.0.1:8000

# frontend (separate terminal)
cd frontend && npm install && npm run dev   # http://localhost:5173
```

`assessment.db` (SQLite) is created on first startup — no migration step.
Swagger UI at `/docs`. Run tests with `python -m pytest -q`. A Postman
collection is at [`postman_collection.json`](postman_collection.json).

## API reference

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/documents` | Create a document |
| `GET` | `/documents` | List all (non-deleted) documents |
| `GET` | `/documents/{id}` | Get one document |
| `DELETE` | `/documents/{id}` | Soft-delete a document |
| `PATCH` | `/documents/{id}` | Apply edits to one document, or preview them |
| `GET` | `/documents/search` | Full-text search, optionally scoped to ids |
| `POST` | `/documents/bulk-changes` | Apply the same edits across many documents |

### Edits — `PATCH /documents/{id}`

Each change in `changes` locates its edit with **exactly one** of:
- `target` — text-match: `{"text": "...", "occurrence": N}` (1-indexed, or
  `"all"` for every occurrence)
- `range` — position: `{"start": N, "end": N}` (character offsets)

`new_text` holds the replacement/inserted content (`""` for `delete`).
`insert` is position-only. Multiple changes apply in order, atomically — if
any fails to resolve, none are applied.

```bash
# replace the 2nd occurrence of a name
curl -X PATCH http://127.0.0.1:8000/documents/1 \
  -H "Content-Type: application/json" \
  -d '{"changes": [{"operation": "replace", "target": {"text": "Acme Corp", "occurrence": 2}, "new_text": "Globex LLC"}]}'

# preview first (writes nothing); re-send with "preview": false to commit
curl -X PATCH http://127.0.0.1:8000/documents/1 \
  -H "Content-Type: application/json" \
  -d '{"changes": [{"operation": "replace", "target": {"text": "Delaware", "occurrence": 1}, "new_text": "New York"}], "preview": true}'
# -> {"doc_id": 1, "old_content": "...", "new_content": "...", "diff": "..."}
```

### Search — `GET /documents/search`

```bash
curl "http://127.0.0.1:8000/documents/search?q=indemnification&limit=10"
curl "http://127.0.0.1:8000/documents/search?q=governing+law&ids=1&ids=2"   # scoped to ids
```

```json
{"results": [{"doc_id": 1, "snippet": "...shall <mark>indemnify</mark>...", "rank": -3.2}], "limit": 10, "offset": 0}
```

`q` is quoted as a single FTS5 phrase literal, so user input is never
interpreted as FTS5 syntax (`*`, `-`, `AND`/`OR`, etc.); an unparseable
query returns `400`, never `500`.

### Bulk changes — `POST /documents/bulk-changes`

Applies one `changes` array across many documents. `filter` selects targets
and **is required** (no "apply to all" default). `occurrence` may be a number
or `"all"`, expanded per document. `filter.ids` + `filter.query` intersect.
Set `"preview": true` for before/after without writing.

```bash
curl -X POST http://127.0.0.1:8000/documents/bulk-changes \
  -H "Content-Type: application/json" \
  -d '{"filter": {"query": "GOVERNING LAW"},
       "changes": [{"operation": "replace", "target": {"text": "Delaware", "occurrence": 1}, "new_text": "New York"}]}'
```

Each document returns a per-document `status`:
- **`ok`** — applied (or would, in preview); includes `old_content`,
  `new_content`, and the new `version` when committed.
- **`skipped`** — target text isn't present, so nothing to change. Expected
  when a filter query (matched case-insensitively by FTS5) selects documents
  lacking the exact find text. **Not a failure**, and never blocks the batch.
- **`error`** — a genuine problem (malformed change, out-of-bounds range,
  missing document).

```json
{"results": [
  {"id": 1, "status": "ok", "old_content": "...Delaware...", "new_content": "...New York...", "version": 3},
  {"id": 2, "status": "skipped", "message": "'Delaware' not found (occurrence 1)"},
  {"id": 3, "status": "error", "message": "no document with doc_id=3"}
]}
```

Bulk and single-document edits share the same code — filter resolution
reuses search's query logic in-process, and the edit reuses PATCH's
apply/version code — so they behave identically.

### Errors

- **4xx** — FastAPI's standard `{"detail": "..."}`: `400` bad input/query,
  `404` not found, `422` schema validation.
- **5xx** — `{"error": "internal server error", "code": 500}` (never a stack
  trace); the real exception is logged server-side only.

## Performance

**Documents are plain in-memory strings** — no streaming or chunking. For
contracts (KB–low-MB, not GB) this keeps the edit logic simple and
obviously correct. `tests/test_performance.py` exercises a **10MB document**:
a text-match edit is near-linear (`str.find` per occurrence), a `range` edit
is `O(length)` string slicing, and the preview diff (stdlib `difflib`) is
tested against a 20,000-line document with a single-line change.

**Search is index-backed, not a request-time scan.** SQLite's FTS5 keeps an
inverted index in sync via SQL triggers (`app/schema.sql`) on every content
change, so a search is an index lookup + BM25 ranking — latency scales with
matching terms, not corpus size. Chosen over a hand-rolled index because
FTS5 is built into SQLite (no extra dependency), stays transactionally
consistent with writes, persists across restarts, and provides tokenization,
ranking, and snippets. Trade-off: SQLite-specific (a Postgres move means
`tsvector`/`pg_trgm`), and slightly slower than an in-memory index — which
only matters far beyond this scale.

## Design rationale

**Resource CRUD with one action endpoint.** `/documents` is standard CRUD;
editing is `PATCH` (targeted changes), not `PUT` (full replacement). The one
non-resource endpoint is `POST /documents/bulk-changes` — a bulk edit isn't
idempotent and returns a heterogeneous per-document result set rather than a
single updated resource, so an action endpoint fits better than
`PATCH /documents?filter=...`.

**Preview is a request flag, not a separate endpoint.** `"preview": true` on
both edit endpoints returns the would-be diff and writes nothing. A separate
`/preview` route would duplicate the apply pipeline; a flag guarantees
preview and commit run identical logic, so what you preview is what you get.

**Explicit occurrence numbers, not "smartest guess."** Repeated target text
requires an explicit 1-indexed `occurrence`. For a legal tool, a silent
wrong guess is worse than one required field.

**Append-only edit log, not in-place mutation.** Every committed `PATCH`
inserts a new `edits` row (full snapshot per version); `docs.content` is a
cached pointer to the latest, kept in sync by the same write path. Every
change is auditable and nothing is silently lost.
