// Control-panel API client. All calls go through the Vite dev proxy (/api -> backend).

const TOKEN_KEY = "kp_token";
let token: string | null = localStorage.getItem(TOKEN_KEY);

function setToken(value: string | null) {
  token = value;
  if (value) localStorage.setItem(TOKEN_KEY, value);
  else localStorage.removeItem(TOKEN_KEY);
}

function authHeaders(): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function isAuthenticated(): boolean {
  return Boolean(token);
}

export class AuthError extends Error {}

async function guard(res: Response): Promise<Response> {
  if (res.status === 401) {
    setToken(null);
    throw new AuthError("Your session has expired. Please sign in again.");
  }
  return res;
}

export async function login(password: string): Promise<void> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!res.ok) {
    throw new Error(res.status === 401 ? "Incorrect operator password." : "Login failed.");
  }
  setToken((await res.json()).token);
}

export async function logout(): Promise<void> {
  try {
    await fetch("/api/auth/logout", { method: "POST", headers: authHeaders() });
  } finally {
    setToken(null);
  }
}

export interface SourceRecord {
  id: string;
  filename: string;
  title: string;
  source_type: string;
  sensitivity: string;
  version: number;
  processing_state: string;
  approval_status: string;
  section_count: number;
  size_bytes: number;
  content_sha256: string;
  created_at: string;
}

export interface PublicContentSource {
  id: string;
  provider: string;
  url: string;
  title: string;
  public_body: string;
  topics: string[];
  licence: string;
  update_cadence: string;
  created_at: string;
  updated_at: string;
  snapshot_count: number;
  latest_snapshot_id: string;
  latest_snapshot_date: string;
  latest_update_date: string;
  last_error: string;
}

export interface PublicContentSnapshot {
  id: string;
  source_id: string;
  provider: string;
  version: number;
  url: string;
  title: string;
  public_body: string;
  content_id: string;
  document_type: string;
  locale: string;
  update_date: string;
  retrieved_at: string;
  snapshot_date: string;
  content_sha256: string;
  text?: string;
  metadata: Record<string, string>;
}

export interface RegulatoryCandidate {
  id: string;
  theme: string;
  label: string;
  source_id: string;
  source_title: string;
  confidence: "low" | "medium" | "high";
  score: number;
  reason: string;
  matched_terms: string[];
  passages: {
    source_id: string;
    source_title: string;
    heading: string;
    ordinal: number;
    excerpt: string;
    matched_terms: string[];
  }[];
  external_matches: {
    title: string;
    url: string;
    version: number;
    update_date: string;
    matched_terms: string[];
  }[];
  review_status: "unreviewed" | "relevant" | "irrelevant" | "needs_research";
  review_note: string;
  reviewed_at: string;
}

export interface RegulatoryCandidateReport {
  candidate_count: number;
  review_counts: Record<string, number>;
  taxonomy: { id: string; label: string; terms: string[] }[];
  candidates: RegulatoryCandidate[];
}

export interface HealthResponse {
  status: string;
  service: string;
  sources: number;
  models?: Record<string, string>;
}

export interface AuditRecord {
  timestamp: string;
  question: string;
  mode: string;
  outcome?: "answered" | "refused" | "blocked" | "declined" | string;
  refused: boolean;
  category: string | null;
  confidence: string;
  grounding: string;
  grounding_score: number;
  faithfulness: string;
  latency_ms: number;
  evidence: { source_title: string; heading: string; ordinal: number }[];
}

export async function getTraces(limit = 50): Promise<AuditRecord[]> {
  const res = await guard(await fetch(`/api/observability/traces?limit=${limit}`, { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load traces");
  return res.json();
}

export interface SearchResult {
  source_id: string;
  source_title: string;
  heading: string;
  ordinal: number;
  text: string;
  score: number;
}

export interface SearchResponse {
  mode: string;
  results: SearchResult[];
}

export async function searchKnowledge(q: string, topK = 5): Promise<SearchResponse> {
  const res = await guard(
    await fetch("/api/query", {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ q, top_k: topK }),
    }),
  );
  if (!res.ok) throw new Error("search failed");
  return res.json();
}

export interface Citation {
  source_id: string;
  source_title: string;
  heading: string;
  ordinal: number;
}

export interface AnswerResponse {
  answer: string;
  citations: Citation[];
  mode: string;
  refused: boolean;
  confidence: string;
  grounding: string;
  grounding_score: number;
  faithfulness: string;
}

export async function askQuestion(q: string): Promise<AnswerResponse> {
  const res = await guard(
    await fetch("/api/ask", {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ q }),
    }),
  );
  if (!res.ok) throw new Error("ask failed");
  return res.json();
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch("/api/health");
  if (!res.ok) throw new Error("health check failed");
  return res.json();
}

