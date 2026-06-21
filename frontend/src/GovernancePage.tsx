import { useEffect, useState } from "react";
import {
  approveSource,
  getIntelligence,
  listSources,
  rejectSource,
  type IntelligenceReport,
  type SourceRecord,
} from "./api";

const CATEGORY_LABELS: Record<string, string> = {
  compliance: "Compliance",
  consistency: "Consistency",
  correctness: "Correctness",
};

export function GovernancePage() {
  const [report, setReport] = useState<IntelligenceReport | null>(null);
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      const [r, s] = await Promise.all([getIntelligence(), listSources()]);
      setReport(r);
      setSources(s);
      setError(null);
    } catch {
      setError("Could not reach the backend.");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function act(fn: (id: string) => Promise<void>, id: string) {
    setBusy(true);
    try {
      await fn(id);
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  const allIssues = report ? Object.entries(report.issues).flatMap(([cat, list]) => list.map((i) => ({ cat, ...i }))) : [];

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Governance</h1>
        <p>Knowledge intelligence and the human-in-the-loop approval gate. Only approved sources are queryable.</p>
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Knowledge Intelligence Overview</h2>
            <p className="muted-text">Automated content-quality checks.</p>
          </div>
          <span className={`status-pill${report && report.total_issues > 0 ? " status-pill--warn" : " status-pill--good"}`}>
            {report ? `${report.total_issues} issues to resolve` : "…"}
          </span>
        </div>
        <div className="result-list" style={{ gridTemplateColumns: "repeat(3, 1fr)", display: "grid", gap: 12 }}>
          {report &&
            Object.entries(CATEGORY_LABELS).map(([key, label]) => (
              <div className="result-card" key={key}>
                <div className="result-head">
                  <b>{label}</b>
                  <span className="status-pill">{report.categories[key] ?? 0}</span>
                </div>
              </div>
            ))}
        </div>
        {allIssues.length > 0 ? (
          <div className="result-list" style={{ marginTop: 12 }}>
            {allIssues.map((i, idx) => (
              <div className="result-card" key={idx}>
                <div className="result-head">
                  <b>{CATEGORY_LABELS[i.cat]} · {i.check.replace(/_/g, " ")}</b>
                  <span className="status-pill">{i.source_title}</span>
                </div>
                <p className="result-text">{i.detail}</p>
              </div>
            ))}
          </div>
        ) : report ? (
          <p className="muted-text" style={{ marginTop: 12 }}>No issues detected.</p>
        ) : null}
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Source approval</h2>
            <p className="muted-text">Approve a source before the assistant can use it.</p>
          </div>
        </div>
        {error ? <p className="muted-text" style={{ color: "var(--red)" }}>{error}</p> : null}
        {sources.length === 0 ? (
          <div className="empty-card"><b>No sources</b><span>Upload and ingest documents first.</span></div>
        ) : (
          <div className="table-frame">
            <table className="data-table">
              <thead>
                <tr><th>Title</th><th>State</th><th>Approval</th><th /></tr>
              </thead>
              <tbody>
                {sources.map((s) => (
                  <tr key={s.id}>
                    <td>{s.title}</td>
                    <td>{s.processing_state}</td>
                    <td>
                      <span className={`status-pill${s.approval_status === "approved" ? " status-pill--good" : s.approval_status === "rejected" ? " status-pill--warn" : ""}`}>
                        {s.approval_status}
                      </span>
                    </td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      {s.approval_status !== "approved" ? (
                        <button type="button" className="mini-button" disabled={busy} onClick={() => act(approveSource, s.id)}>Approve</button>
                      ) : null}
                      {s.approval_status !== "rejected" ? (
                        <button type="button" className="text-button" disabled={busy} onClick={() => act(rejectSource, s.id)}>Reject</button>
                      ) : null}
                    </td>
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
