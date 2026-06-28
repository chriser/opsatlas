// Control-panel API client. All calls go through the Vite dev proxy (/api -> backend).

const TOKEN_KEY = "kp_token";
export const AUTH_INVALID_EVENT = "kp-auth-invalid";
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
    window.dispatchEvent(new Event(AUTH_INVALID_EVENT));
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

export interface RegulatoryImpactSimulation {
  candidate_id: string;
  theme: string;
  label: string;
  source_id: string;
  source_title: string;
  review_status: string;
  simulated_at: string;
  impact_score: number;
  impact_band: "low" | "medium" | "high";
  affected_source_count: number;
  affected_process_areas: string[];
  external_context_count: number;
  external_context: {
    title: string;
    url: string;
    version: number;
    update_date: string;
    matched_terms: string[];
  }[];
  affected_sources: {
    source_id: string;
    source_title: string;
    impact_score: number;
    impact_band: "low" | "medium" | "high";
    matched_terms: string[];
    process_areas: string[];
    passages: { heading: string; ordinal: number; excerpt: string; matched_terms: string[] }[];
    recommended_action: string;
  }[];
  recommended_actions: string[];
  assumptions: string[];
}

export interface GovernanceReanalysisCoverage {
  source_id: string;
  snapshot_id: string;
  title: string;
  url: string;
  provider: string;
  version: number;
  snapshot_date: string;
  update_date: string;
  status: "matched" | "unmatched";
  matched_candidate_count: number;
  matched_terms: string[];
  matched_candidates: {
    candidate_id: string;
    label: string;
    source_id: string;
    source_title: string;
    matched_terms: string[];
  }[];
}

export interface GovernanceReanalysisReport {
  has_run: boolean;
  run_id?: string;
  analysed_at?: string;
  needs_reanalysis: boolean;
  pending_external_snapshot_count: number;
  pending_internal_change_count: number;
  total_source_count?: number;
  approved_source_count?: number;
  health?: "green" | "amber" | "red";
  active_issue_count?: number;
  new_issue_count?: number;
  resolved_issue_count?: number;
  candidate_count?: number;
  new_candidate_count?: number;
  changed_candidate_count?: number;
  review_counts?: Record<string, number>;
  external_source_count?: number;
  external_snapshot_count?: number;
  external_matched_count?: number;
  external_unmatched_count?: number;
  previous_decisions_preserved?: number;
  coverage?: GovernanceReanalysisCoverage[];
}

export type ComplianceFindingClassification =
  | "supported"
  | "contradiction"
  | "missing_obligation"
  | "missing_detail"
  | "too_vague"
  | "outdated"
  | "unsupported_claim"
  | "not_related"
  | "needs_human_review";

export interface ComplianceReasoningStatus {
  enabled: boolean;
  service: string;
  status: "not_configured" | "available" | "unavailable";
  detail?: string;
  health?: { status: string; service: string; version?: string };
}

export interface ComplianceReasoningCapabilities {
  service: string;
  version: string;
  modes: string[];
  endpoints: string[];
  supported_findings: ComplianceFindingClassification[];
  model_backends: string[];
  notes: string[];
}

export interface ComplianceTextEvidence {
  source_id: string;
  source_title: string;
  section_id: string;
  heading: string;
  citation: string;
  text: string;
  url: string;
  version: string;
  content_sha256: string;
}

export interface ComplianceStatement {
  id: string;
  modality: "obligation" | "prohibition" | "permission" | "recommendation" | "informational";
  actor: string;
  action: string;
  condition: string;
  key_terms: string[];
  evidence: ComplianceTextEvidence;
}

export interface ComplianceFinding {
  id: string;
  classification: ComplianceFindingClassification;
  severity: "low" | "medium" | "high";
  confidence: number;
  alignment_score: number;
  rationale: string;
  obligation_id: string;
  internal_claim_id: string;
  external_evidence: ComplianceTextEvidence | null;
  internal_evidence: ComplianceTextEvidence | null;
  signals: string[];
}

export interface ComplianceReviewPairProgress {
  pair_id: string;
  external_document_id: string;
  external_title: string;
  internal_document_id: string;
  internal_title: string;
  status: "queued" | "running" | "completed" | "failed" | "not_related";
  classification: ComplianceFindingClassification | "";
  relevance_score: number;
  finding_count: number;
  rationale: string;
}

