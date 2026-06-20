// Control-panel API client. All calls go through the Vite dev proxy (/api -> backend).

export interface SourceRecord {
  id: string;
  filename: string;
  title: string;
  source_type: string;
  sensitivity: string;
  version: number;
  processing_state: string;
  approval_status: string;
  size_bytes: number;
  content_sha256: string;
  created_at: string;
}

export interface HealthResponse {
  status: string;
  service: string;
  sources: number;
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch("/api/health");
  if (!res.ok) throw new Error("health check failed");
  return res.json();
}

export async function listSources(): Promise<SourceRecord[]> {
  const res = await fetch("/api/sources");
  if (!res.ok) throw new Error("could not load sources");
  return res.json();
}

export async function uploadSource(file: File, title?: string): Promise<SourceRecord> {
  const form = new FormData();
  form.append("file", file);
  if (title) form.append("title", title);
  const res = await fetch("/api/sources/upload", { method: "POST", body: form });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "upload failed");
  }
  return res.json();
}

export async function deleteSource(id: string): Promise<void> {
  const res = await fetch(`/api/sources/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("delete failed");
}
