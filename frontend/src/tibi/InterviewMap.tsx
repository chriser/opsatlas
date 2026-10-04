// The live process map of a process interview (TIBI E5, PI F5): the working model, laid out by the process diagram
// service and drawn here, so each step shows how sure we are of it (heard, confirmed, to check) and can be clicked
// to comment on it to Tibi.
import { useEffect, useMemo, useRef, useState } from "react";
import {
  renderInterviewMap,
  type ProcessDiagramChart,
  type ProcessDiagramEdge,
  type ProcessDiagramNode,
  type ProcessModel,
} from "../api";
import { ProcessShape, wrapText } from "../processShapes";

const STATUS_WORD: Record<string, string> = { heard: "Heard", confirmed: "Confirmed", disputed: "To check", open: "Still being described" };

function Text({ node, dx, dy, width, size }: { node: ProcessDiagramNode; dx: number; dy: number; width: number; size: number }) {
  const lines = wrapText(node.label, Math.max(8, Math.floor(width / (size * 0.56))), 5);  // the service sizes the shape to fit
  const height = size + 5;
  const top = node.y + node.height / 2 + dy - ((lines.length - 1) * height) / 2 + size / 3;
  return (
    <>
      {lines.map((line, n) => (
        <text key={n} x={node.x + node.width / 2 + dx} y={top + n * height} textAnchor="middle" fontSize={size} className="imap-text">
          {line}
        </text>
      ))}
    </>
  );
}

const SMALL = new Set(["who", "system", "control", "risk", "annotation"]);

function Node({ node, changed, narrating, onStep }: {
  node: ProcessDiagramNode;
  changed: boolean;
  narrating: boolean;
  onStep?: (id: string, label: string) => void;
}) {
  const status = node.metadata?.status ?? "";
  // Steps, triggers and decisions from the interview, and where the flow carries on ("Still being described"); not the
  // events and joins the notation adds between them (those carry no status).
  const carriesOn = node.type === "end" && node.metadata?.continue === "true";
  const fromInterview =
    ["task", "automated", "interface"].includes(node.type) ||
    (node.type === "gateway" && node.metadata?.join !== "true") ||
    (node.type === "event" && Boolean(status)) ||
    carriesOn;
  const clickable = Boolean(onStep) && fromInterview;
  const common = {
    className: `imap-node imap-node--${node.type} imap-status--${status || "none"}${changed ? " imap-node--changed" : ""}${clickable ? " imap-node--clickable" : ""}${narrating ? " imap-node--narrating" : ""}`,
    ...(clickable
      ? {
          role: "button",
          tabIndex: 0,
          "aria-label": carriesOn
            ? "Still being described. Add what happens next"
            : `${node.label}${status ? `, ${STATUS_WORD[status] ?? status}` : ""}. Change this step, or comment on it to Tibi`,
          onClick: () => onStep?.(node.id, node.label),
          onKeyDown: (e: React.KeyboardEvent) => (e.key === "Enter" || e.key === " ") && onStep?.(node.id, node.label),
        }
      : {}),
  };
  const size = SMALL.has(node.type) ? 13 : 15;
  return (
    <g {...common}>
      <title>{`${node.label}${status ? ` · ${STATUS_WORD[status] ?? status}` : ""}`}</title>
      <ProcessShape node={node} text={(dx, dy, width) => <Text node={node} dx={dx} dy={dy} width={width} size={size} />} />
    </g>
  );
}

function Edge({ edge }: { edge: ProcessDiagramEdge }) {
  const d = edge.points.map((p, n) => `${n ? "L" : "M"} ${p.x} ${p.y}`).join(" ");
  const middle = edge.points[Math.floor(edge.points.length / 2)];
  const open = edge.label === "…";
  return (
    <g className={`imap-edge imap-edge--${edge.type}${open ? " imap-edge--open" : ""}`}>
      <path d={d} markerEnd={edge.type === "sequence" ? "url(#imap-arrow)" : undefined} />
      {edge.label && !open && middle ? (
        <text x={middle.x + 8} y={middle.y - 6} fontSize={12} className="imap-edge-label">
          {edge.label}
        </text>
      ) : null}
    </g>
  );
}

