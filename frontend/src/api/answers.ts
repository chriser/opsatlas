// Written questions, search, answer traces and the Digital SME's avatar.
// One module of the control panel's API client; pages import it through ./index.ts, as "./api".

import { authHeaders, guard } from "./http";

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
