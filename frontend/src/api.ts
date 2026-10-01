// Control-panel API client. All calls go through the Vite dev proxy (/api -> backend).

export const AUTH_INVALID_EVENT = "kp-auth-invalid";
/** Fired whenever the signed-in person changes (sign-in, sign-out, a refreshed profile). */
export const ME_CHANGED_EVENT = "opsatlas-me";

// ---- The session (IAM F3) ----
// The browser holds the session in an HttpOnly cookie it never reads; this module keeps what the server told it
// about the person and the session, including the CSRF token every change must carry.
export interface MeSpace {
  id: string;
  name: string;
  kind: "product" | "playbook" | "system" | "organisation";
  solo_operator: boolean;
  permissions: string[];
}

export interface Me {
  user: {
    id: string;
    login: string;
    email: string;
    display_name: string;
    state: string;
    created_at: string;
    last_sign_in_at: string | null;
    role_label: string;
  };
  session: {
    id: string;
    csrf: string;
    idle_minutes: number;
    fresh_minutes: number;
    created_at: string;
    authenticated_at: string;
    last_seen_at: string;
    absolute_expires_at: string;
    idle_expires_at: string;
    privileged: boolean;
  };
  platform_permissions: string[];
  spaces: MeSpace[];
  legacy: boolean;
}

let me: Me | null = null;

function setMe(value: Me | null) {
  me = value;
  window.dispatchEvent(new CustomEvent(ME_CHANGED_EVENT));
}

export function currentMe(): Me | null {
  return me;
}

/** Whether the signed-in person holds a permission: at the platform, or in a space (the active one by default). */
export function can(permission: string, space?: string | null): boolean {
  if (!me) return false;
  if (me.platform_permissions.includes(permission)) return true;
  const id = space === undefined ? activeSpace : space;
  const found = id ? me.spaces.find((s) => s.id === id) : undefined;
  return Boolean(found?.permissions.includes(permission));
}

try {
  localStorage.removeItem("kp_token"); // the bearer token of the shared sign-in is never kept in the browser again
} catch {
  // storage may be unavailable
}

// A request within a minute of a click or a key press restarts the session's idle clock; a poll does not (IAM F3).
let lastInteraction = 0;
export function noteInteraction() {
  lastInteraction = Date.now();
}
export function lastInteractionAt(): number {
  return lastInteraction;
}
if (typeof document !== "undefined") {
  for (const kind of ["pointerdown", "keydown"] as const) document.addEventListener(kind, noteInteraction, { capture: true, passive: true });
}

/** The sign-in, and the page the request comes from (for the activity log). */
// ---- Knowledge spaces (KS S2, S6) ----
// Every request is for one space. The active space (chosen in the top bar) is used unless a call names its own; a
// request that names none is the Product Guide's.
export const PRODUCT_GUIDE = "product-guide";
const SPACE_KEY = "opsatlas-active-space";
let activeSpace: string = (() => {
  try {
    return localStorage.getItem(SPACE_KEY) || PRODUCT_GUIDE;
  } catch {
    return PRODUCT_GUIDE;
  }
})();

export function getActiveSpace(): string {
  return activeSpace;
}

export function setActiveSpace(space: string) {
  activeSpace = space || PRODUCT_GUIDE;
  try {
    localStorage.setItem(SPACE_KEY, activeSpace);
  } catch {
    // A convenience: the choice is kept for this page only.
  }
  window.dispatchEvent(new CustomEvent("opsatlas-space", { detail: activeSpace }));
}

export function spaceHeader(space?: string | null): Record<string, string> {
  const id = space ?? activeSpace;
  return id && id !== PRODUCT_GUIDE ? { "X-OpsAtlas-Space": id } : {};
}

export function authHeaders(space?: string | null): Record<string, string> {
  const view = window.location.hash.slice(1).split(":")[0] || "dashboard";
  return {
    ...(me ? { "X-CSRF-Token": me.session.csrf } : {}),
    ...(Date.now() - lastInteraction < 60_000 ? { "X-OpsAtlas-Interaction": "1" } : {}),
    "x-opsatlas-view": view,
    ...spaceHeader(space),
  };
}

