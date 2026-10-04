"""Shared test builders (REF S59): set state up through public requests, never by writing stores.

A test that writes `source_register.json`, `content.db` or the Sales records directly, or calls a store's update to
arrange state, is tied to internals: the workspace door alone made 129 such tests fail. A builder here arranges the
same state the way a person would, through the app's routes, so a change inside a component does not ripple through
the tests that only needed it as set-up.

Use the `sales_workspace` fixture (tests/conftest.py): a hermetic Sales app (network refused, models faked), signed in,
with one organisation space.
"""
from __future__ import annotations

import os
import socket
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from door_helpers import decide
from iam_helpers import sign_in
from test_space_leaks import hermetic, refuse


@dataclass
class Workspace:
    app: Any
    client: Any
    root: Path
    space: str

    def __iter__(self):  # unpacks as (app, client, root), the shape older tests use
        return iter((self.app, self.client, self.root))

    @property
    def headers(self) -> dict:
        return {"X-OpsAtlas-Space": self.space}

    @property
    def core(self):
        return self.app.state.cores[self.space]

    def document(self, text: bytes, filename: str = "pricing.md", title: str | None = None, approve: bool = True) -> str:
        """Upload, ingest and (by default) approve a document through the routes; its source id."""
        up = self.client.post("/api/sources/upload", files={"file": (filename, text, "text/markdown")},
                              data={"title": title} if title else None, headers=self.headers)
        assert up.status_code == 200, up.text
        body = up.json()
        source_id = body["id"] if "id" in body else body["source"]["id"]
        ingested = self.client.post(f"/api/sources/{source_id}/ingest", headers=self.headers)
        assert ingested.status_code == 200, ingested.text
        if approve:
            approved = decide(self.client, source_id, headers=self.headers)
            assert approved.status_code == 200, approved.text
        return source_id


@contextmanager
def sales_workspace(tmp_path: Path, monkeypatch, space_name: str = "Acme"):
    """A hermetic Sales app with a signed-in client and one organisation space."""
    from fastapi.testclient import TestClient

    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    os.environ["SME_TIBI_VOICE_URL"] = "http://127.0.0.1:9"
    os.environ["SALES_GOVERNANCE_AUTO_REVIEW"] = "0"
    root = tmp_path / "sales"
    app = create_sales_app(root)
    hermetic(app)
    with TestClient(app) as client:
        client.headers.update({"Authorization": f"Bearer {sign_in(client, app)}"})
        created = client.post("/api/spaces", json={"name": space_name})
        assert created.status_code == 200, created.text
        space = space_name.lower()
        hermetic(app.state.cores[space])
        yield Workspace(app, client, root, space)
