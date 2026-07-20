// Mirrors the backend's occurrence search exactly (app/services/document_service.py
// _resolve_change_location): sequential, overlap-tolerant — after a match at `idx`,
// the next search starts at `idx + 1`, not `idx + target.length`. Keeping this in
// sync with the backend means the occurrence dropdown always reflects what the API
// will actually resolve.
export function findOccurrences(text, target) {
  if (!target) return [];
  const indices = [];
  let searchFrom = 0;
  while (true) {
    const idx = text.indexOf(target, searchFrom);
    if (idx === -1) break;
    indices.push(idx);
    searchFrom = idx + 1;
  }
  return indices;
}

// Builds the single-element `changes` array PATCH/bulk-changes expect. The API
// is the source of truth for how a change is applied — including "all"
// occurrences, which the backend expands per-document — so this just packages
// the form values into one change; it never expands or resolves anything itself.
//
// `params`:
//   operation:   "replace" | "insert" | "delete"
//   locatorType: "text" | "range" (always "range" for insert)
//   findText, occurrence: for locatorType "text" (occurrence: a 1-based number, or "all")
//   rangeStart, rangeEnd: for locatorType "range" (rangeEnd ignored for "insert" —
//                the backend requires start === end for insert-by-range, i.e. a point)
//   newText:     new content; forced to "" for "delete" regardless of what's passed
export function buildChanges({
  operation,
  locatorType,
  findText,
  occurrence,
  rangeStart,
  rangeEnd,
  newText,
}) {
  const effectiveNewText = operation === "delete" ? "" : newText;

  if (locatorType === "range") {
    const start = Number(rangeStart);
    const end = operation === "insert" ? start : Number(rangeEnd);
    return [{ operation, range: { start, end }, new_text: effectiveNewText }];
  }

  // locatorType === "text" — only replace/delete reach here (never insert).
  // occurrence is either a number or the literal "all"; the backend applies it.
  const targetOccurrence = occurrence === "all" ? "all" : Number(occurrence);
  return [
    {
      operation,
      target: { text: findText, occurrence: targetOccurrence },
      new_text: effectiveNewText,
    },
  ];
}
