"""SVG made safe to insert into the control panel (REF S6).

The panel inserts process diagrams and activity-model canvases as markup, so anything executable in them would run
with the signed-in person's session. Their text comes from documents. Every SVG the core returns passes through
``safe_svg`` first: scripts, embedded HTML and frames, event-handler attributes and ``javascript:`` links are removed;
a document type or entity declaration is refused outright. What remains draws the same picture.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

SVG_NS, XLINK_NS = "http://www.w3.org/2000/svg", "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)

BLOCKED = {"script", "foreignobject", "iframe", "object", "embed", "handler", "listener", "use"}
LINKS = {"href", f"{{{XLINK_NS}}}href"}
UNSAFE_URL = re.compile(r"^\s*(javascript|vbscript|data\s*:\s*text/html)", re.I)
UNSAFE_STYLE = re.compile(r"javascript:|expression\s*\(|@import|behavior\s*:", re.I)
REFUSED = '<svg xmlns="http://www.w3.org/2000/svg" width="360" height="40"><text x="8" y="24">' \
          'This diagram could not be shown safely.</text></svg>'


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _clean(element: ET.Element) -> None:
    for child in list(element):
        name = _local(child.tag)
        animated = child.get("attributeName", "").lower()
        if name in BLOCKED or (name in {"set", "animate"} and animated in {"href", "xlink:href"}):
            element.remove(child)
            continue
        _clean(child)
    for attribute in list(element.attrib):
        value = element.attrib[attribute]
        local = _local(attribute)
        if local.startswith("on") or (attribute in LINKS and UNSAFE_URL.match(value.replace("\x00", ""))) \
                or (local == "style" and UNSAFE_STYLE.search(value)):
            del element.attrib[attribute]
    if _local(element.tag) == "style" and element.text and UNSAFE_STYLE.search(element.text):
        element.text = ""


def safe_svg(svg: str | None) -> str | None:
    """The SVG without anything that could run in the panel, or a plain notice when it cannot be read safely."""
    if not svg:
        return svg
    if re.search(r"<!(DOCTYPE|ENTITY)", svg, re.I):
        return REFUSED
    try:
        root = ET.fromstring(svg.lstrip("﻿").split("?>", 1)[-1] if svg.lstrip().startswith("<?xml") else svg)
    except ET.ParseError:
        return REFUSED
    if _local(root.tag) != "svg":
        return REFUSED
    _clean(root)
    return ET.tostring(root, encoding="unicode")
