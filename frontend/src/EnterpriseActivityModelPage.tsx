import { MouseEvent, useEffect, useMemo, useRef, useState } from "react";
import { getEamModel, getEamSvg, type EamEntityRollup, type EamModel } from "./api";

type EamViewKey = "activity" | "accountability" | "risk" | "relationship" | "system-landscape";
type RegistryKey = "roles" | "systems" | "controls";

const EAM_VIEWS: { key: EamViewKey; label: string; title: string; description: string }[] = [
  {
    key: "activity",
    label: "Activity",
    title: "Activity-view canvas",
    description: "Domains run vertically, value-chain stages run horizontally, and shared evidence links connect related activity nodes.",
  },
  {
    key: "accountability",
    label: "Accountability",
    title: "Accountability swimlanes",
    description: "Role and owner lanes show which process nodes carry accountability evidence and where ownership is missing or fragmented.",
  },
  {
    key: "risk",
    label: "Risk Heat",
    title: "Risk and coverage heat view",
    description: "Heat cells combine missing coverage, gap, overlap and clash signals across the EAM domain and value-chain matrix.",
  },
  {
    key: "relationship",
    label: "Relationship",
    title: "Relationship graph",
    description: "Shows shared roles, systems and controls so dependency concentration and cross-process coupling are visible.",
  },
  {
    key: "system-landscape",
    label: "System Landscape",
    title: "Digital System Landscape",
    description: "Maps selected process flow across vertical system layers and animates sequenced data movement through participating systems.",
  },
];

const REGISTRY_TABS: { key: RegistryKey; label: string }[] = [
  { key: "roles", label: "Roles" },
  { key: "systems", label: "Systems" },
  { key: "controls", label: "Controls" },
];

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "not yet generated";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function RegistryRow({ entity }: { entity: EamEntityRollup }) {
  return (
    <div className="eam-registry-row">
      <div>
        <b>{entity.name}</b>
        <span>{entity.process_count} linked processes</span>
      </div>
      <div className="eam-registry-counts">
        <span>R{entity.linked_entity_counts.roles ?? 0}</span>
        <span>S{entity.linked_entity_counts.systems ?? 0}</span>
        <span>C{entity.linked_entity_counts.controls ?? 0}</span>
      </div>
    </div>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="empty-card">
      <b>{title}</b>
      <span>{body}</span>
    </div>
  );
}

