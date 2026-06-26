"""Shared helpers for local avatar runtime wrappers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RuntimeWrapperError(RuntimeError):
    """Raised when a local model wrapper cannot run safely."""


def read_text(path: Path) -> str:
    if not path.exists():
        raise RuntimeWrapperError(f"Input text file does not exist: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeWrapperError(f"Input text file is blank: {path}")
    return text


def load_profile(data_root: Path, profile_type: str, profile_id: str) -> dict[str, Any]:
    profile_path = data_root / f"{profile_type}_profiles" / f"{profile_id}.json"
    if not profile_path.exists():
        raise RuntimeWrapperError(
            f"Missing {profile_type} profile {profile_id!r}. Expected JSON profile at {profile_path}."
        )
    try:
        data = json.loads(profile_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeWrapperError(f"Invalid JSON profile at {profile_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeWrapperError(f"Profile must be a JSON object: {profile_path}")
    return data


def require_file(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.exists() or not resolved.is_file():
        raise RuntimeWrapperError(f"{label} does not exist or is not a file: {resolved}")
    return resolved


def require_dir(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise RuntimeWrapperError(f"{label} does not exist or is not a directory: {resolved}")
    return resolved


def configured_path(env_value: str | None, arg_value: str, label: str) -> Path:
    configured = (env_value or "").strip() or arg_value.strip()
    if not configured:
        raise RuntimeWrapperError(f"{label} must be configured.")
    return Path(configured)
