# Contract Redlining & Search

A full-stack tool for an in-house legal team to run find/replace ("redline")
edits across template agreements and search across document content —
built as a take-home/demo project. FastAPI + SQLite (FTS5) on the backend,
a minimal React frontend, no external services required.

**Contents:** [Setup](#setup) · [Usage / sample requests](#sample-requests) ·
[API reference](#api-reference) · [Performance considerations](#performance-considerations) ·
[API design rationale](#api-design-rationale)

Apply find/replace ("redline") edits across contracts — by matching text (with an
occurrence number for repeated terms) or by character position; replace, insert,
or delete; single-document or in bulk; always previewable before commit — and
full-text search across document content. FastAPI + SQLite (FTS5) backend, a
minimal React frontend.

---

## Setup

Requires Python 3.11+ and Node 18+.

```bash
# backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python seed.py --count 300          # optional: generate 300 sample contracts
uvicorn app.main:app --reload       # http://127.0.0.1:8000

# frontend (separate terminal)
cd frontend
npm install
npm run dev                          # http://localhost:5173
```

The database file (`assessment.db`, SQLite) is created automatically on
first startup — no separate migration step. Interactive API docs (Swagger
UI) are available at `http://127.0.0.1:8000/docs` once the backend is running.

Run the backend tests with:

```bash
python -m pytest -q
```

## Sample requests

Curl examples are inline below under [API reference](#api-reference). A
ready-to-import Postman collection is at
[`postman_collection.json`](postman_collection.json) (uses a
`{{base_url}}` variable, defaulted to `http://127.0.0.1:8000`).

## API reference

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/documents` | Create a document |
| `GET` | `/documents` | List all (non-deleted) documents |
| `GET` | `/documents/{id}` | Get one document |
| `DELETE` | `/documents/{id}` | Soft-delete a document |
| `PATCH` | `/documents/{id}` | Apply edits to one document, or preview them |
| `GET` | `/documents/search` | Full-text search, optionally scoped to specific ids |
| `POST` | `/documents/bulk-changes` | Apply the same edits across many documents |

### Create a document

```bash
curl -X POST http://127.0.0.1:8000/documents \
  -H "Content-Type: application/json" \
  -d '{
    "title": "MSA — Acme Corp",
    "content": "This Master Services Agreement is entered into by Acme Corp. Acme Corp shall indemnify..."
  }'
```

### Change Requests — `PATCH /documents/{id}`

Each change in the `changes` array locates its edit with **exactly one**
of:
- `target` — text-match: `{"text": "...", "occurrence": N}` (1-indexed, or
  `"all"` for every occurrence; handles the "target text appears multiple
  times" case explicitly rather than guessing)
- `range` — position: `{"start": N, "end": N}` (character offsets)

`new_text` holds the replacement/inserted content (`""` for `delete`).
`insert` is position-only (an occurrence-based "insert" doesn't have a
well-defined meaning — insert *where*, relative to the match? — so the API
forces the caller to be explicit about a point).

**Replace the 2nd occurrence of a name:**

```bash
curl -X PATCH http://127.0.0.1:8000/documents/1 \
  -H "Content-Type: application/json" \
  -d '{
    "changes": [
      {"operation": "replace", "target": {"text": "Acme Corp", "occurrence": 2}, "new_text": "Globex LLC"}
    ]
  }'
```

**Preview first (writes nothing), then commit the identical request:**

```bash
curl -X PATCH http://127.0.0.1:8000/documents/1 \
  -H "Content-Type: application/json" \
  -d '{
    "changes": [{"operation": "replace", "target": {"text": "Delaware", "occurrence": 1}, "new_text": "New York"}],
    "preview": true
  }'
# -> {"doc_id": 1, "old_content": "...", "new_content": "...", "diff": "--- before\n+++ after\n..."}
# re-send with "preview": false (or omitted) to commit
```

**Insert at a position, delete a range:**

```bash
curl -X PATCH http://127.0.0.1:8000/documents/1 \
  -H "Content-Type: application/json" \
  -d '{"changes": [{"operation": "insert", "range": {"start": 42, "end": 42}, "new_text": "(as amended) "}]}'

curl -X PATCH http://127.0.0.1:8000/documents/1 \
  -H "Content-Type: application/json" \
  -d '{"changes": [{"operation": "delete", "range": {"start": 100, "end": 150}, "new_text": ""}]}'
```

**Multiple changes in one request** (applied in order, atomically — if any
change fails to resolve, none are applied):

```bash
curl -X PATCH http://127.0.0.1:8000/documents/1 \
  -H "Content-Type: application/json" \
  -d '{
    "changes": [
      {"operation": "replace", "target": {"text": "Acme Corp", "occurrence": 1}, "new_text": "Globex LLC"},
      {"operation": "replace", "target": {"text": "Delaware", "occurrence": 1}, "new_text": "New York"}
    ]
  }'
