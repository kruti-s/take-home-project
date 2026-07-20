-- Documents table: current content lives here, one row per document.
-- Deletion is soft: deleted_at is set instead of removing the row, so
-- edit history is preserved and a delete can be reverted. NULL means
-- the document is live.
CREATE TABLE IF NOT EXISTS docs (
    doc_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    deleted_at TEXT
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

-- FTS5 external-content index over docs.title and docs.content, keyed by docs.doc_id.
-- Kept in sync entirely via triggers below — application code never writes
-- to docs_fts directly.
CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
    title,
    content,
    content='docs',
    content_rowid='doc_id'
);

-- Every edits row is a new "current" version of its document. Re-index
-- the document on each insert: remove whatever version was previously
-- indexed (the prior edits row, if any — none on a document's first
-- version), then index the version this row just introduced.
CREATE TRIGGER IF NOT EXISTS edits_sync_fts AFTER INSERT ON edits
BEGIN
    INSERT INTO docs_fts (docs_fts, rowid, title, content)
    SELECT 'delete', NEW.doc_id, docs.title, prev.current_text
    FROM docs
    JOIN edits AS prev
        ON prev.doc_id = NEW.doc_id AND prev.change_id = NEW.change_id - 1
    WHERE docs.doc_id = NEW.doc_id;

    INSERT INTO docs_fts (rowid, title, content)
    SELECT NEW.doc_id, docs.title, NEW.current_text
    FROM docs
    WHERE docs.doc_id = NEW.doc_id;
END;

-- Once a document is soft-deleted, drop it from the FTS index so it can
-- no longer be found by search.
CREATE TRIGGER IF NOT EXISTS docs_soft_delete_sync_fts
AFTER UPDATE OF deleted_at ON docs
WHEN NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL
BEGIN
    INSERT INTO docs_fts (docs_fts, rowid, title, content)
    VALUES ('delete', OLD.doc_id, OLD.title, OLD.content);
END;
