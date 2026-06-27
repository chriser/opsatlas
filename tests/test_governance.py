"""Governance tests — knowledge intelligence + the approval gate (hermetic)."""

from fastapi.testclient import TestClient

from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.external.models import FetchedPublicContent
from assistant.governance.intelligence import KnowledgeIntelligence
from assistant.ingestion.sections import build_sections
from assistant.ingestion.store import SectionStore
from assistant.retrieval.service import RetrievalService
from assistant.sources.register import SourceRegister
from assistant.sources.service import register_upload

PASSWORD = "test-pass"


class IdenticalEmbedder:
    def embed(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]  # all identical -> cosine 1.0


class RelatedEmbedder:
    """Related but not duplicate: 'mandatory' vs 'optional' ~0.7 cosine."""

    def embed(self, texts):
        out = []
        for t in texts:
            tl = t.lower()
            out.append([1.0, 0.0, 0.0] if "mandatory" in tl else [0.7, 0.7, 0.0] if "optional" in tl else [0.0, 0.0, 1.0])
        return out


class ConflictGenerator:
    def generate(self, prompt):
        return "CONFLICT: one says mandatory, the other says optional."


def test_intelligence_flags_not_ingested(tmp_path):
    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    register_upload(reg, "a.txt", b"some content")  # registered, 0 sections
    report = KnowledgeIntelligence(reg, store).run()
    assert report["total_issues"] >= 1
    assert report["categories"]["compliance"] >= 1
    assert any(i["check"] == "not_ingested" for i in report["issues"]["compliance"])
    assert any("has not been ingested yet" in i["detail"] for i in report["issues"]["compliance"])


def test_intelligence_explains_failed_ingestion(tmp_path):
    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    rec = register_upload(reg, "a.md", b"# Heading only\n\n")
    reg.update(rec.id, processing_state="failed", section_count=0)

    report = KnowledgeIntelligence(reg, store).run()

    issue = next(i for i in report["issues"]["compliance"] if i["check"] == "not_ingested")
    assert "ingestion failed" in issue["detail"].lower()
    assert "usable sections" in issue["detail"].lower()


def test_structural_duplicates_suppressed_across_three_docs(tmp_path):
    from assistant.retrieval.embedder import EmbeddingCache

    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    body = "# H\n\nThis disclaimer and boilerplate appears in every uploaded document verbatim."
    for name in ("a.md", "b.md", "c.md"):
        rec = register_upload(reg, name, body.encode())
        store.replace_for_source(rec.id, build_sections(rec.id, body))
    report = KnowledgeIntelligence(reg, store, IdenticalEmbedder(), EmbeddingCache(reg.base_dir)).run()
    # Content in 3+ docs is boilerplate: dropped from the issue list, counted per source.
    assert not any(i["check"] == "duplicate" for i in report["issues"]["consistency"])
    assert sum(v["structural"] for v in report["source_summary"].values()) >= 3


def test_severity_and_health(tmp_path):
    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    register_upload(reg, "a.txt", b"some content")  # not_ingested -> high severity
    report = KnowledgeIntelligence(reg, store).run()
    issue = report["issues"]["compliance"][0]
    assert issue["severity"] == "high" and issue["score"] == 3
    assert report["health"] == "red"  # a high-severity issue is present


def test_health_green_when_clean(tmp_path):
    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    assert KnowledgeIntelligence(reg, store).run()["health"] == "green"


def test_text_checks_flag_acronym_locale_and_style(tmp_path):
    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    body = "# H\n\nThe ZZQ team must organize and organise the e-mail and email TODO list."
    rec = register_upload(reg, "x.md", body.encode())
    store.replace_for_source(rec.id, build_sections(rec.id, body))
    report = KnowledgeIntelligence(reg, store).run()
    checks = {i["check"] for v in report["issues"].values() for i in v}
    assert "undefined_acronym" in checks  # ZZQ has no definition
    assert "localisation" in checks  # organize + organise
    assert "content_style" in checks  # TODO + email/e-mail
    assert "undefined_acronym" in report["descriptions"]


def test_known_acronyms_not_flagged(tmp_path):
    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    body = "# H\n\nThe VAT and JSON and ID values are recorded in the API."
    rec = register_upload(reg, "y.md", body.encode())
    store.replace_for_source(rec.id, build_sections(rec.id, body))
    report = KnowledgeIntelligence(reg, store).run()
    assert not any(i["check"] == "undefined_acronym" for v in report["issues"].values() for i in v)


def test_acronym_definitions_work_before_or_after_expansion(tmp_path):
    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    body = (
        "# H\n\n"
        "The Responsible, Accountable, Consulted, Informed (RACI) model is used for role mapping.\n\n"
        "The SME (Subject Matter Expert) validates the final handover pack."
    )
    rec = register_upload(reg, "acronyms.md", body.encode())
    store.replace_for_source(rec.id, build_sections(rec.id, body))
    report = KnowledgeIntelligence(reg, store).run()

    assert not any(i["check"] == "undefined_acronym" for v in report["issues"].values() for i in v)


