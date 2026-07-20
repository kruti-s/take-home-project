// Word-level LCS diff between two texts, for rendering an inline "struck-through
// red / underlined green" view right where changes occur in the flowing document
// text. Computed from the before/after content the API returns (PATCH preview's
// old_content/new_content, and the same fields on each bulk-change result), so a
// one-word edit in a long paragraph highlights just that word — not the whole
// line. This is the single diff renderer used by both Document Detail and Bulk
// Changes.
export function diffWords(oldText, newText) {
  const a = oldText.split(/(\s+)/).filter((t) => t.length > 0);
  const b = newText.split(/(\s+)/).filter((t) => t.length > 0);
  const n = a.length;
  const m = b.length;

  // dp[i][j] = length of the LCS of a[i:] and b[j:]
  const dp = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] =
        a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }

  const spans = [];
  const push = (type, text) => {
    const last = spans[spans.length - 1];
    if (last && last.type === type) last.text += text;
    else spans.push({ type, text });
  };

  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      push("same", a[i]);
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      push("del", a[i]);
      i++;
    } else {
      push("ins", b[j]);
      j++;
    }
  }
  while (i < n) push("del", a[i++]);
  while (j < m) push("ins", b[j++]);

  return spans;
}
