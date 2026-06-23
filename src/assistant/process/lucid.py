"""Lucidchart Standard Import adapter for process-map drafts."""

from __future__ import annotations

import html
import io
import json
import os
import re
import uuid
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from urllib import request
from urllib.error import HTTPError, URLError

from .maps import ProcessMapDraft

LUCID_CREATE_ENDPOINT = "https://api.lucid.co/v1/documents/create"
LUCID_IMPORT_CONTENT_TYPE = "x-application/vnd.lucid.standardImport"

STEP_W = 270
STEP_H = 112
STEP_X = 80
STEP_Y = 190
STEP_GAP_X = 80
STEP_GAP_Y = 185
MAX_COLUMNS = 3


@dataclass(frozen=True)
class LucidSettings:
    api_key: str
    parent_folder_id: str = ""
    product: str = "lucidchart"

    @property
    def missing(self) -> list[str]:
        missing: list[str] = []
        if not self.api_key:
            missing.append("LUCID_API_KEY")
        return missing


class LucidCreateError(RuntimeError):
    """Raised when Lucid rejects or cannot receive a document-create request."""


def lucid_settings_from_env() -> LucidSettings:
    return LucidSettings(
        api_key=os.environ.get("LUCID_API_KEY", "").strip(),
        parent_folder_id=os.environ.get("LUCID_PARENT_FOLDER_ID", "").strip(),
        product=os.environ.get("LUCID_PRODUCT", "lucidchart").strip() or "lucidchart",
    )


def safe_lucid_filename(draft: ProcessMapDraft) -> str:
    stem = _safe_id(draft.name or draft.process_id, limit=80).strip("-_.~") or "process-map"
    return f"{stem}.lucid"


def build_lucid_standard_import(draft: ProcessMapDraft) -> dict:
    steps = draft.steps or []
    columns = min(MAX_COLUMNS, max(1, len(steps)))
    rows = max(1, (len(steps) + columns - 1) // columns)
    step_positions = _step_positions(len(steps), columns)
    right_x = STEP_X + columns * (STEP_W + STEP_GAP_X) + 20
    page_w = min(20000, max(1200, right_x + 330))
    page_h = min(20000, max(900, STEP_Y + rows * (STEP_H + STEP_GAP_Y) + 260))

    shapes: list[dict] = [
        _text_shape(
            "title",
            80,
            45,
            page_w - 160,
            52,
            f"<b>{_html(draft.name)}</b>",
            note=f"Generated from source: {draft.source_title}",
        ),
        _text_shape(
            "subtitle",
            82,
            102,
            page_w - 164,
            54,
            _subtitle(draft),
        ),
    ]
    lines: list[dict] = []

    for index, step in enumerate(steps, start=1):
        x, y = step_positions[step.id]
        shape = _step_shape(index, step.id, x, y, step.label, step.owner, step.topic, step.confidence, draft)
        shapes.append(shape)

    for index, edge in enumerate(draft.edges, start=1):
        source_box = step_positions.get(edge.source)
        target_box = step_positions.get(edge.target)
        if not source_box or not target_box:
            continue
        lines.append(_step_line(index, edge.source, edge.target, edge.label, source_box, target_box))

    context_y = STEP_Y
    context_shapes, context_lines = _context_panel(draft, right_x, context_y, first_step_id=steps[0].id if steps else "")
    shapes.extend(context_shapes)
    lines.extend(context_lines)

    page = {
        "id": "page_1",
        "title": _truncate(draft.name or "Process map", 90),
        "settings": {
            "fillColor": "#ffffff",
            "infiniteCanvas": False,
            "autoTiling": True,
            "size": {"type": "custom", "w": page_w, "h": page_h},
        },
        "shapes": shapes,
        "lines": lines,
        "customData": [
            {"key": "process_id", "value": draft.process_id},
            {"key": "source_title", "value": draft.source_title},
            {"key": "domain", "value": draft.domain},
            {"key": "process", "value": draft.process},
        ],
    }
    return {
        "version": 1,
        "pages": [page],
        "documentSettings": {"units": "px"},
    }


def build_lucid_archive(draft: ProcessMapDraft) -> bytes:
    document = build_lucid_standard_import(draft)
    payload = json.dumps(document, indent=2, ensure_ascii=False).encode("utf-8")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        info = zipfile.ZipInfo("document.json")
        info.date_time = (2026, 1, 1, 0, 0, 0)
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, payload)
    return output.getvalue()


