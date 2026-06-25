"""Process registry parser + store tests (deterministic, no LLM)."""

from assistant.process.parser import parse_process
from assistant.process.registry import ProcessRegistry
from assistant.sources.register import SourceRegister
from assistant.sources.service import register_upload

PACK = """# Anonymised Learning Pack 1 – End-to-End Supplier Setup Process

## 3. Roles and responsibilities

| Role | Responsibility |
|---|---|
| Buyer | Identifies the need and completes the form. |
| Trading support team | Reviews the request. |

## 4. Key business rules

- Due diligence and credit checks are gating controls.
- A supplier should not be active until readiness controls are in place.

## 5. Systems and data dependencies

| System / dependency | Purpose | Key data | Notes |
|---|---|---|---|
| Operational master data tool | Supplier creation. | Supplier code. | n/a |
| Finance master data environment | Finance creation. | Finance ID. | n/a |

## 8. JSON-style learning records

```json
{"record_id":"SUP_PROC_001","topic":"trigger","role":"buyer","rule":"setup starts with a request","confidence":"high"}
{"record_id":"SUP_PROC_002","topic":"gate","role":"trading_support","rule":"checks must pass","confidence":"high"}
```

## 9. Suggested tagging structure

- `domain: supplier-onboarding`
- `process: end-to-end-setup`
- `capability: master-data`
- `dependency: finance-mapping`
- `control: status-gating`
"""

ARTICLE_PACK = """# Anonymised Learning Pack 2 - Article Setup and Tax Handling Process

## 3. Roles and responsibilities

| Role | Responsibility |
|---|---|
| Article team | Completes article setup and checks readiness. |
| Tax operations team | Maintains tax handling rules. |

## 4. Key business rules

- A new article cannot be activated until mandatory fields and tax handling have passed validation.
- Tax handling exceptions must be reviewed before article activation.

## 5. Systems and data dependencies

| System / dependency | Purpose | Key data | Notes |
|---|---|---|---|
| Article master data tool | Article setup. | Article code. | n/a |
| Tax parameter register | Tax handling validation. | Tax code. | n/a |

## 8. JSON-style learning records

```json
{"record_id":"ART_001","topic":"activation gate","role":"article_team","rule":"activation waits for tax validation","confidence":"high"}
{"record_id":"ART_PROC_002","topic":"exception review","role":"tax_operations","rule":"tax exceptions need review","confidence":"high"}
```

## 9. Suggested tagging structure

- `domain: article-setup`
- `process: tax-handling`
- `capability: product-master-data`
- `dependency: tax-parameter-register`
- `control: activation-gating`
- `control: exception-review`
"""


def test_parse_process_extracts_structured_fields():
    p = parse_process("s1", "Pack 1: Supplier Setup", PACK)
    assert p.name == "End-to-End Supplier Setup Process"
    assert p.domain == "supplier-onboarding" and p.process == "end-to-end-setup"
    assert p.roles == ["Buyer", "Trading support team"]
    assert p.systems == ["Operational master data tool", "Finance master data environment"]
    assert "finance-mapping" in p.dependencies and "status-gating" in p.controls
    assert "master-data" in p.capabilities
    assert len(p.business_rules) == 2
    assert len(p.rules) == 2 and p.rules[0].role == "buyer" and p.rules[1].topic == "gate"


def test_missing_sections_yield_empty_lists():
    p = parse_process("s2", "Bare", "# Just A Title\n\nSome prose with no structured sections.")
    assert p.name == "Just A Title"
    assert p.roles == [] and p.systems == [] and p.rules == [] and p.domain == ""


def test_router_matches_relevant_process_else_none():
    from assistant.process.router import match_process

    p = parse_process("s1", "Pack 1", PACK)
    assert match_process("who owns the supplier setup process?", [p]) is p  # supplier/setup overlap
    assert match_process("what is the weather today?", [p]) is None  # no overlap


def test_router_matches_controls_dependencies_and_rule_text():
    from assistant.process.router import match_process

    p = parse_process("s2", "Article setup", ARTICLE_PACK)
    query = "Which controls stop an article being activated before tax handling is complete?"
    assert match_process(query, [p]) is p


def test_process_evidence_text_lists_roles_and_systems():
    p = parse_process("s1", "Pack 1", PACK)
    txt = p.as_evidence_text()
    assert "Roles/owners:" in txt and "Buyer" in txt and "Operational master data tool" in txt


