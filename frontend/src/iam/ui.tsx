// Shared pieces of the Identity & access section (IAM F7): drawers, dialogs, fields, notices, the fresh-password
// prompt and the session watch. Styled by iam.css with the control panel's own tokens.
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { fetchMe, lastInteractionAt, ReauthRequired, type Me } from "../api";
import { reauthenticate } from "./api";
import "./iam.css";

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

export const STATE_TONE: Record<string, Tone> = { active: "good", invited: "blue", suspended: "warn", deactivated: "danger" };

export function Notice({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return <div className={`iam-notice iam-notice--${tone}`}>{children}</div>;
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="iam-field">
      <span className="iam-field-label">{label}</span>
      {children}
      {hint ? <span className="iam-field-hint">{hint}</span> : null}
    </label>
  );
}

export function Drawer({ title, subtitle, open, onClose, children, footer, wide }: {
  title: string;
  subtitle?: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="iam-drawer-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside className={`iam-drawer${wide ? " iam-drawer--wide" : ""}`} role="dialog" aria-modal="true" aria-label={title}>
        <header className="iam-drawer-head">
          <div>
            <h2>{title}</h2>
            {subtitle ? <p className="muted-text">{subtitle}</p> : null}
          </div>
          <button type="button" className="text-button" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>
        <div className="iam-drawer-body">{children}</div>
        {footer ? <footer className="iam-drawer-foot">{footer}</footer> : null}
      </aside>
    </div>
  );
}

export function Dialog({ title, open, onClose, children, footer }: { title: string; open: boolean; onClose: () => void; children: ReactNode;
  footer?: ReactNode }) {
  if (!open) return null;
  return (
    <div className="iam-drawer-backdrop iam-drawer-backdrop--center" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="iam-dialog" role="dialog" aria-modal="true" aria-label={title}>
        <h2>{title}</h2>
        <div className="iam-dialog-body">{children}</div>
        {footer ? <div className="iam-dialog-foot">{footer}</div> : null}
      </div>
    </div>
  );
}

/** A yes-or-no with a reason, for changes that are recorded. */
export function ConfirmDialog({ title, body, confirmLabel, danger, open, onClose, onConfirm, reasonLabel = "Reason (recorded)" }: {
  title: string;
  body: ReactNode;
  confirmLabel: string;
  danger?: boolean;
  open: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => Promise<void>;
  reasonLabel?: string | null;
}) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (open) {
      setReason("");
      setError(null);
    }
  }, [open]);
  async function go() {
    setBusy(true);
    setError(null);
    try {
      await onConfirm(reason);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "That did not work.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      title={title}
      open={open}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="secondary-button" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button type="button" className={danger ? "reject-button" : "primary-button"} onClick={() => void go()} disabled={busy}>
            {busy ? "Working…" : confirmLabel}
          </button>
        </>
      }
    >
      <div className="iam-stack">
        <div>{body}</div>
        {reasonLabel ? (
          <Field label={reasonLabel}>
            <input className="iam-input" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={200} />
          </Field>
        ) : null}
        {error ? <Notice tone="danger">{error}</Notice> : null}
      </div>
    </Dialog>
  );
}

