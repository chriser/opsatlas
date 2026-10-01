// The workspace: health, services and knowledge spaces.
// One module of the control panel's API client; pages import it through ./index.ts, as "./api".

import { apiRequest } from "./http";

/** What the core reports about itself to a signed-in person: sources and the configured models. */
export const getHealthDetails = () => apiRequest<HealthResponse>("GET", "/api/health/details");

export interface HealthResponse {
  status: string;
  service: string;
  sources: number;
  models?: Record<string, string>;
}

/** Restart Tibi (you stay signed in), the process diagram service, or everything, OpsAtlas itself last (sign in again). */
export const restartServices = (which: "tibi" | "diagrams" | "all") =>
  apiRequest<{ restarting: string[]; sign_in_again: boolean }>("POST", "/api/services/restart", { which });
/** Start the process diagram service as one of the workspace's services (PI F1). */
export const startDiagramService = () => apiRequest<{ started: string }>("POST", "/api/services/start", { which: "diagrams" });

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