export interface ComplianceReviewStatus {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  created_at: string;
  completed_at: string;
  failure_reason: string;
  obligation_count: number;
  internal_claim_count: number;
  finding_count: number;
  pair_total: number;
  pair_completed: number;
  progress_percent: number;
  current_pair: ComplianceReviewPairProgress | null;
  pairs: ComplianceReviewPairProgress[];
  audit: {
    engine: string;
    engine_version: string;
    model_profile: string;
    prompt_version: string;
    external_document_count: number;
    internal_document_count: number;
    source_hashes: Record<string, string>;
    assumptions: string[];
  };
}

export interface ComplianceReviewResult {
  status: ComplianceReviewStatus;
  obligations: ComplianceStatement[];
  internal_claims: ComplianceStatement[];
  findings: ComplianceFinding[];
}

export interface ComplianceFindingListResponse {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  findings: ComplianceFinding[];
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

export interface AvatarConfig {
  provider: "anam";
  configured: boolean;
  missing: string[];
  persona_id_hint: string;
}

export type AvatarStyleMode = "formal" | "natural";

export interface AvatarAnswerResponse {
  provider: "anam";
  style: AvatarStyleMode;
  rendered_text: string;
  render_notes: string[];
  answer: AnswerResponse;
}

export async function getAvatarConfig(): Promise<AvatarConfig> {
  const res = await guard(await fetch("/api/avatar/anam/config", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load avatar configuration");
  return res.json();
}

export async function createAvatarSessionToken(): Promise<string> {
  const res = await guard(await fetch("/api/avatar/anam/session-token", { method: "POST", headers: authHeaders() }));
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "could not start avatar session");
  }
  return (await res.json()).session_token;
}

export async function askAvatarQuestion(q: string, style: AvatarStyleMode, topK = 5): Promise<AvatarAnswerResponse> {
  const res = await guard(
    await fetch("/api/avatar/answer", {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ q, style, top_k: topK }),
    }),
  );
  if (!res.ok) throw new Error("avatar ask failed");
  return res.json();
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

export async function deleteExternalSource(sourceId: string): Promise<void> {
  const res = await guard(
    await fetch(`/api/external-sources/${sourceId}`, {
      method: "DELETE",
      headers: authHeaders(),
    }),
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "could not remove external source");
  }
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
    throw new Error(body.detail ?? "Public source snapshot failed");
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

export async function simulateRegulatoryImpact(id: string): Promise<RegulatoryImpactSimulation> {
  const res = await guard(
    await fetch(`/api/regulatory/candidates/${id}/impact-simulation`, {
      method: "POST",
      headers: authHeaders(),
    }),
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "could not simulate regulatory impact");
  }
  return res.json();
}

export async function getGovernanceReanalysis(): Promise<GovernanceReanalysisReport> {
  const res = await guard(await fetch("/api/governance/reanalysis/latest", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load governance re-analysis");
  return res.json();
}

export async function reanalyseGovernance(): Promise<GovernanceReanalysisReport> {
  const res = await guard(await fetch("/api/governance/reanalysis", { method: "POST", headers: authHeaders() }));
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "could not re-analyse governance");
  }
  return res.json();
}

export async function getComplianceReasoningStatus(): Promise<ComplianceReasoningStatus> {
  const res = await guard(await fetch("/api/compliance-reasoning/status", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load compliance reasoning status");
  return res.json();
}

export async function getComplianceReasoningCapabilities(): Promise<ComplianceReasoningCapabilities> {
  const res = await guard(await fetch("/api/compliance-reasoning/capabilities", { headers: authHeaders() }));
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "could not load compliance reasoning capabilities");
  }
  return res.json();
}

export async function runComplianceReasoningReview(options?: {
  include_supported_findings?: boolean;
  include_unsupported_internal_claims?: boolean;
  include_missing_obligations?: boolean;
  include_not_related_pairs?: boolean;
  min_alignment_score?: number;
  min_pair_relevance_score?: number;
  min_contradiction_alignment_score?: number;
  max_findings?: number;
}): Promise<ComplianceReviewResult> {
  const res = await guard(
    await fetch("/api/compliance-reasoning/reviews", {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(options ?? {}),
    }),
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "could not run compliance reasoning review");
  }
  return res.json();
}