/** The live map. ``onStep`` makes steps clickable (to comment on them to Tibi); ``narrating`` lights up the steps a
 *  read-back is telling as Tibi speaks (PI F26). */
export function InterviewMap({
  space,
  model,
  onStep,
  narrating = [],
  title = "Process map",
}: {
  space: string;
  model: ProcessModel | null;
  onStep?: (stepId: string, label: string) => void;
  narrating?: string[];
  title?: string;
}) {
  const processes = model?.processes ?? [];
  const [chosen, setChosen] = useState<string | null>(null);
  const process = processes.find((p) => p.id === chosen) ?? processes.find((p) => p.id === model?.focus) ?? processes[0] ?? null;
  const [chart, setChart] = useState<ProcessDiagramChart | null>(null);
  const [state, setState] = useState<"idle" | "drawing" | "unavailable">("idle");
  const [message, setMessage] = useState("");
  const [changed, setChanged] = useState<Set<string>>(new Set());
  // Fit the column, or a readable size to scroll around (the layout is drawn for a full page).
  const [zoom, setZoom] = useState<number | null>(null);
  const frame = useRef<HTMLDivElement>(null);
  // Zoomed in, the flow (the middle column) is in view, not the systems at the left edge.
  useEffect(() => {
    const start = chart?.nodes.find((n) => n.type === "start");
    if (zoom === null || !start || !frame.current) return;
    frame.current.scrollLeft = Math.max(0, (start.x + start.width / 2) * zoom - frame.current.clientWidth / 2);
  }, [zoom, chart]);
  const previous = useRef<Map<string, string>>(new Map());

  // Redraw when this process, or what is open about it, changes; not on every snapshot.
  const drawn = useMemo(
    () => (process && model ? JSON.stringify([process, model.open.filter((o) => o.status !== "resolved").map((o) => o.item)]) : ""),
    [process, model],
  );
  useEffect(() => {
    if (!process || !model || !space) return;
    let live = true;
    setState("drawing");
    const timer = window.setTimeout(() => {
      renderInterviewMap(space, model, process.id)
        .then((result) => {
          if (!live) return;
          if (result.status === "available" && result.chart) {
            setChart(result.chart);
            setState("idle");
            setMessage("");
          } else {
            setState("unavailable");
            setMessage(result.message ?? "The process map could not be drawn.");
          }
        })
        .catch((error) => {
          if (!live) return;
          setState("unavailable");
          setMessage(error instanceof Error ? error.message : "The process map could not be drawn.");
        });
    }, 350);
    // What changed since the last drawing: highlighted for a moment.
    const now = new Map(process.steps.map((s) => [s.id, `${s.label}|${s.who}|${s.system}|${s.status}|${JSON.stringify(s.next)}`]));
    const fresh = new Set([...now].filter(([id, value]) => previous.current.size > 0 && previous.current.get(id) !== value).map(([id]) => id));
    previous.current = now;
    setChanged(fresh);
    const clear = window.setTimeout(() => setChanged(new Set()), 2600);
    return () => {
      live = false;
      window.clearTimeout(timer);
      window.clearTimeout(clear);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [drawn, space]);

  // The steps a read-back is telling, with their role and system cards and, for a way, its condition: lit together.
  const lit = useMemo(() => {
    const ids = new Set(narrating);
    if (!ids.size || !chart) return ids;
    for (const node of chart.nodes) {
      const owner = /^(?:sys|who)_(.+?)(?:_\d+)?$/.exec(node.id)?.[1] ?? /^(.+)__no_system$/.exec(node.id)?.[1];
      const way = node.type === "event" ? /__(.+)$/.exec(node.id)?.[1] : undefined;
      if ((owner && ids.has(owner)) || (way && ids.has(way))) ids.add(node.id);
    }
    return ids;
  }, [narrating, chart]);
  const width = chart ? Math.max(...chart.nodes.map((n) => n.x + n.width + (n.type === "gateway" ? 250 : 0))) + 24 : 0;
  const height = chart ? Math.max(...chart.nodes.map((n) => n.y + n.height)) + 24 : 0;
  const open = (model?.open ?? []).filter((o) => o.status !== "resolved");
  const stepLabel = (id: string) =>
    processes.flatMap((p) => p.steps).find((s) => s.id === id)?.label ?? processes.find((p) => p.id === id)?.name ?? id;

  return (
    <section className="imap" aria-label={title}>
      <header className="imap-head">
        <div>
          <h2>{title}</h2>
          <p className="muted-text">
            {process ? (process.name || "A process being described") : "The map appears once Tibi hears the first process."}
            {state === "drawing" && chart ? " · updating…" : ""}
          </p>
        </div>
        {processes.length > 1 ? (
          <div className="imap-tabs" role="tablist">
            {processes.map((p) => (
              <button key={p.id} type="button" role="tab" aria-selected={p.id === process?.id} onClick={() => setChosen(p.id)}>
                {p.name || "Unnamed"}
              </button>
            ))}
          </div>
        ) : null}
      </header>
      {state === "unavailable" ? <p className="imap-note imap-note--warn">{message}</p> : null}
      {chart && process ? (
        <div className="imap-zoom" role="group" aria-label="Map size">
          <button type="button" aria-pressed={zoom === null} onClick={() => setZoom(null)}>
            Fit
          </button>
          <button type="button" aria-label="Smaller" onClick={() => setZoom(Math.max(0.4, (zoom ?? 0.7) - 0.15))}>
            −
          </button>
          <button type="button" aria-label="Larger" onClick={() => setZoom(Math.min(1.4, (zoom ?? 0.55) + 0.15))}>
            +
          </button>
        </div>
      ) : null}
      {chart && process ? (
        <div ref={frame} className={`imap-frame${zoom !== null ? " imap-frame--zoomed" : ""}`}>
          <svg
            viewBox={`0 0 ${width} ${height}`}
            width={zoom === null ? width : Math.round(width * zoom)}
            height={zoom === null ? undefined : Math.round(height * zoom)}
            role="img"
            className={lit.size ? "imap--narrating" : undefined}
            aria-label={`Process map of ${process.name || "the process"}`}
          >
            <defs>
              <marker id="imap-arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
                <path d="M0,0 L0,6 L9,3 z" className="imap-arrow" />
              </marker>
            </defs>
            {chart.edges.map((edge) => (
              <Edge key={edge.id} edge={edge} />
            ))}
            {chart.nodes
              .filter((node) => node.type !== "lane")
              .map((node) => (
                <Node
                  key={node.id}
                  node={node}
                  changed={changed.has(node.id)}
                  narrating={lit.has(node.id)}
                  // "Still being described" is the map's own: it stands for this process's open ends.
                  onStep={onStep ? (id, label) => onStep(id === "end" ? `end:${process.id}` : id, label) : undefined}
                />
              ))}
          </svg>
        </div>
      ) : process && state !== "unavailable" ? (
        <p className="imap-note">Drawing the map…</p>
      ) : null}
      {process ? (
        <p className="imap-legend">
          <span className="imap-key imap-key--heard">Heard</span>
          <span className="imap-key imap-key--confirmed">Confirmed with you</span>
          <span className="imap-key imap-key--disputed">To check</span>
          {onStep ? (
            <span className="imap-hint">Click a step or a trigger to change it, or “Still being described” to carry on from there.</span>
          ) : null}
        </p>
      ) : null}
      {open.length ? (
        <div className="imap-open">
          <b>To check with you</b>
          <ul>
            {open.map((o) => (
              <li key={o.id}>
                {o.kind === "conflict" ? (
                  <>
                    <span className="imap-open-what">{stepLabel(o.item)}</span> — {o.field}: “{o.earlier}” or “{o.now}”?
                    {o.status === "raised" ? <em> Tibi has asked.</em> : null}
                  </>
                ) : (
                  o.text
                )}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
