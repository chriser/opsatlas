import { useEffect, useMemo, useRef, useState } from "react";
import type { ProcessDiagramContext, ProcessDiagramEdge, ProcessDiagramNode } from "./api";

type NarrationHandler = (text: string) => Promise<void> | void;

interface RevealFrame {
  nodeIds: Set<string>;
  edgeIds: Set<string>;
  focusNodeId: string;
  narration: string;
  label: string;
}

const FLOW_TYPES = new Set(["start", "task", "gateway", "end"]);
const SUPPORT_TYPES = new Set(["system", "control", "risk", "annotation"]);
const PLAYBACK_START_DELAY_MS = 180;
const VISUAL_ONLY_STEP_MS = 3600;
const SPOKEN_WORD_MS = 680;
const SPOKEN_MIN_MS = 5200;
const SPOKEN_MAX_MS = 20000;
const POST_STEP_PAUSE_MS = 1600;

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function estimatedStepDurationMs(text: string, voiced: boolean) {
  if (!voiced) return VISUAL_ONLY_STEP_MS;
  const wordCount = text.split(/\s+/).filter(Boolean).length;
  return Math.min(SPOKEN_MAX_MS, Math.max(SPOKEN_MIN_MS, wordCount * SPOKEN_WORD_MS + POST_STEP_PAUSE_MS));
}

function nodeCenter(node: ProcessDiagramNode) {
  return {
    x: node.x + node.width / 2,
    y: node.y + node.height / 2,
  };
}

function wrapLabel(value: string, maxChars: number) {
  const words = value.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let current: string[] = [];
  for (const word of words) {
    const nextLength = current.join(" ").length + (current.length ? 1 : 0) + word.length;
    if (current.length && nextLength > maxChars) {
      lines.push(current.join(" "));
      current = [word];
    } else {
      current.push(word);
    }
  }
  if (current.length) lines.push(current.join(" "));
  return lines.slice(0, 4);
}