def create_lucid_document(
    draft: ProcessMapDraft,
    settings: LucidSettings,
    *,
    opener: Callable = request.urlopen,
) -> dict:
    if settings.missing:
        raise ValueError(f"Missing Lucid configuration: {', '.join(settings.missing)}")
    if settings.product not in {"lucidchart", "lucidspark"}:
        raise ValueError("LUCID_PRODUCT must be either lucidchart or lucidspark.")

    file_bytes = build_lucid_archive(draft)
    fields = {
        "type": LUCID_IMPORT_CONTENT_TYPE,
        "product": settings.product,
        "title": _truncate(draft.name or "Process map", 120),
    }
    if settings.parent_folder_id:
        fields["parent"] = settings.parent_folder_id

    body, content_type = _multipart_body(
        fields=fields,
        file_field="file",
        filename=safe_lucid_filename(draft),
        file_bytes=file_bytes,
    )
    req = request.Request(
        LUCID_CREATE_ENDPOINT,
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {settings.api_key}",
            "Content-Type": content_type,
        },
    )
    try:
        with opener(req, timeout=45) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise LucidCreateError(f"Lucid document creation failed ({exc.code}): {_truncate(detail, 700)}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise LucidCreateError(f"Lucid document creation failed: {exc}") from exc

    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        raise LucidCreateError("Lucid document creation returned a non-JSON response.") from exc

    return _normalise_lucid_response(payload)


def _step_positions(count: int, columns: int) -> dict[str, tuple[int, int]]:
    positions: dict[str, tuple[int, int]] = {}
    for index in range(1, count + 1):
        row = (index - 1) // columns
        column = (index - 1) % columns
        positions[f"step_{index}"] = (STEP_X + column * (STEP_W + STEP_GAP_X), STEP_Y + row * (STEP_H + STEP_GAP_Y))
    return positions


def _step_shape(
    index: int,
    shape_id: str,
    x: int,
    y: int,
    label: str,
    owner: str,
    topic: str,
    confidence: str,
    draft: ProcessMapDraft,
) -> dict:
    fill, stroke = _confidence_colors(confidence)
    owner_text = f"<b>{_html(owner)}</b><br/>" if owner else ""
    topic_text = f"<br/><span style=\"color:#475569\"><i>{_html(topic)}</i></span>" if topic else ""
    text = f"{owner_text}{_html(label)}{topic_text}"
    task_type = "businessRule" if _looks_like_control(label) else "manual"
    return {
        "id": shape_id,
        "type": "bpmnActivity",
        "boundingBox": {"x": x, "y": y, "w": STEP_W, "h": STEP_H},
        "style": _style(fill, stroke, rounding=14),
        "text": text,
        "activityType": "task",
        "taskType": task_type,
        "activityMarker1": "none",
        "activityMarker2": "none",
        "customData": [
            {"key": "process_id", "value": draft.process_id},
            {"key": "step_index", "value": str(index)},
            {"key": "owner", "value": owner},
            {"key": "topic", "value": topic},
            {"key": "confidence", "value": confidence},
        ],
        "note": _note(
            [
                f"Source: {draft.source_title}",
                f"Owner: {owner or 'not identified'}",
                f"Topic: {topic or 'not identified'}",
                f"Confidence: {confidence or 'not stated'}",
                f"Rule: {label}",
            ],
        ),
        "zIndex": 10,
    }


def _context_panel(draft: ProcessMapDraft, x: int, y: int, *, first_step_id: str) -> tuple[list[dict], list[dict]]:
    shapes: list[dict] = [
        _text_shape("context_title", x, y - 52, 300, 36, "<b>Governance Context</b>"),
    ]
    lines: list[dict] = []
    context_specs = [
        ("controls", "Controls", draft.controls, "#fff7ed", "#ea580c"),
        ("systems", "Systems", draft.systems, "#eff6ff", "#2563eb"),
        ("deps", "Dependencies", draft.dependencies, "#f7fee7", "#65a30d"),
    ]
    block_y = y
    for key, title, items, fill, stroke in context_specs:
        if not items:
            continue
        height = min(210, 70 + 22 * min(len(items), 6))
        shape_id = f"{key}_block"
        shapes.append(_list_shape(shape_id, title, items, x, block_y, 300, height, fill, stroke))
        if first_step_id:
            lines.append(_context_line(f"{key}_line", shape_id, first_step_id))
        block_y += height + 24

    for index, decision in enumerate(draft.open_decisions, start=1):
        shape_id = f"decision_{index}"
        shapes.append(
            {
                "id": shape_id,
                "type": "decision",
                "boundingBox": {"x": x + 30, "y": block_y, "w": 240, "h": 110},
                "style": _style("#fdf2f8", "#db2777", rounding=0),
                "text": f"<b>Validate</b><br/>{_html(decision)}",
                "customData": [
                    {"key": "category", "value": "open_decision"},
                    {"key": "process_id", "value": draft.process_id},
                ],
                "note": f"Open decision extracted from business rules.\n\n{decision}",
                "zIndex": 9,
            }
        )
        if first_step_id:
            lines.append(_step_to_context_line(f"decision_line_{index}", first_step_id, shape_id))
        block_y += 134
    return shapes, lines


def _step_line(
    index: int,
    source_id: str,
    target_id: str,
    label: str,
    source_box: tuple[int, int],
    target_box: tuple[int, int],
) -> dict:
    _, source_y = source_box
    _, target_y = target_box
    if target_y > source_y:
        endpoint1 = _shape_endpoint(source_id, "bottom", "none")
        endpoint2 = _shape_endpoint(target_id, "top", "arrow")
    else:
        endpoint1 = _shape_endpoint(source_id, "right", "none")
        endpoint2 = _shape_endpoint(target_id, "left", "arrow")
    return {
        "id": f"flow_{index}",
        "lineType": "elbow",
        "endpoint1": endpoint1,
        "endpoint2": endpoint2,
        "stroke": {"color": "#475569", "width": 2, "style": "solid"},
        "text": [{"text": _truncate(label or "next", 40), "position": 0.5, "side": "middle"}],
        "customData": [
            {"key": "source_step", "value": source_id},
            {"key": "target_step", "value": target_id},
        ],
        "zIndex": 3,
    }


def _context_line(line_id: str, source_id: str, target_id: str, *, dashed: bool = True) -> dict:
    return {
        "id": line_id,
        "lineType": "straight",
        "endpoint1": _shape_endpoint(source_id, "left", "none"),
        "endpoint2": _shape_endpoint(target_id, "right", "arrow"),
        "stroke": {"color": "#94a3b8", "width": 1, "style": "dashed" if dashed else "solid"},
        "zIndex": 2,
    }


def _step_to_context_line(line_id: str, source_id: str, target_id: str) -> dict:
    return {
        "id": line_id,
        "lineType": "straight",
        "endpoint1": _shape_endpoint(source_id, "right", "none"),
        "endpoint2": _shape_endpoint(target_id, "left", "arrow"),
        "stroke": {"color": "#db2777", "width": 1, "style": "solid"},
        "zIndex": 2,
    }


def _shape_endpoint(shape_id: str, side: str, style: str) -> dict:
    positions = {
        "left": {"x": 0, "y": 0.5},
        "right": {"x": 1, "y": 0.5},
        "top": {"x": 0.5, "y": 0},
        "bottom": {"x": 0.5, "y": 1},
    }
    return {"type": "shapeEndpoint", "style": style, "shapeId": shape_id, "position": positions[side]}


def _text_shape(shape_id: str, x: int, y: int, w: int, h: int, text: str, *, note: str = "") -> dict:
    shape = {
        "id": shape_id,
        "type": "text",
        "boundingBox": {"x": x, "y": y, "w": w, "h": h},
        "text": text,
        "zIndex": 20,
    }
    if note:
        shape["note"] = note
    return shape


def _list_shape(shape_id: str, title: str, items: list[str], x: int, y: int, w: int, h: int, fill: str, stroke: str) -> dict:
    visible_items = items[:8]
    overflow = len(items) - len(visible_items)
    body = "<br/>".join(f"&#8226; {_html(item)}" for item in visible_items)
    if overflow > 0:
        body += f"<br/>+ {overflow} more"
    return {
        "id": shape_id,
        "type": "stickyNote",
        "boundingBox": {"x": x, "y": y, "w": w, "h": h},
        "style": _style(fill, stroke, rounding=10),
        "text": f"<b>{_html(title)}</b><br/>{body}",
        "customData": [{"key": "category", "value": title.lower()}],
        "note": "\n".join(items),
        "zIndex": 8,
    }


def _style(fill: str, stroke: str, *, rounding: int) -> dict:
    return {
        "fill": {"type": "color", "color": fill},
        "stroke": {"color": stroke, "width": 2, "style": "solid"},
        "rounding": rounding,
        "textColor": "#0f172a",
    }


def _multipart_body(
    *,
    fields: dict[str, str],
    file_field: str,
    filename: str,
    file_bytes: bytes,
) -> tuple[bytes, str]:
    boundary = f"----kp-lucid-{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for key, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"),
                f"{value}\r\n".encode("utf-8"),
            ]
        )
    chunks.extend(
        [
            f"--{boundary}\r\n".encode("utf-8"),
            (
                f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
                f"Content-Type: {LUCID_IMPORT_CONTENT_TYPE}\r\n\r\n"
            ).encode("utf-8"),
            file_bytes,
            b"\r\n",
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
    )
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _normalise_lucid_response(payload: dict) -> dict:
    flat = _flatten(payload)
    document_id = _first(flat, "id", "documentId", "document_id")
    edit_url = _first(flat, "editUrl", "edit_url", "url", "documentUrl", "document_url")
    view_url = _first(flat, "viewUrl", "view_url", "shareUrl", "share_url")
    if not edit_url and document_id:
        edit_url = f"https://lucid.app/lucidchart/{document_id}/edit"
    return {
        "document_id": document_id,
        "edit_url": edit_url,
        "view_url": view_url,
        "raw": payload,
    }


def _flatten(payload: dict) -> dict:
    flat = dict(payload)
    for value in payload.values():
        if isinstance(value, dict):
            flat.update(value)
    return flat


def _first(payload: dict, *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value:
            return str(value)
    return ""


def _subtitle(draft: ProcessMapDraft) -> str:
    parts = [
        f"Source: {_html(draft.source_title)}",
        f"Domain: {_html(draft.domain or 'n/a')}",
        f"Process: {_html(draft.process or 'n/a')}",
    ]
    return "<br/>".join(parts)


def _confidence_colors(confidence: str) -> tuple[str, str]:
    value = confidence.lower().strip()
    if value == "high":
        return "#ecfdf3", "#15803d"
    if value == "medium":
        return "#fff7ed", "#c2410c"
    if value == "low":
        return "#fff1f2", "#be123c"
    return "#eef4ff", "#2563eb"


def _looks_like_control(label: str) -> bool:
    value = label.lower()
    return any(term in value for term in ("must", "validation", "approval", "control", "review", "gate"))


def _note(lines: list[str]) -> str:
    return "\n".join(line for line in lines if line)


def _html(value: str) -> str:
    return html.escape(value or "", quote=True)


def _truncate(value: str, limit: int) -> str:
    compact = re.sub(r"\s+", " ", value or "").strip()
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 1)].rstrip() + "..."


def _safe_id(value: str, *, limit: int = 36) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.~-]+", "-", value).strip("-")
    return cleaned[:limit] or "id"
