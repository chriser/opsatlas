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
