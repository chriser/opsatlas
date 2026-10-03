// Analytics: the scorecard, charts, gaps, forecasts, exports and improvement actions.
// One module of the control panel's API client; pages import it through ./index.ts, as "./api".

import { authHeaders, guard } from "./http";

export interface Scorecard {
  total_queries: number;
  answered: number;
  refused: number;
  guardrail_blocks: number;
  answer_rate: number;
  refusal_rate: number;
  grounded_rate: number;
  avg_citations: number;
  knowledge_gaps?: string[];
  by_topic: Record<string, number>;
  by_answer_path: Record<string, number>;
  // Written answers and Tibi's turns, each counted once (REF S20).
  by_channel?: Record<string, { queries: number; answered: number; refused: number; answer_rate: number; refusal_rate: number }>;
}

export type AnalyticsExportFormat = "csv" | "json";

export interface AnalyticsExportDatasetSummary {
  dataset: string;
  label: string;
  description: string;
  row_count: number;
  last_updated: string | null;
  formats: AnalyticsExportFormat[];
}

export interface AnalyticsExportIndex {
  datasets: AnalyticsExportDatasetSummary[];
  dataset_count: number;
  ethics_boundary: string;
}

export interface AnalyticsMethodReference {
  label: string;
  path: string;
  kind: string;
}

export interface AnalyticsMethod {
  id: string;
  name: string;
  status: string;
  technique: string;
  model_family: string;
  formula: string;
  parameters: Record<string, string>;
  inputs: string[];
  assumptions: string[];
  boundaries: string[];
  validation_metric: string;
  references: AnalyticsMethodReference[];
}

export interface AnalyticsMethodsCatalogue {
  generated_at: string;
  methods: AnalyticsMethod[];
  summary: {
    method_count: number;
    implemented_count: number;
    planned_count: number;
  };
}

export interface AnalyticsComputationTrace {
  metric_id: string;
  label: string;
  method_id: string;
  formula: string;
  substituted_formula: string;
  inputs: Record<string, unknown>;
  intermediate_steps: string[];
  output: Record<string, unknown>;
  boundary: string;
}

export interface AnalyticsComputationTraceReport {
  trace_count: number;
  traces: AnalyticsComputationTrace[];
}

export interface AnalyticsForecastPoint {
  step: number;
  value: number;
  lower: number;
  upper: number;
}

export interface AnalyticsSeriesPoint {
  date: string;
  value: number;
}

export interface AnalyticsForecastReport {
  series_id: string;
  label: string;
  bucket: string;
  actuals: AnalyticsSeriesPoint[];
  statistics: Record<string, unknown>;
  chosen_model: string;
  selection_reason: string;
  parameters: Record<string, unknown>;
  forecast: AnalyticsForecastPoint[];
  validation: {
    holdout_n: number;
    actual: number[];
    scorecard: { model: string; parameters: Record<string, unknown>; mae: number; mape: number; rmse: number }[];
    selected: { mae: number; mape: number; rmse: number; residual_std: number };
  };
  method_id: string;
  boundary: string;
}

export interface OagBenchmarkMetric {
  total?: number;
  passed?: number;
  accuracy?: number;
  path_accuracy?: number;
  stable_count?: number;
  question_count?: number;
  mean_latency_seconds?: number;
  p95_latency_seconds?: number;
}

export interface OagBenchmarkLiftRow {
  category?: string;
  split?: string;
  rag_only_accuracy: number;
  oag_first_accuracy: number;
  lift: number;
  rag_only_total: number;
  oag_first_total: number;
}

export interface OagBenchmarkMatrixRow {
  counts: Record<string, number>;
  total: number;
}

export interface OagBenchmarkDetailRow {
  run: number;
  config: string;
  id: string;
  split: string;
  category: string;
  question: string;
  expected_path: string;
  answer_path: string;
  mode: string;
  refused: boolean;
  confidence: string;
  grounding: string;
  facts_hit: string[];
  facts_missed: string[];
  passed: boolean;
  expected_path_hit: boolean;
  citation_types: string[];
  citation_count: number;
  latency_seconds: number;
}

