// Tibi: records, spoken answers, contributions, the text channel and the Tibi service.
// One module of the control panel's API client; pages import it through ./index.ts, as "./api".

import { AuthError, authHeaders, guard } from "./http";

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

/** How busy this Mac is, for the machine indicator on the Talk with Tibi page: each app's share of the graphics
 *  processor over the last few seconds, memory, the processors and the models OpsAtlas has loaded. */
export interface MachineUser {
  group: "voice" | "models" | "other_models" | "screen" | "other";
  label: string;
  share: number;
  models?: string[];
  gb?: number | null;
}

export interface MachineReading {
  available: boolean;
  reason?: string;
  window?: number;
  gpu?: { busy: number; users: MachineUser[] };
  memory?: { total_gb: number; free_pct: number; pressure: "normal" | "warning" | "critical"; swap_used_gb: number | null; swapping: boolean } | null;
  cpu?: { load: number; cores: number; busy: number };
  models?: { name: string; role: string; gb: number }[] | null;
  level?: "ok" | "busy" | "strained";
  advice?: string;
}

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
export async function getMachine(): Promise<MachineReading | null> {
  try {
    return await tibiGet<MachineReading>("/machine");
  } catch (error) {
    if (error instanceof AuthError) throw error;
    return null;
  }
}

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
