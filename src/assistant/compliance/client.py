"""HTTP client for the standalone compliance reasoning service."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ComplianceReasoningUnavailable(RuntimeError):
    """Raised when the compliance reasoning service cannot be reached."""


class ComplianceReasoningClient:
    def __init__(self, base_url: str = "", timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def capabilities(self) -> dict[str, Any]:
        return self._request("GET", "/v1/capabilities")

    def create_review(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v1/reviews", payload)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.enabled:
            raise ComplianceReasoningUnavailable("Compliance reasoning service URL is not configured.")
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=data,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            raise ComplianceReasoningUnavailable(f"Compliance reasoning service failed with status {exc.code}: {detail}") from exc
        except (TimeoutError, URLError, json.JSONDecodeError) as exc:
            raise ComplianceReasoningUnavailable("Compliance reasoning service is unavailable.") from exc
