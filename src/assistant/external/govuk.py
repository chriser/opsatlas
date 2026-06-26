"""Public UK government content connectors."""

from __future__ import annotations

import json
import re
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
GOVUK_HOSTS = {"www.gov.uk", "gov.uk"}
LEGISLATION_WEB_ROOT = "https://www.legislation.gov.uk"
LEGISLATION_HOSTS = {"www.legislation.gov.uk", "legislation.gov.uk"}
SUPPORTED_PUBLIC_HOSTS = GOVUK_HOSTS | LEGISLATION_HOSTS
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


class _HTMLSnapshotExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self._skip_depth = 0
        self._in_title = False
        self._in_h1 = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        if tag == "title":
            self._in_title = True
        if tag == "h1":
            self._in_h1 = True
        if tag in {"p", "li", "h1", "h2", "h3", "h4", "br", "tr", "th", "td"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag == "title":
            self._in_title = False
        if tag == "h1":
            self._in_h1 = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = data.strip()
        if not text:
            return
        self.parts.append(text)
        if self._in_title:
            self.title_parts.append(text)
        if self._in_h1:
            self.h1_parts.append(text)

    def text(self) -> str:
        lines = [" ".join(line.split()) for line in unescape(" ".join(self.parts)).splitlines()]
        return "\n".join(line for line in lines if line)

    def title(self) -> str:
        h1 = " ".join(self.h1_parts).strip()
        title = " ".join(self.title_parts).strip()
        return h1 or title


def public_source_provider(url_or_path: str) -> str:
    raw = url_or_path.strip()
    if raw.startswith("/"):
        return "govuk"
    host = (urlparse(raw).netloc or "").lower()
    if host in LEGISLATION_HOSTS:
        return "legislation"
    return "govuk"


def is_supported_public_source_url(url_or_path: str) -> bool:
    raw = url_or_path.strip()
    if raw.startswith("/"):
        return True
    parsed = urlparse(raw)
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() in SUPPORTED_PUBLIC_HOSTS


def govuk_content_path(url_or_path: str) -> str:
    """Convert a GOV.UK URL or path into a Content API path."""
    raw = url_or_path.strip()
    if not raw:
        raise GOVUKContentError("GOV.UK URL is required.")
    if raw.startswith("/"):
        path = raw
    else:
        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in GOVUK_HOSTS:
            raise GOVUKContentError("Only supported public UK government URLs can be snapshotted.")
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
    """Fetches selected public UK government content pages without sending internal data."""

    def __init__(
        self,
        fetch_json: Callable[[str], dict] | None = None,
        fetch_html: Callable[[str], str] | None = None,
        timeout: int = 20,
    ) -> None:
        self._fetch_json = fetch_json or self._fetch_json_from_network
        self._fetch_html = fetch_html or self._fetch_html_from_network
        self.timeout = timeout

    def fetch(self, url_or_path: str) -> FetchedPublicContent:
        if _is_legislation_url(url_or_path):
            return self._fetch_legislation(url_or_path)
        path = govuk_content_path(url_or_path)
        api_url = f"{GOVUK_CONTENT_API}{quote(path, safe='/-._~')}"
        payload = self._fetch_json(api_url)
        return self._content_from_payload(path, payload)

    def _fetch_legislation(self, url: str) -> FetchedPublicContent:
        canonical_url = _legislation_url(url)
        html_text = self._fetch_html(canonical_url)
        extractor = _HTMLSnapshotExtractor()
        extractor.feed(html_text)
        text = extractor.text()
        if not text:
            raise GOVUKContentError("Legislation page did not include extractable text.")
        title = _clean_page_title(extractor.title())
        if not title:
            raise GOVUKContentError("Legislation page did not include a title.")
        return FetchedPublicContent(
            provider="legislation",
            url=canonical_url,
            title=title,
            public_body="The National Archives",
            document_type="legislation",
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            text=text,
            metadata={
                "source_host": urlparse(canonical_url).netloc,
                "source_type": "legislation.gov.uk",
            },
        )

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

    def _fetch_html_from_network(self, url: str) -> str:
        request = Request(url, headers={"Accept": "text/html", "User-Agent": USER_AGENT})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return response.read().decode("utf-8", "replace")
        except HTTPError as exc:
            if exc.code == 429:
                raise GOVUKRateLimitError("Public source rate limit reached; try again later.") from exc
            raise GOVUKContentError(f"Public source fetch failed with status {exc.code}.") from exc
        except (TimeoutError, URLError) as exc:
            raise GOVUKContentError("Public source fetch failed; external service was unavailable.") from exc

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


def _is_legislation_url(url_or_path: str) -> bool:
    raw = url_or_path.strip()
    if raw.startswith("/"):
        return False
    parsed = urlparse(raw)
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() in LEGISLATION_HOSTS


def _legislation_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in LEGISLATION_HOSTS:
        raise GOVUKContentError("Only supported public UK government URLs can be snapshotted.")
    path = parsed.path.rstrip("/")
    if not path:
        raise GOVUKContentError("A specific legislation.gov.uk page path is required.")
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{LEGISLATION_WEB_ROOT}{path}{query}"


def _clean_page_title(value: str) -> str:
    title = " ".join(value.split())
    title = re.sub(r"\s*\|\s*legislation\.gov\.uk\s*$", "", title, flags=re.IGNORECASE)
    return title.strip()
