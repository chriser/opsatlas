// The process map notation, one standard for every map (the Human's decision, 29 September 2026): the shapes of the
// organisation's legend, drawn the same way by the live interview map and the animated process map, and by the
// diagram service's own SVG (services/process_diagram).
import type { ReactNode } from "react";
import type { ProcessDiagramNode } from "./api";

export const SHAPE_COLOURS: Record<string, string> = {
  start: "#b126e8",
  end: "#b126e8",
  event: "#b126e8",
  task: "#50c463",
  automated: "#2563eb",
  interface: "#6b7280",
  who: "#e8c200",
  lane: "#e8c200",
  system: "#66adff",
  control: "#b91c1c",
  risk: "#ef4444",
  annotation: "#9ca3af",
  line: "#374151",
};

/** XOR: only one path followed; AND: all paths; ANY: any number of paths. */
export const GATEWAY_NAMES: Record<string, string> = { xor: "XOR", and: "AND", or: "ANY" };

/** The flow itself, as against what sits beside a step (roles, systems, controls). */
export const FLOW_NODE_TYPES = new Set(["start", "end", "event", "task", "automated", "interface", "gateway"]);

/** Centred text for a node: offset from its centre, within a width. Each map draws text in its own style. */
export type NodeText = (dx: number, dy: number, width: number) => ReactNode;

export function wrapText(value: string, max: number, limit = 4) {
  const lines: string[] = [];
  let line = "";
  for (const word of value.split(/\s+/).filter(Boolean)) {
    if (line && `${line} ${word}`.length > max) {
      lines.push(line);
      line = word;
    } else line = line ? `${line} ${word}` : word;
  }
  if (line) lines.push(line);
  return lines.slice(0, limit);
}

function gateway(node: ProcessDiagramNode) {
  const { x, y, width: w } = node;
  const kind = node.metadata?.gateway ?? "xor";
  const cx = x + w / 2;
  const cy = y + node.height / 2;
  const r = w / 2;
  const i = r * 0.42;
  const mark =
    kind === "and" ? (
      <polyline points={`${cx - i},${cy + i / 2 + 6} ${cx},${cy - i} ${cx + i},${cy + i / 2 + 6}`} />
    ) : kind === "or" ? (
      <polyline points={`${cx - i},${cy - i / 2 - 6} ${cx},${cy + i} ${cx + i},${cy - i / 2 - 6}`} />
    ) : (
      <>
        <line x1={cx - i} y1={cy - i} x2={cx + i} y2={cy + i} />
        <line x1={cx + i} y1={cy - i} x2={cx - i} y2={cy + i} />
      </>
    );
  return (
    <>
      <circle className="epc-outline" cx={cx} cy={cy} r={r} fill="#ffffff" stroke={SHAPE_COLOURS.line} strokeWidth={2} />
      <g stroke={SHAPE_COLOURS.line} strokeWidth={2.5} fill="none" strokeLinecap="round">
        {mark}
      </g>
      <text x={cx + r + 6} y={y - 4} fontSize={12} fontWeight={700} fill={SHAPE_COLOURS.line} fontFamily="Arial">
        {GATEWAY_NAMES[kind] ?? "XOR"}
      </text>
      {wrapText(node.label, 26, 3).map((line, n) => (
        <text key={n} x={cx + r + 12} y={cy + 4 + n * 16} fontSize={13} fill="#475569" fontFamily="Arial">
          {line}
        </text>
      ))}
    </>
  );
}

/** One node of a process map, in the notation: a connector is a circle (XOR, AND, ANY); everything else is a rounded box
 * in its legend colour (the Human's choice of 29 September 2026). ``text`` draws its words. */
export function ProcessShape({ node, text }: { node: ProcessDiagramNode; text: NodeText }) {
  if (node.type === "gateway") return gateway(node);
  const { x, y, width: w, height: h } = node;
  const support = ["who", "lane", "system", "control", "risk", "annotation"].includes(node.type);
  const dashed = node.type === "risk" || node.type === "annotation" || (node.type === "who" && node.metadata?.external === "true");
  return (
    <>
      <rect className="epc-outline" x={x} y={y} width={w} height={h} rx={12} fill="#ffffff"
        stroke={SHAPE_COLOURS[node.type] ?? SHAPE_COLOURS.task} strokeWidth={support ? 3 : 4} strokeDasharray={dashed ? "9 6" : undefined} />
      {node.type === "interface" && node.metadata?.reference ? (
        <text x={x + w} y={y - 8} textAnchor="end" fontSize={12} fill={SHAPE_COLOURS.line} fontFamily="Arial">
          {node.metadata.reference}
        </text>
      ) : null}
      {text(0, 0, w - 36)}
    </>
  );
}
