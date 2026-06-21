import { useState } from "react";
import { askQuestion, type AnswerResponse } from "./api";

export function AskPage() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<AnswerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!question.trim()) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await askQuestion(question));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed.");
      setResult(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Ask the assistant</h1>
        <p>Grounded answers drawn only from the approved knowledge base, with citations.</p>
      </div>

      <div className="panel">
        <form className="search-row" onSubmit={onSubmit}>
          <input
            className="search-input"
            type="text"
            placeholder="e.g. What checks must pass before a supplier can be onboarded?"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          />
          <button type="submit" className="primary-button" disabled={busy || !question.trim()}>
            {busy ? "Thinking…" : "Ask"}
          </button>
        </form>

        {error ? (
          <p className="muted-text" style={{ color: "var(--red)", marginTop: 12 }}>
            {error}
          </p>
        ) : null}

        {busy ? <p className="muted-text" style={{ marginTop: 14 }}>Generating a grounded answer…</p> : null}

        {result && !busy ? (
          <div style={{ marginTop: 16 }}>
            <div className={`answer-card${result.refused ? " answer-card--refused" : ""}`}>
              <p className="answer-text">{result.answer}</p>
            </div>
            <p className="muted-text" style={{ marginTop: 10 }}>
              {result.refused ? (
                <>No grounded answer · mode: <b>{result.mode}</b></>
              ) : (
                <>mode: <b>{result.mode}</b></>
              )}
            </p>
            {result.citations.length > 0 ? (
              <div style={{ marginTop: 8 }}>
                <p className="muted-text" style={{ marginBottom: 8, fontWeight: 700 }}>Sources</p>
                <div className="result-list">
                  {result.citations.map((c, i) => (
                    <div className="result-card" key={`${c.source_id}-${c.ordinal}-${i}`}>
                      <div className="result-head">
                        <b>{c.heading}</b>
                        <span className="status-pill">section {c.ordinal}</span>
                      </div>
                      <p className="result-cite">{c.source_title}</p>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}
