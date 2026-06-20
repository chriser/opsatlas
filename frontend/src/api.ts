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
