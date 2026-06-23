import { useEffect, useState } from "react";
import { getOperatingModelCoverage, type CoverageDomain, type OperatingModelCoverageMap } from "./api";

function statusTone(status: string): "good" | "warn" {
  return status === "covered" ? "good" : "warn";
}

function Chips({ items, empty = "n/a" }: { items: string[]; empty?: string }) {
  if (!items.length) return <span className="muted-text">{empty}</span>;
  return (
    <div className="coverage-chip-list">
      {items.map((item) => <span key={item} className="status-pill">{item}</span>)}
    </div>
  );
}

function CoverageMetric({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="result-card coverage-metric-card">
      <div className="result-head"><b>{value}</b></div>
      <p className="result-cite">{label}</p>
      <p className="muted-text">{note}</p>
    </div>
  );
}

function DomainCard({ domain }: { domain: CoverageDomain }) {
  return (
    <div className={`result-card coverage-domain-card coverage-domain-card--${domain.coverage_status}`}>
      <div className="result-head">
        <b>{domain.label}</b>
        <span className={`status-pill status-pill--${statusTone(domain.coverage_status)}`}>{domain.coverage_status}</span>
      </div>
      <p className="result-text">{domain.description}</p>
      <div className="coverage-domain-score">
        <span>{domain.evidence_strength_score}</span>
        <small>evidence strength</small>
      </div>
      <p className="result-cite">{domain.process_count} processes · {domain.lifecycle_stages.length} lifecycle stages</p>
      <Chips items={domain.lifecycle_stages} />
      <p className="result-cite">Missing signals</p>
      <Chips items={domain.missing_signals} />
    </div>
  );
}

export function OperatingModelPage() {
  const [coverage, setCoverage] = useState<OperatingModelCoverageMap | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getOperatingModelCoverage()
      .then((report) => {
        setCoverage(report);
        setError(null);
      })
      .catch(() => {
        setCoverage(null);
        setError("Could not load operating-model coverage.");
      });
  }, []);

  if (error) {
    return (
      <div className="view-stack">
        <div className="page-intro">
          <h1>Operating Model</h1>
          <p>End-to-end retail operating-model coverage from approved process evidence.</p>
        </div>
        <div className="empty-card"><b>Coverage unavailable</b><span>{error}</span></div>
      </div>
    );
  }

  if (!coverage) {
    return (
      <div className="view-stack">
        <div className="page-intro">
          <h1>Operating Model</h1>
          <p>End-to-end retail operating-model coverage from approved process evidence.</p>
        </div>
        <div className="empty-card"><b>Loading coverage</b><span>Building coverage across domains, lifecycle stages and evidence signals.</span></div>
      </div>
    );
  }

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Operating Model</h1>
        <p>Map approved process evidence across retail domains, lifecycle stages, roles, systems and controls.</p>
      </div>

      <div className="analytics-metric-grid">
        <CoverageMetric label="Coverage score" value={`${coverage.coverage_score}%`} note="Weighted covered/partial domain score." />
        <CoverageMetric label="Covered domains" value={String(coverage.covered_domain_count)} note={`${coverage.domain_count} domains in the catalogue.`} />
        <CoverageMetric label="Partial domains" value={String(coverage.partial_domain_count)} note="Matched domains needing more evidence." />
        <CoverageMetric label="Uncovered domains" value={String(coverage.uncovered_domain_count)} note="No approved-source evidence matched yet." />
        <CoverageMetric label="Roles" value={String(coverage.role_count)} note="Unique owners extracted from process records." />
        <CoverageMetric label="Systems" value={String(coverage.system_count)} note="Unique systems extracted from process records." />
      </div>

      <div className="analytics-grid analytics-grid--two">
        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>How to read this</h2>
              <p className="muted-text">Coverage is source-evidence breadth, not final operating-model assurance.</p>
            </div>
          </div>
          <div className="result-list">
            {Object.entries(coverage.rubric).map(([key, value]) => (
              <div className="result-card" key={key}>
                <div className="result-head"><b>{key.replace(/_/g, " ")}</b></div>
                <p className="result-text">{value}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Evidence inventory</h2>
              <p className="muted-text">The raw operating-model ingredients currently visible in approved sources.</p>
            </div>
          </div>
          <div className="coverage-inventory-grid">
            <div><b>{coverage.process_count}</b><span>processes</span></div>
            <div><b>{coverage.role_count}</b><span>roles</span></div>
            <div><b>{coverage.system_count}</b><span>systems</span></div>
            <div><b>{coverage.control_count}</b><span>controls</span></div>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Domain coverage map</h2>
            <p className="muted-text">Retail operating-model domains scored from matched process evidence.</p>
          </div>
          <span className="status-pill">{coverage.domain_count} domains</span>
        </div>
        <div className="coverage-domain-grid">
          {coverage.domains.map((domain) => <DomainCard key={domain.domain_id} domain={domain} />)}
        </div>
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Process coverage matrix</h2>
            <p className="muted-text">Which approved process records support each operating-model domain and lifecycle stage.</p>
          </div>
        </div>
        <div className="table-frame coverage-table-frame">
          <table className="data-table coverage-table">
            <thead>
              <tr><th>Process</th><th>Domains</th><th>Lifecycle</th><th>Roles</th><th>Systems</th><th>Evidence notes</th></tr>
            </thead>
            <tbody>
              {coverage.process_matrix.map((row) => (
                <tr key={row.process_id}>
                  <td><b>{row.process_name}</b><p className="result-cite">{row.source_title}</p></td>
                  <td><Chips items={row.matched_domains} empty="No domain match" /></td>
                  <td><Chips items={row.lifecycle_stages} /></td>
                  <td><Chips items={row.roles} /></td>
                  <td><Chips items={row.systems} /></td>
                  <td>{row.evidence_notes.join("; ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
