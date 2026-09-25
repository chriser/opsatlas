import { useState } from "react";
import type { TibiStatus } from "./api";

export type TibiMode = "recall" | "interview" | "governance";

/** Talk with Tibi inside OpsAtlas: the voice client runs in its own local service and is embedded here. */
export function TibiPage({
  status,
  mode,
  onOpenKnowledge,
}: {
  status: TibiStatus | null;
  mode: TibiMode;
  onOpenKnowledge: () => void;
}) {
  const [typed, setTyped] = useState(false);

  if (!status) {
    return (
      <div className="view-stack">
        <div className="page-intro">
          <h1>Talk with Tibi</h1>
          <p>Tibi is not running in this workspace.</p>
        </div>
      </div>
    );
  }

  const src = `${status.voice_url}&mode=${mode}${typed ? "&text=1" : ""}`;
  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Talk with Tibi</h1>
        <p>
          Chat with Tibi, contribute product knowledge, or resolve governance issues by voice. Product answers are checked
          against approved OpsAtlas evidence, and nothing Tibi captures is approved until you review it.
        </p>
      </div>
      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Tibi</h2>
            <p className="muted-text">
              Choose a session below. Captured knowledge waits in Tibi knowledge; governance answers wait on the Governance page.
            </p>
          </div>
          <div className="tibi-actions">
            <button type="button" className="secondary-button" onClick={() => setTyped((value) => !value)}>
              {typed ? "Use voice" : "Type instead"}
            </button>
            <button type="button" className="secondary-button" onClick={onOpenKnowledge}>
              Tibi knowledge
            </button>
          </div>
        </div>
        <iframe key={src} title="Talk with Tibi" src={src} className="tibi-frame" allow="microphone; autoplay; clipboard-write" />
      </div>
    </div>
  );
}
