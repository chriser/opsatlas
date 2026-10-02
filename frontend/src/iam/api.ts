// Identity and access (IAM F7): the API client of the IAM section and the person's own account.
import { apiRequest, apiUpload, fetchMe, type Me } from "../api";
import type { Permission } from "./permissions";

export interface RoleSummary {
  binding_id: string;
  role_id: string;
  role_name: string;
  scope_type: string;
  scope_id: string;
  space_name: string | null;
  ends_at: string | null;
}

export interface Person {
  id: string;
  login: string;
  email: string;
  display_name: string;
  state: "invited" | "active" | "suspended" | "deactivated";
  created_at: string;
  activated_at: string | null;
  last_sign_in_at: string | null;
  note: string;
  roles: RoleSummary[];
  sessions: number;
  invitation: { expires_at: string; issued_at: string } | null;
}

export interface Role {
  id: string;
  name: string;
  boundary: "platform" | "space";
  description: string;
  permissions: Permission[];
  excluded: string;
  grantable: string[];
  protected: boolean;
  system: boolean;
  version: number;
  builtin: boolean;
}

export interface Binding {
  id: string;
  subject_type: "user" | "group";
  subject_id: string;
  role_id: string;
  role_name: string;
  role_boundary: string;
  scope_type: string;
  scope_id: string;
  space_id: string | null;
  space_name: string | null;
  starts_at: string;
  ends_at: string | null;
  issuer_id: string | null;
  reason: string;
  system: boolean;
  subject: { display_name: string; login: string; state: string } | null;
}

export interface Group {
  id: string;
  name: string;
  boundary: string;
  space_id: string | null;
  description: string;
  members: { user_id: string; display_name: string; login: string; state: string; added_at: string }[];
  bindings: Binding[];
}

export interface Deny {
  id: string;
  subject_type: string;
  subject_id: string;
  permission: string;
  scope_type: string;
  scope_id: string;
  starts_at: string;
  ends_at: string | null;
  reason: string;
  subject: { display_name: string; login: string } | null;
}

export interface AccessRequest {
  id: string;
  user_id: string;
  space_id: string | null;
  role_id: string;
  reason: string;
  status: string;
  requested_at: string;
  requested_days: number | null;
  decided_by: string | null;
  decided_at: string | null;
  decision_reason: string;
  display_name?: string;
  login?: string;
}

export interface Session {
  id: string;
  user_id: string;
  created_at: string;
  authenticated_at: string;
  last_seen_at: string;
  absolute_expires_at: string;
  idle_expires_at: string;
  privileged: boolean;
  device: string;
  address: string;
  current: boolean;
  display_name?: string;
  login?: string;
}

export interface AuditEvent {
  seq: number;
  id: string;
  at: string;
  actor_id: string | null;
  actor_name: string | null;
  actor_type: string;
  action: string;
  outcome: string;
  reason: string;
  target_type: string | null;
  target_id: string | null;
  target_label: string | null;
  space_id: string | null;
  before: unknown;
  after: unknown;
  detail: unknown;
  address: string | null;
}

export interface Explanation {
  allowed: boolean;
  code: string;
  reason: string;
  permission: string;
  space_id: string | null;
  membership_active: boolean | null;
  bindings: { binding_id: string; role_id: string; role_name: string; via_group: string | null; scope_type: string; scope_id: string;
    ends_at: string | null; grants_permission: boolean; applies_here: boolean }[];
  denies: { id: string; scope_type: string; scope_id: string; reason: string; ends_at: string | null }[];
}

export interface Invitation {
  user: Person;
  binding: Binding | null;
  token: string | null;
  link: string | null;
  expires_at: string | null;
}

export interface SpaceSetting {
  id: string;
  name: string;
  kind: string;
  status: string;
  solo_operator: boolean;
}

export const SETTING_LABELS: Record<string, string> = {
  "session.idle_minutes": "Idle timeout (minutes)",
  "session.absolute_hours": "Session lifetime (hours)",
  "session.privileged_idle_minutes": "Administrator idle timeout (minutes)",
  "session.privileged_absolute_hours": "Administrator session lifetime (hours)",
  "session.max_active": "Sessions per person (soft limit)",
  "reauth.fresh_minutes": "Fresh password window (minutes)",
  "throttle.account_attempts": "Failed attempts before a delay (per account)",
  "throttle.account_window_minutes": "Counting window (minutes, per account)",
  "throttle.network_attempts": "Failed attempts before a delay (per address)",
  "throttle.network_window_minutes": "Counting window (minutes, per address)",
  "throttle.cap_minutes": "Longest delay (minutes)",
  "throttle.recovery_per_hour": "Recovery links per account per hour",
  "invitation.hours": "Invitation link lifetime (hours)",
  "reset.minutes": "Reset link lifetime (minutes)",
  "ws_ticket.seconds": "Voice socket ticket lifetime (seconds)",
  "guest.days": "Guest access (days)",
  "elevated.days": "Temporary elevated access (days)",
  "review.admin_days": "Administrator access review (days)",
  "review.member_days": "Membership access review (days)",
};

