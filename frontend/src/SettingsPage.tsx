import { useEffect, useState } from "react";
import {
  getScorecard,
  getHealth,
  getProcessDiagramServiceStatus,
  getTraces,
  startProcessDiagramService,
  type AuditRecord,
  type HealthResponse,
  type ProcessDiagramServiceStatus,
  type Scorecard,
} from "./api";

function fmtTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

export function SystemPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [diagramStatus, setDiagramStatus] = useState<ProcessDiagramServiceStatus | null>(null);
  const [diagramBusy, setDiagramBusy] = useState(false);
  const [diagramError, setDiagramError] = useState<string | null>(null);
  const [traces, setTraces] = useState<AuditRecord[]>([]);
  const [scorecard, setScorecard] = useState<Scorecard | null>(null);
  const [knowledgeGapsOpen, setKnowledgeGapsOpen] = useState(false);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null));
    getProcessDiagramServiceStatus().then(setDiagramStatus).catch(() => setDiagramStatus(null));
    getTraces().then(setTraces).catch(() => setTraces([]));
    getScorecard().then(setScorecard).catch(() => setScorecard(null));
  }, []);

  async function onStartDiagramService() {
    setDiagramBusy(true);
    setDiagramError(null);
    try {
      setDiagramStatus(await startProcessDiagramService());
    } catch (err) {
      setDiagramError(err instanceof Error ? err.message : "Could not start diagram service.");
    } finally {
      setDiagramBusy(false);
    }
  }

  async function onRefreshDiagramService() {
    setDiagramBusy(true);
    setDiagramError(null);
    try {
      setDiagramStatus(await getProcessDiagramServiceStatus());
    } catch (err) {
      setDiagramError(err instanceof Error ? err.message : "Could not refresh diagram service status.");
    } finally {
      setDiagramBusy(false);
    }
  }

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>System</h1>
        <p>Models, diagnostics and platform signals. The audit trace explains how each answer was produced.</p>
      </div>

      <div className="panel settings-collapsible-panel">
        <div className="panel-heading">
          <div>
            <h2>Knowledge gaps</h2>
            <p className="muted-text">Questions the assistant could not answer from approved knowledge.</p>
          </div>
          <div className="settings-panel-actions">
            <span className={`status-pill${scorecard && scorecard.knowledge_gaps.length ? " status-pill--warn" : " status-pill--good"}`}>
              {scorecard ? scorecard.knowledge_gaps.length : 0}
            </span>
            <button
              type="button"
              className="secondary-button settings-collapse-button"
              aria-expanded={knowledgeGapsOpen}
              onClick={() => setKnowledgeGapsOpen((open) => !open)}
            >
              {knowledgeGapsOpen ? "Hide" : "Show"}
            </button>
          </div>
        </div>
        {knowledgeGapsOpen ? (
          scorecard && scorecard.knowledge_gaps.length > 0 ? (
            <div className="result-list">
              {scorecard.knowledge_gaps.map((question, index) => (
                <div className="result-card" key={`${question}-${index}`}>
                  <p className="result-text">{question}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted-text">No knowledge gaps detected yet.</p>
          )
        ) : (
          <p className="muted-text settings-collapsed-note">
            {scorecard && scorecard.knowledge_gaps.length > 0
              ? "Expand to review the latest unanswered or weakly supported questions."
              : "No knowledge gaps detected yet."}
          </p>
        )}
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Models</h2>
            <p className="muted-text">Active local model runtime (swappable by configuration).</p>
          </div>
          <span className={`status-pill${health ? " status-pill--good" : ""}`}>{health ? "online" : "…"}</span>
        </div>
        {health?.models ? (
          <>
            <div className="result-list" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
              {Object.entries(health.models).map(([k, v]) => (
                <div className="result-card" key={k}>
                  <div className="result-head"><b>{k}</b></div>
                  <p className="result-cite">{v}</p>
                </div>
              ))}
            </div>
            <div className="result-card settings-service-card">
              <div className="result-head">
                <div>
                  <b>Process diagram service</b>
                  <p className="result-cite">{diagramStatus?.service_url ?? "http://127.0.0.1:5300"}</p>
                </div>
                <span className={`status-pill${diagramStatus?.running ? " status-pill--good" : " status-pill--warn"}`}>
                  {diagramStatus?.running ? "running" : "stopped"}
                </span>
              </div>
              <p className="result-text">{diagramStatus?.message ?? "Status not checked yet."}</p>
              {diagramStatus?.log_path ? <p className="result-cite">Log: {diagramStatus.log_path}</p> : null}
              <div className="settings-service-actions">
                <button
                  type="button"
                  className="primary-button"
                  onClick={() => void onStartDiagramService()}
                  disabled={diagramBusy || diagramStatus?.running || diagramStatus?.startable === false}
                >
                  {diagramBusy ? "Starting..." : "Start service"}
                </button>
                <button type="button" className="secondary-button" onClick={() => void onRefreshDiagramService()} disabled={diagramBusy}>
                  Refresh status
                </button>
              </div>
              {diagramError ? <p className="muted-text" style={{ color: "var(--red)" }}>{diagramError}</p> : null}
            </div>
          </>
        ) : (
          <p className="muted-text">Backend offline.</p>
        )}
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Audit trace</h2>
            <p className="muted-text">Recent questions with outcome, mode, validation, latency and evidence used.</p>
          </div>
          <span className="status-pill">{traces.length}</span>
        </div>
        <p className="muted-text" style={{ marginTop: 0 }}>
          Generated answer text is not stored in traces; diagnostics keep the question, outcome and evidence metadata.
        </p>
        {traces.length === 0 ? (
          <p className="muted-text">No answers traced yet.</p>
        ) : (
          <div className="table-frame">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Time</th><th>Question</th><th>Outcome</th><th>Mode</th><th>Confidence</th><th>Grounding</th><th>Score</th><th>Faithfulness</th><th>Latency</th><th>Evidence</th>
                </tr>
              </thead>
              <tbody>
                {traces.map((t, i) => (
                  <tr key={i}>
                    <td>{fmtTime(t.timestamp)}</td>
                    <td>{t.question.slice(0, 50)}</td>
                    <td>
                      <span className={`status-pill${t.outcome === "answered" ? " status-pill--good" : " status-pill--warn"}`}>
                        {t.outcome ?? (t.refused ? "refused" : "answered")}
                      </span>
                    </td>
                    <td>{t.category ? `guardrail (${t.category})` : t.mode}</td>
                    <td>{t.confidence}</td>
                    <td>{t.grounding}</td>
                    <td>{Math.round((t.grounding_score ?? 0) * 100)}%</td>
                    <td>{(t.faithfulness || "n/a").replace("_", " ")}</td>
                    <td>{t.latency_ms} ms</td>
                    <td>{t.evidence.length}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
