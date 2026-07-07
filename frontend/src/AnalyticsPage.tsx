import { useEffect, useState } from "react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  captureGovernanceSnapshot,
  createImprovementAction,
  getAnalyticsDictionaryMarkdown,
  getAnalyticsExportDataset,
  getAnalyticsExportIndex,
  getAnalyticsForecast,
  getAnalyticsCharts,
  getAnalyticsComputationTraces,
  getAnalyticsMethods,
  getAnalyticsReportMarkdown,
  getAnalyticsReportPdf,
  getAnalyticsReproducibilityPack,
  getGovernanceHistory,
  getKnowledgeGaps,
  getImprovementActions,
  getImprovementMetrics,
  getOntologyStats,
  getProcessComplexity,
  getRecurringQuestions,
  getRetrievalHealth,
  getScorecard,
  getValidationEvidence,
  getValueAnalytics,
  recordValueEvent,
  transitionImprovementAction,
  type AnalyticsComputationTrace,
  type AnalyticsExportFormat,
  type AnalyticsExportIndex,
  type AnalyticsForecastReport,
  type AnalyticsMethodsCatalogue,
  type ChartData,
  type GovernanceHistory,
  type ImprovementAction,
  type ImprovementActionCreatePayload,
  type ImprovementActionList,
  type ImprovementActionTransitionPayload,
  type ImprovementLoopMetrics,
  type KnowledgeGapAnalytics,
  type OntologyStats,
  type ProcessComplexityAnalytics,
  type RecurringQuestionAnalytics,
  type RetrievalHealthAnalytics,
  type Scorecard,
  type ValidationEvidenceReport,
  type ValueAnalytics,
} from "./api";

const COLORS = ["#16a34a", "#dc2626", "#d97706", "#2563eb", "#7c3aed", "#db2777", "#0891b2", "#65a30d"];

type AnalyticsSection = "summary" | "precision" | "improvement" | "value" | "validation" | "governance" | "process" | "detail" | "forecast" | "methods";

