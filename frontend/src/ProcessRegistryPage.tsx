import { useEffect, useState } from "react";
import {
  getProcessDiagram,
  getProcessMap,
  getProcessRegistry,
  type ProcessDiagramContext,
  type ProcessMapDraft,
  type ProcessRecord,
} from "./api";

function humanise(value: string): string {
  return value.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim();
}

function unique(items: string[]): string[] {
  return Array.from(new Set(items.map((item) => humanise(item)).filter(Boolean)));
}

function processIcon(record: ProcessRecord): { label: string; tone: string; caption: string } {
  const text = [
    record.name,
    record.domain,
    record.process,
    record.source_title,
    ...record.roles,
    ...record.systems,
    ...record.controls,
    ...record.dependencies,
  ].join(" ").toLowerCase();
  if (/\b(supplier|vendor|onboard|supply)\b/.test(text)) return { label: "SUP", tone: "supplier", caption: "Supplier flow" };
  if (/\b(tax|vat|duty|rate)\b/.test(text)) return { label: "TAX", tone: "tax", caption: "Tax flow" };
  if (/\b(contract|legal|terms|agreement)\b/.test(text)) return { label: "CON", tone: "contract", caption: "Contract flow" };
  if (/\b(finance|credit|payment|invoice|cost)\b/.test(text)) return { label: "FIN", tone: "finance", caption: "Finance flow" };
  if (/\b(store|launch|site|location)\b/.test(text)) return { label: "STR", tone: "store", caption: "Store flow" };
  if (/\b(article|product|item|range)\b/.test(text)) return { label: "ART", tone: "article", caption: "Article flow" };
  if (/\b(data|master|record|metadata)\b/.test(text)) return { label: "DAT", tone: "data", caption: "Data flow" };
  if (/\b(control|governance|compliance|approval)\b/.test(text)) return { label: "GOV", tone: "governance", caption: "Control flow" };
  return { label: "PRC", tone: "process", caption: "Process flow" };
}

function Chips({ label, items }: { label: string; items: string[] }) {
  const values = unique(items);
  if (!values.length) return null;
  return (
    <div className="process-signal-block">
      <p className="result-cite">{label}</p>
      <div className="process-chip-list">
        {values.map((item) => <span key={item} className="status-pill">{item}</span>)}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="process-metric">
      <b>{value}</b>
      <span>{label}</span>
    </div>
  );
}

function ProcessIcon({ record }: { record: ProcessRecord }) {
  const icon = processIcon(record);
  return (
    <div className={`process-icon process-icon--${icon.tone}`} aria-label={icon.caption} title={icon.caption}>
      <span>{icon.label}</span>
      <i />
    </div>
  );
}

function DiagramPane({
  diagram,
  loading,
  error,
}: {
  diagram: ProcessDiagramContext | null;
  loading: boolean;
  error: string | null;
}) {
  if (loading) {
    return (
      <div className="process-diagram-preview">
        <div className="result-head">
          <b>Internal process chart</b>
          <span className="status-pill">loading</span>
        </div>
        <p className="muted-text">Rendering the local process chart...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="process-diagram-preview">
        <div className="result-head">
          <b>Internal process chart</b>
          <span className="status-pill status-pill--warn">unavailable</span>
        </div>
        <p className="muted-text" style={{ color: "var(--red)" }}>{error}</p>
      </div>
    );
  }

  if (!diagram || diagram.status !== "available") {
    return (
      <div className="process-diagram-preview">
        <div className="result-head">
          <b>Internal process chart</b>
          <span className="status-pill status-pill--warn">unavailable</span>
        </div>
        <p className="muted-text">
          {diagram?.message || "No chart has been rendered for this process yet."}
        </p>
      </div>
    );
  }

  return (
    <div className="process-diagram-preview">
      <div className="result-head">
        <b>Internal process chart</b>
        <span className="status-pill status-pill--good">local</span>
      </div>
      <div className="process-registry-diagram-frame" dangerouslySetInnerHTML={{ __html: diagram.svg }} />
      <p className="result-cite">
        {diagram.source_title || "Process registry"} - {diagram.service_url || "local diagram service"}
      </p>
    </div>
  );
}

function StepList({ draft }: { draft: ProcessMapDraft | null }) {
  if (!draft) return <p className="muted-text">Loading extracted steps...</p>;
  if (!draft.steps.length) return <p className="muted-text">No structured steps extracted yet.</p>;
  return (
    <div className="process-step-list">
      {draft.steps.map((step, index) => (
        <div className="process-step" key={step.id}>
          <span>{index + 1}</span>
          <div>
            <b>{step.label}</b>
            <small>
              {[step.owner, step.topic, step.confidence].filter(Boolean).map(humanise).join(" - ") || "Unclassified step"}
            </small>
          </div>
        </div>
      ))}
    </div>
  );
}

