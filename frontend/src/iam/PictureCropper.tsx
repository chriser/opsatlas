// Choosing a picture on My account (IAM F10; the Human's request of 2 October 2026): size it and move it in a square
// with rounded corners, as the sidebar shows it under the logo. The crop is made here; the server keeps a square JPEG.
import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { Dialog } from "./ui";

const FRAME = 280; // the square on screen, in CSS pixels
const PREVIEW = 52; // the sidebar's square
const OUTPUT = 512; // pixels sent; the server keeps 256
const MAX_ZOOM = 4;
const BACKGROUND = "#1f2937"; // under a transparent picture, as the server lays it

/** Where the picture sits: its zoom, and its top-left corner within the frame (never leaving a gap). */
interface Placement {
  zoom: number;
  x: number;
  y: number;
}

/** CSS pixels per picture pixel at zoom 1: the picture's shorter side just fills the frame. */
const fit = (image: HTMLImageElement) => FRAME / Math.min(image.naturalWidth, image.naturalHeight);

function clamp(image: HTMLImageElement, place: Placement): Placement {
  const zoom = Math.min(MAX_ZOOM, Math.max(1, place.zoom));
  const width = image.naturalWidth * fit(image) * zoom;
  const height = image.naturalHeight * fit(image) * zoom;
  return { zoom, x: Math.min(0, Math.max(FRAME - width, place.x)), y: Math.min(0, Math.max(FRAME - height, place.y)) };
}

function centred(image: HTMLImageElement): Placement {
  const scale = fit(image);
  return clamp(image, { zoom: 1, x: (FRAME - image.naturalWidth * scale) / 2, y: (FRAME - image.naturalHeight * scale) / 2 });
}

/** Zoom keeping the point (cx, cy) of the frame where it is: the middle for the slider, the pointer for the wheel. */
function zoomAround(image: HTMLImageElement, place: Placement, zoom: number, cx = FRAME / 2, cy = FRAME / 2): Placement {
  const next = Math.min(MAX_ZOOM, Math.max(1, zoom));
  const ratio = next / place.zoom;
  return clamp(image, { zoom: next, x: cx - (cx - place.x) * ratio, y: cy - (cy - place.y) * ratio });
}

function crop(image: HTMLImageElement, place: Placement): Promise<Blob> {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = OUTPUT;
  const context = canvas.getContext("2d");
  if (!context) return Promise.reject(new Error("This browser cannot prepare the picture."));
  context.fillStyle = BACKGROUND;
  context.fillRect(0, 0, OUTPUT, OUTPUT);
  context.imageSmoothingQuality = "high";
  const scale = fit(image) * place.zoom; // CSS pixels per picture pixel
  context.drawImage(image, -place.x / scale, -place.y / scale, FRAME / scale, FRAME / scale, 0, 0, OUTPUT, OUTPUT);
  return new Promise((resolve, reject) =>
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("The picture could not be prepared."))), "image/jpeg", 0.92),
  );
}

