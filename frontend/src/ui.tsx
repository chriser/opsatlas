// Shared pieces for every page (AUDIT F13): data loading, the empty state, a status pill and two formatters. The
// Identity & access pages introduced them; their drawers, dialogs and fields stay in iam/ui.tsx, with their styles.
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return (parts.length > 1 ? parts[0][0] + parts[parts.length - 1][0] : (parts[0] ?? "?").slice(0, 2)).toUpperCase();
}

export function formatWhen(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const minutes = Math.round((Date.now() - date.getTime()) / 60_000);
  if (Math.abs(minutes) < 1) return "just now";
  if (minutes > 0 && minutes < 60) return `${minutes} min ago`;
  if (minutes < 0 && minutes > -60) return `in ${-minutes} min`;
  return date.toLocaleString(undefined, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

export type Tone = "good" | "warn" | "danger" | "blue" | "purple" | "pink" | "neutral";

export function Pill({ tone = "neutral", children, title }: { tone?: Tone; children: ReactNode; title?: string }) {
  return (
    <span className={`status-pill${tone === "neutral" ? "" : ` status-pill--${tone}`}`} title={title}>
      {children}
    </span>
  );
}

export function EmptyCard({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="empty-card">
      <b>{title}</b>
      {hint ? <span>{hint}</span> : null}
    </div>
  );
}

/** What a page says when a load fails: "Could not load the source register: <the reason>." */
export function couldNotLoad(what: string, error: string): string {
  return `Could not load ${what}: ${error.replace(/[\s.]+$/, "")}.`;
}

export interface Loaded<T> {
  /** The last answer; null until the first one arrives. A failed reload keeps the previous answer. */
  data: T | null;
  /** Why the last load failed, in the server's own words when it gave any (a refused permission says so). */
  error: string | null;
  loading: boolean;
  /** Loads again; resolves when the answer is in. */
  reload: () => Promise<void>;
}

/**
 * Loads what a page shows, again whenever `deps` change. Only the latest request's answer is kept, so a slow answer
 * to an earlier request (a session clicked before another, a reload) never replaces a newer one, and nothing is set
 * once the page has gone.
 */
export function useLoad<T>(load: () => Promise<T>, deps: unknown[] = []): Loaded<T> {
  const [state, setState] = useState<{ data: T | null; error: string | null; loading: boolean }>({
    data: null,
    error: null,
    loading: true,
  });
  const loader = useRef(load);
  loader.current = load;
  const latest = useRef(0);
  const mounted = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const reload = useCallback(async () => {
    const request = ++latest.current;
    const current = () => mounted.current && request === latest.current;
    setState((s) => ({ ...s, loading: true }));
    try {
      const data = await loader.current();
      if (current()) setState({ data, error: null, loading: false });
    } catch (err) {
      const error = err instanceof Error ? err.message : "Could not load";
      if (current()) setState((s) => ({ ...s, error, loading: false }));
    }
  }, []);
  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { ...state, reload };
}