```

### Search — `GET /documents/search`

```bash
curl "http://127.0.0.1:8000/documents/search?q=indemnification&limit=10"

# scoped to specific documents:
curl "http://127.0.0.1:8000/documents/search?q=governing+law&ids=1&ids=2"
```

```json
{
  "results": [
    {"doc_id": 1, "snippet": "...shall <mark>indemnify</mark> the other party...", "rank": -3.2}
  ],
  "limit": 10,
  "offset": 0
}
```

`q` is bound as a SQL parameter and quoted as a single FTS5 phrase literal
before being sent to `MATCH` — user input is never interpreted as FTS5
query syntax (`*`, `-`, `^`, `AND`/`OR`/`NOT`, column filters, etc. are all
neutralized), and a query that can't be parsed returns `400`, never `500`.

### Bulk Changes — `POST /documents/bulk-changes`

Applies one `changes` array across many documents at once — the "swap this
clause in 200 templates" case. `filter` selects targets and **is
required**; there's deliberately no "apply to all documents" default
(see [Design rationale](#api-design-rationale)).

```bash
curl -X POST http://127.0.0.1:8000/documents/bulk-changes \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {"query": "GOVERNING LAW"},
    "changes": [{"operation": "replace", "target": {"text": "Delaware", "occurrence": 1}, "new_text": "New York"}]
  }'
