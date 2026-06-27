"""FastAPI app for the standalone compliance reasoning microservice."""

from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

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
) -> FastAPI:
    service_engine = engine or DeterministicComplianceEngine()
    review_store = store or ComplianceReviewStore()
    app = FastAPI(title="Compliance Reasoning Service", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5200", "http://127.0.0.1:5200"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.engine = service_engine
    app.state.review_store = review_store

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
                "too_vague",
                "outdated",
                "unsupported_claim",
                "needs_human_review",
            ],
            notes=[
                "Current engine is deterministic baseline only.",
                "No source approval state is mutated by this service.",
                "Model-backed extraction, retrieval, NLI and LLM adjudication are planned follow-on capabilities.",
            ],
        )

    @app.post("/v1/reviews", response_model=ComplianceReviewResult, status_code=202)
    def create_review(request: ComplianceReviewRequest) -> ComplianceReviewResult:
        job_id = f"cr-{uuid.uuid4().hex[:18]}"
        status = review_store.create_status(job_id)
        result = service_engine.run(job_id, request, created_at=status.created_at)
        return review_store.save(result)

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


app = create_app()