export interface OagBenchmarkScorecard {
  path: string;
  markdown_path: string;
  generated_at: string;
  dataset_version: string;
  source_corpus: string;
  question_count: number;
  evaluated_question_count: number;
  split_filter: string;
  category_filter: string[];
  id_filter: string[];
  split_counts: Record<string, number>;
  runs: number;
  configs: string[];
  model_info: Record<string, string | number | boolean | null>;
  best_config: string;
  winner_config: string;
  diagnostic_run: boolean;
  diagnostic_reasons: string[];
  evidence_grade: "decision_grade" | "holdout_decision" | "diagnostic" | string;
  decision_grade: boolean;
  code_state: Record<string, unknown>;
  latency: Record<string, number>;
  by_config: Record<string, OagBenchmarkMetric>;
  by_split: Record<string, Record<string, OagBenchmarkMetric>>;
  by_split_category: Record<string, Record<string, Record<string, OagBenchmarkMetric>>>;
  by_category: Record<string, Record<string, OagBenchmarkMetric>>;
  category_lift: OagBenchmarkLiftRow[];
  split_lift: OagBenchmarkLiftRow[];
  path_usage: Record<string, OagBenchmarkMatrixRow>;
  citation_type_usage: Record<string, OagBenchmarkMatrixRow>;
  stability: Record<string, Record<string, unknown>>;
  interpretation_targets: Record<string, number>;
  verdict: {
    headline: string;
    rag_only_accuracy: number;
    oag_first_accuracy: number;
    overall_lift: number;
    positive_categories: string[];
    weaker_categories: string[];
    split_lift: OagBenchmarkLiftRow[];
  };
  rows: OagBenchmarkDetailRow[];
}

export interface OagBenchmarkReport {
  scorecard_count: number;
  latest: OagBenchmarkScorecard | null;
  history: Array<{
    path: string;
    generated_at: string;
    dataset_version: string;
    runs: number;
    configs: string[];
    split_filter: string;
    evaluated_question_count: number;
    evidence_grade: string;
    decision_grade: boolean;
    rag_only_accuracy: number;
    oag_first_accuracy: number;
    overall_lift: number;
  }>;
  boundary: string;
}

export interface OagOperationsReport {
  summary: {
    total_queries: number;
    answered_queries: number;
    path_counts: Record<string, number>;
    oag_assisted_count: number;
    rag_fallback_count: number;
    deterministic_evidence_ratio: number;
    generative_evidence_ratio: number;
    ontology_object_citation_rate: number;
  };
  daily_path_split: Array<{
    date: string;
    oag: number;
    rag: number;
    rag_ontology: number;
    other: number;
    total: number;
  }>;
  oag_adoption_forecast: AnalyticsForecastReport;
  path_grounding_matrix: Array<{
    answer_path: string;
    grounded: number;
    unverified: number;
    refused: number;
    none: number;
    total: number;
  }>;
  latency_by_path: Array<{
    answer_path: string;
    count: number;
    mean_ms: number;
    p95_ms: number;
  }>;
  coverage_gaps: Array<{
    gap_id: string;
    question: string;
    timestamp: string;
    topic: string;
    reason: string;
    trigger_ref: string;
    suggested_owner_role: string;
    eam_gap_ref: string;
  }>;
  boundary: string;
}

export interface OntologyStats {
  total_objects: number;
  total_links: number;
  by_object_type: Record<string, number>;
  by_link_type: Record<string, number>;
}

