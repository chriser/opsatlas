import { useEffect, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  getAnalyticsCharts,
  getGovernanceHistory,
  getKnowledgeGaps,
  getProcessComplexity,
  getScorecard,
  getValidationEvidence,
  getValueAnalytics,
  recordValueEvent,
  type ChartData,
  type GovernanceHistory,
  type KnowledgeGapAnalytics,
  type ProcessComplexityAnalytics,
  type Scorecard,
  type ValidationEvidenceReport,
  type ValueAnalytics,
} from "./api";

const COLORS = ["#16a34a", "#dc2626", "#d97706", "#2563eb", "#7c3aed", "#db2777", "#0891b2", "#65a30d"];

function ChartCard({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="panel" style={{ minWidth: 0 }}>
      <div className="panel-heading">
        <div>
          <h2 style={{ fontSize: 15 }}>{title}</h2>
          {subtitle ? <p className="muted-text">{subtitle}</p> : null}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={220}>{children as React.ReactElement}</ResponsiveContainer>
    </div>
  );
}

function formatGbp(value: number): string {
  if (Math.abs(value) >= 1000000) return `GBP ${(value / 1000000).toFixed(1)}m`;
  if (Math.abs(value) >= 1000) return `GBP ${Math.round(value / 1000)}k`;
  return `GBP ${Math.round(value)}`;
}

function formatPercent(value?: number | null): string {
  return value == null ? "n/a" : `${Math.round(value * 100)}%`;
}

function formatAssumption(value: number, unit: string): string {
  if (unit.startsWith("GBP")) return formatGbp(value);
  if (unit === "ratio") return formatPercent(value);
  return `${value} ${unit}`;
}

