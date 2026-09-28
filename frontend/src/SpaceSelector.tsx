import { useEffect, useState } from "react";
import { listSpaces, setActiveSpace, type Space } from "./api";

const KIND: Record<Space["kind"], string> = {
  product: "Product guide",
  playbook: "Internal",
  system: "Administrators",
  organisation: "Organisation",
};

/** The space the page shows (KS S6): its sources, answers, process maps, activity model and analytics. */
export function SpaceSelector({ active }: { active: string }) {
  const [spaces, setSpaces] = useState<Space[]>([]);
  useEffect(() => {
    listSpaces()
      .then((data) => setSpaces(data.spaces))
      .catch(() => setSpaces([]));
  }, []);
  if (!spaces.length) return null;
  const current = spaces.find((s) => s.id === active) ?? spaces[0];
  return (
    <label className="space-selector" title={current.about}>
      <span className="space-selector-label">Space</span>
      <span className={`space-kind space-kind--${current.kind}`}>{KIND[current.kind]}</span>
      <select value={current.id} onChange={(e) => setActiveSpace(e.target.value)} aria-label="Active space">
        {spaces.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name} ({s.documents})
          </option>
        ))}
      </select>
    </label>
  );
}
