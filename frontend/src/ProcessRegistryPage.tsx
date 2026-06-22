import { useEffect, useState } from "react";
import { getProcessRegistry, type ProcessRecord } from "./api";

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

export function ProcessRegistryPage() {
  const [records, setRecords] = useState<ProcessRecord[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    getProcessRegistry().then(setRecords).catch(() => setRecords([]));
  }, []);

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Process Registry</h1>
        <p>Structured process knowledge — owners, systems, controls and rules — extracted from approved sources. Complements the document assistant with precise structured facts.</p>
      </div>

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
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