export function AnalyticsPage() {
  const [card, setCard] = useState<Scorecard | null>(null);
  const [data, setData] = useState<ChartData | null>(null);
  const [governance, setGovernance] = useState<GovernanceHistory | null>(null);
  const [gaps, setGaps] = useState<KnowledgeGapAnalytics | null>(null);
  const [complexity, setComplexity] = useState<ProcessComplexityAnalytics | null>(null);
  const [value, setValue] = useState<ValueAnalytics | null>(null);
  const [validation, setValidation] = useState<ValidationEvidenceReport | null>(null);
  const [valueBusy, setValueBusy] = useState(false);
  const [valueError, setValueError] = useState<string | null>(null);
  const [valueForm, setValueForm] = useState({
    label: "",
    value_driver: "time_saved",
    value_estimate: "",
    process_area: "",
    scenario_id: "base",
  });

  useEffect(() => {
    getScorecard().then(setCard).catch(() => setCard(null));
    getAnalyticsCharts().then(setData).catch(() => setData(null));
    getGovernanceHistory().then(setGovernance).catch(() => setGovernance(null));
    getKnowledgeGaps().then(setGaps).catch(() => setGaps(null));
    getProcessComplexity().then(setComplexity).catch(() => setComplexity(null));
    getValueAnalytics().then(setValue).catch(() => setValue(null));
    getValidationEvidence().then(setValidation).catch(() => setValidation(null));
  }, []);

  async function onRecordValueEvent(event: React.FormEvent) {
    event.preventDefault();
    setValueBusy(true);
    setValueError(null);
    try {
      const updated = await recordValueEvent({
        label: valueForm.label,
        value_driver: valueForm.value_driver,
        value_estimate: Number(valueForm.value_estimate),
        process_area: valueForm.process_area,
        scenario_id: valueForm.scenario_id,
      });
      setValue(updated);
      setValueForm((current) => ({ ...current, label: "", value_estimate: "" }));
    } catch (err) {
      setValueError(err instanceof Error ? err.message : "Could not record value event.");
    } finally {
      setValueBusy(false);
    }
  }

  const activeValueMetric = value?.metrics.find((metric) => metric.scenario_id === value.active_scenario_id) ?? value?.metrics[0] ?? null;
  const valueDriverOptions = Array.from(new Set([
    "time_saved",
    "sme_clarification_avoided",
    "delivery_delay_reduced",
    "rework_avoided",
    ...(value?.driver_options ?? []),
  ]));
  const kpis = card
    ? [
        { label: "Queries", value: String(card.total_queries) },
        { label: "Answer rate", value: `${Math.round(card.answer_rate * 100)}%` },
        { label: "Grounded rate", value: `${Math.round(card.grounded_rate * 100)}%` },
        { label: "Avg citations", value: String(card.avg_citations) },
        { label: "Knowledge gaps", value: String(card.knowledge_gaps.length) },
        { label: "Open issues", value: governance ? String(governance.open_count) : "0" },
        { label: "Gap clusters", value: gaps ? String(gaps.cluster_count) : "0" },
        { label: "Avg complexity", value: complexity ? String(complexity.average_complexity) : "0" },
        { label: "P50 net/year", value: activeValueMetric ? formatGbp(activeValueMetric.net_annual_benefit_gbp) : "GBP 0" },
        { label: "Observed value", value: value ? formatGbp(value.telemetry.observed_total_gbp) : "GBP 0" },
        { label: "Evidence refs", value: validation ? String(validation.summary.evidence_reference_count) : "0" },
      ]
    : [];
  const complexityChartRows = complexity?.processes.slice(0, 12) ?? [];
  const hiddenComplexityCount = Math.max(0, (complexity?.process_count ?? 0) - complexityChartRows.length);

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Analytics</h1>
        <p>Descriptive insight into knowledge demand and answer quality. Diagnostic and predictive tiers follow.</p>
      </div>

      <div className="panel">
        <div className="result-list" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 12 }}>
          {kpis.map((m) => (
            <div className="result-card" key={m.label}>
              <div className="result-head"><b style={{ fontSize: 22 }}>{m.value}</b></div>
              <p className="result-cite">{m.label}</p>
            </div>
          ))}
        </div>
      </div>

      {!data ? (
        <p className="muted-text">Loading charts…</p>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 16 }}>
          <ChartCard title="Query volume over time" subtitle="Daily demand">
            <LineChart data={data.volume_over_time}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e2e8f0)" />
              <XAxis dataKey="date" fontSize={11} /><YAxis allowDecimals={false} fontSize={11} />
              <Tooltip /><Line type="monotone" dataKey="queries" stroke="#2563eb" strokeWidth={2} />
            </LineChart>
          </ChartCard>

          <ChartCard title="Demand by topic" subtitle="What people ask about">
            <BarChart data={data.by_topic}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e2e8f0)" />
              <XAxis dataKey="topic" fontSize={10} interval={0} angle={-20} textAnchor="end" height={50} />
              <YAxis allowDecimals={false} fontSize={11} /><Tooltip />
              <Bar dataKey="count" fill="#7c3aed" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ChartCard>

          <ChartCard title="Outcomes" subtitle="Answered vs refused vs guardrail">
            <PieChart>
              <Pie data={data.outcomes} dataKey="value" nameKey="name" outerRadius={75} label>
                {data.outcomes.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Legend /><Tooltip />
            </PieChart>
          </ChartCard>

          <ChartCard title="Answer latency" subtitle="Response-time distribution">
            <BarChart data={data.latency}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e2e8f0)" />
              <XAxis dataKey="bucket" fontSize={11} /><YAxis allowDecimals={false} fontSize={11} />
              <Tooltip /><Bar dataKey="count" fill="#0891b2" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ChartCard>

          <ChartCard title="Most-cited sources" subtitle="Evidence the assistant relies on">
            <BarChart data={data.top_sources} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e2e8f0)" />
              <XAxis type="number" allowDecimals={false} fontSize={11} />
              <YAxis type="category" dataKey="source" width={150} fontSize={9} />
              <Tooltip /><Bar dataKey="citations" fill="#16a34a" radius={[0, 3, 3, 0]} />
            </BarChart>
          </ChartCard>

          <ChartCard title="Answer confidence" subtitle="Grounded vs unverified">
            <PieChart>
              <Pie data={data.confidence} dataKey="value" nameKey="name" outerRadius={75} label>
                {data.confidence.map((_, i) => <Cell key={i} fill={COLORS[(i + 2) % COLORS.length]} />)}
              </Pie>
              <Legend /><Tooltip />
            </PieChart>
          </ChartCard>

          {value ? (
            <>
              <ChartCard title="Value scenarios" subtitle={`Observed ${formatGbp(value.telemetry.observed_total_gbp)}`}>
                <BarChart data={value.metrics}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e2e8f0)" />
                  <XAxis dataKey="label" fontSize={11} />
                  <YAxis fontSize={11} tickFormatter={(amount) => `${Math.round(Number(amount) / 1000)}k`} />
                  <Tooltip formatter={(amount) => formatGbp(Number(amount))} />
                  <Legend />
                  <Bar dataKey="gross_annual_benefit_gbp" name="Gross annual" fill="#16a34a" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="net_annual_benefit_gbp" name="Net annual" fill="#2563eb" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="npv_gbp" name="NPV" fill="#d97706" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ChartCard>

              <div className="panel" style={{ minWidth: 0 }}>
                <div className="panel-heading">
                  <div>
                    <h2 style={{ fontSize: 15 }}>Value telemetry</h2>
                    <p className="muted-text">{value.telemetry.event_count} recorded events · {formatGbp(value.telemetry.observed_total_gbp)}</p>
                  </div>
                  <span className="status-pill">{activeValueMetric ? `${activeValueMetric.simple_payback_years ?? "n/a"}y payback` : "n/a"}</span>
                </div>
                <form onSubmit={onRecordValueEvent} style={{ display: "grid", gridTemplateColumns: "1fr 150px", gap: 10, alignItems: "end" }}>
                  <label className="muted-text" style={{ display: "grid", gap: 6, fontSize: 12, fontWeight: 800 }}>
                    Event label
                    <input
                      value={valueForm.label}
                      onChange={(event) => setValueForm((current) => ({ ...current, label: event.target.value }))}
                      style={{ border: "1px solid var(--line)", borderRadius: 8, padding: "12px 14px" }}
                    />
                  </label>
                  <label className="muted-text" style={{ display: "grid", gap: 6, fontSize: 12, fontWeight: 800 }}>
                    GBP value
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={valueForm.value_estimate}
                      onChange={(event) => setValueForm((current) => ({ ...current, value_estimate: event.target.value }))}
                      style={{ border: "1px solid var(--line)", borderRadius: 8, padding: "12px 14px" }}
                    />
                  </label>
                  <label className="muted-text" style={{ display: "grid", gap: 6, fontSize: 12, fontWeight: 800 }}>
                    Driver
                    <select
                      value={valueForm.value_driver}
                      onChange={(event) => setValueForm((current) => ({ ...current, value_driver: event.target.value }))}
                      style={{ border: "1px solid var(--line)", borderRadius: 8, padding: "12px 14px" }}
                    >
                      {valueDriverOptions.map((driver) => (
                        <option value={driver} key={driver}>{driver.replace(/_/g, " ")}</option>
                      ))}
                    </select>
                  </label>
                  <label className="muted-text" style={{ display: "grid", gap: 6, fontSize: 12, fontWeight: 800 }}>
                    Scenario
                    <select
                      value={valueForm.scenario_id}
                      onChange={(event) => setValueForm((current) => ({ ...current, scenario_id: event.target.value }))}
                      style={{ border: "1px solid var(--line)", borderRadius: 8, padding: "12px 14px" }}
                    >
                      {value.scenarios.map((scenario) => (
                        <option value={scenario.scenario_id} key={scenario.scenario_id}>{scenario.label}</option>
                      ))}
                    </select>
                  </label>
                  <label className="muted-text" style={{ display: "grid", gap: 6, fontSize: 12, fontWeight: 800 }}>
                    Process area
                    <input
                      value={valueForm.process_area}
                      onChange={(event) => setValueForm((current) => ({ ...current, process_area: event.target.value }))}
                      style={{ border: "1px solid var(--line)", borderRadius: 8, padding: "12px 14px" }}
                    />
                  </label>
                  <button type="submit" className="primary-button" disabled={valueBusy || !valueForm.label.trim() || !valueForm.value_estimate.trim()}>
                    {valueBusy ? "Recording..." : "Record"}
                  </button>
                </form>
                {valueError ? <p className="muted-text" style={{ color: "var(--red)", marginTop: 10 }}>{valueError}</p> : null}
                {value.telemetry.recent_events.length ? (
                  <div className="table-frame" style={{ marginTop: 14 }}>
                    <table className="data-table">
                      <thead>
                        <tr><th>Event</th><th>Driver</th><th>Process</th><th>Value</th></tr>
                      </thead>
                      <tbody>
                        {value.telemetry.recent_events.slice(0, 4).map((event) => (
                          <tr key={event.event_id}>
                            <td>{event.label}</td>
                            <td>{event.value_driver.replace(/_/g, " ")}</td>
                            <td>{event.process_area || "n/a"}</td>
                            <td>{formatGbp(event.value_estimate)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
              </div>

              <div className="panel" style={{ minWidth: 0, gridColumn: "1 / -1" }}>
                <div className="panel-heading">
                  <div>
                    <h2 style={{ fontSize: 15 }}>Value assumptions ledger</h2>
                    <p className="muted-text">{value.assumptions.length} assumptions · schema {value.schema_version}</p>
                  </div>
                  <span className="status-pill">{value.active_scenario_id}</span>
                </div>
                <div className="table-frame">
                  <table className="data-table">
                    <thead>
                      <tr><th>Scenario</th><th>Driver</th><th>Assumption</th><th>Value</th><th>Confidence</th><th>Rationale</th></tr>
                    </thead>
                    <tbody>
                      {value.assumptions.map((assumption) => (
                        <tr key={assumption.assumption_id}>
                          <td>{assumption.scenario_id}</td>
                          <td>{assumption.driver.replace(/_/g, " ")}</td>
                          <td>{assumption.label}</td>
                          <td>{formatAssumption(assumption.value, assumption.unit)}</td>
                          <td>{assumption.confidence}</td>
                          <td>{assumption.rationale}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          ) : null}

          {validation ? (
            <>
              <div className="panel" style={{ minWidth: 0 }}>
                <div className="panel-heading">
                  <div>
                    <h2 style={{ fontSize: 15 }}>Validation protocol</h2>
                    <p className="muted-text">{validation.summary.validation_protocol_count} protocols · {validation.summary.evidence_reference_count} evidence refs</p>
                  </div>
                  <span className="status-pill">{validation.summary.ksb_count} KSB rows</span>
                </div>
                <div className="result-list" style={{ gap: 10 }}>
                  {validation.validation_protocols.slice(0, 4).map((protocol) => (
                    <div className="result-card" key={protocol.protocol_id}>
                      <div className="result-head">
                        <b>{protocol.component}</b>
                        <span className="status-pill">{protocol.status}</span>
                      </div>
                      <p className="result-cite">{protocol.protocol_id} · {protocol.metric}</p>
                      <p className="result-text">{protocol.acceptance_rule}</p>
                      <p className="result-cite">{protocol.boundary}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="panel" style={{ minWidth: 0 }}>
                <div className="panel-heading">
                  <div>
                    <h2 style={{ fontSize: 15 }}>Evidence caveats</h2>
                    <p className="muted-text">{validation.generated_at.slice(0, 10)}</p>
                  </div>
                </div>
                <div className="result-list" style={{ gap: 10 }}>
                  {validation.caveats.map((caveat) => (
                    <div className="result-card" key={caveat}>
                      <p className="result-text">{caveat}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="panel" style={{ minWidth: 0, gridColumn: "1 / -1" }}>
                <div className="panel-heading">
                  <div>
                    <h2 style={{ fontSize: 15 }}>KSB traceability</h2>
                    <p className="muted-text">Project evidence mapping across delivered analytics features.</p>
                  </div>
                  <span className="status-pill">{validation.summary.ksb_by_status.implemented ?? 0} implemented</span>
                </div>
                <div className="table-frame">
                  <table className="data-table">
                    <thead>
                      <tr><th>KSB</th><th>Capability</th><th>Delivered evidence</th><th>References</th><th>Status</th><th>Next evidence</th></tr>
                    </thead>
                    <tbody>
                      {validation.ksb_rows.map((row) => (
                        <tr key={row.ksb_id}>
                          <td>{row.ksb_id}<p className="result-cite">{row.category}</p></td>
                          <td>
                            <b>{row.capability}</b>
                            <p className="result-cite">{row.evidence_claim}</p>
                          </td>
                          <td>{row.delivered_features.join("; ")}</td>
                          <td>{row.evidence_refs.map((ref) => `${ref.label} (${ref.kind})`).join("; ")}</td>
                          <td>{row.validation_status}</td>
                          <td>{row.next_evidence}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          ) : null}

          {governance ? (
            <>
              <ChartCard title="Governance issue burndown" subtitle="Detected, accepted, resolved and still open">
                <LineChart data={governance.issue_events_over_time}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e2e8f0)" />
                  <XAxis dataKey="date" fontSize={11} />
                  <YAxis allowDecimals={false} fontSize={11} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="detected" stroke="#d97706" strokeWidth={2} />
                  <Line type="monotone" dataKey="accepted" stroke="#7c3aed" strokeWidth={2} />
                  <Line type="monotone" dataKey="resolved" stroke="#16a34a" strokeWidth={2} />
                  <Line type="monotone" dataKey="open" stroke="#dc2626" strokeWidth={2} />
                </LineChart>
              </ChartCard>

              <ChartCard title="Issue lifecycle mix" subtitle={`MTTR ${governance.mean_time_to_resolve_hours}h · ${governance.resolved_count} resolved`}>
                <PieChart>
                  <Pie data={governance.issue_state_mix} dataKey="count" nameKey="state" outerRadius={75} label>
                    {governance.issue_state_mix.map((_, i) => <Cell key={i} fill={COLORS[(i + 3) % COLORS.length]} />)}
                  </Pie>
                  <Legend /><Tooltip />
                </PieChart>
              </ChartCard>

              <ChartCard title="Issue types" subtitle="Detected governance checks">
                <BarChart data={governance.issue_type_mix}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e2e8f0)" />
                  <XAxis dataKey="issue_type" fontSize={10} interval={0} angle={-20} textAnchor="end" height={50} />
                  <YAxis allowDecimals={false} fontSize={11} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#d97706" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ChartCard>

              <div className="panel" style={{ minWidth: 0 }}>
                <div className="panel-heading">
                  <div>
                    <h2 style={{ fontSize: 15 }}>Recurring issue signals</h2>
                    <p className="muted-text">Repeated detections across governance snapshots</p>
                  </div>
                </div>
                {governance.recurring_issues.length ? (
                  <div className="table-frame">
                    <table className="data-table">
                      <thead>
                        <tr><th>Issue</th><th>Source</th><th>Detections</th><th>Last seen</th><th>State</th></tr>
                      </thead>
                      <tbody>
                        {governance.recurring_issues.slice(0, 6).map((issue) => (
                          <tr key={issue.issue_id}>
                            <td>{issue.issue_type}</td>
                            <td>{issue.source}</td>
                            <td>{issue.detections}</td>
                            <td>{issue.last_seen}</td>
                            <td>{issue.state}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="muted-text">No recurring governance issues.</p>
                )}
              </div>
            </>
          ) : null}

          {gaps ? (
            <>
              <ChartCard title="Knowledge-gap clusters" subtitle={`Quality ${Math.round(gaps.silhouette_score * 100)}%`}>
                <BarChart data={gaps.clusters}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e2e8f0)" />
                  <XAxis dataKey="label" fontSize={10} interval={0} angle={-20} textAnchor="end" height={64} />
                  <YAxis allowDecimals={false} fontSize={11} />
                  <Tooltip />
                  <Bar dataKey="question_count" fill="#db2777" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ChartCard>

              <div className="panel" style={{ minWidth: 0 }}>
                <div className="panel-heading">
                  <div>
                    <h2 style={{ fontSize: 15 }}>Onboarding friction</h2>
                    <p className="muted-text">{gaps.total_candidates} candidate questions</p>
                  </div>
                  <span className="status-pill">silhouette {gaps.silhouette_score}</span>
                </div>
                {gaps.clusters.length ? (
                  <div className="result-list" style={{ gap: 10 }}>
                    {gaps.clusters.slice(0, 4).map((cluster) => (
                      <div className="result-card" key={cluster.id}>
                        <div className="result-head">
                          <b>{cluster.label}</b>
                          <span className="status-pill">{cluster.friction_score}</span>
                        </div>
                        <p className="result-cite">{cluster.process_area} · {cluster.question_count} questions · {cluster.confidence}</p>
                        <p className="result-text">{cluster.source_gap}</p>
                        {cluster.representative_questions.slice(0, 2).map((question) => (
                          <p className="result-cite" key={question}>{question}</p>
                        ))}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="muted-text">No knowledge-gap clusters.</p>
                )}
              </div>
            </>
          ) : null}

          {complexity ? (
            <>
              <div className="panel" style={{ minWidth: 0 }}>
                <div className="panel-heading">
                  <div>
                    <h2 style={{ fontSize: 15 }}>Process complexity</h2>
                    <p className="muted-text">
                      Top {complexityChartRows.length} by complexity{hiddenComplexityCount ? ` · ${hiddenComplexityCount} more in table` : ""}
                    </p>
                  </div>
                </div>
                {complexityChartRows.length ? (
                  <ResponsiveContainer width="100%" height={Math.max(260, complexityChartRows.length * 34)}>
                    <BarChart data={complexityChartRows} layout="vertical" margin={{ left: 18, right: 12 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e2e8f0)" />
                      <XAxis type="number" domain={[0, 100]} allowDecimals={false} fontSize={11} />
                      <YAxis type="category" dataKey="name" width={170} fontSize={9} interval={0} />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey="complexity_score" fill="#2563eb" radius={[0, 3, 3, 0]} />
                      <Bar dataKey="key_person_risk_score" fill="#dc2626" radius={[0, 3, 3, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="muted-text">No process-complexity indicators.</p>
                )}
              </div>

              <div className="panel" style={{ minWidth: 0 }}>
                <div className="panel-heading">
                  <div>
                    <h2 style={{ fontSize: 15 }}>Score glossary</h2>
                    <p className="muted-text">{complexity.high_risk_count} high key-person-risk indicators</p>
                  </div>
                </div>
                <div className="result-list" style={{ gap: 10 }}>
                  {Object.entries(complexity.rubric).map(([key, value]) => (
                    <div className="result-card" key={key}>
                      <div className="result-head"><b>{key.replace(/_/g, " ")}</b></div>
                      <p className="result-cite">{value}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="panel" style={{ minWidth: 0, gridColumn: "1 / -1" }}>
                <div className="panel-heading">
                  <div>
                    <h2 style={{ fontSize: 15 }}>Process indicator detail</h2>
                    <p className="muted-text">All process records with the signals behind each score.</p>
                  </div>
                  <span className="status-pill">{complexity.process_count} records</span>
                </div>
                {complexity.processes.length ? (
                  <div className="table-frame">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Process</th>
                          <th>Complexity</th>
                          <th>Key-person risk</th>
                          <th>Signals</th>
                          <th>Indicators</th>
                          <th>Explanation</th>
                        </tr>
                      </thead>
                      <tbody>
                        {complexity.processes.map((process) => (
                          <tr key={process.id}>
                            <td>
                              <b>{process.name}</b>
                              <p className="result-cite">{process.source_title}</p>
                            </td>
                            <td>{process.complexity_score} · {process.complexity_band}</td>
                            <td>
                              {process.key_person_risk_score} · {process.key_person_risk_band}
                              {process.dominant_role ? <p className="result-cite">dominant: {process.dominant_role}</p> : null}
                            </td>
                            <td>
                              roles {process.signals.roles ?? 0} · systems {process.signals.systems ?? 0} · deps {process.signals.dependencies ?? 0} · controls {process.signals.controls ?? 0}
                            </td>
                            <td>{process.indicators.join("; ")}</td>
                            <td>{process.explanation}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="muted-text">No process-complexity indicators.</p>
                )}
              </div>
            </>
          ) : null}
        </div>
      )}
    </div>
  );
}
