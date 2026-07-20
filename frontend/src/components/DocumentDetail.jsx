import { useEffect, useMemo, useState } from "react";
import { getDocument, patchDocument } from "../api";
import { buildChanges, findOccurrences } from "../lib/changes";
import { diffWords } from "../lib/diff";
import ChangeForm from "./ChangeForm";
import DiffView from "./DiffView";

export default function DocumentDetail({ docId, onBack }) {
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const [operation, setOperation] = useState("replace");
  const [locatorType, setLocatorType] = useState("text");
  const [findText, setFindText] = useState("");
  const [occurrence, setOccurrence] = useState("1");
  const [rangeStart, setRangeStart] = useState("");
  const [rangeEnd, setRangeEnd] = useState("");
  const [newText, setNewText] = useState("");

  const [preview, setPreview] = useState(null); // { changes, oldContent, newContent }
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState(null);

  function refresh() {
    setLoading(true);
    setLoadError(null);
    getDocument(docId)
      .then(setDoc)
      .catch((err) => setLoadError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(refresh, [docId]);

  const matchCount = useMemo(
    () => (doc && locatorType === "text" ? findOccurrences(doc.content, findText).length : 0),
    [doc, locatorType, findText]
  );
  const occurrenceOptions = useMemo(
    () => Array.from({ length: Math.max(matchCount, 1) }, (_, i) => i + 1),
    [matchCount]
  );

  const canSubmit =
    doc &&
    (locatorType === "text"
      ? !!findText
      : locatorType === "range" &&
        rangeStart !== "" &&
        (operation === "insert" || rangeEnd !== "")) &&
    (operation === "delete" || !!newText);

  function currentChanges() {
    return buildChanges({
      operation,
      locatorType,
      findText,
      occurrence,
      rangeStart,
      rangeEnd,
      newText,
    });
  }

  function handlePreview() {
    if (!canSubmit) return;
    setFormError(null);
    const changes = currentChanges();
    setBusy(true);
    patchDocument(docId, { changes, preview: true })
      .then((result) => {
        setPreview({
          changes,
          oldContent: result.old_content,
          newContent: result.new_content,
        });
      })
      .catch((err) => setFormError(err.message))
      .finally(() => setBusy(false));
  }

  function handleAccept() {
    if (!preview) return;
    setFormError(null);
    setBusy(true);
    patchDocument(docId, { changes: preview.changes, preview: false })
      .then(() => {
        setPreview(null);
        setFindText("");
        setRangeStart("");
        setRangeEnd("");
        setNewText("");
        refresh();
      })
      .catch((err) => setFormError(err.message))
      .finally(() => setBusy(false));
  }

  function handleDiscard() {
    setPreview(null);
    setFormError(null);
  }

  if (loading) return <p className="muted">Loading…</p>;
  if (loadError) return <p className="error-message">{loadError}</p>;
  if (!doc) return null;

  const spans = preview ? diffWords(preview.oldContent, preview.newContent) : null;

  return (
    <section>
      <div className="section-header">
        <button className="btn btn-plain" onClick={onBack}>
          ← Documents
        </button>
      </div>

      <h1>{doc.title}</h1>

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
          occurrenceOptions={occurrenceOptions}
          rangeStart={rangeStart}
          onRangeStartChange={setRangeStart}
          rangeEnd={rangeEnd}
          onRangeEndChange={setRangeEnd}
          newText={newText}
          onNewTextChange={setNewText}
          disabled={busy || !!preview}
        />
        {formError && <p className="error-message">{formError}</p>}
        <div className="button-row">
          {!preview ? (
            <button
              className="btn btn-accent"
              onClick={handlePreview}
              disabled={busy || !canSubmit}
            >
              {busy ? "Previewing…" : "Preview Change"}
            </button>
          ) : (
            <>
              <button className="btn btn-accent" onClick={handleAccept} disabled={busy}>
                {busy ? "Applying…" : "Accept"}
              </button>
              <button className="btn btn-plain" onClick={handleDiscard} disabled={busy}>
                Discard
              </button>
            </>
          )}
        </div>
      </div>

      <div className="document-text">
        {spans ? <DiffView spans={spans} /> : doc.content}
      </div>
    </section>
  );
}