const SECTIONS: { key: AnalyticsSection; label: string; summary: string }[] = [
  { key: "summary", label: "Summary", summary: "Demand, quality and attention signals" },
  { key: "precision", label: "Precision", summary: "Recurring questions and retrieval health" },
  { key: "improvement", label: "Improvement Loop", summary: "Action lifecycle and review workload" },
  { key: "value", label: "Value", summary: "Assumptions, scenarios and observed benefit" },
  { key: "validation", label: "Validation/KSB", summary: "Evidence discipline and claims boundaries" },
  { key: "governance", label: "Governance Gaps", summary: "Issue trends and knowledge-gap clusters" },
  { key: "process", label: "Process Complexity", summary: "Risk, complexity and glossary" },
  { key: "detail", label: "Process Detail", summary: "Full process indicator table" },
  { key: "forecast", label: "Forecast", summary: "Demand, refusal and accuracy signals" },
  { key: "methods", label: "Methods", summary: "Models, formulas and calculation traces" },
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

type MetricItem = { label: string; value: string; note?: string; tone?: "good" | "warn"; traceId?: string };

function MetricGrid({ items, traces = {} }: { items: MetricItem[]; traces?: Record<string, AnalyticsComputationTrace> }) {
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
          {metric.traceId && traces[metric.traceId] ? <TraceDisclosure trace={traces[metric.traceId]} compact /> : null}
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

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
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
  const [recurring, setRecurring] = useState<RecurringQuestionAnalytics | null>(null);
  const [retrievalHealth, setRetrievalHealth] = useState<RetrievalHealthAnalytics | null>(null);
  const [improvementActions, setImprovementActions] = useState<ImprovementActionList | null>(null);
  const [improvementMetrics, setImprovementMetrics] = useState<ImprovementLoopMetrics | null>(null);
  const [improvementBusy, setImprovementBusy] = useState<string | null>(null);
  const [improvementError, setImprovementError] = useState<string | null>(null);
  const [complexity, setComplexity] = useState<ProcessComplexityAnalytics | null>(null);
  const [ontologyStats, setOntologyStats] = useState<OntologyStats | null>(null);
  const [value, setValue] = useState<ValueAnalytics | null>(null);
  const [validation, setValidation] = useState<ValidationEvidenceReport | null>(null);
  const [methods, setMethods] = useState<AnalyticsMethodsCatalogue | null>(null);
  const [traces, setTraces] = useState<Record<string, AnalyticsComputationTrace>>({});
  const [forecastSeries, setForecastSeries] = useState("query_volume");
  const [forecast, setForecast] = useState<AnalyticsForecastReport | null>(null);
  const [forecastError, setForecastError] = useState<string | null>(null);
  const [reportBusy, setReportBusy] = useState<"markdown" | "pdf" | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const [exportIndex, setExportIndex] = useState<AnalyticsExportIndex | null>(null);
  const [exportDataset, setExportDataset] = useState("usage_log");
  const [exportFormat, setExportFormat] = useState<AnalyticsExportFormat>("csv");
  const [exportBusy, setExportBusy] = useState<"dataset" | "dictionary" | "bundle" | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [snapshotBusy, setSnapshotBusy] = useState(false);
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
    getRecurringQuestions().then(setRecurring).catch(() => setRecurring(null));
    getRetrievalHealth().then(setRetrievalHealth).catch(() => setRetrievalHealth(null));
    refreshImprovementLoop();
    getProcessComplexity().then(setComplexity).catch(() => setComplexity(null));
    getOntologyStats().then(setOntologyStats).catch(() => setOntologyStats(null));
    getValueAnalytics().then(setValue).catch(() => setValue(null));
    getValidationEvidence().then(setValidation).catch(() => setValidation(null));
    getAnalyticsMethods().then(setMethods).catch(() => setMethods(null));
    getAnalyticsComputationTraces()
      .then((report) => setTraces(Object.fromEntries(report.traces.map((trace) => [trace.metric_id, trace]))))
      .catch(() => setTraces({}));
    getAnalyticsExportIndex()
      .then((index) => {
        setExportIndex(index);
        if (index.datasets.length && !index.datasets.some((dataset) => dataset.dataset === "usage_log")) {
          setExportDataset(index.datasets[0].dataset);
        }
      })
      .catch(() => setExportIndex(null));
  }, []);

  async function refreshImprovementLoop() {
    try {
      const [actions, metrics] = await Promise.all([getImprovementActions(), getImprovementMetrics()]);
      setImprovementActions(actions);
      setImprovementMetrics(metrics);
    } catch {
      setImprovementActions(null);
      setImprovementMetrics(null);
    }
  }

  useEffect(() => {
    setForecastError(null);
    getAnalyticsForecast(forecastSeries, 7)
      .then(setForecast)
      .catch((err) => {
        setForecast(null);
        setForecastError(err instanceof Error ? err.message : "Could not load analytics forecast.");
      });
  }, [forecastSeries]);

  function onSelectSection(next: AnalyticsSection) {
    setSection(next);
    window.history.replaceState(null, "", `#analytics-${next}`);
  }

  async function onCaptureSnapshot() {
    setSnapshotBusy(true);
    try {
      setGovernance(await captureGovernanceSnapshot());
    } catch {
      // leave existing history in place on failure
    } finally {
      setSnapshotBusy(false);
    }
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

  async function onRaiseImprovement(payload: ImprovementActionCreatePayload) {
    setImprovementBusy(`${payload.trigger_type}:${payload.trigger_ref}`);
    setImprovementError(null);
    try {
      await createImprovementAction(payload);
      await refreshImprovementLoop();
    } catch (err) {
      setImprovementError(err instanceof Error ? err.message : "Could not raise improvement action.");
    } finally {
      setImprovementBusy(null);
    }
  }

  async function onTransitionImprovement(actionId: string, payload: ImprovementActionTransitionPayload) {
    setImprovementBusy(`${actionId}:${payload.status}`);
    setImprovementError(null);
    try {
      await transitionImprovementAction(actionId, payload);
      await refreshImprovementLoop();
    } catch (err) {
      setImprovementError(err instanceof Error ? err.message : "Could not update improvement action.");
    } finally {
      setImprovementBusy(null);
    }
  }

  async function onDownloadReport() {
    setReportBusy("markdown");
    setReportError(null);
    try {
      const markdown = await getAnalyticsReportMarkdown();
      downloadBlob(new Blob([markdown], { type: "text/markdown" }), "analytics-evidence-report.md");
    } catch (err) {
      setReportError(err instanceof Error ? err.message : "Could not export analytics report.");
    } finally {
      setReportBusy(null);
    }
  }

  async function onDownloadPdfReport() {
    setReportBusy("pdf");
    setReportError(null);
    try {
      const pdf = await getAnalyticsReportPdf();
      downloadBlob(pdf, "analytics-evidence-report.pdf");
    } catch (err) {
      setReportError(err instanceof Error ? err.message : "Could not export analytics PDF report.");
    } finally {
      setReportBusy(null);
    }
  }

  async function onDownloadDataset() {
    setExportBusy("dataset");
    setExportError(null);
    try {
      const dataset = await getAnalyticsExportDataset(exportDataset, exportFormat);
      downloadBlob(dataset, `opsatlas-${exportDataset}.${exportFormat}`);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "Could not export analytics dataset.");
    } finally {
      setExportBusy(null);
    }
  }

  async function onDownloadDictionary() {
    setExportBusy("dictionary");
    setExportError(null);
    try {
      const markdown = await getAnalyticsDictionaryMarkdown();
      downloadBlob(new Blob([markdown], { type: "text/markdown" }), "opsatlas-analytics-data-dictionary.md");
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "Could not export analytics data dictionary.");
    } finally {
      setExportBusy(null);
    }
  }

  async function onDownloadReproducibilityPack() {
    setExportBusy("bundle");
    setExportError(null);
    try {
      const bundle = await getAnalyticsReproducibilityPack();
      downloadBlob(bundle, "opsatlas-analytics-reproducibility-pack.zip");
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "Could not export analytics reproducibility pack.");
    } finally {
      setExportBusy(null);
    }
  }

  const activeValueMetric = value?.metrics.find((metric) => metric.scenario_id === value.active_scenario_id) ?? value?.metrics[0] ?? null;
  const selectedExportDataset = exportIndex?.datasets.find((dataset) => dataset.dataset === exportDataset) ?? exportIndex?.datasets[0] ?? null;
  const valueDriverOptions = Array.from(new Set([
    "time_saved",
    "sme_clarification_avoided",
    "delivery_delay_reduced",
    "rework_avoided",
    ...(value?.driver_options ?? []),
  ]));
  const summaryMetrics = [
    { label: "Queries", value: card ? String(card.total_queries) : "0", note: "Total assistant demand captured in trace data." },
    {
      label: "Answer rate",
      value: card ? `${Math.round(card.answer_rate * 100)}%` : "0%",
      note: "Higher is better when answers remain grounded.",
      traceId: "coverage_score",
    },
    {
      label: "Grounded rate",
      value: card ? `${Math.round(card.grounded_rate * 100)}%` : "0%",
      note: "Low values point to evidence or validation problems.",
      traceId: "coverage_score",
    },
    {
      label: "Knowledge gaps",
      value: card ? String(card.knowledge_gaps.length) : "0",
      tone: card?.knowledge_gaps.length ? "warn" as const : "good" as const,
      traceId: "knowledge_gap_silhouette",
    },
    { label: "Open issues", value: governance ? String(governance.open_count) : "0", tone: governance?.open_count ? "warn" as const : "good" as const },
    {
      label: "Observed value",
      value: value ? formatGbp(value.telemetry.observed_total_gbp) : "GBP 0",
      note: "Recorded value events, not forecast value.",
      traceId: "value_forecast_projection",
    },
    { label: "Evidence refs", value: validation ? String(validation.summary.evidence_reference_count) : "0", note: "References backing KSB and validation evidence." },
    {
      label: "Avg complexity",
      value: complexity ? String(complexity.average_complexity) : "0",
      note: "Extracted process-complexity indicator.",
      traceId: "process_complexity",
    },
    { label: "Ontology objects", value: ontologyStats ? String(ontologyStats.total_objects) : "0", note: `${ontologyStats?.total_links ?? 0} governed links` },
  ];
  const complexityChartRows = complexity?.processes.slice(0, 12) ?? [];
  const hiddenComplexityCount = Math.max(0, (complexity?.process_count ?? 0) - complexityChartRows.length);

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Analytics</h1>
        <p>Focused views for demand, quality, value, validation, governance and process-risk evidence.</p>
        <div className="analytics-actions">
          <button type="button" className="secondary-button" onClick={onDownloadReport} disabled={reportBusy !== null}>
            {reportBusy === "markdown" ? "Exporting..." : "Export Markdown"}
          </button>
          <button type="button" className="secondary-button" onClick={onDownloadPdfReport} disabled={reportBusy !== null}>
            {reportBusy === "pdf" ? "Exporting..." : "Export PDF"}
          </button>
          {reportError ? <span className="muted-text" style={{ color: "var(--red)" }}>{reportError}</span> : null}
        </div>
      </div>

      <div className="panel analytics-export-panel">
        <div className="panel-heading">
          <div>
            <h2>Raw Data Export</h2>
            <p className="muted-text">Download reproducible analytics datasets and the generated field dictionary.</p>
          </div>
          <span className="status-pill">{exportIndex ? `${exportIndex.dataset_count} datasets` : "loading"}</span>
        </div>
        <div className="analytics-export-controls">
          <label className="field-label analytics-export-dataset">
            Dataset
            <select
              value={selectedExportDataset?.dataset ?? exportDataset}
              onChange={(event) => setExportDataset(event.target.value)}
              disabled={!exportIndex?.datasets.length || exportBusy !== null}
            >
              {(exportIndex?.datasets ?? []).map((dataset) => (
                <option value={dataset.dataset} key={dataset.dataset}>
                  {dataset.label} ({dataset.row_count})
                </option>
              ))}
            </select>
          </label>
          <div className="analytics-export-format" aria-label="Dataset export format">
            <span className="field-label">Format</span>
            <div className="segmented-control">
              {(["csv", "json"] as AnalyticsExportFormat[]).map((format) => (
                <button
                  key={format}
                  type="button"
                  className={exportFormat === format ? "is-active" : ""}
                  onClick={() => setExportFormat(format)}
                  disabled={exportBusy !== null}
                >
                  {format.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <button
            type="button"
            className="secondary-button"
            onClick={onDownloadDataset}
            disabled={!selectedExportDataset || exportBusy !== null}
          >
            {exportBusy === "dataset" ? "Exporting..." : "Export Dataset"}
          </button>
          <button type="button" className="secondary-button" onClick={onDownloadDictionary} disabled={exportBusy !== null}>
            {exportBusy === "dictionary" ? "Exporting..." : "Data Dictionary"}
          </button>
          <button type="button" className="primary-button" onClick={onDownloadReproducibilityPack} disabled={exportBusy !== null}>
            {exportBusy === "bundle" ? "Building..." : "Reproducibility Pack"}
          </button>
        </div>
        {selectedExportDataset ? <p className="muted-text">{selectedExportDataset.description}</p> : null}
        {exportIndex?.ethics_boundary ? <p className="muted-text">{exportIndex.ethics_boundary}</p> : null}
        {exportError ? <p className="muted-text" style={{ color: "var(--red)", marginBottom: 0 }}>{exportError}</p> : null}
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
        <SummarySection
          card={card}
          data={data}
          metrics={summaryMetrics}
          governance={governance}
          gaps={gaps}
          complexity={complexity}
          ontologyStats={ontologyStats}
          value={value}
          traces={traces}
        />
      ) : null}
      {section === "precision" ? (
        <PrecisionSection
          recurring={recurring}
          retrievalHealth={retrievalHealth}
          improvementActions={improvementActions?.actions ?? []}
          improvementBusy={improvementBusy}
          improvementError={improvementError}
          onRaiseImprovement={onRaiseImprovement}
        />
      ) : null}
      {section === "improvement" ? (
        <ImprovementLoopSection
          actions={improvementActions?.actions ?? []}
          metrics={improvementMetrics}
          improvementBusy={improvementBusy}
          improvementError={improvementError}
          onTransitionImprovement={onTransitionImprovement}
        />
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
      {section === "governance" ? (
        <>
          <div className="panel" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
            <p className="muted-text" style={{ margin: 0 }}>Governance health is captured on demand (the trend builds one point per capture).</p>
            <button type="button" className="mini-button" disabled={snapshotBusy} onClick={() => void onCaptureSnapshot()}>
              {snapshotBusy ? "Capturing…" : "Capture snapshot"}
            </button>
          </div>
          <GovernanceGapsSection governance={governance} gaps={gaps} />
        </>
      ) : null}
      {section === "process" ? (
        <ProcessComplexitySection
          complexity={complexity}
          rows={complexityChartRows}
          hiddenCount={hiddenComplexityCount}
        />
      ) : null}
      {section === "detail" ? <ProcessDetailSection complexity={complexity} /> : null}
      {section === "forecast" ? (
        <ForecastSection
          forecast={forecast}
          forecastSeries={forecastSeries}
          forecastError={forecastError}
          onChangeSeries={setForecastSeries}
          onShowMethods={() => onSelectSection("methods")}
        />
      ) : null}
      {section === "methods" ? <MethodsSection methods={methods} traces={traces} /> : null}
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
  ontologyStats,
  value,
  traces,
}: {
  card: Scorecard | null;
  data: ChartData | null;
  metrics: MetricItem[];
  governance: GovernanceHistory | null;
  gaps: KnowledgeGapAnalytics | null;
  complexity: ProcessComplexityAnalytics | null;
  ontologyStats: OntologyStats | null;
  value: ValueAnalytics | null;
  traces: Record<string, AnalyticsComputationTrace>;
}) {
  const answerPathRows = Object.entries(card?.by_answer_path ?? {}).map(([name, value]) => ({
    name: answerPathLabel(name),
    value,
  }));
  const objectRows = Object.entries(ontologyStats?.by_object_type ?? {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8);
  const linkRows = Object.entries(ontologyStats?.by_link_type ?? {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8);
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
        <MetricGrid items={metrics} traces={traces} />
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

          <ChartCard title="Answer path split" subtitle="RAG, OAG and hybrid routing">
            <PieChart>
              <Pie data={answerPathRows} dataKey="value" nameKey="name" outerRadius={75} label>
                {answerPathRows.map((_, i) => <Cell key={i} fill={COLORS[(i + 4) % COLORS.length]} />)}
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

      <div className="analytics-grid analytics-grid--two">
        <OntologyBreakdown title="Ontology objects" rows={objectRows} empty="No ontology objects available." />
        <OntologyBreakdown title="Ontology links" rows={linkRows} empty="No ontology links available." />
      </div>
    </>
  );
}

function PrecisionSection({
  recurring,
  retrievalHealth,
  improvementActions,
  improvementBusy,
  improvementError,
  onRaiseImprovement,
}: {
  recurring: RecurringQuestionAnalytics | null;
  retrievalHealth: RetrievalHealthAnalytics | null;
  improvementActions: ImprovementAction[];
  improvementBusy: string | null;
  improvementError: string | null;
  onRaiseImprovement: (payload: ImprovementActionCreatePayload) => Promise<void>;
}) {
  const recurringRows = recurring?.groups.slice(0, 8) ?? [];
  const failingRows = retrievalHealth?.top_failing_patterns.slice(0, 8) ?? [];
  const metricItems: MetricItem[] = [
    {
      label: "Recurring groups",
      value: recurring ? String(recurring.group_count) : "0",
      note: `${recurring?.total_recurring_questions ?? 0} repeated questions`,
      tone: recurring?.group_count ? "warn" : "good",
    },
    {
      label: "Failed retrievals",
      value: retrievalHealth ? String(retrievalHealth.counts.failure ?? 0) : "0",
      note: `${retrievalHealth?.total_queries ?? 0} total queries`,
      tone: retrievalHealth?.counts.failure ? "warn" : "good",
    },
    {
      label: "Refusal rate",
      value: formatPercent(retrievalHealth?.rates.refusal_rate),
      note: "Queries blocked or unanswered.",
    },
    {
      label: "No-citation rate",
      value: formatPercent(retrievalHealth?.rates.no_citation_rate),
      note: "Answered rows without citations.",
    },
    {
      label: "Low-grounding rate",
      value: formatPercent(retrievalHealth?.rates.low_grounding_rate),
      note: "Confidence below grounded/high.",
    },
  ];

  return (
    <>
      <div className="analytics-grid analytics-grid--two">
        <InsightPanel title="What this shows">
          <p>Repeated questions and weak retrieval outcomes identify where approved content needs clearer wording, stronger coverage or better source structure.</p>
        </InsightPanel>
        <InsightPanel title="Expected follow-up action" tone={(recurring?.group_count ?? 0) || (retrievalHealth?.counts.failure ?? 0) ? "warn" : "good"}>
          <p>
            {(recurring?.group_count ?? 0) || (retrievalHealth?.counts.failure ?? 0)
              ? "Raise improvement actions for patterns that keep coming back or fail to retrieve grounded evidence."
              : "No repeated precision pattern is visible in the current usage data."}
          </p>
        </InsightPanel>
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Precision Metrics</h2>
            <p className="muted-text">Recurring demand and retrieval-health signals from the assistant usage ledger.</p>
          </div>
          <span className="status-pill">{retrievalHealth ? `${retrievalHealth.total_queries} queries` : "loading"}</span>
        </div>
        <MetricGrid items={metricItems} />
        {improvementError ? <p className="muted-text" style={{ color: "var(--red)", marginBottom: 0 }}>{improvementError}</p> : null}
      </div>

      <div className="analytics-grid analytics-grid--two">
        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2 style={{ fontSize: 15 }}>Recurring Questions</h2>
              <p className="muted-text">{recurring ? `${recurring.group_count} grouped patterns` : "Loading patterns"}</p>
            </div>
          </div>
          {recurringRows.length ? (
            <div className="result-list" style={{ gap: 10 }}>
              {recurringRows.map((group) => {
                const triggerKey = `recurring_question:${group.id}`;
                const alreadyRaised = hasImprovementAction(improvementActions, "recurring_question", group.id);
                return (
                  <div className="result-card" key={group.id}>
                    <div className="result-head">
                      <b>{group.representative_question}</b>
                      <span className="status-pill">{group.demand_frequency} asks</span>
                    </div>
                    <p className="result-cite">{group.topic} · {group.trend} · {group.first_seen} to {group.last_seen}</p>
                    <p className="result-text">{group.terms.slice(0, 6).join(", ") || "No dominant terms"}</p>
                    <button
                      type="button"
                      className="mini-button"
                      disabled={alreadyRaised || improvementBusy === triggerKey}
                      onClick={() => void onRaiseImprovement({
                        trigger_type: "recurring_question",
                        trigger_ref: group.id,
                        recommended_action: `Clarify source coverage for recurring question: ${group.representative_question}`,
                        owner_role: "Knowledge owner",
                        review_cadence: "weekly",
                        note: `${group.demand_frequency} repeated questions; trend ${group.trend}.`,
                      })}
                    >
                      {alreadyRaised ? "Action raised" : improvementBusy === triggerKey ? "Raising..." : "Raise action"}
                    </button>
                  </div>
                );
              })}
            </div>
          ) : <p className="muted-text">{recurring ? "No recurring question groups." : "Loading recurring questions..."}</p>}
        </div>

        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2 style={{ fontSize: 15 }}>Failed Retrieval Patterns</h2>
              <p className="muted-text">{retrievalHealth ? `${failingRows.length} visible patterns` : "Loading retrieval health"}</p>
            </div>
          </div>
          {failingRows.length ? (
            <div className="result-list" style={{ gap: 10 }}>
              {failingRows.map((pattern) => {
                const triggerKey = `failed_retrieval:${pattern.id}`;
                const alreadyRaised = hasImprovementAction(improvementActions, "failed_retrieval", pattern.id);
                return (
                  <div className="result-card" key={pattern.id}>
                    <div className="result-head">
                      <b>{pattern.representative_question}</b>
                      <span className="status-pill">{pattern.demand_frequency} failures</span>
                    </div>
                    <p className="result-cite">{pattern.topic} · {Object.entries(pattern.failure_reasons).map(([key, value]) => `${key} ${value}`).join(" · ")}</p>
                    <p className="result-text">{pattern.recommended_action}</p>
                    <button
                      type="button"
                      className="mini-button"
                      disabled={alreadyRaised || improvementBusy === triggerKey}
                      onClick={() => void onRaiseImprovement({
                        trigger_type: "failed_retrieval",
                        trigger_ref: pattern.id,
                        recommended_action: pattern.recommended_action,
                        owner_role: "Knowledge owner",
                        review_cadence: "weekly",
                        note: `${pattern.demand_frequency} failed retrieval signals from ${pattern.first_seen} to ${pattern.last_seen}.`,
                      })}
                    >
                      {alreadyRaised ? "Action raised" : improvementBusy === triggerKey ? "Raising..." : "Raise action"}
                    </button>
                  </div>
                );
              })}
            </div>
          ) : <p className="muted-text">{retrievalHealth ? "No failed retrieval patterns." : "Loading retrieval health..."}</p>}
        </div>
      </div>
    </>
  );
}

const IMPROVEMENT_STATUSES: ImprovementAction["status"][] = ["open", "in_progress", "actioned", "closed", "wont_fix"];

function ImprovementLoopSection({
  actions,
  metrics,
  improvementBusy,
  improvementError,
  onTransitionImprovement,
}: {
  actions: ImprovementAction[];
  metrics: ImprovementLoopMetrics | null;
  improvementBusy: string | null;
  improvementError: string | null;
  onTransitionImprovement: (actionId: string, payload: ImprovementActionTransitionPayload) => Promise<void>;
}) {
  const [linkedSourceIds, setLinkedSourceIds] = useState<Record<string, string>>({});
  const grouped = Object.fromEntries(
    IMPROVEMENT_STATUSES.map((status) => [status, actions.filter((action) => action.status === status)]),
  ) as Record<ImprovementAction["status"], ImprovementAction[]>;
  const metricItems: MetricItem[] = [
    { label: "Actions", value: metrics ? String(metrics.action_count) : String(actions.length), note: "All improvement actions." },
    { label: "Actioned rate", value: formatPercent(metrics?.rates.actioned_rate), note: "Actioned or closed actions." },
    { label: "Closure rate", value: formatPercent(metrics?.rates.closure_rate), note: "Closed with linked source evidence." },
    { label: "Repeat trigger rate", value: formatPercent(metrics?.rates.repeat_trigger_rate), note: "Same trigger raised more than once." },
    { label: "Oldest open age", value: metrics ? `${metrics.age.oldest_open_age_days}d` : "0d", tone: (metrics?.age.oldest_open_age_days ?? 0) > 14 ? "warn" : "good" },
    { label: "Due reviews", value: metrics ? String(metrics.review_due_count) : "0", tone: metrics?.review_due_count ? "warn" : "good" },
  ];

  function setLinkedSource(actionId: string, value: string) {
    setLinkedSourceIds((current) => ({ ...current, [actionId]: value }));
  }

  return (
    <>
      <div className="analytics-grid analytics-grid--two">
        <InsightPanel title="What this shows">
          <p>Improvement actions connect analytics findings to owned remediation work, status changes and source updates.</p>
        </InsightPanel>
        <InsightPanel title="Expected follow-up action" tone={metrics?.review_due_count ? "warn" : "good"}>
          <p>{metrics?.review_due_count ? "Review overdue actions and close only when a linked source or documented decision exists." : "No improvement action is currently overdue for review."}</p>
        </InsightPanel>
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Improvement Loop</h2>
            <p className="muted-text">Lifecycle metrics for analytics-driven source and retrieval improvements.</p>
          </div>
          <span className="status-pill">{metrics ? `${metrics.action_count} actions` : "loading"}</span>
        </div>
        <MetricGrid items={metricItems} />
        {improvementError ? <p className="muted-text" style={{ color: "var(--red)", marginBottom: 0 }}>{improvementError}</p> : null}
      </div>

      <div className="analytics-grid analytics-grid--two">
        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2 style={{ fontSize: 15 }}>Review Due</h2>
              <p className="muted-text">{metrics ? `${metrics.review_due_count} actions outside cadence` : "Loading review due list"}</p>
            </div>
          </div>
          {metrics?.review_due.length ? (
            <div className="table-frame">
              <table className="data-table">
                <thead><tr><th>Action</th><th>Owner</th><th>Status</th><th>Overdue</th></tr></thead>
                <tbody>
                  {metrics.review_due.map((row) => (
                    <tr key={row.id}>
                      <td><b>{row.recommended_action}</b><p className="result-cite">{row.trigger_type.replace(/_/g, " ")} · {row.trigger_ref}</p></td>
                      <td>{row.owner_role}</td>
                      <td>{statusLabel(row.status)}</td>
                      <td>{row.days_overdue}d</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="muted-text">{metrics ? "No actions are due for review." : "Loading improvement metrics..."}</p>}
        </div>

        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2 style={{ fontSize: 15 }}>Owner Workload</h2>
              <p className="muted-text">Open, in-progress and actioned work by owner role.</p>
            </div>
          </div>
          {metrics?.owner_workload.length ? (
            <div className="result-list" style={{ gap: 10 }}>
              {metrics.owner_workload.map((row) => (
                <div className="result-card" key={row.owner_role}>
                  <div className="result-head">
                    <b>{row.owner_role}</b>
                    <span className="status-pill">{row.open_actions} open</span>
                  </div>
                </div>
              ))}
            </div>
          ) : <p className="muted-text">{metrics ? "No open owner workload." : "Loading owner workload..."}</p>}
        </div>
      </div>

      <div className="improvement-board">
        {IMPROVEMENT_STATUSES.map((status) => (
          <div className="improvement-column" key={status}>
            <div className="result-head">
              <b>{statusLabel(status)}</b>
              <span className="status-pill">{grouped[status].length}</span>
            </div>
            <div className="result-list" style={{ gap: 10 }}>
              {grouped[status].length ? grouped[status].map((action) => {
                const linkedSource = linkedSourceIds[action.id] ?? action.linked_source_id ?? "";
                return (
                  <div className="result-card" key={action.id}>
                    <div className="result-head">
                      <b>{action.recommended_action}</b>
                      <span className="status-pill">{action.review_cadence.replace(/_/g, " ")}</span>
                    </div>
                    <p className="result-cite">{action.trigger_type.replace(/_/g, " ")} · {action.trigger_ref}</p>
                    <p className="result-text">{action.owner_role}</p>
                    {action.linked_source_id ? <p className="result-cite">Linked source: {action.linked_source_id}</p> : null}
                    {action.notes.slice(-1).map((note) => <p className="result-cite" key={`${action.id}-${note.timestamp}`}>{note.note}</p>)}
                    <ImprovementActionControls
                      action={action}
                      busy={improvementBusy}
                      linkedSource={linkedSource}
                      onLinkedSourceChange={(value) => setLinkedSource(action.id, value)}
                      onTransition={onTransitionImprovement}
                    />
                  </div>
                );
              }) : <p className="muted-text">No actions.</p>}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

function ImprovementActionControls({
  action,
  busy,
  linkedSource,
  onLinkedSourceChange,
  onTransition,
}: {
  action: ImprovementAction;
  busy: string | null;
  linkedSource: string;
  onLinkedSourceChange: (value: string) => void;
  onTransition: (actionId: string, payload: ImprovementActionTransitionPayload) => Promise<void>;
}) {
  if (action.status === "closed" || action.status === "wont_fix") return null;
  const controls: { status: ImprovementAction["status"]; label: string }[] = [];
  if (action.status === "open") controls.push({ status: "in_progress", label: "Start" }, { status: "actioned", label: "Actioned" });
  if (action.status === "in_progress") controls.push({ status: "actioned", label: "Actioned" });
  controls.push({ status: "wont_fix", label: "Won't fix" });
  return (
    <div className="improvement-card-actions">
      {controls.map((control) => (
        <button
          key={control.status}
          type="button"
          className="mini-button"
          disabled={busy === `${action.id}:${control.status}`}
          onClick={() => void onTransition(action.id, { status: control.status, note: `${statusLabel(control.status)} from Analytics.` })}
        >
          {busy === `${action.id}:${control.status}` ? "Saving..." : control.label}
        </button>
      ))}
      {action.status === "actioned" ? (
        <div className="improvement-close-row">
          <input
            value={linkedSource}
            onChange={(event) => onLinkedSourceChange(event.target.value)}
            placeholder="Linked source id"
          />
          <button
            type="button"
            className="primary-button"
            disabled={!linkedSource.trim() || busy === `${action.id}:closed`}
            onClick={() => void onTransition(action.id, {
              status: "closed",
              linked_source_id: linkedSource.trim(),
              note: "Closed with linked source evidence from Analytics.",
            })}
          >
            {busy === `${action.id}:closed` ? "Closing..." : "Close"}
          </button>
        </div>
      ) : null}
    </div>
  );
}

function statusLabel(status: ImprovementAction["status"]): string {
  if (status === "in_progress") return "In progress";
  if (status === "wont_fix") return "Won't fix";
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function answerPathLabel(path: string): string {
  if (path === "oag") return "OAG";
  if (path === "rag+ontology") return "RAG + ontology";
  if (path === "rag") return "RAG";
  return path || "unknown";
}

function hasImprovementAction(actions: ImprovementAction[], triggerType: ImprovementAction["trigger_type"], triggerRef: string): boolean {
  return actions.some((action) => (
    action.trigger_type === triggerType
    && action.trigger_ref === triggerRef
    && action.status !== "closed"
    && action.status !== "wont_fix"
  ));
}

function OntologyBreakdown({ title, rows, empty }: { title: string; rows: [string, number][]; empty: string }) {
  return (
    <div className="panel">
      <div className="panel-heading">
        <div>
          <h2 style={{ fontSize: 15 }}>{title}</h2>
          <p className="muted-text">{rows.reduce((total, [, value]) => total + value, 0)} visible in current graph snapshot.</p>
        </div>
      </div>
      {rows.length ? (
        <div className="ontology-breakdown-list">
          {rows.map(([name, value]) => (
            <div className="ontology-breakdown-row" key={name}>
              <span>{name.replace(/_/g, " ")}</span>
              <b>{value}</b>
            </div>
          ))}
        </div>
      ) : <p className="muted-text">{empty}</p>}
    </div>
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

function TraceDisclosure({ trace, compact = false }: { trace: AnalyticsComputationTrace; compact?: boolean }) {
  return (
    <details className={`analytics-trace${compact ? " analytics-trace--compact" : ""}`}>
      <summary>{compact ? "How calculated" : trace.label}</summary>
      <div className="analytics-trace-body">
        <p><b>Formula</b> <code>{trace.formula}</code></p>
        <p><b>With values</b> <code>{trace.substituted_formula}</code></p>
        <div className="analytics-trace-grid">
          <TraceList title="Steps" rows={trace.intermediate_steps} />
          <TraceKeyValues title="Output" values={trace.output} />
        </div>
        <p className="muted-text">{trace.boundary}</p>
      </div>
    </details>
  );
}

function TraceList({ title, rows }: { title: string; rows: string[] }) {
  return (
    <div>
      <b>{title}</b>
      <ul className="analytics-method-list">
        {rows.map((row) => <li key={row}>{row}</li>)}
      </ul>
    </div>
  );
}

function TraceKeyValues({ title, values }: { title: string; values: Record<string, unknown> }) {
  return (
    <div>
      <b>{title}</b>
      <dl className="analytics-key-values">
        {Object.entries(values).map(([key, value]) => (
          <div key={key}>
            <dt>{key.replace(/_/g, " ")}</dt>
            <dd>{formatTraceValue(value)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function formatTraceValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "n/a";
  if (Array.isArray(value) || typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function ForecastSection({
  forecast,
  forecastSeries,
  forecastError,
  onChangeSeries,
  onShowMethods,
}: {
  forecast: AnalyticsForecastReport | null;
  forecastSeries: string;
  forecastError: string | null;
  onChangeSeries: (series: string) => void;
  onShowMethods: () => void;
}) {
  const rows = forecast ? forecastChartRows(forecast) : [];
  return (
    <>
      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Forecast</h2>
            <p className="muted-text">Validated projections over platform telemetry series.</p>
          </div>
          <button type="button" className="text-button" onClick={onShowMethods}>How is this forecast made?</button>
        </div>
        <div className="analytics-export-controls">
          <label className="field-label analytics-export-dataset">
            Series
            <select value={forecastSeries} onChange={(event) => onChangeSeries(event.target.value)}>
              <option value="query_volume">Query demand</option>
              <option value="refusal_rate">Refusal rate</option>
              <option value="low_grounding_rate">Low-grounding rate</option>
              <option value="governance_issue_count">Governance issue count</option>
            </select>
          </label>
          {forecast ? (
            <MetricGrid
              items={[
                { label: "Selected model", value: forecast.chosen_model.replace(/_/g, " "), note: forecast.selection_reason },
                { label: "MAPE", value: formatPercent(forecast.validation.selected.mape), note: "Backtest validation error." },
                { label: "MAE", value: String(forecast.validation.selected.mae), note: `${forecast.validation.holdout_n} holdout periods.` },
              ]}
            />
          ) : null}
        </div>
        {forecastError ? <p className="muted-text" style={{ color: "var(--red)" }}>{forecastError}</p> : null}
      </div>

      {!forecast ? (
        <EmptyPanel>Loading forecast...</EmptyPanel>
      ) : (
        <div className="analytics-grid analytics-grid--two">
          <ChartCard title={`${forecast.label} forecast`} subtitle={`${forecast.bucket} · ${forecast.chosen_model.replace(/_/g, " ")}`}>
            <AreaChart data={rows}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e2e8f0)" />
              <XAxis dataKey="label" fontSize={10} />
              <YAxis fontSize={11} />
              <Tooltip />
              <Legend />
              <Area type="monotone" dataKey="upper" name="Upper band" stroke="none" fill="#fbcfe8" fillOpacity={0.35} />
              <Area type="monotone" dataKey="lower" name="Lower band" stroke="none" fill="#ffffff" fillOpacity={1} />
              <Line type="monotone" dataKey="actual" name="Actual" stroke="#2563eb" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="forecast" name="Forecast" stroke="#db2777" strokeWidth={2} dot />
            </AreaChart>
          </ChartCard>
          <div className="panel">
            <div className="panel-heading">
              <div>
                <h2 style={{ fontSize: 15 }}>Validation Scorecard</h2>
                <p className="muted-text">{forecast.validation.scorecard.length} candidate models tested.</p>
              </div>
              <span className="status-pill">{forecast.validation.holdout_n} holdout</span>
            </div>
            <div className="table-frame">
              <table className="data-table">
                <thead><tr><th>Model</th><th>MAE</th><th>MAPE</th><th>RMSE</th></tr></thead>
                <tbody>
                  {forecast.validation.scorecard.slice(0, 8).map((row) => (
                    <tr key={`${row.model}-${JSON.stringify(row.parameters)}`}>
                      <td>{row.model.replace(/_/g, " ")}</td>
                      <td>{row.mae}</td>
                      <td>{formatPercent(row.mape)}</td>
                      <td>{row.rmse}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="muted-text">{forecast.boundary}</p>
          </div>
        </div>
      )}
    </>
  );
}

function forecastChartRows(forecast: AnalyticsForecastReport) {
  return [
    ...forecast.actuals.map((point) => ({
      label: point.date,
      actual: point.value,
      forecast: null,
      lower: null,
      upper: null,
    })),
    ...forecast.forecast.map((point) => ({
      label: `+${point.step}`,
      actual: null,
      forecast: point.value,
      lower: point.lower,
      upper: point.upper,
    })),
  ];
}

function MethodsSection({
  methods,
  traces,
}: {
  methods: AnalyticsMethodsCatalogue | null;
  traces: Record<string, AnalyticsComputationTrace>;
}) {
  if (!methods) return <EmptyPanel>Loading methods and models catalogue...</EmptyPanel>;
  const implemented = methods.methods.filter((method) => method.status === "implemented").length;
  const planned = methods.methods.length - implemented;
  const traceRows = Object.values(traces);
  return (
    <>
      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Methods and Models</h2>
            <p className="muted-text">Transparent formulas, assumptions, boundaries and validation signals for each analytic.</p>
          </div>
          <span className="status-pill">{implemented} live · {planned} planned</span>
        </div>
        <MetricGrid
          items={[
            { label: "Catalogue entries", value: String(methods.summary.method_count), note: "Implemented and planned analytics." },
            { label: "Implemented", value: String(methods.summary.implemented_count), note: "Currently backing platform numbers." },
            { label: "Calculation traces", value: String(traceRows.length), note: "Current values with substituted formulas." },
          ]}
        />
      </div>

      <div className="analytics-method-grid">
        {methods.methods.map((method) => (
          <div className="analytics-method-card" key={method.id}>
            <div className="result-head">
              <b>{method.name}</b>
              <span className={`status-pill${method.status === "planned" ? " status-pill--warn" : " status-pill--good"}`}>
                {method.status}
              </span>
            </div>
            <p className="muted-text">{method.technique} · {method.model_family}</p>
            <p><code>{method.formula}</code></p>
            <div className="analytics-trace-grid">
              <TraceList title="Inputs" rows={method.inputs} />
              <TraceList title="Assumptions" rows={method.assumptions} />
            </div>
            <details className="analytics-method-details">
              <summary>Boundaries and validation</summary>
              <TraceList title="Boundaries" rows={method.boundaries} />
              <p><b>Validation</b> {method.validation_metric}</p>
              <TraceList title="References" rows={method.references.map((reference) => `${reference.label}: ${reference.path}`)} />
            </details>
          </div>
        ))}
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Current Calculation Traces</h2>
            <p className="muted-text">The same formulas with the current values substituted in.</p>
          </div>
          <span className="status-pill">{traceRows.length} traces</span>
        </div>
        <div className="analytics-trace-list">
          {traceRows.map((trace) => <TraceDisclosure key={trace.metric_id} trace={trace} />)}
        </div>
      </div>
    </>
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

      <MetricGrid
        items={[
          { label: "Observed real value", value: formatGbp(value.telemetry.observed_total_gbp), note: `${value.telemetry.event_count} operator events` },
          { label: "Synthetic pilot value", value: formatGbp(value.telemetry.synthetic_total_gbp), note: `${value.telemetry.synthetic_event_count} simulator events` },
          { label: "Synthetic projection", value: formatGbp(value.telemetry.projection.synthetic_ytd_projection_gbp), note: "Annualised from simulator months" },
          { label: "Combined projection", value: formatGbp(value.telemetry.projection.combined_ytd_projection_gbp), note: "For scenario testing only" },
        ]}
      />

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

        <ChartCard title="Monthly value trend" subtitle="Real observed value versus synthetic pilot replay">
          <BarChart data={value.telemetry.monthly_trend}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e2e8f0)" />
            <XAxis dataKey="month" fontSize={11} />
            <YAxis fontSize={11} tickFormatter={(amount) => `${Math.round(Number(amount) / 1000)}k`} />
            <Tooltip formatter={(amount) => formatGbp(Number(amount))} />
            <Legend />
            <Bar dataKey="observed_gbp" name="Observed" fill="#2563eb" radius={[3, 3, 0, 0]} />
            <Bar dataKey="synthetic_gbp" name="Synthetic pilot" fill="#d97706" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ChartCard>

        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2 style={{ fontSize: 15 }}>Value telemetry</h2>
              <p className="muted-text">
                {value.telemetry.event_count} observed · {value.telemetry.synthetic_event_count} synthetic · {formatGbp(value.telemetry.combined_total_gbp)}
              </p>
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

        <InsightPanel title="Projection boundary" tone="warn">
          <p>{value.telemetry.projection.basis} Keep synthetic pilot replay separate from audited savings and live operator evidence.</p>
        </InsightPanel>
      </div>

      <ValueAssumptionsMatrix value={value} />

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

function ValueAssumptionsMatrix({ value }: { value: ValueAnalytics }) {
  if (!value.assumption_matrix.length) {
    return <EmptyPanel>No value assumptions are available for scenario comparison.</EmptyPanel>;
  }

  return (
    <div className="panel">
      <div className="panel-heading">
        <div>
          <h2>Value assumptions matrix</h2>
          <p className="muted-text">
            {value.assumption_matrix.length} drivers compared across {value.scenarios.length} scenarios · schema {value.schema_version}
          </p>
        </div>
        <span className="status-pill">generated view</span>
      </div>
      <div className="table-frame value-matrix-frame">
        <table className="data-table value-matrix-table">
          <thead>
            <tr>
              <th className="value-matrix-driver">Driver</th>
              {value.scenarios.map((scenario) => (
                <th key={scenario.scenario_id}>
                  <span>{scenario.label}</span>
                  <small>{scenario.confidence} confidence</small>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {value.assumption_matrix.map((row) => (
              <tr key={row.metric}>
                <td className="value-matrix-driver">
                  <b>{row.label}</b>
                  <span>{driverLabel(row.driver)}</span>
                  <small>{row.metric}</small>
                </td>
                {value.scenarios.map((scenario) => {
                  const cell = row.scenario_values[scenario.scenario_id];
                  return (
                    <td key={scenario.scenario_id}>
                      {cell ? (
                        <div className="value-matrix-cell">
                          <b>{formatAssumption(cell.value, cell.unit)}</b>
                          <span className="status-pill">{cell.confidence}</span>
                          <p>{cell.rationale}</p>
                          <small>{cell.source}</small>
                        </div>
                      ) : (
                        <span className="muted-text">Not set</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
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
          <thead><tr><th>Event</th><th>Source</th><th>Driver</th><th>Process</th><th>Scenario</th><th>Value</th></tr></thead>
          <tbody>
            {value.telemetry.recent_events.slice(0, 8).map((event) => (
              <tr key={event.event_id}>
                <td>{event.label}</td>
                <td>{event.synthetic_historical ? "Synthetic pilot" : "Observed"}</td>
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
          { label: "Official refs", value: String(validation.summary.official_reference_count) },
          { label: "History events", value: String(validation.summary.evidence_history_event_count) },
          { label: "Evidence refs", value: String(validation.summary.evidence_reference_count) },
          { label: "Implemented KSB", value: String(validation.summary.ksb_by_status.implemented ?? 0) },
        ]}
      />

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Ethics and Professional Boundaries</h2>
            <p className="muted-text">Data protection, analytical limitation and compute-footprint controls surfaced with the live evidence report.</p>
          </div>
          <span className="status-pill">{validation.ethics_notes.length} notes</span>
        </div>
        <div className="analytics-method-grid">
          {validation.ethics_notes.map((note) => (
            <div className="analytics-method-card" key={note.note_id}>
              <div className="result-head">
                <b>{note.title}</b>
                <span className="status-pill">{note.category}</span>
              </div>
              <p className="result-cite">{note.surface}</p>
              <p className="result-text">{note.statement}</p>
              <p className="muted-text">{note.mitigation}</p>
              <TraceKeyValues title="Current signal" values={note.current_signal} />
              <p className="result-cite">{note.evidence_refs.map((ref) => `${ref.label} (${ref.kind})`).join("; ")}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="analytics-grid analytics-grid--two">
        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Official reference mapping</h2>
              <p className="muted-text">Provisional slots for the final assessor-supplied KSB reference IDs.</p>
            </div>
            <span className="status-pill">{validation.summary.official_references_by_status.mapped_provisional ?? 0} provisional</span>
          </div>
          <div className="result-list" style={{ gap: 10 }}>
            {validation.ksb_rows.map((row) => (
              <div className="result-card" key={`${row.ksb_id}-official`}>
                <div className="result-head">
                  <b>{row.ksb_id}</b>
                  <span className="status-pill">{row.category}</span>
                </div>
                {row.official_references.map((ref) => (
                  <div key={ref.reference_id} className="ksb-reference-block">
                    <p className="result-cite">{ref.reference_id} · {ref.mapping_status.replace(/_/g, " ")}</p>
                    <p className="result-text">{ref.framework_area}</p>
                    <p className="result-cite">{ref.rationale}</p>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Evidence history</h2>
              <p className="muted-text">Dated events explaining how each evidence claim matured.</p>
            </div>
          </div>
          <div className="result-list" style={{ gap: 10 }}>
            {validation.ksb_rows.flatMap((row) => row.evidence_history.map((event) => ({ row, event }))).slice(0, 10).map(({ row, event }) => (
              <div className="result-card" key={`${row.ksb_id}-${event.event_date}-${event.event_type}`}>
                <div className="result-head">
                  <b>{row.ksb_id}</b>
                  <span className="status-pill">{event.event_type.replace(/_/g, " ")}</span>
                </div>
                <p className="result-cite">{event.event_date}</p>
                <p className="result-text">{event.summary}</p>
                <p className="result-cite">{event.evidence_refs.map((ref) => `${ref.label} (${ref.kind})`).join("; ")}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

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
                {Object.keys(protocol.current_metrics).length ? <TraceKeyValues title="Current metrics" values={protocol.current_metrics} /> : null}
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