export function isAuthenticated(): boolean {
  return me !== null;
}

export class AuthError extends Error {}
/** The server wants the password entered again before this change (IAM F3). */
export class ReauthRequired extends Error {}

/** Access control refused the request: the message is the server's own reason (AUDIT F9). */
export class AccessDenied extends Error {}

// Codes the server's access control sends with a 403. Other 403s, such as the Tibi service's stale token, stay with
// their callers, which retry.
const ACCESS_CODES = new Set(["ACCESS_DENIED", "REAUTH_REQUIRED", "CSRF_REQUIRED"]);

async function guard(res: Response): Promise<Response> {
  if (res.status === 401) {
    setMe(null);
    window.dispatchEvent(new Event(AUTH_INVALID_EVENT));
    throw new AuthError("Your session has ended. Please sign in again.");
  }
  if (res.status === 403) {
    // A refused permission reads as such, not as the caller's generic "could not load…" (D6).
    const data = (await res.clone().json().catch(() => ({}))) as { detail?: unknown; code?: string };
    if (data.code && ACCESS_CODES.has(data.code)) {
      const message = typeof data.detail === "string" ? data.detail : "You do not have permission to do that.";
      if (data.code === "REAUTH_REQUIRED") throw new ReauthRequired(message);
      throw new AccessDenied(message);
    }
  }
  return res;
}

/** An authenticated JSON request. On failure it throws with the server's own explanation (its `detail`). */
export async function apiRequest<T>(method: string, path: string, body?: unknown, space?: string | null): Promise<T> {
  const headers: Record<string, string> = { ...authHeaders(space) };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await guard(await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) }));
  if (!res.ok) {
    const data = (await res.json().catch(() => ({}))) as { detail?: unknown; code?: string };
    const message = typeof data.detail === "string" ? data.detail : `Request failed (${res.status})`;
    if (data.code === "REAUTH_REQUIRED") throw new ReauthRequired(message);
    throw new Error(message);
  }
  return (await res.json()) as T;
}

/** An authenticated multipart upload (a file in a form). */
export async function apiUpload<T>(path: string, form: FormData, space?: string | null): Promise<T> {
  const res = await guard(await fetch(path, { method: "POST", headers: authHeaders(space), body: form }));
  if (!res.ok) {
    const data = (await res.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(typeof data.detail === "string" ? data.detail : `Upload failed (${res.status})`);
  }
  return (await res.json()) as T;
}

/** Sign in with an email address and password. The pre-authentication CSRF token protects the sign-in itself. */
export async function login(loginName: string, password: string): Promise<Me> {
  const csrf = ((await (await fetch("/api/auth/csrf")).json().catch(() => ({}))) as { csrf?: string }).csrf ?? "";
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
    body: JSON.stringify({ login: loginName, password }),
  });
  if (!res.ok) {
    const data = (await res.json().catch(() => ({}))) as { detail?: string; code?: string };
    if (res.status === 429) throw new Error(data.detail ?? "Too many attempts; try again shortly.");
    if (res.status === 403) throw new Error("Reload the page and sign in again.");
    throw new Error(res.status === 401 ? "That email address and password do not match." : (data.detail ?? "Sign-in failed."));
  }
  const who = (await res.json()) as Me;
  setMe(who);
  return who;
}

/** The signed-in person, from the session cookie; throws when there is no live session. */
export async function fetchMe(): Promise<Me> {
  const res = await fetch("/api/auth/me", { headers: authHeaders() });
  if (res.status === 401) {
    setMe(null);
    throw new AuthError("Not signed in");
  }
  if (!res.ok) throw new Error(`Could not load the account (${res.status})`);
  const who = (await res.json()) as Me;
  setMe(who);
  return who;
}

export async function logout(): Promise<void> {
  try {
    await fetch("/api/auth/logout", { method: "POST", headers: authHeaders() });
  } finally {
    setMe(null);
  }
}

/** A one-use ticket for the voice socket's hello (IAM F6); it lives 30 seconds and is bound to this conversation. */
export async function getSocketTicket(conversationId: string): Promise<string> {
  return (await apiRequest<{ ticket: string }>("POST", "/api/tibi/ws-ticket", { conversation_id: conversationId })).ticket;
}