/** Runs an action; when the server asks for the password again, prompts for it and retries once. */
export function useReauth(): [ReactNode, <T>(action: () => Promise<T>) => Promise<T>] {
  const [pending, setPending] = useState<{ action: () => Promise<unknown>; resolve: (v: unknown) => void; reject: (e: unknown) => void } | null>(null);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = useCallback(async <T,>(action: () => Promise<T>): Promise<T> => {
    try {
      return await action();
    } catch (err) {
      if (!(err instanceof ReauthRequired)) throw err;
      return new Promise<T>((resolve, reject) => {
        setPassword("");
        setError(null);
        setPending({ action, resolve: resolve as (v: unknown) => void, reject });
      });
    }
  }, []);
  async function confirm() {
    if (!pending) return;
    setBusy(true);
    setError(null);
    try {
      await reauthenticate(password);
      const result = await pending.action();
      pending.resolve(result);
      setPending(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "That did not work.");
    } finally {
      setBusy(false);
    }
  }
  function cancel() {
    pending?.reject(new Error("Cancelled: the password was not entered."));
    setPending(null);
  }
  const element = (
    <Dialog
      title="Enter your password again"
      open={pending !== null}
      onClose={cancel}
      footer={
        <>
          <button type="button" className="secondary-button" onClick={cancel} disabled={busy}>
            Cancel
          </button>
          <button type="button" className="primary-button" onClick={() => void confirm()} disabled={busy || !password}>
            {busy ? "Checking…" : "Continue"}
          </button>
        </>
      }
    >
      <form
        className="iam-stack"
        onSubmit={(e) => {
          e.preventDefault();
          void confirm();
        }}
      >
        <p className="muted-text">This change is protected: confirm it is you before it goes ahead.</p>
        <Field label="Password">
          <input className="iam-input" type="password" autoComplete="current-password" autoFocus value={password}
            onChange={(e) => setPassword(e.target.value)} />
        </Field>
        {error ? <Notice tone="danger">{error}</Notice> : null}
      </form>
    </Dialog>
  );
  return [element, run];
}

/** A link shown once: invitation or recovery. It is not kept anywhere, so it is copied now or issued again. */
export function LinkOnce({ link, expiresAt, what }: { link: string; expiresAt: string | null; what: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }
  return (
    <div className="iam-link-once">
      <b>{what}: shown once.</b>
      <p className="muted-text">Hand it over yourself: it is not sent anywhere and not kept. {expiresAt ? `Valid until ${formatWhen(expiresAt)}.` : ""}</p>
      <code>{link}</code>
      <button type="button" className="secondary-button" onClick={() => void copy()}>
        {copied ? "Copied" : "Copy link"}
      </button>
    </div>
  );
}

export function Tabs<K extends string>({ tabs, active, onChange }: { tabs: { key: K; label: string }[]; active: K; onChange: (k: K) => void }) {
  return (
    <div className="segmented-control iam-tabs" role="tablist">
      {tabs.map((tab) => (
        <button key={tab.key} type="button" role="tab" aria-selected={tab.key === active} className={tab.key === active ? "is-active" : ""}
          onClick={() => onChange(tab.key)}>
          {tab.label}
        </button>
      ))}
    </div>
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

export function useLoad<T>(load: () => Promise<T>, deps: unknown[] = []): { data: T | null; error: string | null; loading: boolean; reload: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const loader = useRef(load);
  loader.current = load;
  useEffect(() => {
    let live = true;
    setLoading(true);
    loader
      .current()
      .then((value) => {
        if (live) {
          setData(value);
          setError(null);
        }
      })
      .catch((err) => live && setError(err instanceof Error ? err.message : "Could not load"))
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick, ...deps]);
  return { data, error, loading, reload: () => setTick((n) => n + 1) };
}

/** Warns before the session ends for want of interaction, and lets the person stay signed in deliberately. */
export function SessionWatch({ me, onExpired }: { me: Me; onExpired: () => void }) {
  const [remaining, setRemaining] = useState<number | null>(null);
  useEffect(() => {
    const timer = window.setInterval(() => {
      const idleEnd = Math.max(lastInteractionAt(), new Date(me.session.last_seen_at).getTime()) + me.session.idle_minutes * 60_000;
      const absoluteEnd = new Date(me.session.absolute_expires_at).getTime();
      const left = Math.min(idleEnd, absoluteEnd) - Date.now();
      if (left <= 0) {
        fetchMe().catch(onExpired);
        setRemaining(null);
      } else {
        setRemaining(left < 2 * 60_000 ? Math.ceil(left / 1000) : null);
      }
    }, 5_000);
    return () => window.clearInterval(timer);
  }, [me, onExpired]);
  if (remaining === null) return null;
  return (
    <div className="iam-session-banner" role="status">
      <span>Your session ends in {remaining} s without activity.</span>
      <button type="button" className="secondary-button" onClick={() => void fetchMe().catch(onExpired)}>
        Stay signed in
      </button>
    </div>
  );
}
