import { useState } from "react";
import { searchKnowledge, type SearchResult } from "./api";

export function RetrievalPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [mode, setMode] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const res = await searchKnowledge(query, 5);
      setResults(res.results);
      setMode(res.mode);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed.");
      setResults(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Citation Check</h1>
        <p>Inspect the retrieved passages behind an answer and confirm which source sections support the response.</p>
      </div>

      <div className="panel">
        <form className="search-row" onSubmit={onSubmit}>
          <input
            className="search-input"
            type="text"
            placeholder="Ask about the process, e.g. what checks are needed before onboarding a supplier?"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button type="submit" className="primary-button" disabled={busy || !query.trim()}>
            {busy ? "Searching…" : "Search"}
          </button>
        </form>

        {error ? (
          <p className="muted-text" style={{ color: "var(--red)", marginTop: 12 }}>
            {error}
          </p>
        ) : null}

        {results !== null ? (
          <div style={{ marginTop: 16 }}>
            {results.length === 0 ? (
              <div className="empty-card">
                <b>No matching passages</b>
                <span>
                  {mode === "empty"
                    ? "Nothing has been ingested yet — upload a document and click Ingest first."
                    : "No section matched that query. Try different wording."}
                </span>
              </div>
            ) : (
              <>
                <p className="muted-text" style={{ marginBottom: 10 }}>
                  {results.length} passages · retrieval mode: <b>{mode}</b>
                </p>
                <div className="result-list">
                  {results.map((r, i) => (
                    <div className="result-card" key={`${r.source_id}-${r.ordinal}-${i}`}>
                      <div className="result-head">
                        <b>{r.heading}</b>
                        <span className="status-pill">score {r.score}</span>
                      </div>
                      <p className="result-text">{r.text}</p>
                      <p className="result-cite">
                        {r.source_title} · section {r.ordinal}
                      </p>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
