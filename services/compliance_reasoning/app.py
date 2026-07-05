"""FastAPI app for the standalone compliance reasoning microservice."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from threading import Thread

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .agent import AgenticComplianceEngine, OllamaComplianceEmbedder, OllamaComplianceGenerator
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
                "POST /v1/reviews/{job_id}/cancel",
            ],
            supported_findings=[
                "supported",
                "contradiction",
                "missing_obligation",
                "missing_detail",
                "duplicate",
                "too_vague",
                "outdated",
                "unsupported_claim",
                "not_related",
                "needs_human_review",
            ],
            modes=getattr(service_engine, "modes", ["queued-pairwise-review", "deterministic-fallback"]),
            model_backends=getattr(service_engine, "model_backends", ["deterministic-fallback"]),
            notes=[
                (
                    "Reviews are queued and processed pairwise: external_vs_internal checks each external document "
                    "against each internal document; internal_vs_internal checks each unique internal source pair."
                ),
                (
                    "Operator review depth is quick scan or full review; balanced remains available as an internal "
                    "same-obligation screen and explicit benchmark/API compatibility profile."
                ),
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
        review_store.create_status(
            job_id,
            pairs,
            review_mode=request.review_mode,
            review_depth=request.options.review_depth,
            throttle_deep=request.options.throttle_deep,
        )
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

    @app.post("/v1/reviews/{job_id}/cancel", response_model=ReviewStatus)
    def cancel_review(job_id: str) -> ReviewStatus:
        status = review_store.request_cancel(job_id)
        if status is None:
            raise HTTPException(status_code=404, detail=f"Review job {job_id} was not found.")
        return status

    return app


def _engine_from_env() -> DeterministicComplianceEngine:
    enabled = os.environ.get("KP_COMPLIANCE_AGENT_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return DeterministicComplianceEngine()
    base_url = os.environ.get("KP_OLLAMA_URL", "http://127.0.0.1:11434")
    balanced_model = os.environ.get("KP_COMPLIANCE_BALANCED_LLM_MODEL", "deepseek-r1:8b")
    deep_model = os.environ.get("KP_COMPLIANCE_DEEP_LLM_MODEL", os.environ.get("KP_COMPLIANCE_LLM_MODEL", "qwen2.5:14b-instruct"))
    balanced_generator = _ollama_generator_from_env(
        "BALANCED",
        base_url=base_url,
        model=balanced_model,
        default_num_ctx=int(os.environ.get("KP_COMPLIANCE_BALANCED_LLM_NUM_CTX", "4096")),
        default_timeout=float(
            os.environ.get("KP_COMPLIANCE_BALANCED_LLM_TIMEOUT", os.environ.get("KP_COMPLIANCE_LLM_TIMEOUT", "120"))
        ),
    )
    deep_num_ctx = os.environ.get(
        "KP_COMPLIANCE_DEEP_LLM_NUM_CTX",
        os.environ.get("KP_COMPLIANCE_LLM_NUM_CTX", os.environ.get("KP_LLM_NUM_CTX", "8192")),
    )
    deep_generator = _ollama_generator_from_env(
        "DEEP",
        base_url=base_url,
        model=deep_model,
        default_num_ctx=int(deep_num_ctx),
        default_timeout=float(os.environ.get("KP_COMPLIANCE_DEEP_LLM_TIMEOUT", os.environ.get("KP_COMPLIANCE_LLM_TIMEOUT", "120"))),
        throttle_enabled=os.environ.get("KP_COMPLIANCE_DEEP_THROTTLE", "0").strip().lower() in {"1", "true", "yes", "on"},
    )
    throttled_deep_generator = _ollama_generator_from_env(
        "DEEP_THROTTLED",
        base_url=base_url,
        model=deep_model,
        default_num_ctx=int(os.environ.get("KP_COMPLIANCE_DEEP_THROTTLED_LLM_NUM_CTX", "4096")),
        default_timeout=float(os.environ.get("KP_COMPLIANCE_DEEP_LLM_TIMEOUT", os.environ.get("KP_COMPLIANCE_LLM_TIMEOUT", "120"))),
        throttle_enabled=True,
    )
    embedder = _embedder_from_env(base_url)
    return AgenticComplianceEngine(
        generator=deep_generator,
        model_name=deep_model,
        depth_generators={"balanced": balanced_generator, "deep": deep_generator, "deep_throttled": throttled_deep_generator},
        depth_model_names={"fast": "", "balanced": balanced_model, "deep": deep_model, "deep_throttled": deep_model},
        embedder=embedder,
        min_semantic_candidate_score=float(os.environ.get("KP_COMPLIANCE_SEMANTIC_CANDIDATE_SCORE", "0.58")),
    )


def _ollama_generator_from_env(
    profile: str,
    *,
    base_url: str,
    model: str,
    default_num_ctx: int,
    default_timeout: float,
    throttle_enabled: bool = False,
) -> OllamaComplianceGenerator:
    prefix = f"KP_COMPLIANCE_{profile}_LLM"
    options: dict[str, int | float | str | bool] = {}
    default_batch = "16" if throttle_enabled else ""
    default_num_gpu = "0" if throttle_enabled else ""
    default_num_thread = "4" if throttle_enabled else ""
    for env_name, option_name in (
        (f"{prefix}_NUM_BATCH", "num_batch"),
        (f"{prefix}_NUM_GPU", "num_gpu"),
        (f"{prefix}_NUM_THREAD", "num_thread"),
    ):
        value = os.environ.get(env_name)
        if value is None and option_name == "num_batch" and default_batch:
            value = default_batch
        if value is None and option_name == "num_gpu" and default_num_gpu:
            value = default_num_gpu
        if value is None and option_name == "num_thread" and default_num_thread:
            value = default_num_thread
        if value is None or value == "":
            continue
        try:
            options[option_name] = int(value)
        except ValueError:
            continue
    return OllamaComplianceGenerator(
        base_url=base_url,
        model=model,
        num_ctx=int(os.environ.get(f"{prefix}_NUM_CTX", str(default_num_ctx))),
        timeout=float(os.environ.get(f"{prefix}_TIMEOUT", str(default_timeout))),
        extra_options=options,
        cooldown_seconds=float(os.environ.get(f"{prefix}_COOLDOWN_SECONDS", "3" if throttle_enabled else "0")),
    )


def _cache_from_env() -> PairResultCache:
    path = os.environ.get("KP_COMPLIANCE_PAIR_CACHE_PATH")
    if not path:
        cache_dir = os.environ.get("KP_COMPLIANCE_CACHE_DIR", "data")
        path = str(Path(cache_dir) / "compliance_reasoning_pair_cache.json")
    return PairResultCache(path)


def _embedder_from_env(base_url: str) -> OllamaComplianceEmbedder | None:
    enabled = os.environ.get("KP_COMPLIANCE_EMBEDDINGS_ENABLED", "1").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return None
    return OllamaComplianceEmbedder(
        base_url=base_url,
        model=os.environ.get("KP_COMPLIANCE_EMBED_MODEL", os.environ.get("KP_EMBED_MODEL", "nomic-embed-text")),
        timeout=float(os.environ.get("KP_COMPLIANCE_EMBED_TIMEOUT", "30")),
    )


app = create_app()
