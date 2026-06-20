import { useEffect, useState } from "react";
import { isAuthenticated, logout } from "./api";
import { KnowledgeSourcesPage } from "./KnowledgeSourcesPage";
import { LoginScreen } from "./LoginScreen";
import "./App.css";

type ViewKey = "dashboard" | "sources" | "rag" | "governance" | "settings";

interface NavItem {
  key: ViewKey;
  label: string;
  summary: string;
  icon: string;
}

const NAV_ITEMS: NavItem[] = [
  { key: "dashboard", label: "Dashboard", summary: "Platform overview & knowledge health", icon: "D" },
  { key: "sources", label: "Knowledge Sources", summary: "Upload & manage source documents", icon: "K" },
  { key: "rag", label: "RAG Setup", summary: "Retrieval, indexing & embeddings", icon: "R" },
  { key: "governance", label: "Governance", summary: "Duplicates, conflicts & regulation checks", icon: "G" },
  { key: "settings", label: "Settings", summary: "Models, providers & diagnostics", icon: "S" },
];

const VIEW_TITLE: Record<ViewKey, string> = {
  dashboard: "Dashboard",
  sources: "Knowledge Sources",
  rag: "RAG Setup",
  governance: "Governance",
  settings: "Settings",
};

type Health = "checking" | "online" | "offline";

function useBackendHealth(): Health {
  const [health, setHealth] = useState<Health>("checking");
  useEffect(() => {
    let active = true;
    fetch("/api/health")
      .then((r) => {
        if (active) setHealth(r.ok ? "online" : "offline");
      })
      .catch(() => {
        if (active) setHealth("offline");
      });
    return () => {
      active = false;
    };
  }, []);
  return health;
}

function HealthPill({ health }: { health: Health }) {
  const label = health === "online" ? "Backend online" : health === "offline" ? "Backend offline" : "Checking backend";
  const cls = health === "online" ? "status-pill status-pill--good" : health === "offline" ? "status-pill status-pill--warn" : "status-pill";
  return <span className={cls}>{label}</span>;
}

function Sidebar({ view, onSelect }: { view: ViewKey; onSelect: (v: ViewKey) => void }) {
  return (
    <aside className="sidebar">
      <div className="brand-block">
        <p>
          Knowledge<span>.</span>
        </p>
      </div>
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`sidebar-link${item.key === view ? " sidebar-link--active" : ""}`}
            onClick={() => onSelect(item.key)}
          >
            <span className="nav-icon">{item.icon}</span>
            <span className="nav-text">
              <span className="nav-label">{item.label}</span>
              <span className="nav-summary">{item.summary}</span>
            </span>
            {item.key === view ? (
              <span className="nav-active-dot">
                <span />
              </span>
            ) : null}
          </button>
        ))}
      </nav>
      <div className="sidebar-footer">
        <span>Knowledge Platform</span>
        <b>Control Panel</b>
      </div>
    </aside>
  );
}

function DashboardView({ onSelect }: { onSelect: (v: ViewKey) => void }) {
  const quick: { key: ViewKey; icon: string; title: string; sub: string; primary?: boolean }[] = [
    { key: "sources", icon: "+", title: "Upload a document", sub: "Add anonymised source material", primary: true },
    { key: "governance", icon: "!", title: "Review conflicts", sub: "Duplicates & regulation flags" },
    { key: "rag", icon: "R", title: "Open RAG setup", sub: "Indexing & retrieval config" },
  ];
  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Welcome back</h1>
        <p>Manage the knowledge base lifecycle: ingest, govern and make source material queryable.</p>
      </div>
      <div className="dashboard-grid">
        <div className="column-stack">
          <div className="panel">
            <div className="panel-heading">
              <div>
                <h2>Quick actions</h2>
                <p className="muted-text">Jump into the most common tasks.</p>
              </div>
            </div>
            <div className="quick-list">
              {quick.map((q) => (
                <button
                  key={q.title}
                  type="button"
                  className={`quick-card${q.primary ? " quick-card--primary" : ""}`}
                  onClick={() => onSelect(q.key)}
                >
                  <span className="quick-icon">{q.icon}</span>
                  <span>
                    <b>{q.title}</b>
                    <small>{q.sub}</small>
                  </span>
                  <span className="quick-chevron">›</span>
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="column-stack">
          <div className="panel">
            <div className="panel-heading">
              <div>
                <h2>Knowledge health</h2>
                <p className="muted-text">A snapshot of the source register and pipeline.</p>
              </div>
              <span className="status-pill">No data yet</span>
            </div>
            <div className="empty-card">
              <b>No sources registered yet</b>
              <span>Upload your first anonymised document to start building the knowledge base.</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function PlaceholderView({ view }: { view: ViewKey }) {
  const item = NAV_ITEMS.find((n) => n.key === view)!;
  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>{item.label}</h1>
        <p>{item.summary}</p>
      </div>
      <div className="panel">
        <div className="empty-card">
          <b>Coming soon</b>
          <span>This area is part of a later sprint. The shell and design system are in place.</span>
        </div>
      </div>
    </div>
  );
}

export function App() {
  const [view, setView] = useState<ViewKey>("dashboard");
  const [authed, setAuthed] = useState(isAuthenticated());
  const health = useBackendHealth();

  async function onLogout() {
    await logout();
    setAuthed(false);
  }

  if (!authed) {
    return <LoginScreen onSuccess={() => setAuthed(true)} />;
  }

  return (
    <div className="console-shell">
      <Sidebar view={view} onSelect={setView} />
      <main className="content-shell">
        <div className="topbar">
          <b>{VIEW_TITLE[view]}</b>
          <div className="topbar-actions">
            <HealthPill health={health} />
          </div>
          <button type="button" className="secondary-button" onClick={onLogout}>
            Sign out
          </button>
        </div>
        {view === "dashboard" ? (
          <DashboardView onSelect={setView} />
        ) : view === "sources" ? (
          <KnowledgeSourcesPage />
        ) : (
          <PlaceholderView view={view} />
        )}
      </main>
    </div>
  );
}
