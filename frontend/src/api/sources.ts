// Knowledge sources: upload, ingest, approval, listing and deletion.
// One module of the control panel's API client; pages import it through ./index.ts, as "./api".

import { authHeaders, guard } from "./http";

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

export async function listSources(space?: string | null): Promise<SourceRecord[]> {
  const res = await guard(await fetch("/api/sources", { headers: authHeaders(space) }));
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
