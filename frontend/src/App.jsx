import { useState } from "react";
import DocumentList from "./components/DocumentList";
import DocumentDetail from "./components/DocumentDetail";
import Search from "./components/Search";
import BulkChanges from "./components/BulkChanges";

const TABS = [
  { key: "list", label: "Documents" },
  { key: "search", label: "Search" },
  { key: "bulk", label: "Bulk Changes" },
];

export default function App() {
  const [view, setView] = useState("list");
  const [selectedDocId, setSelectedDocId] = useState(null);

  function openDocument(docId) {
    setSelectedDocId(docId);
    setView("detail");
  }

  return (
    <div className="app">
      <header className="topnav">
        <span className="brand">Document Assessment</span>
        <nav className="tabs">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              className={
                "tab" +
                (view === tab.key || (tab.key === "list" && view === "detail")
                  ? " tab-active"
                  : "")
              }
              onClick={() => setView(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="content">
        {view === "list" && <DocumentList onOpenDocument={openDocument} />}
        {view === "detail" && selectedDocId != null && (
          <DocumentDetail docId={selectedDocId} onBack={() => setView("list")} />
        )}
        {view === "search" && <Search onOpenDocument={openDocument} />}
        {view === "bulk" && <BulkChanges />}
      </main>
    </div>
  );
}
