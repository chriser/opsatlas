import { useEffect, useState } from "react";
import {
  acceptIssue,
  approveSource,
  getIntelligence,
  getRegulatoryCandidates,
  listSources,
  rejectSource,
  reviewRegulatoryCandidate,
  simulateRegulatoryImpact,
  type IntelligenceIssue,
  type IntelligenceReport,
  type RegulatoryCandidate,
  type RegulatoryCandidateReport,
  type RegulatoryImpactSimulation,
  type SourceRecord,
} from "./api";
import { ReviewWorkbench } from "./ReviewWorkbench";

const CATEGORY_LABELS: Record<string, string> = {
  compliance: "Compliance",
  consistency: "Consistency",
  correctness: "Correctness",
};

const CATEGORY_DESCRIPTIONS: Record<string, string> = {
  compliance: "Readiness & hygiene: metadata, acronyms, readability.",
  consistency: "Uniformity: duplicates, locale and house-style.",
  correctness: "Accuracy: contradictions, currency and links.",
};

// What leaving (or accepting) each issue costs the assistant — shown so the decision is informed.
const IMPACT: Record<string, string> = {
  conflict: "May cause wrong or inconsistent answers (correctness risk).",
  duplicate: "Redundant citations and less complete answers — alternative evidence gets crowded out.",
  not_ingested: "Content is unusable — related questions get refused (coverage gap).",
  undefined_acronym: "Queries using the full term may miss this document; answers less clear.",
  readability: "Dense text extracts less cleanly into answers.",
  localisation: "Split retrieval matches and inconsistent wording in answers.",
  content_style: "Inconsistent wording; placeholders may surface in answers.",
  metadata_title: "Unhelpful source name in citations (traceability only — no quality impact).",
  broken_link: "A cited reference can’t be followed (traceability only).",
};

const SEVERITY_COLOR: Record<string, string> = { high: "#dc2626", medium: "#d97706", low: "#64748b" };
const HEALTH: Record<string, { color: string; label: string }> = {
  green: { color: "#16a34a", label: "Healthy" },
  amber: { color: "#d97706", label: "Needs attention" },
  red: { color: "#dc2626", label: "Critical" },
};
const REGULATORY_STATUS_GUIDE: Record<string, string> = {
  unreviewed: "New candidate generated from approved ingested knowledge; no human decision has been recorded yet.",
  relevant: "Keep as an in-scope regulatory signal for follow-up analysis and future content prioritisation.",
  needs_research: "Hold for manual validation against authoritative guidance before treating it as confirmed relevant.",
  irrelevant: "Mark as out of scope for this platform direction; it stays auditable but should not drive follow-up work.",
};

function Dot({ color }: { color: string }) {
  return <span style={{ width: 9, height: 9, borderRadius: "50%", background: color, display: "inline-block", flexShrink: 0 }} />;
}

