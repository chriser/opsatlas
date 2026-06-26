import { useState } from "react";
import { askQuestion, resolveProcessDiagram, type AnswerResponse, type ProcessDiagramContext } from "./api";
import { Markdown } from "./Markdown";
import { ProcessDiagramPanel } from "./ProcessDiagramPanel";

export function AskPage() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<AnswerResponse | null>(null);
  const [diagram, setDiagram] = useState<ProcessDiagramContext | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [diagramBusy, setDiagramBusy] = useState(false);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!question.trim()) return;
    const asked = question.trim();
    setBusy(true);
    setDiagram(null);
    setError(null);
    try {
      const answer = await askQuestion(asked);
      setResult(answer);
      setBusy(false);
      setDiagramBusy(true);
      try {
        setDiagram(await resolveProcessDiagram(asked, answer.citations));
      } catch (err) {
        setDiagram({
          status: "unavailable",
          message: err instanceof Error ? err.message : "Could not load process map.",
          process_id: "",
          process_name: "",
          source_title: "",
          service_url: "",
          chart: null,
          svg: "",
        });
      } finally {
        setDiagramBusy(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed.");
      setResult(null);
      setDiagram(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Written Query</h1>
        <p>Ask a written question and receive a grounded answer drawn only from the approved knowledge base, with citations.</p>
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
          <div className="answer-diagram-grid" style={{ marginTop: 16 }}>
            <div>
              <div className={`answer-card${result.refused ? " answer-card--refused" : ""}`}>
                <div className="answer-text"><Markdown text={result.answer} /></div>
              </div>
              <p className="muted-text" style={{ marginTop: 10, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                {result.refused ? (
                  <>No grounded answer · mode: <b>{result.mode}</b></>
                ) : (
                  <>
                    <span
                      className={`status-pill${result.confidence === "grounded" ? " status-pill--good" : " status-pill--warn"}`}
                    >
                      {result.confidence === "grounded" ? "grounded" : "unverified"}
                    </span>
                    <span>mode: <b>{result.mode}</b></span>
                    {result.grounding && result.grounding !== "n/a" ? (
                      <span>· grounding: <b>{result.grounding}</b> ({Math.round(result.grounding_score * 100)}%)</span>
                    ) : null}
                    {result.faithfulness && result.faithfulness !== "n/a" ? (
                      <span>· faithfulness: <b>{result.faithfulness.replace("_", " ")}</b></span>
                    ) : null}
                  </>
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
            <ProcessDiagramPanel diagram={diagram} loading={diagramBusy} />
          </div>
        ) : null}
      </div>
    </div>
  );
}
