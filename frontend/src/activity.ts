// The page's side of the activity log (OBS S3): pages opened, buttons pressed, errors the page met, and Tibi's
// microphone and socket events, sent to OpsAtlas in small batches. Never what is typed into a field.
import { authHeaders, isAuthenticated } from "./api";

type ActivityEvent = { kind: string; name: string } & Record<string, unknown>;

const queue: ActivityEvent[] = [];
let timer: number | null = null;

export function currentView(): string {
  return window.location.hash.slice(1).split(":")[0] || "dashboard";
}

/** One event: its kind (page, action, error, tibi...), a short name and any detail worth keeping. */
export function record(kind: string, name: string, detail: Record<string, unknown> = {}) {
  queue.push({ kind, name: name.slice(0, 120), view: currentView(), page_time: new Date().toISOString(), ...detail });
  if (queue.length > 300) queue.splice(0, queue.length - 300);
  if (timer === null) timer = window.setTimeout(() => void flush(), 2000);
}

async function flush(keepalive = false) {
  timer = null;
  if (!queue.length || !isAuthenticated()) return;
  const batch = queue.splice(0, 100);
  try {
    await fetch("/api/activity", {
      method: "POST",
      keepalive,
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ events: batch }),
    });
  } catch {
    // The activity log is for diagnosis; the page never fails because of it.
  }
  if (queue.length && timer === null) timer = window.setTimeout(() => void flush(), 2000);
}

function label(element: Element): string {
  const text = element.getAttribute("aria-label") || element.getAttribute("title") || element.textContent || "";
  return text.trim().replace(/\s+/g, " ").slice(0, 80) || element.tagName.toLowerCase();
}

let started = false;

export function startActivityCapture() {
  if (started) return;
  started = true;
  document.addEventListener(
    "click",
    (event) => {
      const element = (event.target as Element | null)?.closest?.("button, a, [role=button], summary, select, input[type=checkbox]");
      if (element) record("action", label(element), { element: element.tagName.toLowerCase() });
    },
    { capture: true },
  );
  window.addEventListener("error", (event) => record("error", event.message || "Page error", { file: event.filename, line: event.lineno }));
  window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason as { message?: string } | undefined;
    record("error", String(reason?.message ?? event.reason ?? "Unhandled rejection"));
  });
  window.addEventListener("hashchange", () => record("page", currentView()));
  document.addEventListener("visibilitychange", () => {
    record("page", document.visibilityState === "hidden" ? "page hidden" : "page shown");
    if (document.visibilityState === "hidden") void flush(true);
  });
  record("page", currentView(), { event: "control panel opened" });
}
