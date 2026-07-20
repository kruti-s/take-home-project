-- Documents table: current content lives here, one row per document.
CREATE TABLE IF NOT EXISTS docs (
    doc_id INTEGER PRIMARY KEY,
    content TEXT NOT NULL
);

-- Edit history: one row per change applied to a document. change_id is
-- scoped per doc_id (not globally unique) and increments with each edit.
CREATE TABLE IF NOT EXISTS edits (
    doc_id INTEGER NOT NULL,
    change_id INTEGER NOT NULL,
    current_text TEXT NOT NULL,
    PRIMARY KEY (doc_id, change_id),
    FOREIGN KEY (doc_id) REFERENCES docs(doc_id) ON DELETE CASCADE
);

-- FTS5 external-content index over docs.content, keyed by docs.doc_id.
CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
    content,
    content='docs',
    content_rowid='doc_id'
);