```

`occurrence` may be a 1-based number or `"all"` (replace/delete every
occurrence in each document) — the backend expands `"all"` per document, so
one request covers documents with different match counts.

Each document gets a per-document outcome. `status` is one of:
- **`ok`** — the change applied (or, in preview, would apply). Includes `old_content` and `new_content` (the before/after text, so the client can render a precise word-level diff) and, when committed, the new `version`.
- **`skipped`** — the edit target text isn't present in that document, so there's nothing to change. Common and expected when a filter query (matched case-insensitively / by token by FTS5) selects documents that don't contain the exact find text — it is **not** a failure.
- **`error`** — a genuine problem (malformed change, out-of-bounds range, or a document that doesn't exist).

```json
{
  "results": [
    {"id": 1, "status": "ok", "old_content": "...Delaware...", "new_content": "...New York...", "version": 3},
    {"id": 2, "status": "skipped", "message": "'Delaware' not found (occurrence 1)"},
    {"id": 3, "status": "error", "message": "no document with doc_id=3"}
  ]
}
```

A single document's `skipped`/`error` never blocks the rest of the batch.
`filter.ids` + `filter.query` together scope the search to those ids
(intersection) rather than one overriding the other. Set `"preview": true`
to get every document's before/after without writing anything.

Both this and `PATCH /documents/{id}` route through the same underlying
functions — filter resolution reuses the search endpoint's query logic
(in-process, not an HTTP self-call), and the edit itself reuses the exact
apply/version code PATCH uses — so a bulk edit and a single-document edit
behave identically.

### Errors

- **4xx** — client errors (bad payload, unknown document, unresolvable
  edit) use FastAPI's standard shape: `{"detail": "<message>"}`, with an
  appropriate status (`400` malformed input/query, `404` document not
  found, `422` schema validation).
- **5xx** — any unhandled server-side failure returns
  `{"error": "internal server error", "code": 500}` (never a stack trace
  or bare 500 with no body); the real exception is logged server-side only.

## Performance considerations

**Documents are treated as plain Python strings in memory** — no
streaming, no chunking. For a legal-contract tool (single documents,
typically KB–low-MB, not GB) this is the right trade-off: it keeps the
edit logic (`apply_range_operation`, `_resolve_change_location` in
`app/services/document_service.py`) simple, obviously correct, and easy to
audit — which matters more than throughput headroom nobody asked for. The
suite includes tests against a **10MB synthetic document**
(`tests/test_performance.py`) confirming:

- A text-match replace/delete/insert stays **near-linear**: locating
  occurrence *N* is one `str.find` scan per occurrence
- A position-based (`range`) edit is `O(document length)` — Python string
  slicing/concatenation, no re-scanning.
- `diff_text` (unified diff, for the preview response) is line-based via
  stdlib `difflib`, tested against a 20,000-line document with a
  single-line change.

**Search does not scan document text at request time.** It's backed by
SQLite's FTS5 extension — an inverted index kept in sync by SQL triggers
(`app/schema.sql`) on every content change. A search is an index lookup +
BM25 ranking, not a linear scan, so latency scales with matching terms,
not with the number or size of stored documents. FTS5 was chosen over a
hand-rolled in-memory index because it's built into SQLite (no extra
dependency), stays transactionally consistent with writes via triggers
rather than an out-of-band reindex, persists across restarts for free,
and already handles tokenization, BM25 ranking, and snippets. Trade-off:
it's SQLite-specific (a Postgres move means `tsvector`/`pg_trgm`, not a
port) and, being disk-backed, is slightly slower than a hand-tuned
in-memory index — irrelevant at hundreds-of-documents scale, relevant only
if this needed sub-millisecond search-as-you-type over millions of docs.

## API design rationale

**Resource-based REST, with one deliberate escape hatch.** `/documents` is
standard CRUD (`POST`/`GET`/`DELETE`); editing is `PATCH`, not `PUT`,
since a redline is a set of targeted changes rather than a full-document
replacement. `GET /documents/search` stays a `GET` with query params
(cacheable, bookmarkable, safe to retry) rather than a `POST`.

The one non-resource endpoint is `POST /documents/bulk-changes` —
deliberately action-based rather than `PATCH /documents?filter=...`. A
bulk edit isn't idempotent the way a resource `PATCH` implies, and it
returns a heterogeneous per-document result set (some succeed, some fail)
rather than one updated resource — forcing that into REST's resource
model would fit the workflow poorly. Action endpoints alongside resource
CRUD are a common pattern in REST APIs for bulk operations.

**Preview is a request flag, not a separate endpoint.** `PATCH .../{id}`
and `POST .../bulk-changes` both accept `"preview": true`, returning the
would-be diff and writing nothing. A separate `POST .../preview` endpoint
would duplicate the whole resolve/apply/diff pipeline for no benefit; a
flag guarantees preview and commit run the exact same resolution logic, so
what you previewed is what you get.

**Occurrence numbers over "smartest guess" matching.** When target text
appears multiple times, the API requires an explicit 1-indexed
`occurrence` rather than silently picking "the first." For a legal tool, a
silent wrong guess is worse than one extra required field.

**Errors: framework defaults, with a custom shape only where needed.**
FastAPI/Pydantic already produce well-formed `{"detail": ...}` 4xx bodies
for validation and domain errors (`HTTPException`) — no need to reinvent
that. The one custom case is unhandled 5xxs, which get a top-level handler
enforcing `{"error": str, "code": 500}` and server-side logging instead of
a leaked stack trace.

**Versioning via an append-only edit log, not in-place mutation.** Every
committed `PATCH` inserts a new row into an `edits` table (full snapshot
per version) instead of overwriting content; `docs.content` is a cached
pointer to the latest version, kept in sync by the same write path. Every
change is individually auditable and nothing is silently lost — important
for a legal tool where "what did this clause say before" is a real
question.