export async function getComplianceReasoningReviewStatus(jobId: string): Promise<ComplianceReviewStatus> {
  const res = await guard(await fetch(`/api/compliance-reasoning/reviews/${jobId}`, { headers: authHeaders() }));
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "could not load compliance reasoning review status");
  }
  return res.json();
}

export async function getComplianceReasoningFindings(jobId: string): Promise<ComplianceFindingListResponse> {
  const res = await guard(await fetch(`/api/compliance-reasoning/reviews/${jobId}/findings`, { headers: authHeaders() }));
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "could not load compliance reasoning findings");
  }
  return res.json();
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

export interface ProcessMapDraft {
  process_id: string;
  name: string;
  source_title: string;
  domain: string;
  process: string;
  roles: string[];
  systems: string[];
  controls: string[];
  dependencies: string[];
  open_decisions: string[];
  steps: { id: string; label: string; owner: string; topic: string; confidence: string }[];
  edges: { source: string; target: string; label: string }[];
  mermaid: string;
}

export interface ProcessDiagramContext {
  status: "available" | "empty" | "unavailable" | string;
  message: string;
  process_id: string;
  process_name: string;
  source_title: string;
  service_url: string;
  chart?: ProcessDiagramChart | null;
  svg: string;
}

export interface ProcessDiagramServiceStatus {
  service_url: string;
  running: boolean;
  started: boolean;
  startable: boolean;
  pid?: number | null;
  message: string;
  health: Record<string, unknown>;
  start_command: string[];
  log_path: string;
}

export interface ProcessDiagramPoint {
  x: number;
  y: number;
}

export interface ProcessDiagramNode {
  id: string;
  type: "lane" | "who" | "start" | "end" | "task" | "gateway" | "control" | "system" | "risk" | "annotation" | string;
  label: string;
  lane: string;
  x: number;
  y: number;
  width: number;
  height: number;
  metadata: Record<string, string>;
}

export interface ProcessDiagramEdge {
  id: string;
  from: string;
  to: string;
  label: string;
  type: "sequence" | "message" | "association" | "control" | string;
  points: ProcessDiagramPoint[];
}

export interface ProcessDiagramAnimationStep {
  step: number;
  action: "draw_node" | "draw_edge" | "draw_lane" | "highlight_node" | string;
  target_id: string;
  label: string;
  narration: string;
}

export interface ProcessDiagramChart {
  schema_version: string;
  chart_id: string;
  title: string;
  style: string;
  format: string;
  nodes: ProcessDiagramNode[];
  edges: ProcessDiagramEdge[];
  animation_steps: ProcessDiagramAnimationStep[];
  narration_script: string[];
  warnings: string[];
}

export interface ProcessStressRuleSet {
  process_id: string;
  process_name: string;
  source_title: string;
  role_count: number;
  system_count: number;
  dependency_count: number;
  control_count: number;
  rule_count: number;
  handoff_count: number;
  exception_term_count: number;
  validation_gate_count: number;
  dominant_role: string;
  stress_factors: string[];
}

export interface ProcessStressScenario {
  scenario_id: string;
  label: string;
  demand_multiplier: number;
  exception_rate: number;
  staffing_factor: number;
}

export interface ProcessStressResult {
  process_id: string;
  process_name: string;
  scenario_id: string;
  scenario_label: string;
  cycle_time_index: number;
  queue_pressure_score: number;
  rework_risk_score: number;
  bottleneck_role: string;
  bottleneck_reason: string;
  optimisation_actions: string[];
}

export interface ProcessStressReport {
  process_count: number;
  scenario_count: number;
  rules: ProcessStressRuleSet[];
  scenarios: ProcessStressScenario[];
  results: ProcessStressResult[];
  highest_risk?: ProcessStressResult | null;
  rubric: Record<string, string>;
}

export interface CoverageDomain {
  domain_id: string;
  label: string;
  description: string;
  coverage_status: "covered" | "partial" | "uncovered" | string;
  evidence_strength_score: number;
  process_count: number;
  process_ids: string[];
  source_titles: string[];
  roles: string[];
  systems: string[];
  controls: string[];
  dependencies: string[];
  lifecycle_stages: string[];
  missing_signals: string[];
}

