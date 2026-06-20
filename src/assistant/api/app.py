"""FastAPI application for the Knowledge Platform control panel backend."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..sources.register import SourceRegister
from .auth import AuthService, auth_from_env
from .routes_auth import build_auth_router, make_require_auth
from .routes_sources import build_sources_router


def create_app(register: SourceRegister | None = None, auth: AuthService | None = None) -> FastAPI:
    app = FastAPI(title="Knowledge Platform API", version="0.1.0")

    # The control panel dev server (Vite) proxies /api to this backend; CORS is
    # permissive in this PoC but scoped to local development origins.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5200", "http://127.0.0.1:5200"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    data_dir = Path(os.environ.get("KP_DATA_DIR", "data"))
    registry = register or SourceRegister(data_dir)
    auth_service = auth or auth_from_env()
    app.state.register = registry
    app.state.auth = auth_service

    @app.get("/api/health")
    def health() -> dict:
        return {
            "status": "ok",
            "service": "knowledge-platform",
            "sources": len(registry.list()),
        }

    app.include_router(build_auth_router(auth_service))
    app.include_router(
        build_sources_router(registry, dependencies=[Depends(make_require_auth(auth_service))])
    )
    return app


# Module-level app for `uvicorn assistant.api.app:app --app-dir src`.
app = create_app()