export function PictureCropper({ file, onCancel, onSave }: { file: File; onCancel: () => void; onSave: (picture: Blob) => Promise<void> }) {
  const url = useMemo(() => URL.createObjectURL(file), [file]);
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [place, setPlace] = useState<Placement>({ zoom: 1, x: 0, y: 0 });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const frame = useRef<HTMLDivElement>(null);
  const drag = useRef<{ id: number; x: number; y: number } | null>(null);

  useEffect(() => () => URL.revokeObjectURL(url), [url]);
  useEffect(() => {
    const loaded = new Image();
    loaded.onload = () => {
      setImage(loaded);
      setPlace(centred(loaded));
    };
    loaded.onerror = () => setError("This browser cannot open that file as a picture. Try a JPEG or PNG.");
    loaded.src = url;
  }, [url]);

  // The wheel zooms around the pointer; a native listener, so the page behind does not scroll as well.
  useEffect(() => {
    const element = frame.current;
    if (!element || !image) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const box = element.getBoundingClientRect();
      setPlace((p) => zoomAround(image, p, p.zoom * Math.exp(-event.deltaY * 0.0015), event.clientX - box.left, event.clientY - box.top));
    };
    element.addEventListener("wheel", onWheel, { passive: false });
    return () => element.removeEventListener("wheel", onWheel);
  }, [image]);

  function down(event: PointerEvent<HTMLDivElement>) {
    if (!image) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { id: event.pointerId, x: event.clientX, y: event.clientY };
  }
  function move(event: PointerEvent<HTMLDivElement>) {
    const from = drag.current;
    if (!image || !from || from.id !== event.pointerId) return;
    const dx = event.clientX - from.x;
    const dy = event.clientY - from.y;
    drag.current = { ...from, x: event.clientX, y: event.clientY };
    setPlace((p) => clamp(image, { ...p, x: p.x + dx, y: p.y + dy }));
  }
  function up(event: PointerEvent<HTMLDivElement>) {
    if (drag.current?.id === event.pointerId) drag.current = null;
  }
  function key(event: KeyboardEvent<HTMLDivElement>) {
    if (!image) return;
    const step = event.shiftKey ? 1 : 10;
    const moves: Record<string, [number, number]> = { ArrowLeft: [step, 0], ArrowRight: [-step, 0], ArrowUp: [0, step], ArrowDown: [0, -step] };
    if (moves[event.key]) {
      event.preventDefault();
      const [dx, dy] = moves[event.key];
      setPlace((p) => clamp(image, { ...p, x: p.x + dx, y: p.y + dy }));
    } else if (event.key === "+" || event.key === "=" || event.key === "-") {
      event.preventDefault();
      setPlace((p) => zoomAround(image, p, p.zoom * (event.key === "-" ? 1 / 1.1 : 1.1)));
    }
  }

  async function save() {
    if (!image) return;
    setBusy(true);
    setError(null);
    try {
      await onSave(await crop(image, place));
    } catch (err) {
      setError(err instanceof Error ? err.message : "The picture was not saved.");
      setBusy(false);
    }
  }

  const scale = image ? fit(image) * place.zoom : 1;
  const picture = image ? (
    <img
      src={url}
      alt=""
      draggable={false}
      style={{ width: image.naturalWidth * scale, height: image.naturalHeight * scale, transform: `translate(${place.x}px, ${place.y}px)` }}
    />
  ) : null;

  return (
    <Dialog
      title="Your picture"
      open
      onClose={busy ? () => undefined : onCancel}
      footer={
        <>
          <button type="button" className="secondary-button" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button type="button" className="primary-button" onClick={() => void save()} disabled={!image || busy}>
            {busy ? "Saving…" : "Save picture"}
          </button>
        </>
      }
    >
      <div className="picture-cropper">
        <p className="muted-text">Drag the picture to move it; use the slider or the mouse wheel to size it.</p>
        <div className="picture-cropper-stage">
          <div
            ref={frame}
            className="picture-cropper-frame"
            style={{ width: FRAME, height: FRAME }}
            tabIndex={0}
            role="img"
            aria-label="Your picture as it will be cropped: drag or use the arrow keys to move it, plus and minus to size it"
            onPointerDown={down}
            onPointerMove={move}
            onPointerUp={up}
            onPointerCancel={up}
            onKeyDown={key}
          >
            {picture}
          </div>
          <div className="picture-cropper-preview">
            <span className="picture-cropper-mini" style={{ width: PREVIEW, height: PREVIEW }} aria-hidden="true">
              <span style={{ width: FRAME, height: FRAME, transform: `scale(${PREVIEW / FRAME})` }}>{picture}</span>
            </span>
            <small>In the sidebar</small>
          </div>
        </div>
        <label className="picture-cropper-zoom">
          <span>Size</span>
          <input
            type="range"
            min={1}
            max={MAX_ZOOM}
            step={0.01}
            value={place.zoom}
            disabled={!image}
            onChange={(e) => image && setPlace((p) => zoomAround(image, p, Number(e.target.value)))}
          />
          <button type="button" className="text-button" disabled={!image} onClick={() => image && setPlace(centred(image))}>
            Reset
          </button>
        </label>
        {error ? <p className="picture-cropper-error">{error}</p> : null}
      </div>
    </Dialog>
  );
}