export function GovernancePage() {
  const [report, setReport] = useState<IntelligenceReport | null>(null);
  const [regulatory, setRegulatory] = useState<RegulatoryCandidateReport | null>(null);
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState<IntelligenceIssue | null>(null);
  const [impact, setImpact] = useState<RegulatoryImpactSimulation | null>(null);

  async function refresh() {
    try {
      const [r, s, regulatoryReport] = await Promise.all([getIntelligence(), listSources(), getRegulatoryCandidates()]);
      setReport(r);
      setSources(s);
      setRegulatory(regulatoryReport);
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

  async function accept(i: IntelligenceIssue) {
    setBusy(true);
    try {
      await acceptIssue(i.source_id, i.check, i.detail);
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  async function reviewCandidate(candidate: RegulatoryCandidate, status: "relevant" | "irrelevant" | "needs_research") {
    setBusy(true);
    try {
      await reviewRegulatoryCandidate(candidate.id, status);
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  async function simulateImpact(candidate: RegulatoryCandidate) {
    setBusy(true);
    try {
      setImpact(await simulateRegulatoryImpact(candidate.id));
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
                <p className="result-cite" style={{ marginTop: 4 }}>{CATEGORY_DESCRIPTIONS[key]}</p>
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
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                    <span className="status-pill">{i.severity}</span>
                    <button type="button" className="mini-button" onClick={() => setReviewing(i)}>Review</button>
                    <button type="button" className="text-button" disabled={busy} onClick={() => accept(i)} title="Drop from the list and record as accepted">Accept</button>
                  </span>
                </div>
                {report?.descriptions?.[i.check] ? <p className="result-cite">{report.descriptions[i.check]}</p> : null}
                <p className="result-text">{i.detail}</p>
                {IMPACT[i.check] ? <p className="result-cite" style={{ color: "#b45309" }}>Impact if unresolved: {IMPACT[i.check]}</p> : null}
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

      {reviewing ? (
        <ReviewWorkbench issue={reviewing} onClose={() => setReviewing(null)} onSaved={() => void refresh()} />
      ) : null}

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Regulatory candidate review</h2>
            <p className="muted-text">Candidate themes from approved knowledge sections.</p>
          </div>
          <span className="status-pill">
            {regulatory ? `${regulatory.candidate_count} candidates` : "…"}
          </span>
        </div>
        {regulatory && regulatory.candidates.length ? (
          <>
            <div className="result-list" style={{ marginBottom: 12 }}>
              {Object.entries(REGULATORY_STATUS_GUIDE).map(([status, description]) => (
                <div className="result-card" key={status}>
                  <div className="result-head">
                    <b>{status.replace("_", " ")}</b>
                    <span className="status-pill">{regulatory.review_counts[status] ?? 0}</span>
                  </div>
                  <p className="result-cite">{description}</p>
                </div>
              ))}
            </div>
            <div className="result-list">
              {regulatory.candidates.slice(0, 8).map((candidate) => (
                <div className="result-card" key={candidate.id}>
                  <div className="result-head">
                    <b>{candidate.label}</b>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                      <span className="status-pill">{candidate.confidence}</span>
                      <span className="status-pill">{candidate.review_status.replace("_", " ")}</span>
                    </span>
                  </div>
                  <p className="result-cite">{candidate.source_title} · score {candidate.score}</p>
                  <p className="result-text">{candidate.reason}</p>
                  {candidate.passages.slice(0, 2).map((passage) => (
                    <p className="result-cite" key={`${candidate.id}-${passage.ordinal}`}>
                      {passage.heading}: {passage.excerpt}
                    </p>
                  ))}
                  {candidate.external_matches.length ? (
                    <p className="result-cite">
                      GOV.UK context: {candidate.external_matches.map((match) => `${match.title} v${match.version}`).join("; ")}
                    </p>
                  ) : null}
                  <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
                    <button
                      type="button"
                      className="mini-button"
                      disabled={busy}
                      onClick={() => reviewCandidate(candidate, "relevant")}
                      title={REGULATORY_STATUS_GUIDE.relevant}
                    >
                      Relevant
                    </button>
                    <button
                      type="button"
                      className="mini-button"
                      disabled={busy}
                      onClick={() => simulateImpact(candidate)}
                    >
                      Simulate impact
                    </button>
                    <button
                      type="button"
                      className="mini-button"
                      disabled={busy}
                      onClick={() => reviewCandidate(candidate, "needs_research")}
                      title={REGULATORY_STATUS_GUIDE.needs_research}
                    >
                      Needs research
                    </button>
                    <button
                      type="button"
                      className="text-button"
                      disabled={busy}
                      onClick={() => reviewCandidate(candidate, "irrelevant")}
                      title={REGULATORY_STATUS_GUIDE.irrelevant}
                    >
                      Irrelevant
                    </button>
                  </div>
                </div>
              ))}
            </div>
            {impact ? (
              <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid var(--line)" }}>
                <div className="panel-heading">
                  <div>
                    <h2 style={{ fontSize: 15 }}>Impact simulation</h2>
                    <p className="muted-text">{impact.label} · {impact.affected_source_count} affected sources · {impact.external_context_count} GOV.UK contexts</p>
                  </div>
                  <span className={`status-pill${impact.impact_band === "high" ? " status-pill--warn" : " status-pill--good"}`}>
                    {impact.impact_score} · {impact.impact_band}
                  </span>
                </div>
                <div className="result-list" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 12 }}>
                  <div className="result-card">
                    <div className="result-head"><b>{impact.review_status.replace("_", " ")}</b></div>
                    <p className="result-cite">Review state</p>
                  </div>
                  <div className="result-card">
                    <div className="result-head"><b>{impact.affected_process_areas.length}</b></div>
                    <p className="result-cite">Process areas</p>
                  </div>
                  <div className="result-card">
                    <div className="result-head"><b>{impact.external_context_count}</b></div>
                    <p className="result-cite">External matches</p>
                  </div>
                </div>
                <div className="result-list" style={{ gap: 10, marginBottom: 12 }}>
                  {impact.recommended_actions.map((action) => (
                    <div className="result-card" key={action}>
                      <p className="result-text">{action}</p>
                    </div>
                  ))}
                </div>
                <div className="table-frame">
                  <table className="data-table regulatory-impact-table">
                    <colgroup>
                      <col style={{ width: "18%" }} />
                      <col style={{ width: "10%" }} />
                      <col style={{ width: "20%" }} />
                      <col style={{ width: "30%" }} />
                      <col style={{ width: "22%" }} />
                    </colgroup>
                    <thead>
                      <tr><th>Source</th><th>Impact</th><th>Process areas</th><th>Evidence</th><th>Action</th></tr>
                    </thead>
                    <tbody>
                      {impact.affected_sources.map((source) => (
                        <tr key={source.source_id}>
                          <td>{source.source_title}</td>
                          <td>{source.impact_score} · {source.impact_band}</td>
                          <td>{source.process_areas.join("; ")}</td>
                          <td>
                            {source.passages.slice(0, 2).map((passage) => (
                              <p className="result-cite" key={`${source.source_id}-${passage.ordinal}`}>
                                {passage.heading}: {passage.excerpt}
                              </p>
                            ))}
                          </td>
                          <td>{source.recommended_action}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="result-cite" style={{ marginTop: 10 }}>{impact.assumptions.join(" ")}</p>
              </div>
            ) : null}
          </>
        ) : regulatory ? (
          <p className="muted-text">No regulatory candidates detected in approved ingested sources.</p>
        ) : (
          <p className="muted-text">Loading regulatory candidates…</p>
        )}
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
                <tr><th>Title</th><th>Issues</th><th>State</th><th>Approval</th><th /></tr>
              </thead>
              <tbody>
                {sources.map((s) => {
                  const sum = report?.source_summary?.[s.id];
                  return (
                  <tr key={s.id}>
                    <td>{s.title}</td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      {sum?.active ? <span className="status-pill status-pill--warn" title="Actionable issues">{sum.active} to review</span> : null}
                      {sum?.structural ? <span className="status-pill" title="Boilerplate shared across documents (titles, disclaimers) — expected, excluded from the list">{sum.structural} structural</span> : null}
                      {sum?.accepted ? <span className="status-pill" title="Issues you accepted">{sum.accepted} accepted</span> : null}
                      {!sum?.active && !sum?.structural && !sum?.accepted ? <span className="muted-text">—</span> : null}
                    </td>
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
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
