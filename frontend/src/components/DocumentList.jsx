import { useEffect, useState } from "react";
import { createDocument, listDocuments } from "../api";

export default function DocumentList({ onOpenDocument }) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showNewForm, setShowNewForm] = useState(false);

  function refresh() {
    setLoading(true);
    setError(null);
    listDocuments()
      .then((data) => setDocuments(data.documents))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(refresh, []);

  return (
    <section>
      <div className="section-header">
        <h1>Documents</h1>
        <button className="btn btn-accent" onClick={() => setShowNewForm((v) => !v)}>
          {showNewForm ? "Cancel" : "New Document"}
        </button>
      </div>

      {showNewForm && (
        <NewDocumentForm
          onCreated={(doc) => {
            setShowNewForm(false);
            refresh();
            onOpenDocument(doc.doc_id);
          }}
        />
      )}

      {error && <p className="error-message">{error}</p>}
      {loading ? (
        <p className="muted">Loading…</p>
      ) : documents.length === 0 ? (
        <p className="muted">No documents yet.</p>
      ) : (
        <table className="doc-table">
          <thead>
            <tr>
              <th>Title</th>
              <th className="col-id">ID</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => (
              <tr key={doc.doc_id} onClick={() => onOpenDocument(doc.doc_id)}>
                <td>{doc.title}</td>
                <td className="col-id muted">{doc.doc_id}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function NewDocumentForm({ onCreated }) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    createDocument({ title, content })
      .then(onCreated)
      .catch((err) => setError(err.message))
      .finally(() => setSubmitting(false));
  }

  return (
    <form className="panel new-doc-form" onSubmit={handleSubmit}>
      <label className="field">
        <span>Title</span>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
        />
      </label>
      <label className="field">
        <span>Text</span>
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          rows={10}
          required
        />
      </label>
      {error && <p className="error-message">{error}</p>}
      <button className="btn btn-accent" type="submit" disabled={submitting}>
        {submitting ? "Creating…" : "Create Document"}
      </button>
    </form>
  );
}
