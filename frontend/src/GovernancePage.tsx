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

const SEVERITY_COLOR: Record<string, string> = { high: "#dc2626", medium: "#d97706", low: "#64748b" };
const HEALTH: Record<string, { color: string; label: string }> = {
  green: { color: "#16a34a", label: "Healthy" },
  amber: { color: "#d97706", label: "Needs attention" },
  red: { color: "#dc2626", label: "Critical" },
};

function Dot({ color }: { color: string }) {
  return <span style={{ width: 9, height: 9, borderRadius: "50%", background: color, display: "inline-block", flexShrink: 0 }} />;
}

export function GovernancePage() {
  const [report, setReport] = useState<IntelligenceReport | null>(null);
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState<string | null>(null);

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
  const visibleIssues = allIssues
    .filter((i) => filter === null || i.cat === filter)
    .sort((a, b) => b.score - a.score);

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
          {report ? (
            <span className="status-pill" style={{ display: "inline-flex", alignItems: "center", gap: 7 }}>
              <Dot color={HEALTH[report.health].color} />
              {HEALTH[report.health].label} · {report.total_issues} issues
            </span>
          ) : (
            <span className="status-pill">…</span>
          )}
        </div>
        {/* Click a category to filter the list; click again (or All) to clear. */}
        <div className="result-list" style={{ gridTemplateColumns: "repeat(4, 1fr)", display: "grid", gap: 12 }}>
          {report && (
            <button
              type="button"
              className="result-card"
              style={{ cursor: "pointer", textAlign: "left", boxShadow: filter === null ? "0 0 0 2px #db2777" : undefined }}
              onClick={() => setFilter(null)}
            >
              <div className="result-head"><b>All</b><span className="status-pill">{report.total_issues}</span></div>
            </button>
          )}
          {report &&
            Object.entries(CATEGORY_LABELS).map(([key, label]) => (
              <button
                type="button"
                key={key}
                className="result-card"
                style={{ cursor: "pointer", textAlign: "left", boxShadow: filter === key ? "0 0 0 2px #db2777" : undefined }}
                onClick={() => setFilter((f) => (f === key ? null : key))}
              >
                <div className="result-head">
                  <b>{label}</b>
                  <span className="status-pill">{report.categories[key] ?? 0}</span>
                </div>
              </button>
            ))}
        </div>
        {visibleIssues.length > 0 ? (
          <div className="result-list" style={{ marginTop: 12 }}>
            {visibleIssues.map((i, idx) => (
              <div className="result-card" key={idx}>
                <div className="result-head">
                  <b style={{ display: "inline-flex", alignItems: "center", gap: 7 }}>
                    <Dot color={SEVERITY_COLOR[i.severity]} />
                    {CATEGORY_LABELS[i.cat]} · {i.check.replace(/_/g, " ")}
                  </b>
                  <span className="status-pill">{i.severity}</span>
                </div>
                <p className="result-text">{i.detail}</p>
                <p className="result-cite">{i.source_title}</p>
              </div>
            ))}
          </div>
        ) : report ? (
          <p className="muted-text" style={{ marginTop: 12 }}>
            {filter ? `No ${CATEGORY_LABELS[filter]} issues.` : "No issues detected."}
          </p>
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
