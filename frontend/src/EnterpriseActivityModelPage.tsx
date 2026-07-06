import { useEffect, useMemo, useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import { getEamModel, getEamSvg, type EamFinding, type EamModel } from "./api";

const DONUT_COLORS = ["#ec0b72", "#e5e7eb"];
type EamViewKey = "activity" | "accountability" | "risk" | "relationship";

const EAM_VIEWS: { key: EamViewKey; label: string; title: string; description: string }[] = [
  {
    key: "activity",
    label: "Activity",
    title: "Activity-view canvas",
    description: "Domains run vertically, lifecycle stages run horizontally, and shared evidence links connect related activity nodes.",
  },
  {
    key: "accountability",
    label: "Accountability",
    title: "Accountability swimlanes",
    description: "Role and owner lanes show which process nodes carry accountability evidence and where ownership is missing or fragmented.",
  },
  {
    key: "risk",
    label: "Risk Heat",
    title: "Risk and coverage heat view",
    description: "Heat cells combine missing coverage, gap, overlap and clash signals across the EAM domain and lifecycle matrix.",
  },
  {
    key: "relationship",
    label: "Relationship",
    title: "Relationship graph",
    description: "Process nodes are linked to the role, system and control entities extracted into the ontology graph.",
  },
];

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "not yet generated";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function evidenceTone(band: string): "good" | "warn" {
  return band === "green" ? "good" : "warn";
}

function findingTone(severity: string): "good" | "warn" {
  return severity === "low" ? "good" : "warn";
}

function CoverageDonut({ score }: { score: number }) {
  const boundedScore = Math.max(0, Math.min(100, score));
  const data = [
    { name: "covered", value: boundedScore },
    { name: "remaining", value: 100 - boundedScore },
  ];

  return (
    <div className="eam-donut" aria-label={`EAM coverage score ${boundedScore}%`}>
      <ResponsiveContainer width="100%" height={126}>
        <PieChart>
          <Pie data={data} dataKey="value" innerRadius={38} outerRadius={56} startAngle={90} endAngle={-270} stroke="none">
            {data.map((_, index) => <Cell key={index} fill={DONUT_COLORS[index]} />)}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="eam-donut-centre">
        <b>{boundedScore}%</b>
        <span>coverage</span>
      </div>
    </div>
  );
}

function MetricCard({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="result-card eam-metric-card">
      <div className="result-head"><b>{value}</b></div>
      <p className="result-cite">{label}</p>
      <p className="muted-text">{note}</p>
    </div>
  );
}

function FindingCard({ finding }: { finding: EamFinding }) {
  return (
    <div className={`result-card eam-finding-card eam-finding-card--${finding.finding_type}`}>
      <div className="result-head">
        <b>{finding.title}</b>
        <span className={`status-pill status-pill--${findingTone(finding.severity)}`}>{finding.severity}</span>
      </div>
      <p className="result-cite">{finding.finding_type} · {finding.node_ids.length || "catalogue"} node links</p>
      <p className="result-text">{finding.description}</p>
      <p className="result-cite">Action: {finding.recommended_action}</p>
    </div>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="empty-card">
      <b>{title}</b>
      <span>{body}</span>
    </div>
  );
}

export function EnterpriseActivityModelPage() {
  const [model, setModel] = useState<EamModel | null>(null);
  const [svg, setSvg] = useState<string>("");
  const [view, setView] = useState<EamViewKey>("activity");
  const [svgBusy, setSvgBusy] = useState(false);
  const [svgError, setSvgError] = useState<string | null>(null);
  const [viewport, setViewport] = useState({ zoom: 1, x: 0, y: 0 });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getEamModel()
      .then((nextModel) => {
        if (!active) return;
        setModel(nextModel);
        setError(null);
      })
      .catch(() => {
        if (!active) return;
        setModel(null);
        setSvg("");
        setError("Could not load the Enterprise Activity Model.");
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    setSvgBusy(true);
    getEamSvg(view)
      .then((nextSvg) => {
        if (!active) return;
        setSvg(nextSvg);
        setSvgError(null);
      })
      .catch(() => {
        if (!active) return;
        setSvg("");
        setSvgError("Could not load this EAM canvas view.");
      })
      .finally(() => {
        if (active) setSvgBusy(false);
      });
    return () => {
      active = false;
    };
  }, [view]);

  const domainCoverage = useMemo(() => {
    if (!model) return { evidenced: 0, total: 0 };
    return {
      evidenced: model.coverage.covered_domain_count + model.coverage.partial_domain_count,
      total: model.coverage.domains.length,
    };
  }, [model]);

  const topFindings = useMemo(() => {
    if (!model) return [];
    const severityRank: Record<string, number> = { high: 0, medium: 1, low: 2 };
    return [...model.findings]
      .sort((a, b) => (severityRank[a.severity] ?? 3) - (severityRank[b.severity] ?? 3))
      .slice(0, 6);
  }, [model]);

  const activeView = EAM_VIEWS.find((item) => item.key === view) ?? EAM_VIEWS[0];

  function zoomCanvas(delta: number) {
    setViewport((current) => ({ ...current, zoom: Math.max(0.55, Math.min(1.75, Number((current.zoom + delta).toFixed(2)))) }));
  }

  function panCanvas(dx: number, dy: number) {
    setViewport((current) => ({ ...current, x: current.x + dx, y: current.y + dy }));
  }

  function resetCanvas() {
    setViewport({ zoom: 1, x: 0, y: 0 });
  }

  if (error) {
    return (
      <div className="view-stack">
        <div className="page-intro">
          <h1>Enterprise Activity Model</h1>
          <p>A governed activity map generated from ontology objects, source evidence and taxonomy rules.</p>
        </div>
        <EmptyState title="EAM unavailable" body={error} />
      </div>
    );
  }

  if (!model) {
    return (
      <div className="view-stack">
        <div className="page-intro">
          <h1>Enterprise Activity Model</h1>
          <p>A governed activity map generated from ontology objects, source evidence and taxonomy rules.</p>
        </div>
        <EmptyState title="Building model" body="Projecting approved ontology records across domains, lifecycle stages and shared evidence links." />
      </div>
    );
  }

  return (
    <div className="view-stack">
      <div className="page-intro eam-hero">
        <div>
          <p className="result-cite">Enterprise architecture memory</p>
          <h1>Enterprise Activity Model</h1>
          <p>
            Derived from {model.source_count} approved sources, projected through {model.taxonomy_version}.
            Last updated {formatDate(model.generated_at)}.
          </p>
        </div>
        <div className="eam-hero-summary">
          <CoverageDonut score={model.coverage.score} />
        </div>
      </div>

      <div className="analytics-metric-grid eam-headline-grid">
        <MetricCard
          label="EAM Coverage Score"
          value={`${model.coverage.score}%`}
          note="Weighted domain coverage from ontology-backed process evidence."
        />
        <MetricCard
          label="Domains Evidenced"
          value={`${domainCoverage.evidenced} of ${domainCoverage.total}`}
          note={`${model.coverage.uncovered_domain_count} domains currently have no mapped activity evidence.`}
        />
        <MetricCard
          label="Risk Signals"
          value={String(model.finding_counts.clash ?? 0)}
          note="Potential clashes where shared systems, controls or ownership are incomplete."
        />
        <MetricCard
          label="Process Nodes"
          value={String(model.process_count)}
          note={`${model.edges.length} shared-entity links visible on the activity canvas.`}
        />
      </div>

      <div className="analytics-grid analytics-grid--two eam-overview-grid">
        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Coverage by domain</h2>
              <p className="muted-text">Configured EAM domains with current ontology evidence status.</p>
            </div>
          </div>
          <div className="eam-domain-list">
            {model.coverage.domains.map((domain) => (
              <div className={`eam-domain-row eam-domain-row--${domain.status}`} key={domain.domain_id}>
                <div>
                  <b>{domain.label}</b>
                  <span>{domain.node_count} nodes · {domain.lifecycle_stage_count} lifecycle stages</span>
                </div>
                <span className={`status-pill status-pill--${domain.status === "covered" ? "good" : "warn"}`}>{domain.status}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Evidence quality</h2>
              <p className="muted-text">Process nodes grouped by generated evidence confidence band.</p>
            </div>
          </div>
          <div className="eam-band-list">
            {(["green", "amber", "red"] as const).map((band) => {
              const nodes = model.nodes.filter((node) => node.confidence_band === band);
              return (
                <div className={`eam-band-row eam-band-row--${band}`} key={band}>
                  <b>{nodes.length}</b>
                  <span>{band} evidence band</span>
                  <small>{nodes.slice(0, 3).map((node) => node.name).join("; ") || "No nodes"}</small>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="panel eam-canvas-panel">
        <div className="panel-heading">
          <div>
            <h2>{activeView.title}</h2>
            <p className="muted-text">{activeView.description}</p>
          </div>
          <span className="status-pill">{model.nodes.length} nodes</span>
        </div>
        <div className="eam-canvas-toolbar">
          <span className="segmented-control" role="group" aria-label="EAM canvas view">
            {EAM_VIEWS.map((item) => (
              <button
                type="button"
                className={view === item.key ? "is-active" : ""}
                key={item.key}
                onClick={() => setView(item.key)}
              >
                {item.label}
              </button>
            ))}
          </span>
          <div className="eam-canvas-controls" aria-label="Canvas navigation controls">
            <button type="button" className="secondary-button" onClick={() => panCanvas(0, -48)} aria-label="Pan up">↑</button>
            <button type="button" className="secondary-button" onClick={() => panCanvas(-48, 0)} aria-label="Pan left">←</button>
            <button type="button" className="secondary-button" onClick={() => panCanvas(48, 0)} aria-label="Pan right">→</button>
            <button type="button" className="secondary-button" onClick={() => panCanvas(0, 48)} aria-label="Pan down">↓</button>
            <button type="button" className="secondary-button" onClick={() => zoomCanvas(-0.1)} aria-label="Zoom out">−</button>
            <span className="status-pill">{Math.round(viewport.zoom * 100)}%</span>
            <button type="button" className="secondary-button" onClick={() => zoomCanvas(0.1)} aria-label="Zoom in">+</button>
            <button type="button" className="secondary-button" onClick={resetCanvas}>Reset</button>
          </div>
        </div>
        {svgError ? <EmptyState title="Canvas unavailable" body={svgError} /> : null}
        <div className={`eam-canvas-scroll${svgBusy ? " is-loading" : ""}`} aria-busy={svgBusy}>
          {svgBusy ? <span className="eam-canvas-loading">Loading {activeView.label.toLowerCase()} view</span> : null}
          <div
            className="eam-canvas-transform"
            style={{ transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})` }}
            dangerouslySetInnerHTML={{ __html: svg }}
          />
        </div>
        <p className="result-cite">
          The selected lens, zoom and pan position are shared across the EAM canvas. The generated SVG highlights evidence coverage and structural signals, not final architecture assurance.
        </p>
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Current triage signals</h2>
            <p className="muted-text">Top gap, overlap and clash findings produced by the EAM projection service.</p>
          </div>
          <span className="status-pill">{model.findings.length} findings</span>
        </div>
        {topFindings.length ? (
          <div className="gap-finding-grid">
            {topFindings.map((finding) => <FindingCard key={finding.id} finding={finding} />)}
          </div>
        ) : (
          <EmptyState title="No findings" body="The current ontology projection did not generate gap, overlap or clash signals." />
        )}
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Process evidence table</h2>
            <p className="muted-text">Underlying process nodes used to create the canvas.</p>
          </div>
        </div>
        <div className="table-frame coverage-table-frame">
          <table className="data-table coverage-table">
            <thead>
              <tr>
                <th>Process</th>
                <th>Domain</th>
                <th>Lifecycle</th>
                <th>Evidence</th>
                <th>Links</th>
              </tr>
            </thead>
            <tbody>
              {model.nodes.map((node) => (
                <tr key={node.id}>
                  <td><b>{node.name}</b><p className="result-cite">{node.process_id}</p></td>
                  <td>{node.domain_label}<p className="result-cite">{node.matched_domain_keywords.join(", ") || "No keyword match"}</p></td>
                  <td>{node.lifecycle_label}<p className="result-cite">{node.matched_lifecycle_keywords.join(", ") || "No keyword match"}</p></td>
                  <td>
                    <span className={`status-pill status-pill--${evidenceTone(node.confidence_band)}`}>{node.confidence_band}</span>
                    <p className="result-cite">{node.evidence_strength} evidence score</p>
                  </td>
                  <td>{node.role_count} roles · {node.system_count} systems · {node.control_count} controls</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