/** What the core reports about itself to a signed-in person: sources and the configured models. */
export const getHealthDetails = () => apiRequest<HealthResponse>("GET", "/api/health/details");

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
  // Scope and lifecycle (GOV S8), all optional.
  effective_from?: string | null;
  effective_to?: string | null;
  phases?: string[];
  applies_to?: string[];
  supersedes?: string[];
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
  answer_path?: "oag" | "rag" | "rag+ontology" | string;
  outcome?: "answered" | "refused" | "blocked" | "declined" | string;
  refused: boolean;
  category: string | null;
  confidence: string;
  grounding: string;
  grounding_score: number;
  faithfulness: string;
  latency_ms: number;
  evidence?: { source_title: string; heading: string; ordinal: number }[];
}

export interface ActionExecution {
  execution_id: string;
  action: string;
  params: Record<string, unknown>;
  actor: { type: "operator" | "agent" | string; id: string; approved_by?: string | null };
  validation_results?: { rule: string; passed: boolean; message: string }[];
  outcome: "ok" | "rejected" | "error" | string;
  duration_ms: number;
  timestamp: string;
  failed_rule?: string | null;
  message: string;
}

export interface AgentStep {
  tool: string;
  args: Record<string, unknown>;
  result_summary: string;
  latency_ms: number;
}

export interface ProposedAction {
  proposal_id: string;
  action: string;
  params: Record<string, unknown>;
  rationale: string;
  status: string;
}

export interface PendingActionProposal extends ProposedAction {
  agent_run_id: string;
  created_at: string;
  execution_id: string;
  approved_at: string;
  declined_at: string;
  declined_reason: string;
}

export interface AgentRunTrace {
  run_id: string;
  question: string;
  steps: AgentStep[];
  final_answer: string;
  proposed_actions: ProposedAction[];
  persisted_proposals?: PendingActionProposal[];
  total_latency_ms: number;
  created_at: string;
  stopped_reason: string;
}

export async function getTraces(limit = 50): Promise<AuditRecord[]> {
  const res = await guard(await fetch(`/api/observability/traces?limit=${limit}`, { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load traces");
  return res.json();
}

export async function getActionLog(limit = 20): Promise<ActionExecution[]> {
  const res = await guard(await fetch(`/api/ontology/actions/log?limit=${limit}`, { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load action log");
  return (await res.json()).executions;
}

export async function runOntologyInvestigation(question: string): Promise<AgentRunTrace> {
  const res = await guard(
    await fetch("/api/ontology/agent/runs", {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    }),
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "could not run ontology investigation");
  }
  return res.json();
}

export async function approveOntologyProposal(proposalId: string): Promise<{ proposal: PendingActionProposal; execution?: ActionExecution; already_approved: boolean }> {
  const res = await guard(await fetch(`/api/ontology/proposals/${proposalId}/approve`, { method: "POST", headers: authHeaders() }));
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "could not approve proposal");
  }
  return res.json();
}

export async function declineOntologyProposal(proposalId: string, reason = ""): Promise<{ proposal: PendingActionProposal; already_declined: boolean }> {
  const res = await guard(
    await fetch(`/api/ontology/proposals/${proposalId}/decline`, {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ reason }),
    }),
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "could not decline proposal");
  }
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
  citation_type?: "document" | "ontology_object" | "process_registry" | string;
}