export async function listSources(): Promise<SourceRecord[]> {
  const res = await guard(await fetch("/api/sources", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load sources");
  return res.json();
}

export async function listExternalSources(): Promise<PublicContentSource[]> {
  const res = await guard(await fetch("/api/external-sources", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load external sources");
  return res.json();
}

export async function listExternalSnapshots(): Promise<PublicContentSnapshot[]> {
  const res = await guard(await fetch("/api/external-sources/snapshots", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load external snapshots");
  return res.json();
}

export async function snapshotGovUkSource(url: string, topics: string[] = []): Promise<{ source: PublicContentSource; snapshot: PublicContentSnapshot }> {
  const res = await guard(
    await fetch("/api/external-sources/govuk/snapshot", {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ url, topics }),
    }),
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "GOV.UK snapshot failed");
  }
  return res.json();
}

export async function getRegulatoryCandidates(): Promise<RegulatoryCandidateReport> {
  const res = await guard(await fetch("/api/regulatory/candidates", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load regulatory candidates");
  return res.json();
}

export async function reviewRegulatoryCandidate(id: string, status: "relevant" | "irrelevant" | "needs_research", note = ""): Promise<void> {
  const res = await guard(
    await fetch(`/api/regulatory/candidates/${id}/review`, {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ status, note }),
    }),
  );
  if (!res.ok) throw new Error("could not save regulatory review");
}

export async function uploadSource(file: File, title?: string): Promise<SourceRecord> {
  const form = new FormData();
  form.append("file", file);
  if (title) form.append("title", title);
  const res = await guard(
    await fetch("/api/sources/upload", { method: "POST", headers: authHeaders(), body: form }),
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "upload failed");
  }
  return res.json();
}

export async function deleteSource(id: string): Promise<void> {
  const res = await guard(
    await fetch(`/api/sources/${id}`, { method: "DELETE", headers: authHeaders() }),
  );
  if (!res.ok) throw new Error("delete failed");
}

export interface IntelligenceIssue {
  check: string;
  severity: "high" | "medium" | "low";
  score: number;
  source_id: string;
  source_title: string;
  detail: string;
  source_b_id?: string;
  source_b_title?: string;
}

export interface DocumentPayload {
  id: string;
  title: string;
  text: string;
}

export async function getDocument(id: string): Promise<DocumentPayload> {
  const res = await guard(await fetch(`/api/governance/sources/${id}/document`, { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load document");
  return res.json();
}

export interface RemediationSuggestion {
  shared_lines: number;
  keep_id: string;
  keep_title: string;
  trim_id: string;
  trim_title: string;
  reason: string;
  trim_suggested_text: string;
}

export async function acceptIssue(sourceId: string, check: string, detail: string): Promise<void> {
  const res = await guard(
    await fetch("/api/governance/issues/accept", {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ source_id: sourceId, check, detail }),
    }),
  );
  if (!res.ok) throw new Error("could not accept issue");
}

export async function getRemediation(aId: string, bId: string): Promise<RemediationSuggestion> {
  const res = await guard(await fetch(`/api/governance/remediation/${aId}/${bId}`, { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load suggestion");
  return res.json();
}

export async function saveDocument(id: string, text: string): Promise<void> {
  const res = await guard(
    await fetch(`/api/governance/sources/${id}/document`, {
      method: "PUT",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    }),
  );
  if (!res.ok) throw new Error("could not save document");
}

export interface IntelligenceReport {
  total_issues: number;
  health: "green" | "amber" | "red";
  categories: Record<string, number>;
  descriptions: Record<string, string>;
  source_summary: Record<string, { active: number; structural: number; accepted?: number }>;
  issues: Record<string, IntelligenceIssue[]>;
}

export interface Scorecard {
  total_queries: number;
  answered: number;
  refused: number;
  guardrail_blocks: number;
  answer_rate: number;
  refusal_rate: number;
  grounded_rate: number;
  avg_citations: number;
  knowledge_gaps: string[];
  by_topic: Record<string, number>;
}

export interface ProcessRule {
  record_id: string;
  topic: string;
  role: string;
  rule: string;
  confidence: string;
}

export interface ProcessRecord {
  id: string;
  source_id: string;
  source_title: string;
  name: string;
  domain: string;
  process: string;
  capabilities: string[];
  roles: string[];
  systems: string[];
  controls: string[];
  dependencies: string[];
  business_rules: string[];
  rules: ProcessRule[];
}

export async function getProcessRegistry(): Promise<ProcessRecord[]> {
  const res = await guard(await fetch("/api/process/registry", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load process registry");
  return res.json();
}

export async function getScorecard(): Promise<Scorecard> {
  const res = await guard(await fetch("/api/analytics/scorecard", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load scorecard");
  return res.json();
}

export interface ChartData {
  volume_over_time: { date: string; queries: number }[];
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

export interface SimulatorPersona {
  persona_id: string;
  persona_type: string;
  display_name: string;
  context: string;
  primary_needs: string[];
  constraints: string[];
  default_value_driver: string;
}

export interface SimulatorQuestion {
  question_id: string;
  text: string;
  expected_behavior: "answer" | "decline" | "refuse" | "guardrail";
  expected_signal: string;
}

export interface SimulatorScenario {
  scenario_id: string;
  persona_id: string;
  journey: string;
  intent: string;
  process_area: string;
  value_driver: string;
  difficulty: "basic" | "intermediate" | "advanced";
  expected_outcome: string;
  expected_evidence: string[];
  success_criteria: string[];
  questions: SimulatorQuestion[];
}

export interface SimulatorCatalogue {
  schema_version: string;
  created_for: string;
  purpose: string;
  safety: Record<string, string | boolean>;
  personas: SimulatorPersona[];
  scenarios: SimulatorScenario[];
}

export interface SimulationRunConfig {
  scenario_ids?: string[];
  persona_ids?: string[];
  seed?: number;
  max_questions?: number;
  top_k?: number;
}

export interface SimulationQuestionResult {
  scenario_id: string;
  question_id: string;
  persona_id: string;
  process_area: string;
  value_driver: string;
  difficulty: string;
  question: string;
  expected_behavior: string;
  expected_signal: string;
  observed_behavior: string;
  matched_expectation: boolean;
  refused: boolean;
  mode: string;
  confidence: string;
  grounding: string;
  grounding_score: number;
  faithfulness: string;
  citation_count: number;
  latency_ms: number;
}

export interface SimulationRunSummary {
  total_questions: number;
  answered: number;
  refused: number;
  guardrail_blocks: number;
  declined: number;
  expected_gap_questions: number;
  expectation_matches: number;
  average_latency_ms: number;
}

export interface SimulationRun {
  run_id: string;
  started_at: string;
  completed_at: string;
  config: SimulationRunConfig;
  scenario_count: number;
  results: SimulationQuestionResult[];
  summary: SimulationRunSummary;
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

export async function getKnowledgeGaps(): Promise<KnowledgeGapAnalytics> {
  const res = await guard(await fetch("/api/analytics/knowledge-gaps", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load knowledge gaps");
  return res.json();
}

export async function getProcessComplexity(): Promise<ProcessComplexityAnalytics> {
  const res = await guard(await fetch("/api/analytics/process-complexity", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load process complexity");
  return res.json();
}

export async function getSimulatorCatalogue(): Promise<SimulatorCatalogue> {
  const res = await guard(await fetch("/api/simulator/scenarios", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load simulator scenarios");
  return res.json();
}

export async function listSimulationRuns(limit = 20): Promise<SimulationRun[]> {
  const res = await guard(await fetch(`/api/simulator/runs?limit=${limit}`, { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load simulation runs");
  return res.json();
}

export async function runSimulation(config: SimulationRunConfig): Promise<SimulationRun> {
  const res = await guard(
    await fetch("/api/simulator/runs", {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(config),
    }),
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "simulation run failed");
  }
  return res.json();
}

export async function getIntelligence(): Promise<IntelligenceReport> {
  const res = await guard(await fetch("/api/governance/intelligence", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load knowledge intelligence");
  return res.json();
}

export async function approveSource(id: string): Promise<void> {
  const res = await guard(await fetch(`/api/governance/sources/${id}/approve`, { method: "POST", headers: authHeaders() }));
  if (!res.ok) throw new Error("approve failed");
}

export async function rejectSource(id: string): Promise<void> {
  const res = await guard(await fetch(`/api/governance/sources/${id}/reject`, { method: "POST", headers: authHeaders() }));
  if (!res.ok) throw new Error("reject failed");
}

export async function ingestSource(id: string): Promise<SourceRecord> {
  const res = await guard(
    await fetch(`/api/sources/${id}/ingest`, { method: "POST", headers: authHeaders() }),
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "ingest failed");
  }
  return res.json();
}