export interface CoverageProcessRow {
  process_id: string;
  process_name: string;
  source_title: string;
  matched_domains: string[];
  lifecycle_stages: string[];
  roles: string[];
  systems: string[];
  controls: string[];
  evidence_notes: string[];
}

export interface OperatingModelCoverageMap {
  process_count: number;
  domain_count: number;
  covered_domain_count: number;
  partial_domain_count: number;
  uncovered_domain_count: number;
  coverage_score: number;
  role_count: number;
  system_count: number;
  control_count: number;
  domains: CoverageDomain[];
  process_matrix: CoverageProcessRow[];
  rubric: Record<string, string>;
}

export interface GapOverlapFinding {
  finding_id: string;
  finding_type: "gap" | "overlap" | "clash" | string;
  severity: "high" | "medium" | "low" | string;
  title: string;
  description: string;
  affected_process_ids: string[];
  affected_processes: string[];
  evidence: string[];
  recommended_action: string;
}

export interface ProcessGapOverlapReport {
  process_count: number;
  finding_count: number;
  gap_count: number;
  overlap_count: number;
  clash_count: number;
  high_severity_count: number;
  findings: GapOverlapFinding[];
  rubric: Record<string, string>;
}

export async function getProcessRegistry(): Promise<ProcessRecord[]> {
  const res = await guard(await fetch("/api/process/registry", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load process registry");
  return res.json();
}

export async function getProcessStressTest(): Promise<ProcessStressReport> {
  const res = await guard(await fetch("/api/process/stress-test", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load process stress test");
  return res.json();
}

export async function getOperatingModelCoverage(): Promise<OperatingModelCoverageMap> {
  const res = await guard(await fetch("/api/process/coverage-map", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load operating model coverage");
  return res.json();
}

export async function getProcessGapOverlap(): Promise<ProcessGapOverlapReport> {
  const res = await guard(await fetch("/api/process/gap-overlap", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load process gap/overlap findings");
  return res.json();
}

export async function getProcessMap(processId: string): Promise<ProcessMapDraft> {
  const res = await guard(await fetch(`/api/process/maps/${processId}`, { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load process map");
  return res.json();
}

export async function getProcessDiagram(processId: string): Promise<ProcessDiagramContext> {
  const res = await guard(await fetch(`/api/process/diagrams/${processId}`, { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load process diagram");
  return res.json();
}

export async function resolveProcessDiagram(question: string, citations: Citation[]): Promise<ProcessDiagramContext> {
  const res = await guard(
    await fetch("/api/process/diagrams/resolve", {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ question, citations }),
    }),
  );
  if (!res.ok) throw new Error("could not resolve process diagram");
  return res.json();
}

export async function getProcessDiagramServiceStatus(): Promise<ProcessDiagramServiceStatus> {
  const res = await guard(await fetch("/api/process/diagrams/service/status", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load diagram service status");
  return res.json();
}

export async function startProcessDiagramService(): Promise<ProcessDiagramServiceStatus> {
  const res = await guard(await fetch("/api/process/diagrams/service/start", { method: "POST", headers: authHeaders() }));
  if (!res.ok) throw new Error("could not start diagram service");
  return res.json();
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

export interface ValueScenario {
  scenario_id: string;
  label: string;
  description: string;
  confidence: string;
}

export interface ValueAssumption {
  assumption_id: string;
  scenario_id: string;
  driver: string;
  metric: string;
  label: string;
  value: number;
  unit: string;
  confidence: string;
  rationale: string;
  source: string;
}

export interface ValueAssumptionMatrixCell {
  assumption_id: string;
  scenario_id: string;
  label: string;
  value: number;
  unit: string;
  confidence: string;
  rationale: string;
  source: string;
}

export interface ValueAssumptionMatrixRow {
  metric: string;
  driver: string;
  label: string;
  unit: string;
  scenario_values: Record<string, ValueAssumptionMatrixCell>;
  confidence_mix: string[];
  value_spread?: number | null;
}

export interface ValueScenarioMetric {
  scenario_id: string;
  label: string;
  confidence: string;
  gross_annual_benefit_gbp: number;
  annual_opex_gbp: number;
  net_annual_benefit_gbp: number;
  one_off_capex_gbp: number;
  simple_payback_years?: number | null;
  npv_gbp: number;
  irr?: number | null;
  horizon_years: number;
  formula: string;
}

export interface ValueTelemetry {
  event_count: number;
  observed_total_gbp: number;
  synthetic_event_count: number;
  synthetic_total_gbp: number;
  combined_event_count: number;
  combined_total_gbp: number;
  by_driver: { value_driver: string; count: number; value_estimate: number }[];
  monthly_trend: {
    month: string;
    observed_gbp: number;
    synthetic_gbp: number;
    total_gbp: number;
    observed_events: number;
    synthetic_events: number;
  }[];
  projection: {
    observed_ytd_projection_gbp: number;
    synthetic_ytd_projection_gbp: number;
    combined_ytd_projection_gbp: number;
    basis: string;
  };
  recent_events: {
    event_id: string;
    timestamp: string;
    label: string;
    value_driver: string;
    process_area: string;
    scenario_id: string;
    unit: string;
    confidence: string;
    value_estimate: number;
    synthetic_historical: boolean;
    evidence_type: string;
    run_id: string;
  }[];
}

export interface ValueAnalytics {
  schema_version: string;
  active_scenario_id: string;
  scenarios: ValueScenario[];
  assumptions: ValueAssumption[];
  assumption_matrix: ValueAssumptionMatrixRow[];
  metrics: ValueScenarioMetric[];
  telemetry: ValueTelemetry;
  driver_options: string[];
  rubric: Record<string, string>;
}

export interface ValueEventPayload {
  label: string;
  value_driver: string;
  value_estimate: number;
  process_area?: string;
  scenario_id?: string;
  unit?: string;
  confidence?: string;
  evidence_type?: string;
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
  status: string;
  cadence: string;
  boundary: string;
}

export interface ValidationEvidenceReport {
  generated_at: string;
  ksb_rows: KsbTraceabilityRow[];
  validation_protocols: ValidationProtocolRow[];
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
  run_kind?: "single" | "period";
  scenario_ids?: string[];
  persona_ids?: string[];
  seed?: number;
  max_questions?: number;
  top_k?: number;
  preset_period?: "last_7_days" | "last_30_days" | "last_90_days" | "custom";
  start_date?: string;
  end_date?: string;
  usage_density?: "light" | "moderate" | "heavy";
  usage_pattern?: "steady" | "weekday_peak" | "ramp_up" | "month_end";
}

export interface SimulationQuestionResult {
  timestamp: string;
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

export interface SimulationRunQa {
  synthetic_only: boolean;
  replayable: boolean;
  synthetic_historical: boolean;
  actor_type: string;
  source: string;
  replay_of_run_id?: string | null;
  question_fingerprint: string;
  replay_fingerprint: string;
  selected_scenario_ids: string[];
  selected_persona_ids: string[];
  selected_question_ids: string[];
  period_start: string;
  period_end: string;
  period_day_count: number;
  usage_density: string;
  usage_pattern: string;
}

export interface SimulationRun {
  run_id: string;
  started_at: string;
  completed_at: string;
  config: SimulationRunConfig;
  qa: SimulationRunQa;
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

export async function getProcessComplexity(): Promise<ProcessComplexityAnalytics> {
  const res = await guard(await fetch("/api/analytics/process-complexity", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load process complexity");
  return res.json();
}

export async function getValueAnalytics(): Promise<ValueAnalytics> {
  const res = await guard(await fetch("/api/analytics/value", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load value analytics");
  return res.json();
}

export async function recordValueEvent(payload: ValueEventPayload): Promise<ValueAnalytics> {
  const res = await guard(
    await fetch("/api/analytics/value/events", {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "could not record value event");
  }
  return res.json();
}

export async function getValidationEvidence(): Promise<ValidationEvidenceReport> {
  const res = await guard(await fetch("/api/analytics/validation-evidence", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load validation evidence");
  return res.json();
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

export async function runHistoricalSimulation(config: SimulationRunConfig): Promise<SimulationRun> {
  const res = await guard(
    await fetch("/api/simulator/period-runs", {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ ...config, run_kind: "period" }),
    }),
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "historical simulation failed");
  }
  return res.json();
}

export async function replaySimulationRun(runId: string): Promise<SimulationRun> {
  const res = await guard(
    await fetch(`/api/simulator/runs/${runId}/replay`, {
      method: "POST",
      headers: authHeaders(),
    }),
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "simulation replay failed");
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
