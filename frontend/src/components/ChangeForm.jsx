const NUMBERED_OCCURRENCES = [1, 2, 3, 4, 5];
const ORDINALS = { 1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th" };

const NEW_TEXT_LABEL = {
  replace: "Replace with",
  insert: "Text to insert",
};

// Shared change-building form used by both Document Detail (single document)
// and Bulk Changes (many documents). Covers every shape PATCH/bulk-changes
// support: operation (replace/insert/delete) x locator (by text-match-and-
// occurrence, or by numeric start/end position). "insert" is position-only —
// the backend rejects an occurrence-based insert — so the form hides the
// text-match locator when the operation is "insert".
export default function ChangeForm({
  operation,
  onOperationChange,
  locatorType,
  onLocatorTypeChange,
  findText,
  onFindChange,
  occurrence,
  onOccurrenceChange,
  occurrenceOptions,
  rangeStart,
  onRangeStartChange,
  rangeEnd,
  onRangeEndChange,
  newText,
  onNewTextChange,
  disabled,
}) {
  const options = occurrenceOptions || NUMBERED_OCCURRENCES;
  const isInsert = operation === "insert";
  const isRangeInsert = locatorType === "range" && isInsert;

  return (
    <div className="change-form">
      <div className="change-form-row">
        <label className="field field-narrow">
          <span>Operation</span>
          <select
            value={operation}
            onChange={(e) => onOperationChange(e.target.value)}
            disabled={disabled}
          >
            <option value="replace">Replace</option>
            <option value="insert">Insert</option>
            <option value="delete">Delete</option>
          </select>
        </label>
        <label className="field field-narrow">
          <span>Locate by</span>
          <select
            value={locatorType}
            onChange={(e) => onLocatorTypeChange(e.target.value)}
            disabled={disabled || isInsert}
          >
            {/* insert is position-only — no text-match/occurrence locator */}
            {!isInsert && <option value="text">Text match</option>}
            <option value="range">Position</option>
          </select>
        </label>
      </div>

      <div className="change-form-row">
        {locatorType === "text" ? (
          <>
            <label className="field">
              <span>Find</span>
              <input
                type="text"
                value={findText}
                onChange={(e) => onFindChange(e.target.value)}
                placeholder="Text to find"
                disabled={disabled}
              />
            </label>
            <label className="field field-narrow">
              <span>Occurrence</span>
              <select
                value={occurrence}
                onChange={(e) => onOccurrenceChange(e.target.value)}
                disabled={disabled}
              >
                {options.map((n) => (
                  <option key={n} value={n}>
                    {ORDINALS[n] || `${n}th`}
                  </option>
                ))}
                <option value="all">All</option>
              </select>
            </label>
          </>
        ) : isRangeInsert ? (
          <label className="field field-narrow">
            <span>Position</span>
            <input
              type="number"
              min="0"
              value={rangeStart}
              onChange={(e) => onRangeStartChange(e.target.value)}
              placeholder="e.g. 100"
              disabled={disabled}
            />
          </label>
        ) : (
          <>
            <label className="field field-narrow">
              <span>Start</span>
              <input
                type="number"
                min="0"
                value={rangeStart}
                onChange={(e) => onRangeStartChange(e.target.value)}
                placeholder="e.g. 100"
                disabled={disabled}
              />
            </label>
            <label className="field field-narrow">
              <span>End</span>
              <input
                type="number"
                min="0"
                value={rangeEnd}
                onChange={(e) => onRangeEndChange(e.target.value)}
                placeholder="e.g. 108"
                disabled={disabled}
              />
            </label>
          </>
        )}

        {operation !== "delete" && (
          <label className="field">
            <span>{NEW_TEXT_LABEL[operation]}</span>
            <input
              type="text"
              value={newText}
              onChange={(e) => onNewTextChange(e.target.value)}
              placeholder={operation === "insert" ? "Text to insert" : "Replacement text"}
              disabled={disabled}
            />
          </label>
        )}
      </div>
    </div>
  );
}
