import { useEffect, useState } from "react";
import { listDocuments, searchDocuments } from "../api";

export default function Search({ onOpenDocument }) {
  const [allDocuments, setAllDocuments] = useState([]);
  const [query, setQuery] = useState("");
  const [selectedIds, setSelectedIds] = useState([]);
  const [results, setResults] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    listDocuments()
      .then((data) => setAllDocuments(data.documents))
      .catch(() => {
        /* the doc-title picker is optional; a failure here isn't fatal to search */
      });
  }, []);

  function toggleId(docId) {
    setSelectedIds((prev) =>
      prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId]
    );
  }

  function handleSearch(e) {
    e.preventDefault();
    if (!query.trim()) return;
    setBusy(true);
    setError(null);
    searchDocuments({ q: query, ids: selectedIds })
      .then((data) => setResults(data.results))
      .catch((err) => setError(err.message))
      .finally(() => setBusy(false));
  }

  return (
    <section>
      <h1>Search</h1>

      <form className="panel search-form" onSubmit={handleSearch}>
        <label className="field">
          <span>Search text</span>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search across all documents…"
          />
        </label>
        <button className="btn btn-accent" type="submit" disabled={busy}>
          {busy ? "Searching…" : "Search"}
        </button>

        {allDocuments.length > 0 && (
          <details className="doc-picker">
            <summary>
              Limit to specific documents
              {selectedIds.length > 0 ? ` (${selectedIds.length} selected)` : ""}
            </summary>
            <div className="doc-picker-list">
              {allDocuments.map((doc) => (
                <label key={doc.doc_id} className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(doc.doc_id)}
                    onChange={() => toggleId(doc.doc_id)}
                  />
                  <span>{doc.title}</span>
                </label>
              ))}
            </div>
          </details>
        )}
      </form>

      {error && <p className="error-message">{error}</p>}

      {results && (
        <div className="result-list">
          {results.length === 0 ? (
            <p className="muted">No matches.</p>
          ) : (
            results.map((result) => {
              const doc = allDocuments.find((d) => d.doc_id === result.doc_id);
              return (
                <div className="card" key={result.doc_id}>
                  <button
                    className="card-title"
                    onClick={() => onOpenDocument(result.doc_id)}
                  >
                    {doc ? doc.title : `Document #${result.doc_id}`}
                  </button>
                  <p
                    className="snippet"
                    // Trusted: the API only ever emits <mark>/</mark> around
                    // matched terms in this field, nothing else.
                    dangerouslySetInnerHTML={{ __html: result.snippet }}
                  />
                </div>
              );
            })
          )}
        </div>
      )}
    </section>
  );
}
