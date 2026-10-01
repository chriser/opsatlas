// External sources and the regulatory review.
// One module of the control panel's API client; pages import it through ./index.ts, as "./api".

import { authHeaders, guard } from "./http";

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
