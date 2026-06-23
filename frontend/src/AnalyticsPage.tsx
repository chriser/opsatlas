import { useEffect, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  getAnalyticsCharts,
  getAnalyticsReportMarkdown,
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

type AnalyticsSection = "summary" | "value" | "validation" | "governance" | "process" | "detail";

const SECTIONS: { key: AnalyticsSection; label: string; summary: string }[] = [
  { key: "summary", label: "Summary", summary: "Demand, quality and attention signals" },
  { key: "value", label: "Value", summary: "Assumptions, scenarios and observed benefit" },
  { key: "validation", label: "Validation/KSB", summary: "Evidence discipline and claims boundaries" },
  { key: "governance", label: "Governance Gaps", summary: "Issue trends and knowledge-gap clusters" },
  { key: "process", label: "Process Complexity", summary: "Risk, complexity and glossary" },
  { key: "detail", label: "Process Detail", summary: "Full process indicator table" },
];

function initialSection(): AnalyticsSection {
  const hash = window.location.hash.replace("#analytics-", "");
  return SECTIONS.some((section) => section.key === hash) ? (hash as AnalyticsSection) : "summary";
}

function ChartCard({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="panel analytics-chart-card">
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

function InsightPanel({ title, children, tone = "neutral" }: { title: string; children: React.ReactNode; tone?: "neutral" | "good" | "warn" }) {
  return (
    <div className={`insight-panel insight-panel--${tone}`}>
      <b>{title}</b>
      <div>{children}</div>
    </div>
  );
}

function MetricGrid({ items }: { items: { label: string; value: string; note?: string; tone?: "good" | "warn" }[] }) {
  return (
    <div className="analytics-metric-grid">
      {items.map((metric) => (
        <div className="result-card" key={metric.label}>
          <div className="result-head">
            <b style={{ fontSize: 22 }}>{metric.value}</b>
            {metric.tone ? <span className={`status-pill status-pill--${metric.tone}`}>{metric.tone}</span> : null}
          </div>
          <p className="result-cite">{metric.label}</p>
          {metric.note ? <p className="result-cite">{metric.note}</p> : null}
        </div>
      ))}
    </div>
  );
}

function EmptyPanel({ children }: { children: React.ReactNode }) {
  return (
    <div className="panel">
      <p className="muted-text">{children}</p>
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

function driverLabel(value: string): string {
  return value.replace(/_/g, " ");
}

export function AnalyticsPage() {
  const [section, setSection] = useState<AnalyticsSection>(() => initialSection());
  const [card, setCard] = useState<Scorecard | null>(null);
  const [data, setData] = useState<ChartData | null>(null);
  const [governance, setGovernance] = useState<GovernanceHistory | null>(null);
  const [gaps, setGaps] = useState<KnowledgeGapAnalytics | null>(null);
  const [complexity, setComplexity] = useState<ProcessComplexityAnalytics | null>(null);
  const [value, setValue] = useState<ValueAnalytics | null>(null);
  const [validation, setValidation] = useState<ValidationEvidenceReport | null>(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
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

  function onSelectSection(next: AnalyticsSection) {
    setSection(next);
    window.history.replaceState(null, "", `#analytics-${next}`);
  }

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

  async function onDownloadReport() {
    setReportBusy(true);
    setReportError(null);
    try {
      const markdown = await getAnalyticsReportMarkdown();
      const url = URL.createObjectURL(new Blob([markdown], { type: "text/markdown" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = "analytics-evidence-report.md";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setReportError(err instanceof Error ? err.message : "Could not export analytics report.");
    } finally {
      setReportBusy(false);
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
  const summaryMetrics = [
    { label: "Queries", value: card ? String(card.total_queries) : "0", note: "Total assistant demand captured in trace data." },
    { label: "Answer rate", value: card ? `${Math.round(card.answer_rate * 100)}%` : "0%", note: "Higher is better when answers remain grounded." },
    { label: "Grounded rate", value: card ? `${Math.round(card.grounded_rate * 100)}%` : "0%", note: "Low values point to evidence or validation problems." },
    { label: "Knowledge gaps", value: card ? String(card.knowledge_gaps.length) : "0", tone: card?.knowledge_gaps.length ? "warn" as const : "good" as const },
    { label: "Open issues", value: governance ? String(governance.open_count) : "0", tone: governance?.open_count ? "warn" as const : "good" as const },
    { label: "Observed value", value: value ? formatGbp(value.telemetry.observed_total_gbp) : "GBP 0", note: "Recorded value events, not forecast value." },
    { label: "Evidence refs", value: validation ? String(validation.summary.evidence_reference_count) : "0", note: "References backing KSB and validation evidence." },
    { label: "Avg complexity", value: complexity ? String(complexity.average_complexity) : "0", note: "Extracted process-complexity indicator." },
  ];
  const complexityChartRows = complexity?.processes.slice(0, 12) ?? [];
  const hiddenComplexityCount = Math.max(0, (complexity?.process_count ?? 0) - complexityChartRows.length);

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Analytics</h1>
        <p>Focused views for demand, quality, value, validation, governance and process-risk evidence.</p>
        <div className="analytics-actions">
          <button type="button" className="secondary-button" onClick={onDownloadReport} disabled={reportBusy}>
            {reportBusy ? "Exporting..." : "Export report"}
          </button>
          {reportError ? <span className="muted-text" style={{ color: "var(--red)" }}>{reportError}</span> : null}
        </div>
      </div>

      <div className="analytics-nav" aria-label="Analytics sections">
        {SECTIONS.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`analytics-nav-button${section === item.key ? " analytics-nav-button--active" : ""}`}
            onClick={() => onSelectSection(item.key)}
          >
            <span>{item.label}</span>
            <small>{item.summary}</small>
          </button>
        ))}
      </div>

      {section === "summary" ? (
        <SummarySection card={card} data={data} metrics={summaryMetrics} governance={governance} gaps={gaps} complexity={complexity} value={value} />
      ) : null}
      {section === "value" ? (
        <ValueSection
          value={value}
          activeValueMetric={activeValueMetric}
          valueDriverOptions={valueDriverOptions}
          valueForm={valueForm}
          valueBusy={valueBusy}
          valueError={valueError}
          onChangeForm={setValueForm}
          onRecordValueEvent={onRecordValueEvent}
        />
      ) : null}
      {section === "validation" ? <ValidationSection validation={validation} /> : null}
      {section === "governance" ? <GovernanceGapsSection governance={governance} gaps={gaps} /> : null}
      {section === "process" ? (
        <ProcessComplexitySection
          complexity={complexity}
          rows={complexityChartRows}
          hiddenCount={hiddenComplexityCount}
        />
      ) : null}
      {section === "detail" ? <ProcessDetailSection complexity={complexity} /> : null}
    </div>
  );
}

function SummarySection({
  card,
  data,
  metrics,
  governance,
  gaps,
  complexity,
  value,
}: {
  card: Scorecard | null;
  data: ChartData | null;
  metrics: { label: string; value: string; note?: string; tone?: "good" | "warn" }[];
  governance: GovernanceHistory | null;
  gaps: KnowledgeGapAnalytics | null;
  complexity: ProcessComplexityAnalytics | null;
  value: ValueAnalytics | null;
}) {
  return (
    <>
      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Executive Summary</h2>
            <p className="muted-text">The first read across demand, quality, governance and value signals.</p>
          </div>
          <span className="status-pill">{card ? `${card.total_queries} queries` : "loading"}</span>
        </div>
        <MetricGrid items={metrics} />
      </div>

      <div className="analytics-grid analytics-grid--two">
        <InsightPanel title="How to read this page">
          <p>Use answer rate and grounded rate together. A high answer rate is useful only when the answer remains supported by approved evidence.</p>
        </InsightPanel>
        <InsightPanel title="Current review focus" tone={(governance?.open_count ?? 0) || (card?.knowledge_gaps.length ?? 0) ? "warn" : "good"}>
          <p>
            {(governance?.open_count ?? 0) || (card?.knowledge_gaps.length ?? 0)
              ? "Prioritise open governance issues and repeated knowledge gaps before treating value projections as reliable."
              : "No major open governance or knowledge-gap signal is visible in the current data."}
          </p>
        </InsightPanel>
      </div>

      {!data ? (
        <EmptyPanel>Loading summary charts...</EmptyPanel>
      ) : (
        <div className="analytics-grid analytics-grid--two">
          <ChartCard title="Query volume over time" subtitle="Daily demand for approved knowledge">
            <LineChart data={data.volume_over_time}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e2e8f0)" />
              <XAxis dataKey="date" fontSize={11} /><YAxis allowDecimals={false} fontSize={11} />
              <Tooltip /><Legend />
              <Line type="monotone" dataKey="real_queries" name="Real" stroke="#2563eb" strokeWidth={2} />
              <Line type="monotone" dataKey="synthetic_queries" name="Synthetic" stroke="#d97706" strokeWidth={2} />
            </LineChart>
          </ChartCard>

          <ChartCard title="Outcomes" subtitle="Answered, refused and guardrail outcomes">
            <PieChart>
              <Pie data={data.outcomes} dataKey="value" nameKey="name" outerRadius={75} label>
                {data.outcomes.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Legend /><Tooltip />
            </PieChart>
          </ChartCard>

          <ChartCard title="Demand by topic" subtitle="What people ask about">
            <BarChart data={data.by_topic}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e2e8f0)" />
              <XAxis dataKey="topic" fontSize={10} interval={0} angle={-20} textAnchor="end" height={50} />
              <YAxis allowDecimals={false} fontSize={11} /><Tooltip />
              <Bar dataKey="count" fill="#7c3aed" radius={[3, 3, 0, 0]} />
            </BarChart>
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

          <ChartCard title="Answer confidence" subtitle="Grounded versus unverified">
            <PieChart>
              <Pie data={data.confidence} dataKey="value" nameKey="name" outerRadius={75} label>
                {data.confidence.map((_, i) => <Cell key={i} fill={COLORS[(i + 2) % COLORS.length]} />)}
              </Pie>
              <Legend /><Tooltip />
            </PieChart>
          </ChartCard>
        </div>
      )}

      <div className="analytics-grid analytics-grid--three">
        <SmallSignal title="Value base" value={value ? formatGbp(value.metrics[0]?.net_annual_benefit_gbp ?? 0) : "GBP 0"} note="Assumption-led net annual benefit." />
        <SmallSignal title="Gap clusters" value={gaps ? String(gaps.cluster_count) : "0"} note="Repeated unanswered or weakly answered themes." />
        <SmallSignal title="High process risk" value={complexity ? String(complexity.high_risk_count) : "0"} note="High key-person-risk indicators." />
      </div>
    </>
  );
}

function SmallSignal({ title, value, note }: { title: string; value: string; note: string }) {
  return (
    <div className="panel">
      <div className="result-head"><b style={{ fontSize: 22 }}>{value}</b></div>
      <p className="result-cite">{title}</p>
      <p className="muted-text" style={{ marginBottom: 0 }}>{note}</p>
    </div>
  );
}

function ValueSection({
  value,
  activeValueMetric,
  valueDriverOptions,
  valueForm,
  valueBusy,
  valueError,
  onChangeForm,
  onRecordValueEvent,
}: {
  value: ValueAnalytics | null;
  activeValueMetric: ValueAnalytics["metrics"][number] | null;
  valueDriverOptions: string[];
  valueForm: { label: string; value_driver: string; value_estimate: string; process_area: string; scenario_id: string };
  valueBusy: boolean;
  valueError: string | null;
  onChangeForm: React.Dispatch<React.SetStateAction<{ label: string; value_driver: string; value_estimate: string; process_area: string; scenario_id: string }>>;
  onRecordValueEvent: (event: React.FormEvent) => Promise<void>;
}) {
  if (!value) return <EmptyPanel>Loading value analytics...</EmptyPanel>;

  return (
    <>
      <div className="analytics-grid analytics-grid--two">
        <InsightPanel title="What this proves">
          <p>Scenario metrics show the commercial case the platform is trying to test. Recorded events show observed evidence, not final enterprise value.</p>
        </InsightPanel>
        <InsightPanel title="Expected follow-up action">
          <p>Keep assumptions conservative until real usage telemetry and stakeholder validation confirm the time, delay and rework reductions.</p>
        </InsightPanel>
      </div>

      <div className="analytics-grid analytics-grid--two">
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

        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2 style={{ fontSize: 15 }}>Value telemetry</h2>
              <p className="muted-text">{value.telemetry.event_count} recorded events · {formatGbp(value.telemetry.observed_total_gbp)}</p>
            </div>
            <span className="status-pill">{activeValueMetric ? `${activeValueMetric.simple_payback_years ?? "n/a"}y payback` : "n/a"}</span>
          </div>
          <form onSubmit={onRecordValueEvent} className="analytics-form-grid">
            <label className="field-label">
              Event label
              <input
                value={valueForm.label}
                onChange={(event) => onChangeForm((current) => ({ ...current, label: event.target.value }))}
              />
            </label>
            <label className="field-label">
              GBP value
              <input
                type="number"
                min="0"
                step="0.01"
                value={valueForm.value_estimate}
                onChange={(event) => onChangeForm((current) => ({ ...current, value_estimate: event.target.value }))}
              />
            </label>
            <label className="field-label">
              Driver
              <select value={valueForm.value_driver} onChange={(event) => onChangeForm((current) => ({ ...current, value_driver: event.target.value }))}>
                {valueDriverOptions.map((driver) => <option value={driver} key={driver}>{driverLabel(driver)}</option>)}
              </select>
            </label>
            <label className="field-label">
              Scenario
              <select value={valueForm.scenario_id} onChange={(event) => onChangeForm((current) => ({ ...current, scenario_id: event.target.value }))}>
                {value.scenarios.map((scenario) => <option value={scenario.scenario_id} key={scenario.scenario_id}>{scenario.label}</option>)}
              </select>
            </label>
            <label className="field-label">
              Process area
              <input
                value={valueForm.process_area}
                onChange={(event) => onChangeForm((current) => ({ ...current, process_area: event.target.value }))}
              />
            </label>
            <button type="submit" className="primary-button" disabled={valueBusy || !valueForm.label.trim() || !valueForm.value_estimate.trim()}>
              {valueBusy ? "Recording..." : "Record"}
            </button>
          </form>
          {valueError ? <p className="muted-text" style={{ color: "var(--red)", marginTop: 10 }}>{valueError}</p> : null}
        </div>
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Value assumptions ledger</h2>
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
                  <td>{driverLabel(assumption.driver)}</td>
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

      <RecentValueEvents value={value} />
    </>
  );
}

function RecentValueEvents({ value }: { value: ValueAnalytics }) {
  if (!value.telemetry.recent_events.length) {
    return <EmptyPanel>No observed value events have been recorded yet.</EmptyPanel>;
  }
  return (
    <div className="panel">
      <div className="panel-heading">
        <div>
          <h2>Recent value events</h2>
          <p className="muted-text">Operator-entered evidence used to compare assumptions with observed signals.</p>
        </div>
      </div>
      <div className="table-frame">
        <table className="data-table">
          <thead><tr><th>Event</th><th>Driver</th><th>Process</th><th>Scenario</th><th>Value</th></tr></thead>
          <tbody>
            {value.telemetry.recent_events.slice(0, 8).map((event) => (
              <tr key={event.event_id}>
                <td>{event.label}</td>
                <td>{driverLabel(event.value_driver)}</td>
                <td>{event.process_area || "n/a"}</td>
                <td>{event.scenario_id}</td>
                <td>{formatGbp(event.value_estimate)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ValidationSection({ validation }: { validation: ValidationEvidenceReport | null }) {
  if (!validation) return <EmptyPanel>Loading validation evidence...</EmptyPanel>;

  return (
    <>
      <div className="analytics-grid analytics-grid--two">
        <InsightPanel title="What this proves">
          <p>These rows show that analytics claims are tied to named evidence, acceptance rules and known boundaries.</p>
        </InsightPanel>
        <InsightPanel title="What it does not prove" tone="warn">
          <p>Validation evidence is not a guarantee that every business outcome is correct; it is a controlled audit trail for how claims are tested.</p>
        </InsightPanel>
      </div>

      <MetricGrid
        items={[
          { label: "KSB rows", value: String(validation.summary.ksb_count) },
          { label: "Protocols", value: String(validation.summary.validation_protocol_count) },
          { label: "Evidence refs", value: String(validation.summary.evidence_reference_count) },
          { label: "Implemented KSB", value: String(validation.summary.ksb_by_status.implemented ?? 0) },
        ]}
      />

      <div className="analytics-grid analytics-grid--two">
        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Validation protocol catalogue</h2>
              <p className="muted-text">How each analytics component is checked and bounded.</p>
            </div>
          </div>
          <div className="result-list" style={{ gap: 10 }}>
            {validation.validation_protocols.map((protocol) => (
              <div className="result-card" key={protocol.protocol_id}>
                <div className="result-head">
                  <b>{protocol.component}</b>
                  <span className="status-pill">{protocol.status}</span>
                </div>
                <p className="result-cite">{protocol.protocol_id} · {protocol.metric} · {protocol.cadence}</p>
                <p className="result-text">{protocol.acceptance_rule}</p>
                <p className="result-cite">{protocol.boundary}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Evidence caveats</h2>
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
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>KSB traceability</h2>
            <p className="muted-text">Project evidence mapping across delivered analytics features.</p>
          </div>
          <span className="status-pill">{validation.summary.ksb_by_status.implemented ?? 0} implemented</span>
        </div>
        <div className="table-frame">
          <table className="data-table">
            <thead><tr><th>KSB</th><th>Capability</th><th>Delivered evidence</th><th>References</th><th>Status</th><th>Next evidence</th></tr></thead>
            <tbody>
              {validation.ksb_rows.map((row) => (
                <tr key={row.ksb_id}>
                  <td>{row.ksb_id}<p className="result-cite">{row.category}</p></td>
                  <td><b>{row.capability}</b><p className="result-cite">{row.evidence_claim}</p></td>
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
  );
}

function GovernanceGapsSection({ governance, gaps }: { governance: GovernanceHistory | null; gaps: KnowledgeGapAnalytics | null }) {
  return (
    <>
      <div className="analytics-grid analytics-grid--two">
        <InsightPanel title="What this shows">
          <p>Governance charts show source-quality workflow pressure. Gap clusters show where users are repeatedly not getting grounded answers.</p>
        </InsightPanel>
        <InsightPanel title="Expected follow-up action">
          <p>Use recurring issues and high-friction clusters to decide which sources to repair, approve, merge or supplement next.</p>
        </InsightPanel>
      </div>

      {!governance ? (
        <EmptyPanel>Loading governance history...</EmptyPanel>
      ) : (
        <div className="analytics-grid analytics-grid--two">
          <ChartCard title="Governance issue burndown" subtitle="Detected, accepted, resolved and still open">
            <LineChart data={governance.issue_events_over_time}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e2e8f0)" />
              <XAxis dataKey="date" fontSize={11} />
              <YAxis allowDecimals={false} fontSize={11} />
              <Tooltip /><Legend />
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
              <Tooltip /><Bar dataKey="count" fill="#d97706" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ChartCard>

          <div className="panel">
            <div className="panel-heading">
              <div>
                <h2 style={{ fontSize: 15 }}>Recurring issue signals</h2>
                <p className="muted-text">Repeated detections across governance snapshots.</p>
              </div>
            </div>
            {governance.recurring_issues.length ? (
              <div className="table-frame">
                <table className="data-table">
                  <thead><tr><th>Issue</th><th>Source</th><th>Detections</th><th>Last seen</th><th>State</th></tr></thead>
                  <tbody>
                    {governance.recurring_issues.slice(0, 8).map((issue) => (
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
            ) : <p className="muted-text">No recurring governance issues.</p>}
          </div>
        </div>
      )}

      {!gaps ? (
        <EmptyPanel>Loading knowledge-gap analytics...</EmptyPanel>
      ) : (
        <div className="analytics-grid analytics-grid--two">
          <ChartCard title="Knowledge-gap clusters" subtitle={`Quality ${Math.round(gaps.silhouette_score * 100)}%`}>
            <BarChart data={gaps.clusters}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e2e8f0)" />
              <XAxis dataKey="label" fontSize={10} interval={0} angle={-20} textAnchor="end" height={64} />
              <YAxis allowDecimals={false} fontSize={11} />
              <Tooltip /><Bar dataKey="question_count" fill="#db2777" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ChartCard>

          <div className="panel">
            <div className="panel-heading">
              <div>
                <h2 style={{ fontSize: 15 }}>Onboarding friction</h2>
                <p className="muted-text">{gaps.total_candidates} candidate questions</p>
              </div>
              <span className="status-pill">silhouette {gaps.silhouette_score}</span>
            </div>
            {gaps.clusters.length ? (
              <div className="result-list" style={{ gap: 10 }}>
                {gaps.clusters.map((cluster) => (
                  <div className="result-card" key={cluster.id}>
                    <div className="result-head">
                      <b>{cluster.label}</b>
                      <span className="status-pill">{cluster.friction_score}</span>
                    </div>
                    <p className="result-cite">{cluster.process_area} · {cluster.question_count} questions · {cluster.confidence}</p>
                    <p className="result-text">{cluster.source_gap}</p>
                    {cluster.representative_questions.slice(0, 2).map((question) => <p className="result-cite" key={question}>{question}</p>)}
                  </div>
                ))}
              </div>
            ) : <p className="muted-text">No knowledge-gap clusters.</p>}
          </div>
        </div>
      )}
    </>
  );
}

function ProcessComplexitySection({
  complexity,
  rows,
  hiddenCount,
}: {
  complexity: ProcessComplexityAnalytics | null;
  rows: ProcessComplexityAnalytics["processes"];
  hiddenCount: number;
}) {
  if (!complexity) return <EmptyPanel>Loading process-complexity analytics...</EmptyPanel>;

  return (
    <>
      <div className="analytics-grid analytics-grid--two">
        <InsightPanel title="What this shows">
          <p>Complexity scores combine extracted signals such as roles, systems, dependencies, controls, hand-offs and exception wording.</p>
        </InsightPanel>
        <InsightPanel title="Expected follow-up action">
          <p>High complexity or key-person risk should trigger source review, SME validation or process-map refinement before operational conclusions are drawn.</p>
        </InsightPanel>
      </div>

      <MetricGrid
        items={[
          { label: "Process records", value: String(complexity.process_count) },
          { label: "Average complexity", value: String(complexity.average_complexity) },
          { label: "High key-person risk", value: String(complexity.high_risk_count), tone: complexity.high_risk_count ? "warn" : "good" },
        ]}
      />

      <div className="analytics-grid analytics-grid--two">
        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2 style={{ fontSize: 15 }}>Process complexity</h2>
              <p className="muted-text">Top {rows.length} by complexity{hiddenCount ? ` · ${hiddenCount} more in detail` : ""}</p>
            </div>
          </div>
          {rows.length ? (
            <ResponsiveContainer width="100%" height={Math.max(260, rows.length * 34)}>
              <BarChart data={rows} layout="vertical" margin={{ left: 18, right: 12 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e2e8f0)" />
                <XAxis type="number" domain={[0, 100]} allowDecimals={false} fontSize={11} />
                <YAxis type="category" dataKey="name" width={170} fontSize={9} interval={0} />
                <Tooltip /><Legend />
                <Bar dataKey="complexity_score" fill="#2563eb" radius={[0, 3, 3, 0]} />
                <Bar dataKey="key_person_risk_score" fill="#dc2626" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <p className="muted-text">No process-complexity indicators.</p>}
        </div>

        <div className="panel">
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
      </div>
    </>
  );
}

function ProcessDetailSection({ complexity }: { complexity: ProcessComplexityAnalytics | null }) {
  if (!complexity) return <EmptyPanel>Loading process detail...</EmptyPanel>;

  return (
    <>
      <InsightPanel title="How to use this table">
        <p>Use the full detail table when a high-level score needs evidence. The signals explain which extracted process attributes drove each rating.</p>
      </InsightPanel>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Process indicator detail</h2>
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
                    <td><b>{process.name}</b><p className="result-cite">{process.source_title}</p></td>
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
        ) : <p className="muted-text">No process-complexity indicators.</p>}
      </div>
    </>
  );
}
