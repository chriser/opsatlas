// The version of a document an answer cited (REF S18): read-only, with when it was kept and its hash, and a way to the
// document as it is now. A citation in an answer links here, so yesterday's answer shows yesterday's words.
import { useEffect, useState } from "react";
import { Markdown } from "../Markdown";
import { getVersion, type VersionText } from "./api";

export function CitedVersion({ sourceId, space, version }: { sourceId: string; space: string | null; version: number }) {
  const [row, setRow] = useState<VersionText | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    getVersion(sourceId, version, space)
      .then((data) => (setRow(data), setError(null)))
      .catch((e) => setError(e instanceof Error ? e.message : "This version could not be opened"));
  }, [sourceId, version, space]);
  const current = `#document:${sourceId}${space ? `@${space}` : ""}`;
  return (
    <div className="view-stack">
      <div className="page-intro">
        <div>
          <h1>Version {version}, as cited</h1>
          <p>
            The words an answer rested on, kept when the answer was given.{" "}
            <a href={current}>Open the document as it is now</a>.
          </p>
        </div>
      </div>
      {error ? <p className="cm-inline-error">{error}</p> : null}
      {row ? (
        <div className="panel">
          <p className="muted-text">
            {row.label} by {row.author} on {new Date(row.at).toLocaleString()}
            {row.note ? ` · ${row.note}` : ""} · SHA-256 <code>{row.sha.slice(0, 12)}</code>
          </p>
          <Markdown text={row.text} />
        </div>
      ) : !error ? (
        <p className="muted-text">Opening the version…</p>
      ) : null}
    </div>
  );
}
