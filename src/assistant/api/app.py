"""FastAPI application for the Knowledge Platform control panel backend."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..answer.generator import OllamaGenerator
from ..answer.service import AnswerService
from ..governance.intelligence import KnowledgeIntelligence
from ..ingestion.store import SectionStore
from ..retrieval.embedder import EmbeddingCache, OllamaEmbedder
from ..retrieval.service import RetrievalService
from ..sources.register import SourceRegister
from .auth import AuthService, auth_from_env
from .routes_ask import build_ask_router
from .routes_auth import build_auth_router, make_require_auth
from .routes_governance import build_governance_router
from .routes_ingestion import build_ingestion_router
from .routes_query import build_query_router
from .routes_sources import build_sources_router


def create_app(
    register: SourceRegister | None = None,
    auth: AuthService | None = None,
    retrieval: RetrievalService | None = None,
    answer: AnswerService | None = None,
) -> FastAPI:
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
    section_store = SectionStore(registry.base_dir)
    auth_service = auth or auth_from_env()
    retrieval_service = retrieval or RetrievalService(
        registry,
        section_store,
        embedder=OllamaEmbedder(),
        cache=EmbeddingCache(registry.base_dir),
    )
    answer_service = answer or AnswerService(retrieval_service, OllamaGenerator())
    app.state.register = registry
    app.state.section_store = section_store
    app.state.auth = auth_service
    app.state.retrieval = retrieval_service
    app.state.answer = answer_service

    @app.get("/api/health")
    def health() -> dict:
        return {
            "status": "ok",
            "service": "knowledge-platform",
            "sources": len(registry.list()),
        }

    protected = [Depends(make_require_auth(auth_service))]
    app.include_router(build_auth_router(auth_service))
    app.include_router(build_sources_router(registry, dependencies=protected))
    app.include_router(build_ingestion_router(registry, section_store, dependencies=protected))
    app.include_router(build_query_router(retrieval_service, dependencies=protected))
    app.include_router(build_ask_router(answer_service, dependencies=protected))
    intelligence = KnowledgeIntelligence(
        registry, section_store, retrieval_service.embedder, retrieval_service.cache
    )
    app.include_router(build_governance_router(registry, intelligence, dependencies=protected))
    return app


# Module-level app for `uvicorn assistant.api.app:app --app-dir src`.
app = create_app()
