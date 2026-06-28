"""FastAPI app for the standalone compliance reasoning microservice."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from threading import Thread

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .agent import AgenticComplianceEngine, OllamaComplianceGenerator
from .cache import PairResultCache
from .engine import DeterministicComplianceEngine
from .models import (
    CapabilityResponse,
    ComplianceReviewRequest,
    ComplianceReviewResult,
    FindingListResponse,
    ReviewStatus,
)
from .store import ComplianceReviewStore


def create_app(
    engine: DeterministicComplianceEngine | None = None,
    store: ComplianceReviewStore | None = None,
    cache: PairResultCache | None = None,
) -> FastAPI:
    service_engine = engine or _engine_from_env()
    review_store = store or ComplianceReviewStore()
    pair_cache = cache if cache is not None else (_cache_from_env() if engine is None and store is None else None)
    app = FastAPI(title="Compliance Reasoning Service", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5200", "http://127.0.0.1:5200"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.engine = service_engine
    app.state.review_store = review_store
    app.state.pair_cache = pair_cache

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "service": "compliance-reasoning", "version": "0.1.0"}

    @app.get("/v1/capabilities", response_model=CapabilityResponse)
    def capabilities() -> CapabilityResponse:
        return CapabilityResponse(
            endpoints=[
                "GET /health",
                "GET /v1/capabilities",
                "POST /v1/reviews",
                "GET /v1/reviews/{job_id}",
                "GET /v1/reviews/{job_id}/findings",
            ],
            supported_findings=[
                "supported",
                "contradiction",
                "missing_obligation",
                "missing_detail",
                "too_vague",
                "outdated",
                "unsupported_claim",
                "not_related",
                "needs_human_review",
            ],
            modes=getattr(service_engine, "modes", ["queued-pairwise-review", "deterministic-fallback"]),
            model_backends=getattr(service_engine, "model_backends", ["deterministic-fallback"]),
            notes=[
                "Reviews are queued and processed pairwise: each external document is checked against each internal document.",
                "Current workflow suppresses unrelated pairs by default.",
                "Unchanged pair results are cached by source hashes, model, prompt and review options unless force_rerun is requested.",
                "No source approval state is mutated by this service.",
                getattr(
                    service_engine,
                    "capability_note",
                    "Deterministic fallback is enabled; long-context LLM adjudication is not enabled.",
                ),
            ],
        )

    @app.post("/v1/reviews", response_model=ComplianceReviewResult, status_code=202)
    def create_review(request: ComplianceReviewRequest) -> ComplianceReviewResult:
        job_id = f"cr-{uuid.uuid4().hex[:18]}"
        pairs = service_engine.prepare_pairs(request)
        review_store.create_status(job_id, pairs)
        worker = Thread(target=service_engine.run_queued_job, args=(job_id, request, review_store, pair_cache), daemon=True)
        worker.start()
        result = review_store.get_result(job_id)
        if result is None:
            raise HTTPException(status_code=500, detail=f"Review job {job_id} could not be queued.")
        return result

    @app.get("/v1/reviews/{job_id}", response_model=ReviewStatus)
    def review_status(job_id: str) -> ReviewStatus:
        status = review_store.get_status(job_id)
        if status is None:
            raise HTTPException(status_code=404, detail=f"Review job {job_id} was not found.")
        return status

    @app.get("/v1/reviews/{job_id}/findings", response_model=FindingListResponse)
    def review_findings(job_id: str) -> FindingListResponse:
        result = review_store.get_result(job_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Review job {job_id} was not found.")
        return FindingListResponse(job_id=job_id, status=result.status.status, findings=result.findings)

    return app


def _engine_from_env() -> DeterministicComplianceEngine:
    enabled = os.environ.get("KP_COMPLIANCE_AGENT_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return DeterministicComplianceEngine()
    model = os.environ.get("KP_COMPLIANCE_LLM_MODEL", "deepseek-r1:32b")
    generator = OllamaComplianceGenerator(
        base_url=os.environ.get("KP_OLLAMA_URL", "http://127.0.0.1:11434"),
        model=model,
        num_ctx=int(os.environ.get("KP_COMPLIANCE_LLM_NUM_CTX", os.environ.get("KP_LLM_NUM_CTX", "8192"))),
        timeout=float(os.environ.get("KP_COMPLIANCE_LLM_TIMEOUT", "120")),
    )
    return AgenticComplianceEngine(generator=generator, model_name=model)


def _cache_from_env() -> PairResultCache:
    path = os.environ.get("KP_COMPLIANCE_PAIR_CACHE_PATH")
    if not path:
        cache_dir = os.environ.get("KP_COMPLIANCE_CACHE_DIR", "data")
        path = str(Path(cache_dir) / "compliance_reasoning_pair_cache.json")
    return PairResultCache(path)


app = create_app()