const get = <T,>(path: string) => apiRequest<T>("GET", path);
const post = <T,>(path: string, body?: unknown) => apiRequest<T>("POST", path, body ?? {});
const patch = <T,>(path: string, body: unknown) => apiRequest<T>("PATCH", path, body);
const del = <T,>(path: string) => apiRequest<T>("DELETE", path);

// People
export const listPeople = () => get<{ users: Person[] }>("/api/iam/users").then((d) => d.users);
export const invitePerson = (body: { email: string; display_name?: string; role_id?: string | null; space_id?: string | null;
  days?: number | null; message?: string }) => post<Invitation>("/api/iam/users/invite", body);
export const updatePerson = (id: string, body: { display_name?: string; email?: string; note?: string }) => patch<Person>(`/api/iam/users/${id}`, body);
export const suspendPerson = (id: string, reason: string) => post<Person>(`/api/iam/users/${id}/suspend`, { reason });
export const reactivatePerson = (id: string, reason: string) => post<Person>(`/api/iam/users/${id}/reactivate`, { reason });
export const deactivatePerson = (id: string, reason: string) => post<Person>(`/api/iam/users/${id}/deactivate`, { reason });
export const recoveryLink = (id: string, reason: string) => post<{ link: string; expires_at: string }>(`/api/iam/users/${id}/recovery`, { reason });
export const resendInvitation = (id: string) => post<{ link: string; expires_at: string }>(`/api/iam/users/${id}/invitation/resend`);
export const personSessions = (id: string) => get<{ sessions: Session[] }>(`/api/iam/users/${id}/sessions`).then((d) => d.sessions);
export const signOutPerson = (id: string) => post<{ revoked: number }>(`/api/iam/users/${id}/logout-all`);
export const capabilitiesOf = (id: string) => get<{ platform: string[]; spaces: Record<string, string[]> }>(`/api/iam/capabilities/${id}`);

// Roles and grants
export const listRoles = () => get<{ roles: Role[]; space_role_ids: string[]; platform_role_ids: string[] }>("/api/iam/roles");
export const createRole = (body: { name: string; boundary: string; permissions: string[]; description?: string; based_on?: string | null }) =>
  post<Role>("/api/iam/roles", body);
export const updateRole = (id: string, body: { name?: string; description?: string; permissions?: string[] }) => patch<Role>(`/api/iam/roles/${id}`, body);
export const deleteRole = (id: string) => del<{ ok: boolean }>(`/api/iam/roles/${id}`);
export const grantableRoles = (spaceId?: string | null) =>
  get<{ roles: Role[] }>(`/api/iam/grantable${spaceId ? `?space_id=${encodeURIComponent(spaceId)}` : ""}`).then((d) => d.roles);
export const listBindings = (filter: { user_id?: string; space_id?: string; role_id?: string; include_system?: boolean } = {}) => {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(filter)) if (v !== undefined && v !== "" && v !== false) params.set(k, String(v));
  return get<{ bindings: Binding[] }>(`/api/iam/bindings${params.size ? `?${params}` : ""}`).then((d) => d.bindings);
};
export const grant = (body: { subject_id: string; subject_type?: string; role_id: string; scope_type: string; scope_id?: string;
  days?: number | null; reason?: string }) => post<Binding>("/api/iam/bindings", body);
export const revoke = (id: string, reason: string) => del<{ ok: boolean }>(`/api/iam/bindings/${id}?reason=${encodeURIComponent(reason)}`);
/** A document or folder restricted to named people or groups (REF S13). */
export interface Restriction {
  resource_type: "document" | "folder";
  resource_id: string;
  restricted_to: string[];
  updated_at?: string;
  updated_by?: string | null;
}
export const spaceRestrictions = (spaceId: string) =>
  get<{ restrictions: Restriction[] }>(`/api/iam/spaces/${spaceId}/restrictions`).then((d) => d.restrictions);
export const setRestriction = (spaceId: string, type: "document" | "folder", id: string, audience: string[], reason = "") =>
  apiRequest<Restriction>("PUT", `/api/iam/spaces/${spaceId}/restrictions/${type}/${encodeURIComponent(id)}`, { audience, reason });
export const spaceMembers = (spaceId: string) => get<{ members: (Person & { user_id: string })[] }>(`/api/iam/spaces/${spaceId}/members`).then((d) => d.members);
export const removeMember = (spaceId: string, userId: string, reason: string) =>
  del<{ ok: boolean }>(`/api/iam/spaces/${spaceId}/members/${userId}?reason=${encodeURIComponent(reason)}`);
