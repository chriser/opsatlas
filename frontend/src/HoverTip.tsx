import { useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

/** A small dark tooltip shown on hover or keyboard focus. It is drawn on the page body, so a table or panel that
 * clips its content never cuts it off. */
export function HoverTip({ tip, children }: { tip: ReactNode; children: ReactNode }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [at, setAt] = useState<{ left: number; top: number; above: boolean } | null>(null);

  function show() {
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return;
    const above = rect.bottom + 180 > window.innerHeight;
    setAt({ left: Math.min(rect.left, window.innerWidth - 316), top: above ? rect.top - 8 : rect.bottom + 8, above });
  }

  return (
    <span ref={ref} className="hover-tip" onMouseEnter={show} onMouseLeave={() => setAt(null)} onFocus={show} onBlur={() => setAt(null)}>
      {children}
      {at
        ? createPortal(
            <span
              className={`hover-tip-box${at.above ? " hover-tip-box--above" : ""}`}
              role="tooltip"
              style={{ left: at.left, top: at.top }}
            >
              {tip}
            </span>,
            document.body,
          )
        : null}
    </span>
  );
}
