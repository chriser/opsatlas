"""Every route, mount and socket is classified (IAM F5): public, human with permissions, service, or handler-checked."""
import os

from assistant.api.access import manifest, unclassified
from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.sources.register import SourceRegister

PUBLIC_CORE = {"GET /api/health", "GET /api/auth/csrf", "POST /api/auth/login", "POST /api/auth/logout",
               "POST /api/auth/password/forgot", "POST /api/auth/password/reset/preview", "POST /api/auth/password/reset",
               "POST /api/auth/invitations/preview", "POST /api/auth/invitations/accept"}


def test_the_core_has_no_unclassified_route_and_a_small_public_set(tmp_path):
    app = create_app(SourceRegister(tmp_path), AuthService("operator-pw"))
    assert unclassified(app) == []
    rows = manifest(app)
    public = {f"{r['method']} {r['path']}" for r in rows if r["kind"] == "public"}
    docs = {f"{m} {p}" for p in ("/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc") for m in ("GET", "HEAD")}
    assert public == PUBLIC_CORE | docs
    for row in rows:
        if row["kind"] == "human" and row["method"] not in ("GET", "HEAD", "OPTIONS"):
            assert row["permissions"] or row["note"], row
    assert {"GET /docs", "GET /openapi.json"} & {f"{r['method']} {r['path']}" for r in rows}  # the development core keeps its docs


def test_the_sales_workspace_and_every_space_core_are_classified(tmp_path, monkeypatch):
    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    os.environ["SME_TIBI_VOICE_URL"] = "http://127.0.0.1:9"
    app = create_sales_app(tmp_path / "sales")
    assert unclassified(app) == []
    for space, core in app.state.cores.items():
        assert unclassified(core) == [], space
    rows = {f"{r['method']} {r['path']}": r for r in manifest(app)}
    assert rows["GET /{path:path}"]["kind"] == "public"
    assert rows["GET /api/sales/knowledge"]["kind"] == "service"
    assert rows["POST /api/services/restart"]["permissions"] == ["platform.services.restart"]
    assert rows["WEBSOCKET /services/tibi/api/conversation/{identifier}"]["permissions"] == ["tibi.voice.use"]
    assert rows["POST /api/tibi/ws-ticket"]["permissions"] == ["tibi.voice.use"]
    assert "GET /docs" not in rows and "GET /openapi.json" not in rows  # no API reference in the secured mode