export interface AnswerResponse {
  answer: string;
  citations: Citation[];
  mode: string;
  answer_path?: "oag" | "rag" | "rag+ontology" | string;
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

export async function listSources(space?: string | null): Promise<SourceRecord[]> {
  const res = await guard(await fetch("/api/sources", { headers: authHeaders(space) }));
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

export interface EamTaxonomyEntry {
  id: string;
  label: string;
  description: string;
  keywords: string[];
  order: number;
}

export interface EamNode {
  id: string;
  process_id: string;
  name: string;
  domain_id: string;
  domain_label: string;
  lifecycle_id: string;
  lifecycle_label: string;
  domain_confidence: number;
  lifecycle_confidence: number;
  matched_domain_keywords: string[];
  matched_lifecycle_keywords: string[];
  role_count: number;
  system_count: number;
  control_count: number;
  dependency_count: number;
  source_refs: string[];
  evidence_strength: number;
  confidence_band: "green" | "amber" | "red" | string;
}

export interface EamCell {
  domain_id: string;
  lifecycle_id: string;
  node_ids: string[];
  is_gap: boolean;
}

export interface EamEdge {
  id: string;
  edge_type: "system" | "control" | "dependency" | string;
  from_node_id: string;
  to_node_id: string;
  shared_entity_ids: string[];
  shared_entity_labels: string[];
}

export interface EamEntityRollup {
  id: string;
  object_type: string;
  name: string;
  process_count: number;
  linked_process_ids: string[];
  linked_entity_counts: Record<string, number>;
}

export interface EamDomainCoverage {
  domain_id: string;
  label: string;
  status: "covered" | "partial" | "uncovered" | string;
  node_count: number;
  lifecycle_stage_count: number;
  average_evidence_strength: number;
  node_ids: string[];
}

export interface EamCoverage {
  score: number;
  covered_domain_count: number;
  partial_domain_count: number;
  uncovered_domain_count: number;
  domains: EamDomainCoverage[];
}

export interface EamFinding {
  id: string;
  finding_type: "gap" | "overlap" | "clash" | string;
  severity: "high" | "medium" | "low" | string;
  title: string;
  description: string;
  node_ids: string[];
  entity_ids: string[];
  evidence: string[];
  recommended_action: string;
}

export interface EamModel {
  taxonomy_version: string;
  generated_at: string;
  source_count: number;
  process_count: number;
  domains: EamTaxonomyEntry[];
  lifecycle_stages: EamTaxonomyEntry[];
  nodes: EamNode[];
  cells: EamCell[];
  edges: EamEdge[];
  entity_rollups: Record<string, EamEntityRollup[]>;
  coverage: EamCoverage;
  findings: EamFinding[];
  finding_counts: Record<string, number>;
  meta: Record<string, unknown>;
}

export async function getProcessRegistry(): Promise<ProcessRecord[]> {
  const res = await guard(await fetch("/api/process/registry", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load process registry");
  return res.json();
}

export async function getEamModel(): Promise<EamModel> {
  const res = await guard(await fetch("/api/eam/model", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load Enterprise Activity Model");
  return res.json();
}

export async function getEamSvg(
  view = "activity",
  expandedNodeIds: string[] = [],
  selectedNodeId = "",
  showAllConnections = false,
): Promise<string> {
  const params = new URLSearchParams({ view });
  if (expandedNodeIds.length) params.set("expanded", expandedNodeIds.join(","));
  if (selectedNodeId) params.set("selected", selectedNodeId);
  if (showAllConnections) params.set("connections", "all");
  const res = await guard(await fetch(`/api/eam/svg?${params.toString()}`, { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load Enterprise Activity Model canvas");
  return res.text();
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

export type ImprovementTriggerType = "knowledge_gap" | "failed_retrieval" | "recurring_question" | "oag_coverage_gap";
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

export async function approveSource(id: string, space?: string | null): Promise<void> {
  const res = await guard(await fetch(`/api/governance/sources/${id}/approve`, { method: "POST", headers: authHeaders(space) }));
  if (!res.ok) throw new Error("approve failed");
}

export async function rejectSource(id: string, space?: string | null): Promise<void> {
  const res = await guard(await fetch(`/api/governance/sources/${id}/reject`, { method: "POST", headers: authHeaders(space) }));
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

// ---- Tibi, the voice companion (available when the workspace runs Tibi) ----

export interface TibiStatus {
  available: boolean;
  service: {
    service: string;
    status: string;
    api_version: number;
    modes: string[];
    /** The Tibi engine answering (OBS S9): its version, and whether it matches the release or has changed since. */
    engine?: { version: string; released: string; fingerprint: string; matches_release: boolean };
  } | null;
  gateway: string;
  /** Why Tibi may be slow to start, such as the governance review using the local model. */
  busy?: string | null;
}

/** Restart Tibi (you stay signed in), the process diagram service, or everything, OpsAtlas itself last (sign in again). */
export const restartServices = (which: "tibi" | "diagrams" | "all") =>
  apiRequest<{ restarting: string[]; sign_in_again: boolean }>("POST", "/api/services/restart", { which });
/** Start the process diagram service as one of the workspace's services (PI F1). */
export const startDiagramService = () => apiRequest<{ started: string }>("POST", "/api/services/start", { which: "diagrams" });

export interface TibiRecord {
  id: string;
  title: string;
  text: string;
  status: string;
  kind?: string;
  pages?: string;
  topics?: string[];
  references: { path: string; source_id: string; sha256: string }[];
  source_id: string;
  /** The OpsAtlas family space its document sits in (KS F1). */
  space?: string;
  sha256: string;
  eligible: boolean;
  approval: string;
  review_block?: string | null;
  /** Supporting documents changed since the record was enabled: it waits for the Human to reconfirm it (audit F01). */
  evidence_changed?: { source_id: string; title: string }[];
  overlaps: { id: string; title: string; text: string; sha256: string }[];
  provenance?: { contributor: string; topic: string; session_id: string; turn_id: string; text: string } | null;
  resolution?: { decision: string; reason: string } | null;
  disputed?: boolean;
}

export interface TibiSpokenVariant {
  id: string;
  record_id: string;
  text: string;
  text_sha256: string;
  status: string;
  usable: boolean;
  current: boolean;
}

export interface TibiContribution {
  id: string;
  session_id: string;
  contributor: string;
  topic: string;
  question: string;
  raw_text: string;
  quote?: string;
  status: string;
  issue: string;
}

export interface TibiOntologyObject {
  id: string;
  type: string;
  name: string;
  status?: string;
  technology?: string;
  runs?: string;
  scope?: string;
  evidence: string[];
}

export interface TibiOntology {
  objects: TibiOntologyObject[];
  links: { type: string; from: string; to: string }[];
  /** Facts not in use: waiting on records (``missing``), or withdrawn because a record changed since the fact was
   *  curated (``changed``) until the Human confirms it still holds (audit F04). */
  unusable: {
    id: string;
    name: string;
    type?: string;
    missing: string[];
    fact?: string;
    changed?: { record_id: string; title: string; sha256: string }[];
    records?: Record<string, string>;
  }[];
}

export interface TibiGovernanceAnswer {
  id: string;
  issue_key: string;
  kind: string;
  check: string;
  category: string;
  severity: string;
  source_title: string;
  detail: string;
  issues: { key: string; source_id: string; source_title: string; check: string; detail: string }[];
  contributor: string;
  answer: string;
  resolution: {
    decision: string;
    definitions?: { acronym: string; expansion: string }[];
    url?: string;
    replacement?: string;
    note?: string;
    keep?: "a" | "b";
  };
  verification: { status: string; message: string }[];
  status: string;
  created_at: string;
  text_sha256: string;
  statements?: TibiRecordStatement[];
  relation?: "conflict" | "duplicate";
}

/** One statement of a sales record, as quoted by a statement-level finding. */
export interface TibiRecordStatement {
  record_id: string;
  title: string;
  status: string;
  kind: string;
  contributor: string | null;
  source_id: string;
  statement_id: string;
  text: string;
  /** What the statement covers (phase, dates, sites), when its words or its record say (GOV S8). */
  applies_to?: string;
}

export interface TibiStatementFinding {
  key: string;
  relation: "conflict" | "duplicate";
  statements: TibiRecordStatement[];
  reason: string;
  second_opinion?: { relation: string; reason: string; model: string } | null;
  same_document: boolean;
  answer?: { id: string; status: string; answer: string } | null;
}

export interface TibiStatementReview {
  status: "idle" | "running" | "finished" | "failed";
  /** A change arrived during the review: it runs again when this one finishes (audit F06). */
  queued?: boolean;
  /** Whether the latest review covers the records as they stand now. */
  up_to_date?: boolean;
  started_at: string | null;
  progress: { judged: number; total: number } | null;
  error: string | null;
  profile: { name: string; judge: string; reviewer: string | null; data_leaves: boolean; where: string; note?: string };
  latest: {
    finished_at: string;
    judge_model: string;
    raised: { conflict: number; duplicate: number };
    total_seconds: number;
    candidates: number;
    statements: number;
    errors: number;
    dismissed_by_second_opinion: number;
    set_aside_by_scope?: { dates: number; phase: number } | null;
  } | null;
  open?: TibiStatementFinding[];
}

/** An open governance issue other than a conflict or duplicate between records, in plain words. */
export interface TibiOpenIssue {
  key: string;
  kind: string;
  check: string;
  label: string;
  severity: string | null;
  text: string;
  where: string[];
  hint: string | null;
  answer: string | null;
}

export interface TibiGovernanceSummary {
  issues: number;
  total: number;
  answered: number;
  open: number;
  items?: TibiOpenIssue[];
}

async function tibiGet<T>(path: string): Promise<T> {
  const res = await guard(await fetch(`/api/tibi${path}`, { headers: authHeaders() }));
  if (!res.ok) throw new Error(`Tibi request failed (${res.status})`);
  return (await res.json()) as T;
}

async function tibiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await guard(
    await fetch(`/api/tibi${path}`, {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(detail.detail ?? `Tibi request failed (${res.status})`);
  }
  return (await res.json()) as T;
}

/** The OpsAtlas sign-in, for the one call that cannot carry a header: Tibi's live voice socket. */

// ---- The Tibi service, through the OpsAtlas gateway (/services/tibi) ----

let tibiServiceToken: string | null = null;

async function tibiServiceRequest(path: string, init: RequestInit = {}): Promise<Response> {
  return guard(await fetch(`/services/tibi${path}`, { ...init, headers: { ...authHeaders(), ...(init.headers ?? {}) } }));
}

/** A refusal from the Tibi service, with its HTTP status (404: that conversation has ended). */
export class TibiServiceError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

async function tibiServiceRead<T>(res: Response, fallback: string): Promise<T> {
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new TibiServiceError(detail.detail ?? fallback, res.status);
  }
  return (await res.json()) as T;
}

/** The Tibi service's own token, required on every change it accepts. */
export async function getTibiServiceToken(refresh = false): Promise<string> {
  if (!tibiServiceToken || refresh) {
    const data = await tibiServiceRead<{ token: string }>(await tibiServiceRequest("/api/bootstrap"), "Tibi is not running.");
    tibiServiceToken = data.token;
  }
  return tibiServiceToken;
}

export async function tibiServiceGet<T>(path: string): Promise<T> {
  return tibiServiceRead<T>(await tibiServiceRequest(path), "Tibi could not complete this request.");
}

export async function tibiServicePost<T>(path: string, body: unknown): Promise<T> {
  const post = async (refresh: boolean) =>
    tibiServiceRequest(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-sme-token": await getTibiServiceToken(refresh) },
      body: JSON.stringify(body),
    });
  let res = await post(false);
  if (res.status === 403) res = await post(true); // the Tibi service restarted: its token changed
  return tibiServiceRead<T>(res, "Tibi could not complete this request.");
}

export async function tibiServiceDelete<T>(path: string): Promise<T> {
  const remove = async (refresh: boolean) =>
    tibiServiceRequest(path, { method: "DELETE", headers: { "x-sme-token": await getTibiServiceToken(refresh) } });
  let res = await remove(false);
  if (res.status === 403) res = await remove(true); // the Tibi service restarted: its token changed
  return tibiServiceRead<T>(res, "Tibi could not complete this request.");
}

/** Null when this OpsAtlas workspace does not run Tibi. */
export async function getTibiStatus(): Promise<TibiStatus | null> {
  try {
    return await tibiGet<TibiStatus>("/status");
  } catch (error) {
    if (error instanceof AuthError) throw error;
    return null;
  }
}

export const getTibiRecords = () => tibiGet<{ records: TibiRecord[]; digest: string }>("/knowledge");
export const reviewTibiRecord = (id: string, expectedHash: string, approve: boolean) =>
  tibiPost<TibiRecord>(`/knowledge/${encodeURIComponent(id)}/review`, { expected_hash: expectedHash, approve });
export const resolveTibiRecord = (id: string, expectedHash: string, decision: string, related: Record<string, string>, reason: string) =>
  tibiPost<TibiRecord>(`/knowledge/${encodeURIComponent(id)}/resolve`, { expected_hash: expectedHash, decision, related, reason });
export const getTibiSource = (id: string) => tibiGet<{ title: string; text: string }>(`/sources/${encodeURIComponent(id)}`);
export const getTibiSpoken = () => tibiGet<{ variants: TibiSpokenVariant[] }>("/spoken");
export const reviewTibiSpoken = (id: string, expectedHash: string, approve: boolean) =>
  tibiPost<TibiSpokenVariant>(`/spoken/${encodeURIComponent(id)}/review`, { expected_hash: expectedHash, approve });
// Drafting, contributions and proposals belong to the Tibi service.
export const draftTibiSpoken = () =>
  tibiServicePost<{ drafted: string[]; rejected: { record_id: string; reason: string }[] }>("/api/spoken/draft", {});
export const getTibiContributions = () => tibiServiceGet<{ turns: TibiContribution[] }>("/api/contributions");
export const proposeTibiClaim = (body: { session_id: string; turn_id: string; text: string; status: string; expected_hash: string | null; wording_confirmed: boolean }) =>
  tibiServicePost<TibiRecord>("/api/contributions/propose", body);
export const getTibiOntology = () => tibiGet<TibiOntology>("/ontology");
export const confirmTibiFact = (id: string, records: Record<string, string>) =>
  tibiPost<TibiOntology>(`/ontology/${encodeURIComponent(id)}/confirm`, { records });

/** A typed turn through Tibi's engine (DSME S1): what the Digital SME speaks, and how Tibi reached it. */
export interface TibiTextTurn {
  reply: string;
  segments: string[];
  route: string;
  route_reasons: string[];
  grounding: string | null;
  records: { id: string; title: string; source_id: string; status: string }[];
  blocked?: number | string[] | null;
  phase?: string;
  reasoning_ms: number | null;
  total_ms: number;
  engine: { version: string; fingerprint: string };
}
// The Digital SME asks the same engine as Tibi's voice, through the Tibi service's text channel.
export const openTibiText = () => tibiServicePost<{ id: string; channel: string; engine: string }>("/api/text/sessions", { channel: "digital_sme" });
export const askTibiText = (id: string, text: string) =>
  tibiServicePost<TibiTextTurn>(`/api/text/sessions/${encodeURIComponent(id)}/turns`, { text });
export const closeTibiText = (id: string) => tibiServicePost<{ closed: boolean }>(`/api/text/sessions/${encodeURIComponent(id)}/close`, {});
export const getTibiGovernanceAnswers = () => tibiGet<{ answers: TibiGovernanceAnswer[] }>("/governance/answers");
export const getTibiGovernanceSummary = () => tibiGet<TibiGovernanceSummary>("/governance/agenda");
export const reviewTibiGovernanceAnswer = (id: string, expectedHash: string, approve: boolean) =>
  tibiPost<TibiGovernanceAnswer>(`/governance/answers/${encodeURIComponent(id)}/review`, { expected_hash: expectedHash, approve });
export const getTibiStatementReview = () => tibiGet<TibiStatementReview>("/governance/statements");
export const runTibiStatementReview = () => tibiPost<TibiStatementReview>("/governance/statements/run", {});

// ---- Knowledge spaces ----
export interface Space {
  id: string;
  kind: "product" | "playbook" | "system" | "organisation";
  name: string;
  about?: string;
  status: string;
  documents: number;
}
export const listSpaces = () => apiRequest<{ spaces: Space[] }>("GET", "/api/spaces");
/** Pages listing spaces refresh when one is created, renamed, archived or restored (KS S7). */
export const SPACES_CHANGED = "opsatlas-spaces";
const spacesChanged = () => window.dispatchEvent(new CustomEvent(SPACES_CHANGED));
/** A new organisation space, empty and ready at once. */
export async function createSpace(name: string, about: string): Promise<Space> {
  const space = await apiRequest<Space>("POST", "/api/spaces", { name, about });
  spacesChanged();
  return space;
}
/** Rename, describe, archive or restore an organisation space. Archiving keeps its documents. */
export async function changeSpace(id: string, fields: { name?: string; about?: string; status?: "active" | "archived" }): Promise<Space> {
  const space = await apiRequest<Space>("PATCH", `/api/spaces/${encodeURIComponent(id)}`, fields);
  spacesChanged();
  return space;
}
export const transferDocument = (sourceId: string, to: string) =>
  apiRequest<{ source_id: string; title: string; from: string; to: string; approval: string }>("POST", "/api/spaces/transfer", {
    source_id: sourceId,
    to,
  });

// ---- Process interviews (TIBI E5): the working process model, the live map, continuing and saving --------------------

export interface ProcessQuote {
  text: string;
  turn: number;
}
export interface ProcessStep {
  id: string;
  kind: "task" | "decision" | "end";
  label: string;
  who: string;
  system: string;
  next: { to: string; label: string }[];
  status: "heard" | "confirmed" | "disputed";
  quotes: ProcessQuote[];
  unknown?: string[];
}
export interface ProcessNote {
  id: string;
  text: string;
  at: string;
  handling?: string;
  status: string;
  quotes: ProcessQuote[];
}
export interface InterviewedProcess {
  id: string;
  name: string;
  status: "planned" | "active" | "done";
  quote: string;
  details: Record<string, { value: string; quote: string; turn: number; status: string }>;
  start: string | null;
  steps: ProcessStep[];
  exceptions: ProcessNote[];
  controls: ProcessNote[];
}
export interface ProcessOpenItem {
  id: string;
  kind: "conflict" | "unclear";
  status: "open" | "raised" | "resolved";
  item: string;
  field: string;
  earlier?: string;
  earlier_quote?: string;
  now?: string;
  text?: string;
  quote?: string;
  turn: number;
  resolution?: string;
}
/** What the participant has said so far, as Tibi's note-taker has captured it (opsatlas.process-model.v1). */
export interface ProcessModel {
  schema: string;
  space: { id: string; name: string };
  participant: Record<string, { value: string; quote: string; turn: number }>;
  processes: InterviewedProcess[];
  open: ProcessOpenItem[];
  focus: string | null;
  turns: number;
}
export interface ProcessInterviewSummary {
  id: string;
  status: string;
  updated_at: string;
  created_at: string;
  space_name: string;
  participant: string;
  role: string;
  processes: { id: string; name: string; steps: number }[];
  open: number;
  pending: number;
  turns: number;
}
export interface ProcessInterviewSession {
  id: string;
  status: string;
  revision: number;
  evidence: { process_interview?: { space: string; space_name: string } };
  process_model?: ProcessModel;
  process_pending?: { turn: number; answer: string; question: string }[];
  social_transcript?: { role: string; content: string }[];
}
export const listProcessInterviews = (space: string) =>
  tibiServiceGet<{ interviews: ProcessInterviewSummary[] }>(`/api/process-interviews?space=${encodeURIComponent(space)}`);
/** Delete an interview for good: its notes, map, timings and conversation-log turns (PI F15). Saved processes stay. */
export const deleteProcessInterview = (id: string) =>
  tibiServiceDelete<{ deleted: string }>(`/api/process-interviews/${encodeURIComponent(id)}`);
export const getProcessInterview = (id: string) => tibiServiceGet<ProcessInterviewSession>(`/api/interviews/${encodeURIComponent(id)}`);
/** The live map of an interview's process, drawn by the process diagram service in the interview's space. */
export const renderInterviewMap = (space: string, model: ProcessModel, process?: string | null) =>
  apiRequest<{ status: "available" | "unavailable"; process_name: string; chart?: ProcessDiagramChart; message?: string }>(
    "POST",
    "/api/process/interview-map",
    { process_model: model, process: process ?? null },
    space,
  );
/** Save one interviewed process to its organisation's space: a document waiting for approval in Governance Review. */
export const saveProcessCapture = (space: string, model: ProcessModel, process: string, interview: string, organisation: string) =>
  apiRequest<{ source_id: string; title: string; approval_status: string }>(
    "POST",
    "/api/process/captures",
    { process_model: model, process, interview, organisation },
    space,
  );
