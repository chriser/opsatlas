// Messages for the sidebar (OBS F7): a page says what happened without pushing its own layout down. The Human,
// 2 October 2026: "all warnings, messages should appear in sidebar so we don't disrupt the page layout itself".
export type NoticeTone = "danger" | "warn" | "info" | "good";

export interface PageNotice {
  id: number;
  tone: NoticeTone;
  text: string;
}

export const NOTICE_EVENT = "opsatlas-notice";
let next = 1;

/** Show a message in the sidebar: a confirmation fades after a few seconds, a warning stays until it is hidden. */
export function notify(text: string, tone: NoticeTone = "good"): void {
  window.dispatchEvent(new CustomEvent<PageNotice>(NOTICE_EVENT, { detail: { id: next++, tone, text } }));
}