def test_acronym_expansion_ignores_connector_words(tmp_path):
    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    body = "# H\n\nRACI (Responsible, Accountable, Consulted, and Informed) is defined on first use."
    rec = register_upload(reg, "raci.md", body.encode())
    store.replace_for_source(rec.id, build_sections(rec.id, body))
    report = KnowledgeIntelligence(reg, store).run()

    assert not any(i["check"] == "undefined_acronym" for v in report["issues"].values() for i in v)


def test_readability_flags_repeated_long_prose_sentences(tmp_path):
    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    long_sentence = " ".join(["word"] * 41) + "."
    body = f"# H\n\n{long_sentence} {long_sentence} {long_sentence}"
    rec = register_upload(reg, "long.md", body.encode())
    store.replace_for_source(rec.id, build_sections(rec.id, body))
    report = KnowledgeIntelligence(reg, store).run()

    issue = next(i for i in report["issues"]["compliance"] if i["check"] == "readability")
    assert issue["detail"] == "3 long sentences (40+ words) may be hard to read."


def test_readability_ignores_markdown_tables_and_fenced_code(tmp_path):
    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    prose_a = " ".join(["prose"] * 41) + "."
    prose_b = " ".join(["context"] * 41) + "."
    table_cell = " ".join(["table"] * 55) + "."
    code_value = " ".join(["json"] * 70)
    body = f"""# H

{prose_a}

{prose_b}

| Step | Activity | What happens |
|---:|---|---|
| 1 | Validate content | {table_cell} |
| 2 | Process upload | {table_cell} |

```jsonl
{{"record_id":"ART_PROC_001","rule":"{code_value}","confidence":"high"}}
```
"""
    rec = register_upload(reg, "structured.md", body.encode())
    store.replace_for_source(rec.id, build_sections(rec.id, body))
    report = KnowledgeIntelligence(reg, store).run()

    assert not any(i["check"] == "readability" for v in report["issues"].values() for i in v)


def test_duplicate_detection(tmp_path):
    from assistant.retrieval.embedder import EmbeddingCache

    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    for name in ("a.md", "b.md"):
        rec = register_upload(reg, name, b"# H\n\nDue diligence and credit checks are mandatory gates.")
        store.replace_for_source(rec.id, build_sections(rec.id, "# H\n\nDue diligence and credit checks are mandatory gates."))
    report = KnowledgeIntelligence(reg, store, IdenticalEmbedder(), EmbeddingCache(reg.base_dir)).run()
    assert report["categories"]["consistency"] >= 1


def test_conflict_detection(tmp_path):
    from assistant.retrieval.embedder import EmbeddingCache

    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    for name, body in (("a.md", "# Checks\n\nCredit checks are mandatory before onboarding."),
                       ("b.md", "# Checks\n\nCredit checks are optional before onboarding.")):
        rec = register_upload(reg, name, body.encode())
        store.replace_for_source(rec.id, build_sections(rec.id, body))
    report = KnowledgeIntelligence(
        reg, store, RelatedEmbedder(), EmbeddingCache(reg.base_dir), generator=ConflictGenerator()
    ).run()
    assert report["categories"]["correctness"] >= 1
    assert any(i["check"] == "conflict" for i in report["issues"]["correctness"])


def make_client(tmp_path):
    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    retrieval = RetrievalService(reg, store)  # lexical only
    client = TestClient(create_app(reg, AuthService(PASSWORD), retrieval=retrieval))
    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def test_approval_gate_controls_queryability(tmp_path):
    client = make_client(tmp_path)
    rec = client.post(
        "/api/sources/upload",
        files={"file": ("s.md", b"# Controls\n\nDue diligence and credit checks are mandatory gates.", "text/markdown")},
        data={"title": "Controls"},
    ).json()
    client.post(f"/api/sources/{rec['id']}/ingest")

    # Not approved yet -> not queryable.
    assert client.post("/api/query", json={"q": "credit checks"}).json()["mode"] == "empty"

    # Approve -> queryable.
    approved = client.post(f"/api/governance/sources/{rec['id']}/approve").json()
    assert approved["approval_status"] == "approved"
    assert client.post("/api/query", json={"q": "credit checks"}).json()["results"]


def test_reject_missing_source_404(tmp_path):
    client = make_client(tmp_path)
    assert client.post("/api/governance/sources/nope/reject").status_code == 404


def test_document_get_and_save_reingests(tmp_path):
    client = make_client(tmp_path)
    rec = client.post(
        "/api/sources/upload",
        files={"file": ("d.md", b"# A\n\nfirst section here.\n\n# B\n\nsecond section here.", "text/markdown")},
        data={"title": "Doc"},
    ).json()
    client.post(f"/api/sources/{rec['id']}/ingest")

    doc = client.get(f"/api/governance/sources/{rec['id']}/document").json()
    assert doc["title"] == "Doc" and "first section" in doc["text"]

    # Edit out the second section and save -> content is re-ingested with fewer sections.
    saved = client.put(f"/api/governance/sources/{rec['id']}/document", json={"text": "# A\n\nfirst section here."}).json()
    assert saved["section_count"] == 1
    assert "second section" not in client.get(f"/api/governance/sources/{rec['id']}/document").json()["text"]


