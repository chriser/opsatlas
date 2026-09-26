import { useEffect, useState } from "react";
import {
  approveSource,
  getGovernanceReanalysis,
  getRegulatoryCandidates,
  listSources,
  reanalyseGovernance,
  rejectSource,
  reviewRegulatoryCandidate,
  simulateRegulatoryImpact,
  type GovernanceReanalysisReport,
  type RegulatoryCandidate,
  type RegulatoryCandidateReport,
  type RegulatoryImpactSimulation,
  type SourceRecord,
} from "./api";
import { Markdown } from "./Markdown";
import { TibiGovernancePanel } from "./TibiGovernancePanel";

// OpsAtlas Sales governs its records with the statement-level review and Tibi (the panel below). The document-pair
// Internal Source Review and the External Source Review were removed on 26 September 2026; they remain in
// OpsAtlas Classic (docs/opsatlas-classic-and-sales.md).

const REGULATORY_STATUS_GUIDE: Record<string, string> = {
  unreviewed: "New candidate generated from approved ingested knowledge; no human decision has been recorded yet.",
  relevant: "Keep as an in-scope regulatory signal for follow-up analysis and future content prioritisation.",
  needs_research: "Hold for manual validation against authoritative guidance before treating it as confirmed relevant.",
  irrelevant: "Mark as out of scope for this platform direction; it stays auditable but should not drive follow-up work.",
};

function formatDate(value?: string) {
  if (!value) return "Not run";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function GovernancePage({ onResolveWithTibi }: { onResolveWithTibi?: () => void } = {}) {
  const [regulatory, setRegulatory] = useState<RegulatoryCandidateReport | null>(null);
  const [reanalysis, setReanalysis] = useState<GovernanceReanalysisReport | null>(null);
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [reanalysisBusy, setReanalysisBusy] = useState(false);
  const [impact, setImpact] = useState<RegulatoryImpactSimulation | null>(null);

  async function refresh() {
    try {
      const [s, regulatoryReport, reanalysisReport] = await Promise.all([listSources(), getRegulatoryCandidates(), getGovernanceReanalysis()]);
      setSources(s);
      setRegulatory(regulatoryReport);
      setReanalysis(reanalysisReport);
      setError(null);
    } catch {
      setError("Could not reach the backend.");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function runReanalysis() {
    setReanalysisBusy(true);
    setBusy(true);
    try {
      setReanalysis(await reanalyseGovernance());
      await refresh();
    } finally {
      setReanalysisBusy(false);
      setBusy(false);
    }
  }

  async function act(fn: (id: string) => Promise<void>, id: string) {
    setBusy(true);
    try {
      await fn(id);
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

  const coverage = reanalysis?.coverage ?? [];
  const coveragePreview = coverage.slice(0, 6);
  const reanalysisStatus = reanalysis?.needs_reanalysis ? "Needs re-analysis" : reanalysis?.has_run ? "Current" : "Not run";
  const reanalysisStatusClass = reanalysis?.has_run && !reanalysis.needs_reanalysis ? "status-pill status-pill--good" : "status-pill status-pill--warn";

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Governance</h1>
        <p>Knowledge intelligence and the human-in-the-loop approval gate. Only approved sources are queryable.</p>
      </div>

      {onResolveWithTibi ? <TibiGovernancePanel onResolveWithTibi={onResolveWithTibi} onChanged={() => void refresh()} /> : null}

      <details className="legacy-governance-details" style={{ order: 99 }}>
        <summary>Legacy regulatory signal triage</summary>
      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Regulatory signals</h2>
            <p className="muted-text">Keyword and theme triage from approved knowledge sections.</p>
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
                      External context: {candidate.external_matches.map((match) => `${match.title} v${match.version}`).join("; ")}
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
                    <p className="muted-text">{impact.label} · {impact.affected_source_count} affected sources · {impact.external_context_count} external contexts</p>
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
                              <div className="regulatory-evidence-block" key={`${source.source_id}-${passage.ordinal}`}>
                                <p className="result-cite">{passage.heading}</p>
                                <Markdown text={passage.excerpt} />
                              </div>
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
      </details>

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

      <details className="legacy-governance-details">
        <summary>Legacy re-analysis audit snapshot</summary>
      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Governance re-analysis</h2>
            <p className="muted-text">
              Last analysed: {formatDate(reanalysis?.analysed_at)}
            </p>
          </div>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
            <span className={reanalysisStatusClass}>{reanalysisStatus}</span>
            <button type="button" className="mini-button" disabled={busy || reanalysisBusy} onClick={runReanalysis}>
              {reanalysisBusy ? "Running..." : "Re-analyse Governance"}
            </button>
          </span>
        </div>
        {reanalysis?.has_run ? (
          <>
            <div className="governance-reanalysis-grid">
              <div className="result-card">
                <div className="result-head"><b>{reanalysis.external_snapshot_count ?? 0}</b></div>
                <p className="result-cite">External snapshots</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{reanalysis.external_matched_count ?? 0}</b></div>
                <p className="result-cite">Matched external sources</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{reanalysis.external_unmatched_count ?? 0}</b></div>
                <p className="result-cite">Unmatched external sources</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{reanalysis.new_issue_count ?? 0}</b></div>
                <p className="result-cite">New active issues</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{reanalysis.new_candidate_count ?? 0}</b></div>
                <p className="result-cite">New candidates</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{reanalysis.previous_decisions_preserved ?? 0}</b></div>
                <p className="result-cite">Preserved decisions</p>
              </div>
            </div>
            {reanalysis.needs_reanalysis ? (
              <p className="result-cite" style={{ marginTop: 10, color: "#b45309" }}>
                Pending: {reanalysis.pending_external_snapshot_count} external snapshot(s), {reanalysis.pending_internal_change_count} internal source change(s).
              </p>
            ) : null}
            {coveragePreview.length ? (
              <div className="result-list governance-coverage-list">
                {coveragePreview.map((item) => (
                  <div className="result-card" key={item.snapshot_id}>
                    <div className="result-head">
                      <b>{item.title}</b>
                      <span className={`status-pill${item.status === "matched" ? " status-pill--good" : ""}`}>
                        {item.status === "matched" ? `${item.matched_candidate_count} match${item.matched_candidate_count === 1 ? "" : "es"}` : "No match"}
                      </span>
                    </div>
                    <p className="result-cite">{item.provider} v{item.version} · {item.url}</p>
                    {item.matched_candidates.length ? (
                      <p className="result-text">
                        {item.matched_candidates.map((candidate) => `${candidate.label} in ${candidate.source_title}`).join("; ")}
                      </p>
                    ) : null}
                    {item.matched_terms.length ? (
                      <p className="result-cite">Terms: {item.matched_terms.slice(0, 10).join(", ")}</p>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted-text" style={{ marginTop: 12 }}>
                No external snapshots were included in the latest run.
              </p>
            )}
          </>
        ) : reanalysis ? (
          <>
            <p className="muted-text">Run re-analysis to create the first audit snapshot.</p>
            {reanalysis.needs_reanalysis ? (
              <p className="result-cite" style={{ marginTop: 10, color: "#b45309" }}>
                Pending: {reanalysis.pending_external_snapshot_count} external snapshot(s), {reanalysis.pending_internal_change_count} internal source change(s).
              </p>
            ) : null}
          </>
        ) : (
          <p className="muted-text">Loading re-analysis status...</p>
        )}
      </div>
      </details>
    </div>
  );
}
