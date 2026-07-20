// Shared by Document Detail (word-level spans) and Bulk Changes (line-level
// spans) — same visual language (struck-through red / underlined green)
// regardless of span granularity.
export default function DiffView({ spans }) {
  return (
    <span className="diff-view">
      {spans.map((span, i) => {
        if (span.type === "del") {
          return (
            <del key={i} className="diff-del">
              {span.text}
            </del>
          );
        }
        if (span.type === "ins") {
          return (
            <ins key={i} className="diff-ins">
              {span.text}
            </ins>
          );
        }
        return <span key={i}>{span.text}</span>;
      })}
    </span>
  );
}
