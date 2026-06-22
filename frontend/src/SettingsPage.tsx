import { useEffect, useState } from "react";
import { getHealth, getTraces, type AuditRecord, type HealthResponse } from "./api";

function fmtTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

export function SettingsPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [traces, setTraces] = useState<AuditRecord[]>([]);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null));
    getTraces().then(setTraces).catch(() => setTraces([]));
  }, []);

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Settings</h1>
        <p>Models and diagnostics. The audit trace explains how each answer was produced.</p>
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
          <div className="result-list" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
            {Object.entries(health.models).map(([k, v]) => (
              <div className="result-card" key={k}>
                <div className="result-head"><b>{k}</b></div>
                <p className="result-cite">{v}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="muted-text">Backend offline.</p>
        )}
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Audit trace</h2>
            <p className="muted-text">Recent answers with mode, validation, latency and evidence used.</p>
          </div>
          <span className="status-pill">{traces.length}</span>
        </div>
        {traces.length === 0 ? (
          <p className="muted-text">No answers traced yet.</p>
        ) : (
          <div className="table-frame">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Time</th><th>Question</th><th>Mode</th><th>Confidence</th><th>Grounding</th><th>Score</th><th>Faithfulness</th><th>Latency</th><th>Evidence</th>
                </tr>
              </thead>
              <tbody>
                {traces.map((t, i) => (
                  <tr key={i}>
                    <td>{fmtTime(t.timestamp)}</td>
                    <td>{t.question.slice(0, 50)}</td>
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
