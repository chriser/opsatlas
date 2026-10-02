// The session, the active space, sign-in and the request helpers every call uses.
// One module of the control panel's API client; pages import it through ./index.ts, as "./api".

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
    /** When the person's picture last changed; null without one (IAM F10). */
    picture: string | null;
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

/** The address of the person's own picture, null without one. It changes with the picture, so a new one is fetched. */
export function pictureUrl(user: Me["user"] | null | undefined): string | null {
  if (!user?.picture) return null;
  return `/api/auth/me/picture?u=${encodeURIComponent(user.id)}&v=${encodeURIComponent(user.picture)}`;
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

export async function guard(res: Response): Promise<Response> {
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
