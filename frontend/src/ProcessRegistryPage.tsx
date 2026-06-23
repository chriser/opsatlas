import { useEffect, useState } from "react";
import {
  createLucidDocument,
  downloadLucidImport,
  getLucidConfig,
  getProcessMap,
  getProcessRegistry,
  getProcessStressTest,
  type LucidConfig,
  type LucidCreateResponse,
  type ProcessMapDraft,
  type ProcessRecord,
  type ProcessStressReport,
} from "./api";

function Chips({ label, items }: { label: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div style={{ marginTop: 8 }}>
      <p className="result-cite" style={{ marginBottom: 4 }}>{label}</p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {items.map((t, i) => <span key={i} className="status-pill">{t}</span>)}
      </div>
    </div>
  );
}

function safeFilename(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 80) || "process-map";
}

export function ProcessRegistryPage() {
  const [records, setRecords] = useState<ProcessRecord[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [mapOpen, setMapOpen] = useState<string | null>(null);
  const [mapDraft, setMapDraft] = useState<ProcessMapDraft | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);
  const [stress, setStress] = useState<ProcessStressReport | null>(null);
  const [lucidConfig, setLucidConfig] = useState<LucidConfig | null>(null);
  const [lucidBusy, setLucidBusy] = useState<"download" | "create" | null>(null);
  const [lucidError, setLucidError] = useState<string | null>(null);
  const [lucidResult, setLucidResult] = useState<LucidCreateResponse | null>(null);

  useEffect(() => {
    getProcessRegistry().then(setRecords).catch(() => setRecords([]));
    getProcessStressTest().then(setStress).catch(() => setStress(null));
    getLucidConfig().then(setLucidConfig).catch(() => setLucidConfig(null));
  }, []);

  async function toggleMap(processId: string) {
    if (mapOpen === processId) {
      setMapOpen(null);
      setMapDraft(null);
      setMapError(null);
      resetLucidState();
      return;
    }
    setMapOpen(processId);
    setMapDraft(null);
    setMapError(null);
    resetLucidState();
    try {
      setMapDraft(await getProcessMap(processId));
    } catch {
      setMapError("Could not load process-map draft.");
    }
  }

  async function onDownloadLucid(processId: string) {
    setLucidBusy("download");
    setLucidError(null);
    setLucidResult(null);
    try {
      const blob = await downloadLucidImport(processId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${safeFilename(mapDraft?.name || processId)}.lucid`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setLucidError(err instanceof Error ? err.message : "Could not download Lucid import.");
    } finally {
      setLucidBusy(null);
    }
  }

  async function onCreateLucid(processId: string) {
    setLucidBusy("create");
    setLucidError(null);
    setLucidResult(null);
    try {
      setLucidResult(await createLucidDocument(processId));
    } catch (err) {
      setLucidError(err instanceof Error ? err.message : "Could not create Lucidchart document.");
    } finally {
      setLucidBusy(null);
    }
  }

  function resetLucidState() {
    setLucidBusy(null);
    setLucidError(null);
    setLucidResult(null);
  }

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Process Registry</h1>
        <p>Structured process knowledge — owners, systems, controls and rules — extracted from approved sources. Complements the document assistant with precise structured facts.</p>
      </div>

      {stress ? (
        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Stress-test lab</h2>
              <p className="muted-text">{stress.process_count} processes · {stress.scenario_count} scenarios</p>
            </div>
            <span className={`status-pill${stress.highest_risk && stress.highest_risk.queue_pressure_score >= 70 ? " status-pill--warn" : " status-pill--good"}`}>
              {stress.highest_risk ? `${stress.highest_risk.queue_pressure_score} queue` : "no processes"}
            </span>
          </div>
          {stress.highest_risk ? (
            <>
              <div className="result-list" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 12 }}>
                <div className="result-card">
                  <div className="result-head"><b>{stress.highest_risk.process_name}</b></div>
                  <p className="result-cite">Highest-risk process</p>
                </div>
                <div className="result-card">
                  <div className="result-head"><b>{stress.highest_risk.scenario_label}</b></div>
                  <p className="result-cite">Stress scenario</p>
                </div>
                <div className="result-card">
                  <div className="result-head"><b>{stress.highest_risk.bottleneck_role}</b></div>
                  <p className="result-cite">Bottleneck role</p>
                </div>
              </div>
              <div className="table-frame">
                <table className="data-table">
                  <thead>
                    <tr><th>Process</th><th>Scenario</th><th>Cycle index</th><th>Queue</th><th>Rework</th><th>Actions</th></tr>
                  </thead>
                  <tbody>
                    {stress.results.slice(0, 8).map((row) => (
                      <tr key={`${row.process_id}-${row.scenario_id}`}>
                        <td>
                          <b>{row.process_name}</b>
                          <p className="result-cite">{row.bottleneck_reason}</p>
                        </td>
                        <td>{row.scenario_label}</td>
                        <td>{row.cycle_time_index}</td>
                        <td>{row.queue_pressure_score}</td>
                        <td>{row.rework_risk_score}</td>
                        <td>{row.optimisation_actions.join("; ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="result-list" style={{ gap: 10, marginTop: 12 }}>
                {stress.rules.slice(0, 3).map((rule) => (
                  <div className="result-card" key={rule.process_id}>
                    <div className="result-head">
                      <b>{rule.process_name}</b>
                      <span className="status-pill">{rule.handoff_count} hand-offs</span>
                    </div>
                    <p className="result-cite">
                      roles {rule.role_count} · systems {rule.system_count} · dependencies {rule.dependency_count} · validation gates {rule.validation_gate_count}
                    </p>
                    <p className="result-text">{rule.stress_factors.join("; ")}</p>
                  </div>
                ))}
              </div>
              <p className="result-cite" style={{ marginTop: 10 }}>{stress.rubric.boundary}</p>
            </>
          ) : (
            <p className="muted-text">No process records available for stress testing.</p>
          )}
        </div>
      ) : null}

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Processes</h2>
            <p className="muted-text">One record per approved source.</p>
          </div>
          <span className="status-pill">{records ? `${records.length}` : "…"}</span>
        </div>
        {!records ? (
          <p className="muted-text">Loading…</p>
        ) : records.length === 0 ? (
          <div className="empty-card"><b>No processes</b><span>Approve structured sources to populate the registry.</span></div>
        ) : (
          <div className="result-list">
            {records.map((p) => (
              <div className="result-card" key={p.id}>
                <div className="result-head">
                  <b>{p.name}</b>
                  <span style={{ display: "inline-flex", gap: 6 }}>
                    {p.domain ? <span className="status-pill">{p.domain}</span> : null}
                    <button type="button" className="text-button" onClick={() => setOpen(open === p.id ? null : p.id)}>
                      {open === p.id ? "Hide rules" : `Rules (${p.rules.length})`}
                    </button>
                    <button type="button" className="text-button" onClick={() => void toggleMap(p.id)}>
                      {mapOpen === p.id ? "Hide map" : "Map draft"}
                    </button>
                  </span>
                </div>
                <Chips label="Roles / owners" items={p.roles} />
                <Chips label="Systems" items={p.systems} />
                <Chips label="Controls" items={p.controls} />
                <Chips label="Dependencies" items={p.dependencies} />
                {open === p.id ? (
                  <div className="table-frame" style={{ marginTop: 10 }}>
                    <table className="data-table">
                      <thead><tr><th>Topic</th><th>Role</th><th>Rule</th><th>Confidence</th></tr></thead>
                      <tbody>
                        {p.rules.map((r, i) => (
                          <tr key={i}>
                            <td>{r.topic.replace(/_/g, " ")}</td>
                            <td>{r.role.replace(/_/g, " ")}</td>
                            <td>{r.rule}</td>
                            <td>{r.confidence.replace(/_/g, " ")}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
                {mapOpen === p.id ? (
                  <div className="result-card" style={{ marginTop: 10 }}>
                    <div className="result-head">
                      <b>Lucid-ready process-map draft</b>
                      <span style={{ display: "inline-flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                        <span className="status-pill">{mapDraft ? `${mapDraft.steps.length} steps` : "loading"}</span>
                        {mapDraft ? (
                          <>
                            <button
                              type="button"
                              className="mini-button"
                              disabled={lucidBusy !== null}
                              onClick={() => void onDownloadLucid(p.id)}
                            >
                              {lucidBusy === "download" ? "Preparing..." : "Download .lucid"}
                            </button>
                            <button
                              type="button"
                              className="secondary-button"
                              disabled={lucidBusy !== null || !lucidConfig?.configured}
                              onClick={() => void onCreateLucid(p.id)}
                              title={lucidConfig?.configured ? "Create Lucidchart document" : "Lucid API key is not configured"}
                            >
                              {lucidBusy === "create" ? "Creating..." : "Create in Lucid"}
                            </button>
                          </>
                        ) : null}
                      </span>
                    </div>
                    {mapError ? <p className="muted-text" style={{ color: "var(--red)" }}>{mapError}</p> : null}
                    {mapDraft ? (
                      <>
                        <p className="result-cite">
                          Lucid export includes BPMN step blocks, connectors, controls, systems, dependencies, open decisions and source metadata.
                        </p>
                        {!lucidConfig?.configured ? (
                          <p className="result-cite">
                            Live create is waiting for {lucidConfig?.missing.join(", ") || "Lucid configuration"}.
                          </p>
                        ) : null}
                        {lucidError ? <p className="muted-text" style={{ color: "var(--red)" }}>{lucidError}</p> : null}
                        {lucidResult ? (
                          <p className="result-cite">
                            Created {lucidResult.document_id || "Lucid document"}
                            {lucidResult.edit_url ? (
                              <>
                                {" "}
                                <a href={lucidResult.edit_url} target="_blank" rel="noreferrer">Open in Lucid</a>
                              </>
                            ) : null}
                          </p>
                        ) : null}
                        <div className="table-frame" style={{ marginTop: 10 }}>
                          <table className="data-table">
                            <thead><tr><th>Step</th><th>Owner</th><th>Topic</th><th>Confidence</th></tr></thead>
                            <tbody>
                              {mapDraft.steps.map((step) => (
                                <tr key={step.id}>
                                  <td>{step.label}</td>
                                  <td>{step.owner || "n/a"}</td>
                                  <td>{step.topic || "n/a"}</td>
                                  <td>{step.confidence || "n/a"}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                        <pre className="code-block">{mapDraft.mermaid}</pre>
                      </>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
