"""FastAPI application for the Knowledge Platform control panel backend."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..analytics.log import UsageLog
from ..answer.service import AnswerService
from ..answer.validation import GroundednessValidator
from ..governance.intelligence import KnowledgeIntelligence
from ..ingestion.store import SectionStore
from ..models.provider import provider_from_env
from ..retrieval.embedder import EmbeddingCache
from ..retrieval.rerank import LLMReranker
from ..retrieval.rewrite import QueryRewriter
from ..retrieval.service import RetrievalService
from ..sources.register import SourceRegister
from .auth import AuthService, auth_from_env
from .routes_analytics import build_analytics_router
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
    provider = provider_from_env()  # swappable LLM + embedding backend (env-configured)
    rewriter = QueryRewriter(provider) if os.environ.get("KP_QUERY_REWRITE", "1") != "0" else None
    reranker = LLMReranker(provider) if os.environ.get("KP_RERANK", "1") != "0" else None
    retrieval_service = retrieval or RetrievalService(
        registry,
        section_store,
        embedder=provider,
        cache=EmbeddingCache(registry.base_dir),
        rewriter=rewriter,
        reranker=reranker,
        min_similarity=float(os.environ.get("KP_MIN_SIMILARITY", "0.45")),
    )
    usage_log = UsageLog(registry.base_dir)
    validator = GroundednessValidator(provider) if os.environ.get("KP_VALIDATE_GROUNDING", "1") != "0" else None
    answer_service = answer or AnswerService(
        retrieval_service, provider, usage_log=usage_log, validator=validator
    )
    app.state.register = registry
    app.state.section_store = section_store
    app.state.auth = auth_service
    app.state.provider = provider
    app.state.retrieval = retrieval_service
    app.state.answer = answer_service

    @app.get("/api/health")
    def health() -> dict:
        return {
            "status": "ok",
            "service": "knowledge-platform",
            "sources": len(registry.list()),
            "models": provider.info(),
        }

    protected = [Depends(make_require_auth(auth_service))]
    app.include_router(build_auth_router(auth_service))
    app.include_router(build_sources_router(registry, dependencies=protected))
    app.include_router(build_ingestion_router(registry, section_store, dependencies=protected))
    app.include_router(build_query_router(retrieval_service, dependencies=protected))
    app.include_router(build_ask_router(answer_service, dependencies=protected))
    intelligence = KnowledgeIntelligence(
        registry, section_store, retrieval_service.embedder, retrieval_service.cache,
        generator=answer_service.generator,
    )
    app.include_router(build_governance_router(registry, intelligence, dependencies=protected))
    app.include_router(build_analytics_router(usage_log, dependencies=protected))
    return app


# Module-level app for `uvicorn assistant.api.app:app --app-dir src`.
app = create_app()