export function ProcessRegistryPage() {
  const [records, setRecords] = useState<ProcessRecord[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [mapDraft, setMapDraft] = useState<ProcessMapDraft | null>(null);
  const [diagram, setDiagram] = useState<ProcessDiagramContext | null>(null);
  const [detailBusy, setDetailBusy] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  useEffect(() => {
    getProcessRegistry().then(setRecords).catch(() => setRecords([]));
  }, []);

  async function toggleProcess(processId: string) {
    if (open === processId) {
      setOpen(null);
      setMapDraft(null);
      setDiagram(null);
      setDetailError(null);
      return;
    }

    setOpen(processId);
    setMapDraft(null);
    setDiagram(null);
    setDetailError(null);
    setDetailBusy(true);

    const [draftResult, diagramResult] = await Promise.allSettled([
      getProcessMap(processId),
      getProcessDiagram(processId),
    ]);

    if (draftResult.status === "fulfilled") {
      setMapDraft(draftResult.value);
    } else {
      setDetailError("Could not load structured process details.");
    }

    if (diagramResult.status === "fulfilled") {
      setDiagram(diagramResult.value);
    } else {
      setDiagram({
        status: "unavailable",
        message: "Could not render the local process chart.",
        process_id: processId,
        process_name: "",
        source_title: "",
        service_url: "",
        chart: null,
        svg: "",
      });
    }

    setDetailBusy(false);
  }

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Process Registry</h1>
        <p>Structured process knowledge from approved sources, with local process charts, owners, systems, controls and dependency signals.</p>
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Discovered processes</h2>
            <p className="muted-text">One process record per approved source, generated from the internal registry and chart builder.</p>
          </div>
          <span className="status-pill">{records ? `${records.length}` : "..."}</span>
        </div>
        {!records ? (
          <p className="muted-text">Loading...</p>
        ) : records.length === 0 ? (
          <div className="empty-card"><b>No processes</b><span>Approve structured sources to populate the registry.</span></div>
        ) : (
          <div className="process-registry-list">
            {records.map((process) => {
              const expanded = open === process.id;
              const activeDraft = expanded ? mapDraft : null;
              return (
                <div className={`process-card${expanded ? " process-card--open" : ""}`} key={process.id}>
                  <div className="process-card-header">
                    <ProcessIcon record={process} />
                    <div className="process-card-title">
                      <b>{process.name}</b>
                      <p className="result-cite">{process.source_title}</p>
                    </div>
                    <div className="process-card-meta">
                      {process.domain ? <span className="status-pill">{humanise(process.domain)}</span> : null}
                      <span className="status-pill">{process.rules.length} rules</span>
                      <button type="button" className="secondary-button" onClick={() => void toggleProcess(process.id)}>
                        {expanded ? "Close map" : "Open map"}
                      </button>
                    </div>
                  </div>

                  <div className="process-card-summary">
                    <Metric label="roles" value={process.roles.length} />
                    <Metric label="systems" value={process.systems.length} />
                    <Metric label="controls" value={process.controls.length} />
                    <Metric label="dependencies" value={process.dependencies.length} />
                  </div>

                  {expanded ? (
                    <div className="process-detail-grid">
                      <div className="process-detail-panel">
                        <div className="process-detail-section">
                          <h3>Process signals</h3>
                          <Chips label="Roles / owners" items={process.roles} />
                          <Chips label="Systems" items={process.systems} />
                          <Chips label="Controls" items={process.controls} />
                          <Chips label="Dependencies" items={process.dependencies} />
                          <Chips label="Capabilities" items={process.capabilities} />
                          {activeDraft?.open_decisions.length ? (
                            <Chips label="Open decisions" items={activeDraft.open_decisions} />
                          ) : null}
                        </div>

                        <div className="process-detail-section">
                          <h3>Extracted steps</h3>
                          <StepList draft={activeDraft} />
                        </div>

                        <div className="process-detail-section">
                          <h3>Rules</h3>
                          {process.rules.length ? (
                            <div className="table-frame process-rules-frame">
                              <table className="data-table">
                                <thead><tr><th>Topic</th><th>Role</th><th>Rule</th><th>Confidence</th></tr></thead>
                                <tbody>
                                  {process.rules.map((rule, index) => (
                                    <tr key={`${rule.record_id}-${index}`}>
                                      <td>{humanise(rule.topic)}</td>
                                      <td>{humanise(rule.role)}</td>
                                      <td>{rule.rule}</td>
                                      <td>{humanise(rule.confidence)}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <p className="muted-text">No structured rules extracted yet.</p>
                          )}
                        </div>
                      </div>

                      <div className="process-detail-panel process-detail-panel--diagram">
                        <DiagramPane diagram={diagram} loading={detailBusy} error={detailError} />
                      </div>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