export function EnterpriseActivityModelPage() {
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const [model, setModel] = useState<EamModel | null>(null);
  const [svg, setSvg] = useState<string>("");
  const [view, setView] = useState<EamViewKey>("activity");
  const [svgBusy, setSvgBusy] = useState(false);
  const [svgError, setSvgError] = useState<string | null>(null);
  const [viewport, setViewport] = useState({ zoom: 1, x: 0, y: 0 });
  const [registryView, setRegistryView] = useState<RegistryKey>("roles");
  const [expandedNodeIds, setExpandedNodeIds] = useState<string[]>([]);
  const [selectedActivityNodeId, setSelectedActivityNodeId] = useState("");
  const [selectedLandscapeNodeId, setSelectedLandscapeNodeId] = useState("");
  const [showActivityConnections, setShowActivityConnections] = useState(false);
  const [showLandscapeConnections, setShowLandscapeConnections] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const expandedKey = expandedNodeIds.join(",");

  useEffect(() => {
    let active = true;
    getEamModel()
      .then((nextModel) => {
        if (!active) return;
        setModel(nextModel);
        setExpandedNodeIds(nextModel.nodes.map((node) => node.id));
        setSelectedActivityNodeId("");
        setSelectedLandscapeNodeId("");
        setError(null);
      })
      .catch(() => {
        if (!active) return;
        setModel(null);
        setSvg("");
        setError("Could not load the Enterprise Activity Model.");
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    setSvgBusy(true);
    getEamSvg(
      view,
      view === "activity" ? expandedNodeIds : [],
      view === "activity" ? selectedActivityNodeId : view === "system-landscape" ? selectedLandscapeNodeId : "",
      view === "activity" ? showActivityConnections : view === "system-landscape" ? showLandscapeConnections : false,
    )
      .then((nextSvg) => {
        if (!active) return;
        setSvg(nextSvg);
        setSvgError(null);
      })
      .catch(() => {
        if (!active) return;
        setSvg("");
        setSvgError("Could not load this EAM canvas view.");
      })
      .finally(() => {
        if (active) setSvgBusy(false);
      });
    return () => {
      active = false;
    };
  }, [view, expandedKey, selectedActivityNodeId, selectedLandscapeNodeId, showActivityConnections, showLandscapeConnections]);

  useEffect(() => {
    if (view === "system-landscape") {
      setViewport({ zoom: 1, x: 0, y: 0 });
    }
  }, [view]);

  const activeView = EAM_VIEWS.find((item) => item.key === view) ?? EAM_VIEWS[0];
  const registryRows = model?.entity_rollups[registryView] ?? [];
  const activityNodeIds = useMemo(() => model?.nodes.map((node) => node.id) ?? [], [model]);
  const selectedLandscapeNode = useMemo(
    () => model?.nodes.find((node) => node.id === selectedLandscapeNodeId) ?? null,
    [model, selectedLandscapeNodeId],
  );
  const selectedActivityNode = useMemo(
    () => model?.nodes.find((node) => node.id === selectedActivityNodeId) ?? null,
    [model, selectedActivityNodeId],
  );
  const allActivityCardsExpanded = activityNodeIds.length > 0
    && activityNodeIds.every((nodeId) => expandedNodeIds.includes(nodeId));

  function zoomCanvas(delta: number) {
    setViewport((current) => ({ ...current, zoom: Math.max(0.55, Math.min(1.75, Number((current.zoom + delta).toFixed(2)))) }));
  }

  function panCanvas(dx: number, dy: number) {
    setViewport((current) => ({ ...current, x: current.x + dx, y: current.y + dy }));
  }

  function resetCanvas() {
    setViewport({ zoom: 1, x: 0, y: 0 });
  }

  function toggleAllCards() {
    setExpandedNodeIds(allActivityCardsExpanded ? [] : activityNodeIds);
  }

  function toggleConnections() {
    if (view === "activity") {
      setShowActivityConnections((current) => !current);
      return;
    }
    if (view === "system-landscape") {
      setShowLandscapeConnections((current) => !current);
    }
  }

  function onCanvasClick(event: MouseEvent<HTMLDivElement>) {
    if (view === "system-landscape") {
      const target = event.target instanceof Element ? event.target.closest("[data-landscape-process-id]") : null;
      const nodeId = target?.getAttribute("data-landscape-process-id") ?? "";
      if (nodeId) setSelectedLandscapeNodeId(nodeId);
      return;
    }
    if (view !== "activity") return;
    const target = event.target instanceof Element ? event.target.closest("[data-node-id]") : null;
    if (!target) return;
    const nodeId = target.getAttribute("data-node-id");
    if (nodeId) {
      setSelectedActivityNodeId((current) => (current === nodeId ? "" : nodeId));
    }
  }

  if (error) {
    return (
      <div className="view-stack">
        <div className="page-intro">
          <h1>Enterprise Activity Model</h1>
          <p>A governed activity map generated from ontology objects, source evidence and taxonomy rules.</p>
        </div>
        <EmptyState title="EAM unavailable" body={error} />
      </div>
    );
  }

  if (!model) {
    return (
      <div className="view-stack">
        <div className="page-intro">
          <h1>Enterprise Activity Model</h1>
          <p>A governed activity map generated from ontology objects, source evidence and taxonomy rules.</p>
        </div>
        <EmptyState title="Building model" body="Projecting approved ontology records across domains, value-chain stages and shared evidence links." />
      </div>
    );
  }

  return (
    <div className="view-stack">
      <div className="page-intro eam-hero">
        <div>
          <p className="result-cite">Enterprise architecture memory</p>
          <h1>Enterprise Activity Model</h1>
          <p>
            Derived from {model.source_count} approved sources, projected through {model.taxonomy_version}.
            Last updated {formatDate(model.generated_at)}.
          </p>
        </div>
      </div>

      <div className="panel eam-canvas-panel">
        <div className="panel-heading">
          <div>
            <h2>{activeView.title}</h2>
            <p className="muted-text">{activeView.description}</p>
          </div>
          <span className="status-pill">{model.nodes.length} nodes</span>
        </div>
        <div className="eam-canvas-workbench">
          <div className="eam-canvas-main">
            <div className="eam-canvas-toolbar">
              <span className="segmented-control" role="group" aria-label="EAM canvas view">
                {EAM_VIEWS.map((item) => (
                  <button
                    type="button"
                    className={view === item.key ? "is-active" : ""}
                    key={item.key}
                    onClick={() => setView(item.key)}
                  >
                    {item.label}
                  </button>
                ))}
              </span>
              <div className="eam-canvas-controls" aria-label="Canvas navigation controls">
                {view === "activity" ? (
                  <button type="button" className="secondary-button" onClick={toggleAllCards}>
                    {allActivityCardsExpanded ? "Collapse all" : "Expand all"}
                  </button>
                ) : null}
                {view === "activity" || view === "system-landscape" ? (
                  <button type="button" className="secondary-button" onClick={toggleConnections}>
                    {(view === "activity" ? showActivityConnections : showLandscapeConnections) ? "Hide connections" : "Reveal all connections"}
                  </button>
                ) : null}
                {view === "activity" && selectedActivityNode ? (
                  <>
                    <span className="status-pill">Focus: {selectedActivityNode.name}</span>
                    <button type="button" className="secondary-button" onClick={() => setSelectedActivityNodeId("")}>
                      Clear focus
                    </button>
                  </>
                ) : null}
                {view === "system-landscape" && selectedLandscapeNode ? (
                  <>
                    <span className="status-pill">Flow: {selectedLandscapeNode.name}</span>
                    <button type="button" className="secondary-button" onClick={() => setSelectedLandscapeNodeId("")}>
                      Clear focus
                    </button>
                  </>
                ) : null}
                <button type="button" className="secondary-button" onClick={() => panCanvas(0, -48)} aria-label="Pan up">↑</button>
                <button type="button" className="secondary-button" onClick={() => panCanvas(-48, 0)} aria-label="Pan left">←</button>
                <button type="button" className="secondary-button" onClick={() => panCanvas(48, 0)} aria-label="Pan right">→</button>
                <button type="button" className="secondary-button" onClick={() => panCanvas(0, 48)} aria-label="Pan down">↓</button>
                <button type="button" className="secondary-button" onClick={() => zoomCanvas(-0.1)} aria-label="Zoom out">−</button>
                <span className="status-pill">{Math.round(viewport.zoom * 100)}%</span>
                <button type="button" className="secondary-button" onClick={() => zoomCanvas(0.1)} aria-label="Zoom in">+</button>
                <button type="button" className="secondary-button" onClick={resetCanvas}>Reset</button>
              </div>
            </div>
            {svgError ? <EmptyState title="Canvas unavailable" body={svgError} /> : null}
            <div className={`eam-canvas-scroll${svgBusy ? " is-loading" : ""}`} aria-busy={svgBusy} ref={canvasRef}>
              {svgBusy ? <span className="eam-canvas-loading">Loading {activeView.label.toLowerCase()} view</span> : null}
              <div
                className="eam-canvas-transform"
                style={{ transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})` }}
                onClick={onCanvasClick}
                dangerouslySetInnerHTML={{ __html: svg }}
              />
            </div>
            <p className="result-cite">
              The selected lens, zoom and pan position are shared across the EAM canvas; generated SVG highlights evidence coverage and structural signals, not final architecture assurance.
            </p>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Entity registry</h2>
            <p className="muted-text">Roles, systems and controls extracted from the ontology graph, with their linked process breadth.</p>
          </div>
          <span className="segmented-control" role="group" aria-label="Entity registry">
            {REGISTRY_TABS.map((tab) => (
              <button
                type="button"
                className={registryView === tab.key ? "is-active" : ""}
                key={tab.key}
                onClick={() => setRegistryView(tab.key)}
              >
                {tab.label}
              </button>
            ))}
          </span>
        </div>
        {registryRows.length ? (
          <div className="eam-registry-grid">
            {registryRows.map((entity) => <RegistryRow key={entity.id} entity={entity} />)}
          </div>
        ) : (
          <EmptyState title="No entities" body="No ontology entities are currently available for this registry type." />
        )}
      </div>

    </div>
  );
}
