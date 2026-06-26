"""Upload handling for the source register.

Validates an uploaded document, builds its governance record, and registers it.
Anonymised/synthetic material only — no real or confidential source data.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .models import ALLOWED_EXTENSIONS, SourceRecord
from .register import SourceRegister
from .title import generate_source_title

MAX_BYTES = 25 * 1024 * 1024  # 25 MB upload ceiling for the proof of concept.


class UploadError(ValueError):
    """Raised when an upload is rejected (bad type, empty, too large)."""


def register_upload(
    register: SourceRegister,
    filename: str,
    content: bytes,
    title: str | None = None,
) -> SourceRecord:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise UploadError(f"Unsupported file type '{extension or filename}'. Allowed: {allowed}.")
    if not content:
        raise UploadError("The uploaded file is empty.")
    if len(content) > MAX_BYTES:
        raise UploadError("The uploaded file exceeds the 25 MB limit.")

    record = SourceRecord(
        id=uuid.uuid4().hex,
        filename=filename,
        title=generate_source_title(filename, content, title),
        size_bytes=len(content),
        content_sha256=hashlib.sha256(content).hexdigest(),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    return register.add(record, content)