def test_get_document_404(tmp_path):
    client = make_client(tmp_path)
    assert client.get("/api/governance/sources/nope/document").status_code == 404


def test_accept_issue_drops_from_list_and_labels_source(tmp_path):
    from assistant.governance.accepted import AcceptedStore

    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    register_upload(reg, "a.txt", b"some content")  # not_ingested issue
    accepted = AcceptedStore(reg.base_dir)
    ki = KnowledgeIntelligence(reg, store, accepted=accepted)

    before = ki.run()
    issue = before["issues"]["compliance"][0]
    assert before["total_issues"] >= 1

    accepted.accept(issue["source_id"], issue["check"], issue["detail"])
    after = ki.run()
    assert not any(i["check"] == "not_ingested" for i in after["issues"]["compliance"])  # dropped
    assert after["source_summary"][issue["source_id"]]["accepted"] >= 1  # labelled


def test_accept_endpoint(tmp_path):
    client = make_client(tmp_path)
    rec = client.post("/api/sources/upload", files={"file": ("a.txt", b"hello", "text/plain")}, data={"title": "a"}).json()
    body = {"source_id": rec["id"], "check": "not_ingested", "detail": "x"}
    assert client.post("/api/governance/issues/accept", json=body).json()["accepted"] is True


def test_reanalysis_records_external_coverage_and_pending_changes(tmp_path):
    client = make_client(tmp_path)
    rec = client.post(
        "/api/sources/upload",
        files={
            "file": (
                "tax.md",
                b"# Tax controls\n\nVAT invoices and tax records are checked before fiscal reconciliation.",
                "text/markdown",
            )
        },
        data={"title": "Tax controls"},
    ).json()
    client.post(f"/api/sources/{rec['id']}/ingest")
    client.post(f"/api/governance/sources/{rec['id']}/approve")
    public = client.app.state.public_content
    external_source = public.upsert_source(provider="govuk", url="https://www.gov.uk/vat-businesses", topics=["tax"])
    public.add_snapshot(
        external_source.id,
        FetchedPublicContent(
            url="https://www.gov.uk/vat-businesses",
            title="VAT guidance for businesses",
            public_body="HM Revenue & Customs",
            document_type="guidance",
            update_date="2026-06-19T00:00:00Z",
            retrieved_at="2026-06-22T10:00:00Z",
            text="VAT records and invoices for tax compliance.",
            metadata={"schema_name": "guide"},
        ),
    )
    candidates = client.get("/api/regulatory/candidates").json()
    financial = next(candidate for candidate in candidates["candidates"] if candidate["theme"] == "financial_tax")
    client.post(f"/api/regulatory/candidates/{financial['id']}/review", json={"status": "relevant"})

    report = client.post("/api/governance/reanalysis").json()

    assert report["has_run"] is True
    assert report["external_snapshot_count"] == 1
    assert report["external_matched_count"] == 1
    assert report["previous_decisions_preserved"] == 1
    assert report["coverage"][0]["status"] == "matched"
    assert report["coverage"][0]["matched_candidates"][0]["source_title"] == "Tax controls"
    assert client.get("/api/governance/reanalysis/latest").json()["needs_reanalysis"] is False

    public.add_snapshot(
        external_source.id,
        FetchedPublicContent(
            url="https://www.gov.uk/vat-businesses",
            title="VAT guidance for businesses",
            public_body="HM Revenue & Customs",
            document_type="guidance",
            update_date="2026-06-20T00:00:00Z",
            retrieved_at="2026-06-22T11:00:00Z",
            text="Updated VAT invoice records for tax compliance.",
            metadata={"schema_name": "guide"},
        ),
    )
    latest = client.get("/api/governance/reanalysis/latest").json()

    assert latest["needs_reanalysis"] is True
    assert latest["pending_external_snapshot_count"] == 1


def test_remediation_recommends_richer_doc_and_trims_overlap():
    from assistant.governance.remediation import suggest_remediation

    overlap = "Due diligence and credit checks are mandatory gates before onboarding a supplier."
    a = {"id": "a", "title": "Rich", "text": f"{overlap}\nExtra unique detail one.\nExtra unique detail two.\nMore unique content here."}
    b = {"id": "b", "title": "Thin", "text": f"{overlap}\nshort."}
    out = suggest_remediation(a, b)
    assert out["keep_id"] == "a" and out["trim_id"] == "b"  # richer doc keeps
    assert out["shared_lines"] == 1
    assert overlap.lower() not in out["trim_suggested_text"].lower()  # overlap removed from the trim suggestion


def test_remediation_endpoint(tmp_path):
    client = make_client(tmp_path)
    text = "Shared overlapping sentence that is clearly long enough to count as duplication.\n\nUnique line."
    ids = []
    for name in ("a.md", "b.md"):
        rec = client.post("/api/sources/upload", files={"file": (name, text.encode(), "text/markdown")}, data={"title": name}).json()
        ids.append(rec["id"])
    out = client.get(f"/api/governance/remediation/{ids[0]}/{ids[1]}").json()
    assert out["shared_lines"] >= 1 and out["keep_id"] in ids and out["trim_id"] in ids