function pathFor(edge: ProcessDiagramEdge) {
  return edge.points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`)
    .join(" ");
}

function polygonPoints(node: ProcessDiagramNode) {
  const cut = 42;
  return [
    `${node.x + cut},${node.y}`,
    `${node.x + node.width - cut},${node.y}`,
    `${node.x + node.width},${node.y + node.height / 2}`,
    `${node.x + node.width - cut},${node.y + node.height}`,
    `${node.x + cut},${node.y + node.height}`,
    `${node.x},${node.y + node.height / 2}`,
  ].join(" ");
}

function textLines(node: ProcessDiagramNode, maxChars = 18, fontSize = 18, xOffset = 0, yOffset = 0) {
  const lines = wrapLabel(node.label, maxChars);
  const lineHeight = fontSize + 7;
  const center = nodeCenter(node);
  const firstY = center.y - ((lines.length - 1) * lineHeight) / 2 + fontSize / 3 + yOffset;
  return lines.map((line, index) => (
    <text
      key={`${node.id}-text-${index}`}
      x={center.x + xOffset}
      y={firstY + index * lineHeight}
      textAnchor="middle"
      fill="#111827"
      fontFamily="Arial"
      fontSize={fontSize}
      fontWeight={400}
    >
      {line}
    </text>
  ));
}

function tabCard(node: ProcessDiagramNode, stroke: string, maxChars = 17) {
  const tabX = node.x + 28;
  const headerY = node.y + 27;
  return (
    <g className="animated-diagram-node" key={node.id}>
      <rect x={node.x} y={node.y} width={node.width} height={node.height} rx={10} fill="#ffffff" stroke={stroke} strokeWidth={4} />
      <line x1={tabX} y1={node.y} x2={tabX} y2={node.y + node.height} stroke={stroke} strokeWidth={4} />
      <line x1={node.x} y1={headerY} x2={node.x + node.width} y2={headerY} stroke={stroke} strokeWidth={4} />
      {textLines(node, maxChars, 17, 12, 8)}
    </g>
  );
}

function supportCard(node: ProcessDiagramNode) {
  const stroke = node.type === "risk" ? "#ef4444" : node.type === "annotation" ? "#9ca3af" : "#f59e0b";
  return (
    <g className="animated-diagram-node" key={node.id}>
      <rect
        x={node.x}
        y={node.y}
        width={node.width}
        height={node.height}
        rx={10}
        fill="#ffffff"
        stroke={stroke}
        strokeWidth={4}
        strokeDasharray="7 6"
      />
      {textLines(node, 17, 17)}
    </g>
  );
}

function diagramNode(node: ProcessDiagramNode) {
  if (node.type === "start" || node.type === "end") {
    return (
      <g className="animated-diagram-node" key={node.id}>
        <polygon points={polygonPoints(node)} fill="#ffffff" stroke="#b126e8" strokeWidth={5} strokeLinejoin="round" />
        {textLines(node)}
      </g>
    );
  }
  if (node.type === "gateway") {
    const center = nodeCenter(node);
    const radius = node.width / 2;
    return (
      <g className="animated-diagram-node" key={node.id}>
        <circle cx={center.x} cy={center.y} r={radius} fill="#ffffff" stroke="#374151" strokeWidth={2} />
        <line x1={center.x - radius + 13} y1={center.y - radius + 13} x2={center.x + radius - 13} y2={center.y + radius - 13} stroke="#374151" strokeWidth={2} />
        <line x1={center.x + radius - 13} y1={center.y - radius + 13} x2={center.x - radius + 13} y2={center.y + radius - 13} stroke="#374151" strokeWidth={2} />
      </g>
    );
  }
  if (node.type === "who" || node.type === "lane") return tabCard(node, "#ffdd33", 18);
  if (node.type === "system") return tabCard(node, "#66adff", 17);
  if (SUPPORT_TYPES.has(node.type)) return supportCard(node);
  return (
    <g className="animated-diagram-node" key={node.id}>
      <rect x={node.x} y={node.y} width={node.width} height={node.height} rx={10} fill="#ffffff" stroke="#50c463" strokeWidth={4} />
      {textLines(node)}
    </g>
  );
}

function buildFrames(nodes: ProcessDiagramNode[], edges: ProcessDiagramEdge[]): RevealFrame[] {
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const flowNodes = nodes
    .filter((node) => FLOW_TYPES.has(node.type))
    .sort((left, right) => left.y - right.y || left.x - right.x);
  return flowNodes.map((node) => {
    const relatedNodes = nodes.filter((candidate) => candidate.metadata?.anchor_id === node.id);
    const relatedNodeIds = new Set([node.id, ...relatedNodes.map((candidate) => candidate.id)]);
    const relatedEdgeIds = new Set(
      edges
        .filter((edge) => {
          const source = nodeById.get(edge.from);
          const incomingFlow = edge.to === node.id && Boolean(source && FLOW_TYPES.has(source.type));
          const supportOrWho = relatedNodeIds.has(edge.from) || relatedNodeIds.has(edge.to);
          const directAnchor = edge.from === node.id || edge.to === node.id;
          return incomingFlow || (supportOrWho && directAnchor);
        })
        .map((edge) => edge.id),
    );
    return {
      nodeIds: relatedNodeIds,
      edgeIds: relatedEdgeIds,
      focusNodeId: node.id,
      label: node.label,
      narration: narrationFor(node, relatedNodes),
    };
  });
}

function narrationFor(node: ProcessDiagramNode, relatedNodes: ProcessDiagramNode[]) {
  const who = relatedNodes.filter((candidate) => candidate.type === "who").map((candidate) => candidate.label);
  const systems = relatedNodes.filter((candidate) => candidate.type === "system").map((candidate) => candidate.label);
  const controls = relatedNodes.filter((candidate) => candidate.type === "control").map((candidate) => candidate.label);
  const risks = relatedNodes.filter((candidate) => candidate.type === "risk" || candidate.type === "annotation").map((candidate) => candidate.label);
  if (node.type === "start") return "Let's start at the beginning of the process.";
  if (node.type === "end") return "That completes the process walkthrough.";
  if (node.type === "gateway") return `The process checks whether ${gatewayCondition(node.label)}.`;
  const actor = actorPhrase(who);
  const sentence = `${actor.text} ${actionPhrase(node.label, actor.plural)}${systemPhrase(systems)}.`;
  return `${sentence}${controlPhrase(controls)}${riskPhrase(risks)}`;
}

function visibleIds(frames: RevealFrame[], index: number) {
  const nodeIds = new Set<string>();
  const edgeIds = new Set<string>();
  frames.slice(0, index + 1).forEach((frame) => {
    frame.nodeIds.forEach((id) => nodeIds.add(id));
    frame.edgeIds.forEach((id) => edgeIds.add(id));
  });
  return { nodeIds, edgeIds };
}

function listPhrase(items: string[]) {
  const unique = Array.from(new Set(items.map((item) => item.trim()).filter(Boolean)));
  if (!unique.length) return "";
  if (unique.length === 1) return unique[0];
  if (unique.length === 2) return `${unique[0]} and ${unique[1]}`;
  return `${unique.slice(0, -1).join(", ")} and ${unique[unique.length - 1]}`;
}

function lowerFirst(value: string) {
  return value ? `${value.charAt(0).toLowerCase()}${value.slice(1)}` : value;
}

function objectPhrase(value: string) {
  const cleaned = lowerFirst(value.trim()).replace(/[.]+$/, "");
  if (!cleaned) return "";
  if (/^(the|a|an|this|that)\s/i.test(cleaned)) return cleaned;
  return `the ${cleaned}`;
}

function gatewayCondition(label: string) {
  const cleaned = lowerFirst(label.trim()).replace(/\?$/, "");
  if (!cleaned) return "the decision is clear";
  if (/\b(is|are|has|have|can|should|must|will)\b/i.test(cleaned)) return cleaned;
  if (cleaned.endsWith(" complete") || cleaned.endsWith(" clear") || cleaned.endsWith(" approved")) {
    const [subject, state] = cleaned.split(/\s+(?=[^\s]+$)/);
    const verb = subject.endsWith("s") ? "are" : "is";
    return `${subject} ${verb} ${state}`;
  }
  return cleaned;
}

function actionPhrase(label: string, plural: boolean) {
  const cleaned = label.trim().replace(/[.]+$/, "");
  const lower = cleaned.toLowerCase();
  const mappings: { prefix: string; singular: string; plural: string }[] = [
    { prefix: "fill in ", singular: "fills in", plural: "fill in" },
    { prefix: "complete ", singular: lower.includes("form") ? "fills in" : "completes", plural: lower.includes("form") ? "fill in" : "complete" },
    { prefix: "prepare ", singular: "prepares", plural: "prepare" },
    { prefix: "submit ", singular: "submits", plural: "submit" },
    { prefix: "send ", singular: "sends", plural: "send" },
    { prefix: "review ", singular: "reviews", plural: "review" },
    { prefix: "validate ", singular: "validates", plural: "validate" },
    { prefix: "create ", singular: "creates", plural: "create" },
    { prefix: "activate ", singular: "activates", plural: "activate" },
    { prefix: "resolve ", singular: "resolves", plural: "resolve" },
    { prefix: "update ", singular: "updates", plural: "update" },
    { prefix: "map ", singular: "maps", plural: "map" },
    { prefix: "confirm ", singular: "confirms", plural: "confirm" },
  ];
  for (const mapping of mappings) {
    if (lower.startsWith(mapping.prefix)) {
      const object = cleaned.slice(mapping.prefix.length);
      return `${plural ? mapping.plural : mapping.singular} ${objectPhrase(object)}`.trim();
    }
  }
  return `${plural ? "carry out" : "carries out"} ${objectPhrase(cleaned)}`;
}

function actorPhrase(roles: string[]) {
  if (!roles.length) return { text: "The process team", plural: false };
  const [primary, ...supporting] = Array.from(new Set(roles));
  if (!supporting.length) return { text: primary, plural: false };
  return { text: `${primary}, supported by ${listPhrase(supporting)}`, plural: false };
}

function systemPhrase(systems: string[]) {
  const unique = Array.from(new Set(systems));
  if (!unique.length) return "";
  const lower = unique.map((system) => system.toLowerCase());
  const hasEmail = lower.some((system) => system === "email" || system.includes("email"));
  const outlook = unique.find((system) => system.toLowerCase().includes("outlook"));
  const forms = unique.filter((system) => system.toLowerCase().includes("form"));
  const tools = unique.filter((system) => !system.toLowerCase().includes("form") && !system.toLowerCase().includes("email"));
  if (hasEmail && outlook) {
    const formPart = forms.length ? ` using ${listPhrase(forms.map(objectPhrase))}` : "";
    return `${formPart} by email in ${outlook}`;
  }
  if (hasEmail) return " by email";
  if (forms.length && tools.length === 1) return ` using ${listPhrase(forms.map(objectPhrase))} in ${tools[0]}`;
  if (forms.length) return ` using ${listPhrase(forms.map(objectPhrase))}`;
  if (unique.length === 1) {
    const [system] = unique;
    return ` in ${system}`;
  }
  return ` using ${listPhrase(unique)}`;
}

function controlPhrase(controls: string[]) {
  if (!controls.length) return "";
  return ` This step is governed by ${listPhrase(controls)}.`;
}

function riskPhrase(risks: string[]) {
  if (!risks.length) return "";
  return ` Watch point: ${listPhrase(risks)}.`;
}

export function AnimatedProcessDiagramPanel({
  diagram,
  loading,
  autoPlay,
  playbackKey,
  title = "Avatar process walkthrough",
  onNarrationStep,
}: {
  diagram: ProcessDiagramContext | null;
  loading: boolean;
  autoPlay: boolean;
  playbackKey: number;
  title?: string;
  onNarrationStep?: NarrationHandler;
}) {
  const [stepIndex, setStepIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const playbackRun = useRef(0);
  const frameRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const chart = diagram?.status === "available" ? diagram.chart : null;
  const frames = useMemo(() => (chart ? buildFrames(chart.nodes ?? [], chart.edges ?? []) : []), [chart]);
  const dimensions = useMemo(() => {
    const nodes = chart?.nodes ?? [];
    return {
      width: Math.max(...nodes.map((node) => node.x + node.width + 56), 900),
      height: Math.max(...nodes.map((node) => node.y + node.height + 56), 520),
    };
  }, [chart]);
  const hasStarted = playbackKey > 0;
  const visible = useMemo(
    () => (hasStarted ? visibleIds(frames, stepIndex) : { nodeIds: new Set<string>(), edgeIds: new Set<string>() }),
    [frames, hasStarted, stepIndex],
  );
  const activeFrame = hasStarted ? frames[stepIndex] : null;

  useEffect(() => {
    setStepIndex(0);
    setPlaying(false);
    playbackRun.current += 1;
  }, [chart?.chart_id, playbackKey]);

  useEffect(() => {
    if (!activeFrame || !chart || !hasStarted) return;
    const frame = frameRef.current;
    const svg = svgRef.current;
    if (!frame || !svg) return;
    const focusNode = chart.nodes.find((node) => node.id === activeFrame.focusNodeId);
    if (!focusNode) return;
    const raf = window.requestAnimationFrame(() => {
      const scaleX = svg.clientWidth / dimensions.width;
      const scaleY = svg.clientHeight / dimensions.height;
      const focusCenterX = (focusNode.x + focusNode.width / 2) * scaleX;
      const focusCenterY = (focusNode.y + focusNode.height / 2) * scaleY;
      frame.scrollTo({
        left: Math.max(0, focusCenterX - frame.clientWidth / 2),
        top: Math.max(0, focusCenterY - frame.clientHeight / 2),
        behavior: playing ? "smooth" : "auto",
      });
    });
    return () => window.cancelAnimationFrame(raf);
  }, [activeFrame, chart, dimensions.height, dimensions.width, hasStarted, playing]);

  useEffect(() => {
    if (!autoPlay || !playbackKey || !frames.length) return;
    const runId = playbackRun.current + 1;
    playbackRun.current = runId;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      void run();
    }, PLAYBACK_START_DELAY_MS);

    async function run() {
      setPlaying(true);
      for (let index = 0; index < frames.length; index += 1) {
        if (cancelled || playbackRun.current !== runId) break;
        setStepIndex(index);
        const narration = frames[index].narration;
        const startedAt = window.performance.now();
        await onNarrationStep?.(narration);
        const elapsed = window.performance.now() - startedAt;
        const holdMs = Math.max(POST_STEP_PAUSE_MS, estimatedStepDurationMs(narration, Boolean(onNarrationStep)) - elapsed);
        await sleep(holdMs);
      }
      if (!cancelled && playbackRun.current === runId) setPlaying(false);
    }

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [autoPlay, chart?.chart_id, frames, onNarrationStep, playbackKey]);

  if (loading) {
    return (
      <div className="panel process-diagram-panel">
        <div className="panel-heading">
          <div>
            <h2>{title}</h2>
            <p className="muted-text">Preparing animated process walkthrough...</p>
          </div>
          <span className="status-pill">loading</span>
        </div>
      </div>
    );
  }

  if (!diagram || diagram.status === "empty") {
    return (
      <div className="panel process-diagram-panel">
        <div className="panel-heading">
          <div>
            <h2>{title}</h2>
            <p className="muted-text">{diagram?.message || "No related process map is available for this answer."}</p>
          </div>
          <span className="status-pill">no map</span>
        </div>
      </div>
    );
  }

  if (diagram.status !== "available" || !chart || !frames.length) {
    return (
      <div className="panel process-diagram-panel">
        <div className="panel-heading">
          <div>
            <h2>{title}</h2>
            <p className="muted-text">{diagram.message || "The process walkthrough is unavailable."}</p>
          </div>
          <span className="status-pill status-pill--warn">unavailable</span>
        </div>
      </div>
    );
  }

  const canGoBack = stepIndex > 0;
  const canGoForward = hasStarted && stepIndex < frames.length - 1;
  const progress = hasStarted ? `${stepIndex + 1} / ${frames.length}` : "Ready";

  return (
    <div className="panel process-diagram-panel animated-diagram-panel">
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          <p className="muted-text">{diagram.process_name}</p>
        </div>
        <span className="status-pill status-pill--good">{playing ? "drawing" : "ready"}</span>
      </div>
      <div className="animated-diagram-narration">
        <span>{progress}</span>
        <p>{activeFrame?.narration || "A related process map is ready. Start the walkthrough when you want the diagram revealed step by step."}</p>
      </div>
      <div className="process-diagram-frame animated-diagram-frame" ref={frameRef}>
        <svg ref={svgRef} viewBox={`0 0 ${dimensions.width} ${dimensions.height}`} role="img" aria-label={`${diagram.process_name} animated process walkthrough`}>
          <defs>
            <marker id="animated-arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L0,6 L9,3 z" fill="#374151" />
            </marker>
          </defs>
          <rect width="100%" height="100%" fill="#ffffff" />
          {chart.edges
            .filter((edge) => visible.edgeIds.has(edge.id))
            .map((edge) => (
              <g className="animated-diagram-edge" key={edge.id}>
                <path d={pathFor(edge)} fill="none" stroke="#334155" strokeWidth={2} markerEnd="url(#animated-arrow)" />
                {edge.label ? (
                  <text
                    x={edge.points[Math.floor(edge.points.length / 2)]?.x + 6}
                    y={(edge.points[Math.floor(edge.points.length / 2)]?.y ?? 0) - 6}
                    fill="#475569"
                    fontFamily="Arial"
                    fontSize={11}
                  >
                    {edge.label}
                  </text>
                ) : null}
              </g>
            ))}
          {chart.nodes
            .filter((node) => visible.nodeIds.has(node.id))
            .map((node) => diagramNode(node))}
        </svg>
      </div>
      <div className="animated-diagram-controls">
        <button type="button" className="secondary-button" disabled={!canGoBack || playing} onClick={() => setStepIndex((value) => Math.max(0, value - 1))}>
          Previous
        </button>
        <button type="button" className="secondary-button" disabled={!canGoForward || playing} onClick={() => setStepIndex((value) => Math.min(frames.length - 1, value + 1))}>
          Next
        </button>
        <button type="button" className="secondary-button" disabled={!hasStarted || playing} onClick={() => setStepIndex(0)}>
          Reset
        </button>
      </div>
      <p className="result-cite">
        {diagram.source_title || "Process registry"} · {diagram.service_url || "local diagram service"}
      </p>
    </div>
  );
}
