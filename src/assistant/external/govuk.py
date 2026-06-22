"""GOV.UK Content API connector."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from .models import FetchedPublicContent

GOVUK_WEB_ROOT = "https://www.gov.uk"
GOVUK_CONTENT_API = "https://www.gov.uk/api/content"
USER_AGENT = "ai-knowledge-analytics-assistant/0.1 public-content-snapshot"


class GOVUKContentError(RuntimeError):
    """Raised when GOV.UK content cannot be fetched or parsed safely."""


class GOVUKRateLimitError(GOVUKContentError):
    """Raised when GOV.UK returns a rate-limit response."""


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"p", "li", "h1", "h2", "h3", "h4", "br"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)

    def text(self) -> str:
        lines = [" ".join(line.split()) for line in unescape(" ".join(self.parts)).splitlines()]
        return "\n".join(line for line in lines if line)


def govuk_content_path(url_or_path: str) -> str:
    """Convert a GOV.UK URL or path into a Content API path."""
    raw = url_or_path.strip()
    if not raw:
        raise GOVUKContentError("GOV.UK URL is required.")
    if raw.startswith("/"):
        path = raw
    else:
        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in {"www.gov.uk", "gov.uk"}:
            raise GOVUKContentError("Only public GOV.UK URLs can be snapshotted.")
        path = parsed.path
    if path.startswith("/api/content/"):
        path = path.removeprefix("/api/content")
    if not path or path == "/":
        raise GOVUKContentError("A specific GOV.UK content page path is required.")
    return path.rstrip("/")


def govuk_web_url(path: str) -> str:
    return f"{GOVUK_WEB_ROOT}{path}"


def extract_text_from_govuk_payload(payload: dict) -> str:
    details = payload.get("details") or {}
    chunks: list[str] = []
    for key in ("body", "introductory_paragraph"):
        value = details.get(key)
        if isinstance(value, str):
            chunks.append(value)
    for part in details.get("parts") or []:
        if not isinstance(part, dict):
            continue
        if isinstance(part.get("title"), str):
            chunks.append(f"<h2>{part['title']}</h2>")
        if isinstance(part.get("body"), str):
            chunks.append(part["body"])
    if not chunks and isinstance(payload.get("description"), str):
        chunks.append(payload["description"])
    parser = _TextExtractor()
    parser.feed("\n".join(chunks))
    text = parser.text()
    if not text:
        raise GOVUKContentError("GOV.UK response did not include extractable text.")
    return text


class GOVUKContentClient:
    """Fetches selected public GOV.UK content pages without sending internal data."""

    def __init__(self, fetch_json: Callable[[str], dict] | None = None, timeout: int = 20) -> None:
        self._fetch_json = fetch_json or self._fetch_json_from_network
        self.timeout = timeout

    def fetch(self, url_or_path: str) -> FetchedPublicContent:
        path = govuk_content_path(url_or_path)
        api_url = f"{GOVUK_CONTENT_API}{quote(path, safe='/-._~')}"
        payload = self._fetch_json(api_url)
        return self._content_from_payload(path, payload)

    def _fetch_json_from_network(self, api_url: str) -> dict:
        request = Request(api_url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read())
        except HTTPError as exc:
            if exc.code == 429:
                raise GOVUKRateLimitError("GOV.UK rate limit reached; try again later.") from exc
            raise GOVUKContentError(f"GOV.UK fetch failed with status {exc.code}.") from exc
        except (TimeoutError, URLError) as exc:
            raise GOVUKContentError("GOV.UK fetch failed; external service was unavailable.") from exc
        except json.JSONDecodeError as exc:
            raise GOVUKContentError("GOV.UK response was not valid JSON.") from exc

    def _content_from_payload(self, requested_path: str, payload: dict) -> FetchedPublicContent:
        base_path = str(payload.get("base_path") or requested_path)
        title = str(payload.get("title") or "").strip()
        if not title:
            raise GOVUKContentError("GOV.UK response did not include a title.")
        links = payload.get("links") or {}
        orgs = links.get("organisations") or []
        public_body = ""
        if orgs and isinstance(orgs[0], dict):
            public_body = str(orgs[0].get("title") or "")
        text = extract_text_from_govuk_payload(payload)
        update_date = str(payload.get("public_updated_at") or payload.get("updated_at") or "")
        return FetchedPublicContent(
            provider="govuk",
            url=govuk_web_url(base_path),
            title=title,
            public_body=public_body,
            content_id=str(payload.get("content_id") or ""),
            document_type=str(payload.get("document_type") or ""),
            locale=str(payload.get("locale") or ""),
            update_date=update_date,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            text=text,
            metadata={
                "api_base_path": base_path,
                "schema_name": str(payload.get("schema_name") or ""),
                "publishing_app": str(payload.get("publishing_app") or ""),
                "government_document_supertype": str(payload.get("government_document_supertype") or ""),
            },
        )
