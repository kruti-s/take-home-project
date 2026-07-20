import { useEffect, useState } from "react";
import { bulkChangeDocuments, listDocuments } from "../api";
import { buildChanges } from "../lib/changes";
import { diffWords } from "../lib/diff";
import ChangeForm from "./ChangeForm";
import DiffView from "./DiffView";

export default function BulkChanges() {
  const [allDocuments, setAllDocuments] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [filterQuery, setFilterQuery] = useState("");

  const [operation, setOperation] = useState("replace");
  const [locatorType, setLocatorType] = useState("text");
  const [findText, setFindText] = useState("");
  const [occurrence, setOccurrence] = useState("1");
  const [rangeStart, setRangeStart] = useState("");
  const [rangeEnd, setRangeEnd] = useState("");
  const [newText, setNewText] = useState("");

  const [results, setResults] = useState(null);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState(null);

  useEffect(() => {
    listDocuments()
      .then((data) => setAllDocuments(data.documents))
      .catch(() => {
        /* the doc-title picker is optional; a failure here isn't fatal */
      });
  }, []);

  function toggleId(docId) {
    setSelectedIds((prev) =>
      prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId]
    );
  }

  // "Select all" resolves to an explicit list of every document id — the
  // bulk-changes endpoint requires a non-empty filter and never defaults to
  // "all", so this is the honest way to target everything.
  function selectAll() {
    setSelectedIds(allDocuments.map((d) => d.doc_id));
  }

  function clearSelection() {
    setSelectedIds([]);
  }

  const allSelected =
    allDocuments.length > 0 && selectedIds.length === allDocuments.length;

  function titleFor(docId) {
    return allDocuments.find((d) => d.doc_id === docId)?.title || `Document #${docId}`;
  }

  function hasFilter() {
    return selectedIds.length > 0 || filterQuery.trim() !== "";
  }

  const canSubmit =
    hasFilter() &&
    (locatorType === "text"
      ? !!findText
      : rangeStart !== "" && (operation === "insert" || rangeEnd !== "")) &&
    (operation === "delete" || !!newText);

  // One code path for every case: build a single change (occurrence "all"
  // included — the backend expands it per document) and hand it, plus the
  // filter, to the bulk-changes endpoint. The endpoint resolves the target
  // set (reusing the same search the search endpoint uses) and applies the
  // change (reusing the same function PATCH uses) — no per-document
  // orchestration or extra endpoint calls here.
  async function run(preview) {
    if (!hasFilter()) {
      setFormError("Select at least one document or enter a filter query.");
      return;
    }
    if (!canSubmit) {
      setFormError("Fill in the required fields for this operation.");
      return;
    }
    setBusy(true);
    setFormError(null);

    const filter = {};
    if (selectedIds.length > 0) filter.ids = selectedIds;
    if (filterQuery.trim()) filter.query = filterQuery.trim();
    const changes = buildChanges({
      operation,
      locatorType,
      findText,
      occurrence,
      rangeStart,
      rangeEnd,
      newText,
    });

    try {
      const response = await bulkChangeDocuments({ filter, changes, preview });
      setResults(
        response.results.map((r) => ({
          id: r.id,
          title: titleFor(r.id),
          status: r.status,
          // Same word-level diff renderer Document Detail uses, from the
          // before/after content the endpoint returns.
          spans:
            r.status === "ok" ? diffWords(r.old_content, r.new_content) : null,
          message: r.message,
        }))
      );
    } catch (err) {
      setFormError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <h1>Bulk Changes</h1>

      <div className="panel">
        <h2 className="panel-heading">Target documents</h2>
        <label className="field">
          <span>Filter query (optional)</span>
          <input
            type="text"
            value={filterQuery}
            onChange={(e) => setFilterQuery(e.target.value)}
            placeholder="e.g. indemnification"
            disabled={busy}
          />
        </label>
        {allDocuments.length > 0 && (
          <details className="doc-picker" open={selectedIds.length > 0}>
            <summary>
              Or pick specific documents
              {selectedIds.length > 0
                ? allSelected
                  ? ` (all ${selectedIds.length} selected)`
                  : ` (${selectedIds.length} selected)`
                : ""}
            </summary>
            <div className="doc-picker-actions">
              <button
                type="button"
                className="link-button"
                onClick={selectAll}
                disabled={busy || allSelected}
              >
                Select all ({allDocuments.length})
              </button>
              <button
                type="button"
                className="link-button"
                onClick={clearSelection}
                disabled={busy || selectedIds.length === 0}
              >
                Clear
              </button>
            </div>
            <div className="doc-picker-list">
              {allDocuments.map((doc) => (
                <label key={doc.doc_id} className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(doc.doc_id)}
                    onChange={() => toggleId(doc.doc_id)}
                    disabled={busy}
                  />
                  <span>{doc.title}</span>
                </label>
              ))}
            </div>
          </details>
        )}
      </div>

      <div className="panel change-panel">
        <ChangeForm
          operation={operation}
          onOperationChange={(op) => {
            setOperation(op);
            // insert is position-only; keep the locator valid on switch
            if (op === "insert") setLocatorType("range");
          }}
          locatorType={locatorType}
          onLocatorTypeChange={setLocatorType}
          findText={findText}
          onFindChange={setFindText}
          occurrence={occurrence}
          onOccurrenceChange={setOccurrence}
          rangeStart={rangeStart}
          onRangeStartChange={setRangeStart}
          rangeEnd={rangeEnd}
          onRangeEndChange={setRangeEnd}
          newText={newText}
          onNewTextChange={setNewText}
          disabled={busy}
        />
        {formError && <p className="error-message">{formError}</p>}
        <div className="button-row">
          <button
            className="btn btn-plain"
            onClick={() => run(true)}
            disabled={busy || !canSubmit}
          >
            {busy ? "Working…" : "Preview"}
          </button>
          <button
            className="btn btn-accent"
            onClick={() => run(false)}
            disabled={busy || !canSubmit}
          >
            {busy ? "Working…" : "Apply to All"}
          </button>
        </div>
      </div>

      {results && (() => {
        // Split by outcome. Documents that matched a broad filter query but
        // don't contain the exact edit target come back as "skipped" — show
        // those as a single muted summary line rather than flooding the view
        // with one card each, so only the documents actually changed (and any
        // genuine errors) get full cards.
        const applied = results.filter((r) => r.status === "ok");
        const errored = results.filter((r) => r.status === "error");
        const skipped = results.filter((r) => r.status === "skipped");
        return (
          <div className="bulk-results">
            <p className="muted bulk-summary">
              {applied.length} changed · {skipped.length} skipped · {errored.length} error
              {errored.length === 1 ? "" : "s"}
            </p>

            {applied.map((r) => (
              <div className="panel bulk-result bulk-result-ok" key={r.id}>
                <div className="bulk-result-header">
                  <span className="bulk-result-title">{r.title}</span>
                  <span className="badge badge-ok">OK</span>
                </div>
                <div className="document-text document-text-compact">
                  <DiffView spans={r.spans} />
                </div>
              </div>
            ))}

            {errored.map((r) => (
              <div className="panel bulk-result bulk-result-error" key={r.id}>
                <div className="bulk-result-header">
                  <span className="bulk-result-title">{r.title}</span>
                  <span className="badge badge-error">Failed</span>
                </div>
                <p className="error-message">{r.message}</p>
              </div>
            ))}

            {skipped.length > 0 && (
              <details className="panel skipped-panel">
                <summary className="muted">
                  {skipped.length} document{skipped.length === 1 ? "" : "s"} skipped — edit
                  target not present
                </summary>
                <ul className="skipped-list">
                  {skipped.map((r) => (
                    <li key={r.id}>{r.title}</li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        );
      })()}
    </section>
  );
}