export const setSoloOperator = (spaceId: string, enabled: boolean, reason: string) =>
  post<SpaceSetting>(`/api/iam/spaces/${spaceId}/solo-operator`, { enabled, reason });

// Groups and denies
export const listGroups = (spaceId?: string | null) => get<{ groups: Group[] }>(`/api/iam/groups${spaceId ? `?space_id=${spaceId}` : ""}`).then((d) => d.groups);
export const createGroup = (body: { name: string; space_id?: string | null; description?: string }) => post<Group>("/api/iam/groups", body);
export const deleteGroup = (id: string) => del<{ ok: boolean }>(`/api/iam/groups/${id}`);
export const addGroupMember = (id: string, userId: string) => post<{ ok: boolean }>(`/api/iam/groups/${id}/members`, { user_id: userId });
export const removeGroupMember = (id: string, userId: string) => del<{ ok: boolean }>(`/api/iam/groups/${id}/members/${userId}`);
export const listDenies = () => get<{ denies: Deny[] }>("/api/iam/denies").then((d) => d.denies);
export const addDeny = (body: { subject_id: string; permission: string; scope_type: string; scope_id?: string; reason?: string; days?: number | null }) =>
  post<Deny>("/api/iam/denies", body);
export const liftDeny = (id: string, reason: string) => del<{ ok: boolean }>(`/api/iam/denies/${id}?reason=${encodeURIComponent(reason)}`);

// Requests and explanations
export const listRequests = (own = false) => get<{ requests: AccessRequest[] }>(`/api/iam/access-requests${own ? "?own=true" : ""}`).then((d) => d.requests);
export const requestAccess = (body: { role_id: string; space_id?: string | null; reason: string; days?: number | null }) =>
  post<AccessRequest>("/api/iam/access-requests", body);
export const decideRequest = (id: string, approve: boolean, reason: string, days?: number | null) =>
  post<AccessRequest>(`/api/iam/access-requests/${id}/decide`, { approve, reason, days: days ?? null });
export const cancelRequest = (id: string) => post<{ ok: boolean }>(`/api/iam/access-requests/${id}/cancel`);
export const explainAccess = (body: { user_id: string; permission: string; space_id?: string | null }) => post<Explanation>("/api/iam/access/explain", body);

// Sessions, audit, settings
export const listSessions = () => get<{ sessions: Session[] }>("/api/iam/sessions").then((d) => d.sessions);
export const revokeSession = (id: string, reason: string) => del<{ ok: boolean }>(`/api/iam/sessions/${id}?reason=${encodeURIComponent(reason)}`);
export const listAudit = (filter: { limit?: number; before?: number | null; action?: string; actor_id?: string; space_id?: string; outcome?: string } = {}) => {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(filter)) if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
  return get<{ events: AuditEvent[]; next: number | null }>(`/api/iam/audit${params.size ? `?${params}` : ""}`);
};
export const verifyAudit = () => get<{ intact: boolean; events: number }>("/api/iam/audit/verify");
export const securityOverview = () =>
  get<{ attacks: { key: string; count: number; blocked_until: string | null; window_started_at: string }[];
    recovery_events: { id: string; at: string; kind: string; reason: string; host_user: string }[]; policy_version: number; refusals: AuditEvent[] }>(
    "/api/iam/security/overview");
export const getSettings = () => get<{ settings: Record<string, number>; spaces: SpaceSetting[] }>("/api/iam/settings");
export const updateSettings = (changes: Record<string, number>) => patch<{ settings: Record<string, number> }>("/api/iam/settings", { changes });

// The person's own account
export const mySessions = () => get<{ sessions: Session[] }>("/api/auth/sessions").then((d) => d.sessions);
export const revokeMySession = (id: string) => del<{ ok: boolean }>(`/api/auth/sessions/${id}`);
export const signOutEverywhere = () => post<{ revoked: number }>("/api/auth/logout-all");
export const changePassword = (current: string, next: string) => post<{ ok: boolean }>("/api/auth/password/change", { current, new: next });
export const updateProfile = (display_name: string) => patch<Me>("/api/auth/me", { display_name }).then(() => fetchMe());
/** Keep the picture cropped on My account (IAM F10); the sidebar shows it once the account is read again. */
export function uploadPicture(picture: Blob): Promise<Me> {
  const form = new FormData();
  form.append("file", picture, "picture.jpg");
  return apiUpload<Me>("/api/auth/me/picture", form).then(() => fetchMe());
}
export const removePicture = () => del<Me>("/api/auth/me/picture").then(() => fetchMe());
export const reauthenticate = (password: string) => post<{ ok: boolean; fresh_minutes: number }>("/api/auth/reauthenticate", { password });