def test_registry_builds_from_approved_sources_only(tmp_path):
    reg = SourceRegister(tmp_path)
    approved = register_upload(reg, "p1.md", PACK.encode(), title="Pack 1")
    reg.update(approved.id, approval_status="approved")
    register_upload(reg, "p2.md", PACK.encode(), title="Pack 2 (pending)")  # not approved

    registry = ProcessRegistry(reg.base_dir)
    built = registry.build_from_sources(reg)
    assert len(built) == 1  # only the approved source
    assert registry.get(approved.id).name == "End-to-End Supplier Setup Process"
    assert [r.id for r in registry.list()] == [approved.id]


def test_answer_adds_process_facts_as_evidence_when_matched(tmp_path):
    from assistant.answer.service import AnswerService
    from assistant.ingestion.service import ingest_source
    from assistant.ingestion.store import SectionStore
    from assistant.retrieval.service import RetrievalService

    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    rec = register_upload(reg, "p1.md", PACK.encode(), title="Pack 1")
    ingest_source(reg, store, rec.id)
    reg.update(rec.id, approval_status="approved")
    pr = ProcessRegistry(reg.base_dir)
    pr.build_from_sources(reg)

    class Gen:
        last = ""

        def generate(self, prompt):
            self.last = prompt
            return "Buyer owns it [1]."

    gen = Gen()
    AnswerService(RetrievalService(reg, store), gen, process_registry=pr).answer("who owns the supplier setup process?")
    # The matched process's structured facts are injected into the prompt as extra evidence.
    assert "structured facts" in gen.last and "Roles/owners: Buyer" in gen.last


def test_answer_rebuilds_process_registry_before_matching_newly_approved_source(tmp_path):
    from assistant.answer.service import AnswerService
    from assistant.ingestion.service import ingest_source
    from assistant.ingestion.store import SectionStore
    from assistant.retrieval.service import RetrievalService

    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    rec = register_upload(reg, "article.md", ARTICLE_PACK.encode(), title="Article setup")
    ingest_source(reg, store, rec.id)
    reg.update(rec.id, approval_status="approved")
    pr = ProcessRegistry(reg.base_dir)

    class Gen:
        last = ""

        def generate(self, prompt):
            self.last = prompt
            return "Activation waits for tax handling validation [1]."

    gen = Gen()
    AnswerService(RetrievalService(reg, store), gen, process_registry=pr).answer(
        "Which controls stop an article being activated before tax handling is complete?"
    )

    assert "structured facts" in gen.last
    assert "Process: Article Setup and Tax Handling Process" in gen.last
    assert "activation-gating" in gen.last and "Tax parameter register" in gen.last


def test_read_endpoint_does_not_write_registry_and_approve_refreshes(tmp_path):
    from fastapi.testclient import TestClient

    from assistant.api.app import create_app
    from assistant.api.auth import AuthService
    from assistant.ingestion.store import SectionStore
    from assistant.retrieval.service import RetrievalService

    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    client = TestClient(create_app(reg, AuthService("pw"), retrieval=RetrievalService(reg, store)))
    token = client.post("/api/auth/login", json={"password": "pw"}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    rec = client.post("/api/sources/upload", files={"file": ("p1.md", PACK.encode(), "text/markdown")}, data={"title": "Pack 1"}).json()
    client.post(f"/api/sources/{rec['id']}/ingest")
    client.post(f"/api/governance/sources/{rec['id']}/approve")  # approve persists the registry

    reg_file = reg.base_dir / "process_registry.json"
    assert reg_file.exists()  # approve refreshed the persisted registry
    reg_file.unlink()
    out = client.get("/api/process/registry").json()  # pure read: derives, must not rewrite
    assert len(out) == 1 and not reg_file.exists()


def test_process_registry_endpoint(tmp_path):
    from fastapi.testclient import TestClient

    from assistant.api.app import create_app
    from assistant.api.auth import AuthService
    from assistant.ingestion.store import SectionStore
    from assistant.retrieval.service import RetrievalService

    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    client = TestClient(create_app(reg, AuthService("pw"), retrieval=RetrievalService(reg, store)))
    token = client.post("/api/auth/login", json={"password": "pw"}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    rec = client.post("/api/sources/upload", files={"file": ("p1.md", PACK.encode(), "text/markdown")}, data={"title": "Pack 1"}).json()
    client.post(f"/api/sources/{rec['id']}/ingest")
    client.post(f"/api/governance/sources/{rec['id']}/approve")

    out = client.get("/api/process/registry").json()
    assert len(out) == 1 and out[0]["name"] == "End-to-End Supplier Setup Process"
    assert client.get("/api/process/registry/nope").status_code == 404
