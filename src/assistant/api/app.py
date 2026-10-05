"""FastAPI application for the OpsAtlas control panel backend."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .. import settings
from ..analytics.event_store import AnalyticsEventStore
from ..analytics.feedback import AnswerFeedbackStore
from ..analytics.governance_history import build_governance_history, record_governance_snapshot
from ..analytics.log import UsageLog
from ..answer.generator import OllamaGenerator
from ..answer.service import AnswerService
from ..answer.validation import GroundednessValidator
from ..compliance.latest import ComplianceLatestReviewStore
from ..content.service import ContentService
from ..evidence.receipts import ReceiptStore
from ..external.registry import PublicContentRegistry
from ..governance.accepted import AcceptedStore
from ..governance.intelligence import KnowledgeIntelligence
from ..iam.policy import AuthorizationContext
from ..iam.service import IamError
from ..ingestion.store import SectionStore
from ..models.provider import provider_from_env
from ..observability.trace import AuditTrace
from ..ontology import (
    ActionsEngine,
    AgentRunStore,
    OntologyAgent,
    OntologyQueryService,
    OntologyStore,
    PendingActionStore,
    rebuild_ontology,
)
from ..process.registry import ProcessRegistry
from ..regulatory.review import RegulatoryReviewStore
from ..retrieval.embedder import EmbeddingCache
from ..retrieval.rerank import LLMReranker
from ..retrieval.rewrite import QueryRewriter
from ..retrieval.service import RetrievalService
from ..sources.register import SourceRegister
from ..sources.settle import stamp_unfingerprinted
from ..space_config import SpaceConfig
from ..space_statements import SpaceStatements, texts_of
from ..storage import WriteDoor, locked
from .access import DEFAULT_SPACE, AccessError, PrincipalMiddleware, by_method, derived_guard, need, public, source_guard
from .auth import AuthService, auth_from_env
from .routes_analytics import build_analytics_router
from .routes_ask import build_ask_router
from .routes_auth import build_auth_router
from .routes_avatar import build_avatar_router
from .routes_content import build_content_assets_router, build_content_router
from .routes_eam import build_eam_router
from .routes_external import build_external_sources_router
from .routes_feedback import build_feedback_router
from .routes_governance import build_governance_router
from .routes_iam import build_iam_router
from .routes_ingestion import build_ingestion_router
from .routes_observability import build_observability_router
from .routes_ontology import build_ontology_router
from .routes_process import build_process_router
from .routes_query import build_query_router
from .routes_regulatory import build_regulatory_router
from .routes_sources import build_sources_router
from .routes_statements import build_statements_router


def _load_dotenv(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def create_app(
    register: SourceRegister | None = None,
    auth: AuthService | None = None,
    retrieval: RetrievalService | None = None,
    answer: AnswerService | None = None,
    space_id: str | None = None,
    space_config: SpaceConfig | None = None,
) -> FastAPI:
    _load_dotenv()
    auth_service = auth or auth_from_env()
    # The API reference is a development aid: it is off in the secured mode (IAM F5).
    docs = {} if auth_service.legacy_login else {"docs_url": None, "redoc_url": None, "openapi_url": None}
    app = FastAPI(title="OpsAtlas API", version="0.1.0", **docs)
    app.state.space_id = space_id or DEFAULT_SPACE  # the knowledge space this core serves: the scope of its permissions

    @app.exception_handler(IamError)
    async def iam_error(request, exc: IamError):
        return JSONResponse({"detail": exc.message, "code": exc.code}, status_code=exc.status)

    @app.exception_handler(AccessError)
    async def access_error(request, exc: AccessError):
        return JSONResponse({"detail": exc.detail, "code": exc.code, "request_id": getattr(request.state, "request_id", "")},
                            status_code=exc.status_code, headers=exc.headers)

    # The door (REF S23, S7): a request that may change something takes the workspace's one lock once, here, before
    # any handler runs. A workspace that governs this core points it at the workspace's lock.
    app.add_middleware(WriteDoor, lock_path=lambda: app.state.write_lock, passes=DOOR_PASSES)
    # The control panel dev server (Vite) proxies /api to this backend; CORS is
    # permissive in this PoC but scoped to local development origins.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5200", "http://127.0.0.1:5200"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(PrincipalMiddleware)  # the person, visible to routes and services (REF S3)

    data_dir = Path(settings.get("KP_DATA_DIR"))
    registry = register or SourceRegister(data_dir)
    app.state.write_lock = registry.index_file  # this core's own, until a workspace governs it (REF S23, S7)
    config = space_config or SpaceConfig.load(registry.base_dir)  # the space's cues and refusal wording (ARCH H2)
    # Its fixed sentences are governed (REF S22): the space speaks their approved versions.
    statements = SpaceStatements(registry.base_dir)
    statements.sync(texts_of(config), adopt_new=statements.new)
    config = statements.governed(config)
    app.state.space_config = config
    app.state.space_statements = statements
    section_store = SectionStore(registry.base_dir)
    provider = provider_from_env()  # swappable LLM + embedding backend (env-configured)
    rewriter = QueryRewriter(provider) if settings.get("KP_QUERY_REWRITE") != "0" else None
    reranker = LLMReranker(provider) if settings.get("KP_RERANK") != "0" else None
    retrieval_service = retrieval or RetrievalService(
        registry,
        section_store,
        embedder=provider,
        cache=EmbeddingCache(registry.base_dir),
        rewriter=rewriter,
        reranker=reranker,
        min_similarity=float(settings.get("KP_MIN_SIMILARITY")),
    )
    usage_log = UsageLog(registry.base_dir)
    event_store = AnalyticsEventStore(registry.base_dir)
    audit_trace = AuditTrace(registry.base_dir)
    validator = GroundednessValidator(provider) if settings.get("KP_VALIDATE_GROUNDING") != "0" else None
    process_registry = ProcessRegistry(registry.base_dir)
    process_registry.build_from_sources(registry)  # populate from approved sources at startup
    ontology_store = OntologyStore(registry.base_dir / "ontology.db")
    compliance_latest_store = ComplianceLatestReviewStore(registry.base_dir)

    def rebuild_ontology_store() -> dict:
        return rebuild_ontology(registry, process_registry, compliance_latest_store, ontology_store)

    rebuild_ontology_store()
    actions_engine = ActionsEngine(ontology_store, base_dir=registry.base_dir)
    actions_engine.register_handler("rebuild_ontology", lambda context: {"accepted": True})
    actions_engine.register_side_effect("refresh_ontology_store", lambda context, result: rebuild_ontology_store())
    ontology_query = OntologyQueryService(ontology_store)
    agent_runs = AgentRunStore(registry.base_dir)
    pending_actions = PendingActionStore(registry.base_dir)
    ontology_agent = OntologyAgent(ontology_query, provider, store=agent_runs, audit_trace=audit_trace)
    public_registry = PublicContentRegistry(registry.base_dir)
    regulatory_reviews = RegulatoryReviewStore(registry.base_dir)
    answer_service = answer or AnswerService(
        retrieval_service, provider, usage_log=usage_log, validator=validator,
        audit_trace=audit_trace, model_info=provider.info(), process_registry=process_registry,
        ontology_query=ontology_query, event_store=event_store,
        space_config=config,
    )
    if getattr(answer_service, "usage_log", None) is None:
        answer_service.usage_log = usage_log
    if getattr(answer_service, "audit_trace", None) is None:
        answer_service.audit_trace = audit_trace
    if getattr(answer_service, "model_info", None) is None:
        answer_service.model_info = provider.info()
    if getattr(answer_service, "process_registry", None) is None:
        answer_service.process_registry = process_registry
    if getattr(answer_service, "ontology_query", None) is None:
        answer_service.ontology_query = ontology_query
    if getattr(answer_service, "event_store", None) is None:
        answer_service.event_store = event_store
    answer_service.space_id = app.state.space_id  # usage and traces say in which space a question was asked (REF S9)
    answer_service.statements = statements
    app.state.register = registry
    app.state.section_store = section_store
    app.state.auth = auth_service
    app.state.provider = provider
    app.state.retrieval = retrieval_service
    app.state.answer = answer_service
    app.state.analytics_events = event_store
    app.state.usage_log = usage_log  # the Sales workspace reads Tibi's turns into it (REF S20)
    app.state.public_content = public_registry
    app.state.regulatory_reviews = regulatory_reviews
    app.state.ontology = ontology_store
    app.state.rebuild_ontology = rebuild_ontology_store
    app.state.actions = actions_engine
    app.state.ontology_agent = ontology_agent
    app.state.pending_actions = pending_actions

    @app.get("/api/health", dependencies=[public("liveness only: no counts, no model details")])
    def health() -> dict:
        return {"status": "ok", "service": "knowledge-platform"}

    @app.get("/api/health/details", dependencies=[need("diagnostics.read")])
    def health_details() -> dict:
        details = {"status": "ok", "service": "knowledge-platform", "sources": len(registry.list()), "models": provider.info()}
        drift = getattr(app.state, "ontology_drift", None)
        if drift is not None:  # a workspace with a product ontology: is its copy still the seed (REF S22)?
            details["product_ontology"] = drift()
        return details

    app.include_router(build_auth_router(auth_service))
    app.include_router(build_iam_router(auth_service))
    app.include_router(build_sources_router(registry, event_store=event_store,
                                            dependencies=[*by_method(GET="documents.read", POST="sources.upload", DELETE="sources.delete"),
                                                          Depends(source_guard)],
                                            ontology_rebuilder=rebuild_ontology_store, section_store=section_store,
                                            forget_content=lambda sid, text: app.state.content.forget(sid, text)))
    app.include_router(build_ingestion_router(registry, section_store, event_store=event_store,
                                              dependencies=[*by_method(GET="documents.draft.read", POST="sources.ingest"),
                                                            Depends(source_guard)]))
    app.include_router(build_query_router(retrieval_service, dependencies=by_method(POST="knowledge.search")))
    app.include_router(build_ask_router(answer_service, dependencies=by_method(POST="knowledge.ask")))
    app.include_router(build_avatar_router(answer_service, dependencies=by_method(GET="avatar.use", POST="avatar.use")))
    accepted_store = AcceptedStore(registry.base_dir)
    governance_generator = None
    governance_llm_enabled = settings.get("KP_GOVERNANCE_LLM_ENABLED").strip().lower() in {"1", "true", "yes", "on"}
    governance_model = settings.get("KP_GOVERNANCE_LLM_MODEL").strip()
    if governance_llm_enabled and governance_model:
        governance_generator = OllamaGenerator(
            model=governance_model,
            base_url=settings.get("KP_OLLAMA_URL"),
            num_ctx=int(settings.get("KP_GOVERNANCE_LLM_NUM_CTX", settings.get("KP_LLM_NUM_CTX"))),
            temperature=0.0,
            timeout=float(settings.get("KP_GOVERNANCE_LLM_TIMEOUT")),
            think=None, num_predict=None,  # the governance model keeps its own behaviour (H3a is about answers)
        )
    elif governance_llm_enabled:
        governance_generator = answer_service.generator
    intelligence = KnowledgeIntelligence(
        registry, section_store, retrieval_service.embedder, retrieval_service.cache,
        generator=governance_generator, accepted=accepted_store,
    )

    def record_analytics_event_side_effect(context, result: dict) -> dict:
        response: dict = {"recorded": False}
        event_payload = result.get("analytics_event") if isinstance(result, dict) else None
        if isinstance(event_payload, dict):
            payload = dict(event_payload)
            event_type = payload.pop("event_type")
            event_store.record(event_type, **payload)
            response["recorded"] = True
        report = result.get("governance_report") if isinstance(result, dict) else None
        if isinstance(report, dict):
            record_governance_snapshot(report, event_store)
            response["history"] = build_governance_history(event_store.events())
            response["recorded"] = True
        return response

    def refresh_process_registry_side_effect(context, result: dict) -> dict:
        records = process_registry.build_from_sources(registry)
        return {"status": "refreshed", "process_count": len(records)}

    actions_engine.register_side_effect("refresh_process_registry", refresh_process_registry_side_effect)
    actions_engine.register_side_effect("rebuild_ontology", lambda context, result: rebuild_ontology_store())
    actions_engine.register_side_effect("record_analytics_event", record_analytics_event_side_effect)
    app.include_router(build_governance_router(
        registry, intelligence, section_store=section_store, accepted=accepted_store,
        regulatory_reviews=regulatory_reviews, public_registry=public_registry,
        event_store=event_store, process_registry=process_registry,
        ontology_rebuilder=rebuild_ontology_store,
        actions=actions_engine,
        dependencies=[*by_method(GET="governance.read"), Depends(source_guard)],
    ))
    app.include_router(build_ontology_router(
        ontology_store,
        rebuild=rebuild_ontology_store,
        actions=actions_engine,
        agent=ontology_agent,
        proposals=pending_actions,
        event_store=event_store,
        dependencies=[*by_method(GET="ontology.read"), Depends(derived_guard)],
    ))
    app.include_router(build_eam_router(ontology_store, dependencies=[*by_method(GET="eam.read"), Depends(derived_guard)]))
    app.include_router(build_external_sources_router(
        public_registry,
        dependencies=by_method(GET="external_sources.read", DELETE="external_sources.delete", POST="external_sources.refresh")))
    app.include_router(build_regulatory_router(
        registry, section_store, regulatory_reviews, public_registry, event_store=event_store,
        dependencies=by_method(GET="regulatory.read"),
    ))
    app.include_router(build_process_router(registry, process_registry,
                                            dependencies=[*by_method(GET="processes.read"), Depends(derived_guard)]))
    app.include_router(build_analytics_router(
        usage_log, audit_trace=audit_trace, event_store=event_store, intelligence=intelligence,
        process_registry=process_registry, register=registry, ontology_store=ontology_store,
        actions=actions_engine, dependencies=by_method(GET="analytics.read"),
    ))
    app.include_router(build_feedback_router(usage_log, AnswerFeedbackStore(registry.base_dir), actions_engine, registry.base_dir))
    app.include_router(build_observability_router(audit_trace, dependencies=by_method(GET="diagnostics.traces.read")))
    # Content management: governed editing of any source (CM E1). A workspace adds its own hooks to app.state.content.
    content_service = ContentService(registry, section_store, actions=actions_engine, events=event_store)
    # A core on its own is governed too (REF S23, S7): its stores refuse a write from anything its door did not let
    # in. A workspace that governs it points all of them at the workspace's lock instead.
    for store in (registry, section_store, content_service.store):
        store.governed_by = app.state.write_lock

    def self_approval(person_id: str) -> bool:
        """REF S15: a person may publish a draft they wrote only in solo-operator mode, holding governance.self_approve.
        The legacy single-operator sign-in (tests, a lone core) is solo by construction."""
        if getattr(auth_service, "legacy_login", False):
            return True
        if not auth_service.iam.solo_operator(app.state.space_id):
            return False
        return bool(auth_service.iam.policy.evaluate(AuthorizationContext(principal_id=person_id), "governance.self_approve",
                                             space_id=app.state.space_id))

    content_service.self_approval = self_approval
    content_service.rebuild_facts = rebuild_ontology_store
    content_service.refresh_processes = lambda: process_registry.build_from_sources(registry)
    app.state.content = content_service
    iam = getattr(auth_service, "iam", None)
    if iam is not None and iam.holds is None:
        # Who holds a document or folder, for a restriction's change (Bug #2202): a lone core holds only its own space's.
        # A workspace that serves several spaces sets its own resolver over all of them.
        def holds(space_id: str, resource_type: str, resource_id: str) -> bool:
            if space_id != app.state.space_id:
                return False
            if resource_type == "document":
                return registry.get(resource_id) is not None
            return any(group["id"] == resource_id for group in content_service.store.groups())
        iam.holds = holds
    # Evidence receipts (REF S18): every source has a version from registration, every answer a stored receipt.
    answer_service.receipts = ReceiptStore(registry.base_dir)
    answer_service.version_of = content_service.current_version
    registry.on_add.append(content_service.first_version)
    with locked(app.state.write_lock):  # start-up is a job: it holds the lock like a request (REF S23, S7)
        content_service.ensure_all_versions()  # sources registered before receipts existed, once
        stamp_unfingerprinted(registry, section_store)  # passages stored before the staged publish, once (REF S23)
    app.include_router(build_content_router(content_service, dependencies=[*by_method(GET="documents.read"), Depends(source_guard)]))
    app.include_router(build_content_assets_router(content_service, dependencies=[need("assets.read")]))
    app.include_router(build_statements_router(app, registry.base_dir))  # governed fixed sentences (REF S22)
    return app


# Requests that change nothing a workspace's door guards (REF S23, S7): sign-in and access management (their own
# store), asks and searches, Tibi's check of a governance answer (it only reads; the independent review's R3), the
# avatar and Tibi's channel, service control and the activity log. They never wait for
# the lock, and the stores prove the list: a governed write from one of them is refused.
DOOR_PASSES = ("/api/auth", "/api/iam", "/api/ask", "/api/query", "/api/answers", "/api/avatar", "/api/sales/search",
               "/api/sales/governance/verify", "/api/tibi/ws-ticket", "/services/tibi", "/api/services", "/api/activity",
               "/api/process/diagrams/service")


# No module-level app (AUDIT F5): importing this module built a second core, with a stray iam.db in the data folder.
# To serve one core on its own: uvicorn --factory assistant.api.app:create_app --app-dir src