export async function getScorecard(): Promise<Scorecard> {
  const res = await guard(await fetch("/api/analytics/scorecard", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load scorecard");
  return res.json();
}

export interface ChartData {
  volume_over_time: { date: string; queries: number; real_queries?: number; synthetic_queries?: number }[];
  by_topic: { topic: string; count: number }[];
  outcomes: { name: string; value: number }[];
  confidence: { name: string; value: number }[];
  latency: { bucket: string; count: number }[];
  top_sources: { source: string; citations: number }[];
}

export interface GovernanceHistory {
  issue_events_over_time: { date: string; detected: number; accepted: number; resolved: number; open: number }[];
  issue_state_mix: { state: string; count: number }[];
  issue_type_mix: { issue_type: string; count: number }[];
  source_issue_counts: { source: string; count: number }[];
  mean_time_to_resolve_hours: number;
  resolved_count: number;
  open_count: number;
  recurring_issues: {
    issue_id: string;
    issue_type: string;
    source: string;
    detections: number;
    first_seen: string;
    last_seen: string;
    state: string;
  }[];
}

export interface KnowledgeGapCluster {
  id: string;
  label: string;
  topic: string;
  process_area: string;
  source_gap: string;
  question_count: number;
  representative_questions: string[];
  terms: string[];
  friction_score: number;
  confidence: string;
}

export interface KnowledgeGapAnalytics {
  total_candidates: number;
  cluster_count: number;
  silhouette_score: number;
  clusters: KnowledgeGapCluster[];
  rubric: Record<string, string>;
}

export interface RecurringQuestionGroup {
  id: string;
  representative_question: string;
  demand_frequency: number;
  first_seen: string;
  last_seen: string;
  trend: string;
  topic: string;
  terms: string[];
  refusal_count: number;
  low_grounding_count: number;
  answer_paths: Record<string, number>;
  questions: string[];
}

export interface RecurringQuestionAnalytics {
  group_count: number;
  total_recurring_questions: number;
  min_count: number;
  similarity_threshold: number;
  groups: RecurringQuestionGroup[];
  rubric: Record<string, string>;
}

export interface RetrievalHealthPattern {
  id: string;
  representative_question: string;
  demand_frequency: number;
  trend: string;
  topic: string;
  first_seen: string;
  last_seen: string;
  failure_reasons: Record<string, number>;
  recommended_action: string;
}

export interface RetrievalHealthAnalytics {
  total_queries: number;
  rates: {
    refusal_rate: number;
    no_citation_rate: number;
    low_grounding_rate: number;
    answered_ungrounded_rate: number;
  };
  counts: Record<string, number>;
  by_topic: {
    topic: string;
    total_queries: number;
    refusal_rate: number;
    no_citation_rate: number;
    low_grounding_rate: number;
    failure_count: number;
  }[];
  trend: {
    date: string;
    queries: number;
    refusal_rate: number;
    no_citation_rate: number;
    low_grounding_rate: number;
    failure_count: number;
  }[];
  top_failing_patterns: RetrievalHealthPattern[];
  rubric: Record<string, string>;
}

export type ImprovementTriggerType =
  "knowledge_gap" | "failed_retrieval" | "recurring_question" | "oag_coverage_gap" | "answer_feedback";
export type ImprovementStatus = "open" | "in_progress" | "actioned" | "closed" | "wont_fix";
export type ImprovementReviewCadence = "weekly" | "monthly" | "ad_hoc";

export interface ImprovementNote {
  timestamp: string;
  note: string;
}

export interface ImprovementAction {
  id: string;
  trigger_type: ImprovementTriggerType;
  trigger_ref: string;
  recommended_action: string;
  owner_role: string;
  review_cadence: ImprovementReviewCadence;
  status: ImprovementStatus;
  linked_source_id: string;
  created_at: string;
  updated_at: string;
  closed_at: string;
  notes: ImprovementNote[];
}

export interface ImprovementActionCreatePayload {
  trigger_type: ImprovementTriggerType;
  trigger_ref: string;
  recommended_action: string;
  owner_role?: string;
  review_cadence?: ImprovementReviewCadence;
  note?: string;
}

export interface ImprovementActionTransitionPayload {
  status: ImprovementStatus;
  linked_source_id?: string;
  note?: string;
}

export interface ImprovementActionList {
  action_count: number;
  actions: ImprovementAction[];
}

export interface ImprovementLoopMetrics {
  action_count: number;
  status_counts: Record<ImprovementStatus, number>;
  trigger_counts: Partial<Record<ImprovementTriggerType, number>>;
  cadence_counts: Partial<Record<ImprovementReviewCadence, number>>;
  owner_workload: { owner_role: string; open_actions: number }[];
  rates: {
    actioned_rate: number;
    closure_rate: number;
    wont_fix_rate: number;
    repeat_trigger_rate: number;
  };
  age: {
    average_open_age_days: number;
    oldest_open_age_days: number;
    mean_time_to_close_days: number;
  };
  review_due_count: number;
  review_due: {
    id: string;
    trigger_type: ImprovementTriggerType;
    trigger_ref: string;
    owner_role: string;
    status: ImprovementStatus;
    review_cadence: ImprovementReviewCadence;
    updated_at: string;
    days_since_update: number;
    days_overdue: number;
    recommended_action: string;
  }[];
  rubric: Record<string, string>;
}

export interface ProcessComplexityRow {
  id: string;
  name: string;
  source_title: string;
  domain: string;
  process: string;
  complexity_score: number;
  complexity_band: "low" | "medium" | "high";
  key_person_risk_score: number;
  key_person_risk_band: "low" | "medium" | "high";
  dominant_role: string;
  signals: Record<string, number>;
  indicators: string[];
  explanation: string;
}

export interface ProcessComplexityAnalytics {
  process_count: number;
  average_complexity: number;
  high_risk_count: number;
  rubric: Record<string, string>;
  processes: ProcessComplexityRow[];
}

export interface EvidenceReference {
  label: string;
  path: string;
  kind: string;
}

export interface OfficialKsbReference {
  reference_id: string;
  category: string;
  framework_area: string;
  mapping_status: string;
  rationale: string;
}

export interface EvidenceHistoryEntry {
  event_date: string;
  event_type: string;
  summary: string;
  evidence_refs: EvidenceReference[];
}

export interface KsbTraceabilityRow {
  ksb_id: string;
  category: string;
  capability: string;
  evidence_claim: string;
  delivered_features: string[];
  evidence_refs: EvidenceReference[];
  official_references: OfficialKsbReference[];
  evidence_history: EvidenceHistoryEntry[];
  validation_status: string;
  next_evidence: string;
}

export interface ValidationProtocolRow {
  protocol_id: string;
  component: string;
  validation_method: string;
  metric: string;
  acceptance_rule: string;
  current_evidence: EvidenceReference[];
  current_metrics: Record<string, string | number | boolean | null>;
  status: string;
  cadence: string;
  boundary: string;
}

export interface EthicsNote {
  note_id: string;
  category: string;
  title: string;
  surface: string;
  statement: string;
  mitigation: string;
  evidence_refs: EvidenceReference[];
  current_signal: Record<string, string | number | boolean | null>;
}

export interface ValidationEvidenceReport {
  generated_at: string;
  ksb_rows: KsbTraceabilityRow[];
  validation_protocols: ValidationProtocolRow[];
  ethics_notes: EthicsNote[];
  summary: {
    ksb_count: number;
    validation_protocol_count: number;
    ksb_by_status: Record<string, number>;
    protocols_by_status: Record<string, number>;
    official_reference_count: number;
    official_references_by_status: Record<string, number>;
    evidence_history_event_count: number;
    evidence_reference_count: number;
  };
  caveats: string[];
}

export async function getAnalyticsCharts(): Promise<ChartData> {
  const res = await guard(await fetch("/api/analytics/charts", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load analytics charts");
  return res.json();
}

export async function getGovernanceHistory(): Promise<GovernanceHistory> {
  const res = await guard(await fetch("/api/analytics/governance-history", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load governance history");
  return res.json();
}

export async function captureGovernanceSnapshot(): Promise<GovernanceHistory> {
  const res = await guard(
    await fetch("/api/analytics/governance-history/snapshot", { method: "POST", headers: authHeaders() }),
  );
  if (!res.ok) throw new Error("could not capture governance snapshot");
  return res.json();
}

export async function getKnowledgeGaps(): Promise<KnowledgeGapAnalytics> {
  const res = await guard(await fetch("/api/analytics/knowledge-gaps", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load knowledge gaps");
  return res.json();
}

export async function getRecurringQuestions(): Promise<RecurringQuestionAnalytics> {
  const res = await guard(await fetch("/api/analytics/recurring-questions", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load recurring questions");
  return res.json();
}

export async function getRetrievalHealth(): Promise<RetrievalHealthAnalytics> {
  const res = await guard(await fetch("/api/analytics/retrieval-health", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load retrieval health");
  return res.json();
}

export async function getImprovementActions(): Promise<ImprovementActionList> {
  const res = await guard(await fetch("/api/analytics/improvements", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load improvement actions");
  return res.json();
}

export async function getImprovementMetrics(): Promise<ImprovementLoopMetrics> {
  const res = await guard(await fetch("/api/analytics/improvements/metrics", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load improvement metrics");
  return res.json();
}

export async function createImprovementAction(payload: ImprovementActionCreatePayload): Promise<{ action: ImprovementAction }> {
  const res = await guard(
    await fetch("/api/analytics/improvements", {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
  if (!res.ok) throw new Error("could not create improvement action");
  return res.json();
}

export async function transitionImprovementAction(
  actionId: string,
  payload: ImprovementActionTransitionPayload,
): Promise<{ action: ImprovementAction }> {
  const res = await guard(
    await fetch(`/api/analytics/improvements/${encodeURIComponent(actionId)}/transition`, {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
  if (!res.ok) throw new Error("could not transition improvement action");
  return res.json();
}

export async function getProcessComplexity(): Promise<ProcessComplexityAnalytics> {
  const res = await guard(await fetch("/api/analytics/process-complexity", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load process complexity");
  return res.json();
}

export async function getOntologyStats(): Promise<OntologyStats> {
  const res = await guard(await fetch("/api/analytics/ontology-stats", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load ontology stats");
  return res.json();
}

export async function getValidationEvidence(): Promise<ValidationEvidenceReport> {
  const res = await guard(await fetch("/api/analytics/validation-evidence", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load validation evidence");
  return res.json();
}

export async function getAnalyticsExportIndex(): Promise<AnalyticsExportIndex> {
  const res = await guard(await fetch("/api/analytics/export", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load analytics export index");
  return res.json();
}

export async function getAnalyticsMethods(): Promise<AnalyticsMethodsCatalogue> {
  const res = await guard(await fetch("/api/analytics/methods", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load analytics methods catalogue");
  return res.json();
}

export async function getAnalyticsComputationTraces(): Promise<AnalyticsComputationTraceReport> {
  const res = await guard(await fetch("/api/analytics/explain", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load analytics computation traces");
  return res.json();
}

export async function getAnalyticsForecast(seriesId: string, horizon = 7): Promise<AnalyticsForecastReport> {
  const res = await guard(
    await fetch(`/api/analytics/forecast/${encodeURIComponent(seriesId)}?horizon=${horizon}`, { headers: authHeaders() }),
  );
  if (!res.ok) throw new Error("could not load analytics forecast");
  return res.json();
}

export async function getOagBenchmark(): Promise<OagBenchmarkReport> {
  const res = await guard(await fetch("/api/analytics/oag-benchmark", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load OAG benchmark analytics");
  return res.json();
}

export async function getOagOperations(): Promise<OagOperationsReport> {
  const res = await guard(await fetch("/api/analytics/oag-operations", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load OAG operations analytics");
  return res.json();
}

export async function getAnalyticsExportDataset(dataset: string, format: AnalyticsExportFormat): Promise<Blob> {
  const res = await guard(
    await fetch(`/api/analytics/export/${encodeURIComponent(dataset)}?format=${format}`, { headers: authHeaders() }),
  );
  if (!res.ok) throw new Error("could not export analytics dataset");
  return res.blob();
}

export async function getAnalyticsDictionaryMarkdown(): Promise<string> {
  const res = await guard(await fetch("/api/analytics/export/dictionary?format=md", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not export analytics data dictionary");
  return res.text();
}

export async function getAnalyticsReproducibilityPack(): Promise<Blob> {
  const res = await guard(await fetch("/api/analytics/export/reproducibility-pack", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not export analytics reproducibility pack");
  return res.blob();
}

export async function getAnalyticsReportMarkdown(): Promise<string> {
  const res = await guard(await fetch("/api/analytics/report.md", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not export analytics report");
  return res.text();
}

export async function getAnalyticsReportPdf(): Promise<Blob> {
  const res = await guard(await fetch("/api/analytics/report.pdf", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not export analytics PDF report");
  return res.blob();
}
