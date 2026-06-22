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
  refused: boolean;
  category: string | null;
  confidence: string;
  grounding: string;
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

export async function getScorecard(): Promise<Scorecard> {
  const res = await guard(await fetch("/api/analytics/scorecard", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load scorecard");
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
