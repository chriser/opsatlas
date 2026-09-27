"""Content management in the sales workspace (CM S12, CM S21, CM S23): records stay consistent when edited."""
import json
import os
from types import SimpleNamespace

import pytest

from services.opsatlas_sales.content import attach, parse_record


@pytest.fixture
def sales(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    os.environ['SME_TIBI_VOICE_URL'] = 'http://127.0.0.1:9'  # no Tibi service in these tests
    root = tmp_path / 'sales'
    app = create_sales_app(root)
    app.state.retrieval.embedder = None
    with TestClient(app) as client:
        token = client.post('/api/auth/login', json={'password': (root / 'local-access.key').read_text().strip()}).json()['token']
        client.headers.update({'Authorization': f'Bearer {token}'})
        yield client, app, root


def records(client):
    return {r['id']: r for r in client.get('/api/tibi/knowledge').json()['records']}


def publish(client, sid, text):
    doc = client.put(f'/api/content/documents/{sid}/draft', json={'text': text}).json()
    client.post(f'/api/content/documents/{sid}/submit', json={'note': 'test'})
    return client.post(f'/api/content/documents/{sid}/publish', json={'draft_sha': doc['draft']['sha']})


def test_editing_a_records_document_keeps_the_record_consistent_and_enables_it(sales):
    client, app, root = sales
    row = records(client)['limitations']
    doc = client.get(f"/api/content/documents/{row['source_id']}").json()
    assert doc['record']['id'] == 'limitations' and doc['title_from_heading'] and doc['published']['text'].startswith('# ')
    assert doc['operator']['name'] == 'Kris Pochopien'
    title, text = parse_record(doc['published']['text'])
    new = f"# {title} (edited)\n\n{text} Single sign-on is planned for a real deployment.\n"
    result = publish(client, row['source_id'], new)
    assert result.status_code == 200, result.text
    assert result.json()['record'] == 'limitations'
    after = records(client)['limitations']
    assert after['title'] == f'{title} (edited)' and after['text'].endswith('planned for a real deployment.')
    assert after['eligible'] and after['approval'] == 'approved'  # publishing is the Human's review
    history = (root / 'core' / 'sales-review-history.jsonl').read_text()
    assert '"edited and approved"' in history
    # A record's title is its heading: the Details panel refuses a separate title.
    refused = client.patch(f"/api/content/documents/{row['source_id']}/details", json={'fields': {'title': 'Other'}})
    assert refused.status_code == 409 and 'heading' in refused.json()['detail']


def test_a_record_draft_must_keep_its_heading_and_a_disputed_record_cannot_be_published(sales):
    client, app, root = sales
    rows = records(client)
    no_heading = publish(client, rows['limitations']['source_id'], 'Just a sentence with no heading at all.\n')
    assert no_heading.status_code == 409 and 'title as a heading' in no_heading.json()['detail']
    path = root / 'core' / 'sales-records.json'
    stored = json.loads(path.read_text())
    next(r for r in stored if r['id'] == 'governance')['disputed'] = True  # a record in both starting corpora
    path.write_text(json.dumps(stored))
    disputed = publish(client, rows['governance']['source_id'], '# Governance\n\nA new wording of the governance record.\n')
    assert disputed.status_code == 409 and 'dispute' in disputed.json()['detail']


def _cited_record(client, register):
    rows = records(client)
    record = next(r for r in rows.values() if any(register.get(ref['source_id']).filename.endswith('.md') for ref in r['references']))
    ref = next(ref for ref in record['references'] if register.get(ref['source_id']).filename.endswith('.md'))
    return record, ref


def test_a_changed_supporting_document_withdraws_the_records_citing_it_until_reconfirmed(sales):
    # Audit F01: approving an edited document is not approving the records that cite it.
    client, app, root = sales
    register = app.state.register
    record, ref = _cited_record(client, register)
    enabled = client.post(f"/api/tibi/knowledge/{record['id']}/review", json={'expected_hash': record['sha256'], 'approve': True}).json()
    assert enabled['eligible']
    digest = app.state.sales.digest()
    evidence = client.get(f"/api/content/documents/{ref['source_id']}").json()
    assert any(c['id'] == record['id'] for c in evidence['cited_by']) and evidence['record'] is None
    # The audit's probe, through the real publish API: the evidence now withdraws what it supported.
    result = publish(client, ref['source_id'], '# Withdrawn evidence\n\nThe previous claims are withdrawn. This document no longer '
                                              'supports any product capability.\n')
    assert result.status_code == 200, result.text
    citing = {c['id']: c for c in result.json()['records_citing']}
    assert citing[record['id']]['reconfirm']
    after = records(client)[record['id']]
    assert not after['eligible'] and after['approval'] == 'approved' and after['text'] == record['text']
    assert [c['source_id'] for c in after['evidence_changed']] == [ref['source_id']]
    assert app.state.sales.digest() != digest  # prepared and cached answers no longer match
    assert record['id'] not in [r['id'] for r in app.state.sales.rank('anything', None)['results']]
    stored = next(r for r in json.loads((root / 'core' / 'sales-records.json').read_text()) if r['id'] == record['id'])
    assert stored['governance'][-1]['evidence_edited'] and not stored['governance'][-1]['reformatted']
    # The Human reconfirms against the new evidence: the review now records the new version.
    confirmed = client.post(f"/api/tibi/knowledge/{record['id']}/review", json={'expected_hash': after['sha256'], 'approve': True}).json()
    assert confirmed['eligible']
    stored = next(r for r in json.loads((root / 'core' / 'sales-records.json').read_text()) if r['id'] == record['id'])
    assert stored['review']['evidence'][ref['source_id']] == register.get(ref['source_id']).content_sha256


def test_reformatting_a_supporting_document_keeps_the_records_citing_it(sales):
    client, app, root = sales
    register = app.state.register
    record, ref = _cited_record(client, register)
    client.post(f"/api/tibi/knowledge/{record['id']}/review", json={'expected_hash': record['sha256'], 'approve': True})
    text = client.get(f"/api/content/documents/{ref['source_id']}").json()['published']['text']
    # Only the formatting changes: the same words in the same order.
    reformatted = text.replace('\n\n', '\n\n\n', 1).rstrip('\n') + '\n\n'
    first = next(w for w in text.split() if w.isalpha() and len(w) > 4)
    reformatted = reformatted.replace(first, f'**{first}**', 1)
    result = publish(client, ref['source_id'], reformatted)
    assert result.status_code == 200, result.text
    assert not {c['id']: c for c in result.json()['records_citing']}[record['id']]['reconfirm']
    after = records(client)[record['id']]
    assert after['eligible'] and after['evidence_changed'] == []


def test_reviews_made_before_evidence_binding_are_bound_on_start_up(tmp_path):
    from assistant.sources.register import SourceRegister
    from services.opsatlas_sales.knowledge import Knowledge
    from services.opsatlas_sales.workspace import workspace
    k = Knowledge(SourceRegister(workspace(tmp_path / 'sales') / 'core'))
    rows = k.seed()
    edited, kept = [r for r in rows if r['references']][:2]
    stored = k.records()
    for row in stored:
        if row['id'] in (edited['id'], kept['id']):
            row['review'] = {'actor': 'local operator', 'at': '2026-09-20T10:00:00+00:00', 'hash': row['sha256']}
    k._save(stored)
    with (k.register.base_dir / 'sales-review-history.jsonl').open('a') as log:
        log.write(json.dumps({'id': edited['id'], 'decision': 'evidence updated', 'evidence': edited['references'][0]['source_id'],
                              'at': '2026-09-21T10:00:00+00:00'}) + '\n')
    k.seed()
    rows = {r['id']: r for r in k.records()}
    assert rows[edited['id']]['review']['evidence'][edited['references'][0]['source_id']] is None  # edited after it was enabled
    assert k.evidence_changed(rows[edited['id']]) and not k.evidence_changed(rows[kept['id']])


def test_governance_findings_become_suggestions_on_the_passage():
    items = [
        {'key': 'acronym:RAG', 'kind': 'acronym', 'check': 'undefined_acronym', 'acronym': 'RAG', 'source_title': 'Evaluation',
         'sources': ['Evaluation'], 'issues': [{'source_id': 's1'}], 'known': [{'expansion': 'Retrieval-Augmented Generation',
                                                                                  'source_title': 'DT603 Appendix A'}]},
        {'key': 'k2', 'kind': 'statement', 'check': 'statement_conflict', 'relation': 'conflict', 'reason': 'Local against cloud.',
         'answer': {'status': 'pending'}, 'statements': [
             {'source_id': 's1', 'title': 'Architecture', 'text': 'Models run locally.'},
             {'source_id': 's2', 'title': 'Claim · Dan', 'text': 'Models run in a cloud service.'}]},
        {'key': 'k3', 'kind': 'issue', 'check': 'broken_link', 'source_title': 'Other', 'detail': 'x', 'issues': [{'source_id': 's9'}]},
        {'key': 'acronym:SME', 'kind': 'acronym', 'check': 'undefined_acronym', 'acronym': 'SME', 'source_title': 'Deployment',
         'sources': ['Deployment'], 'issues': [{'source_id': 's3'}], 'known': [],
         'mentions': [{'phrase': 'subject matter experts', 'source_title': 'DT603 Part A · 1'}]},
    ]
    content = SimpleNamespace(hooks={})
    attach(content, knowledge=None, desk=SimpleNamespace(agenda=lambda: {'items': items}))
    acronym, conflict = content.hooks['suggestions']('s1')
    assert acronym['quote'] == 'RAG' and acronym['fix'] == {
        'find': 'RAG', 'replace': 'Retrieval-Augmented Generation (RAG)', 'label': 'Spell it out as Retrieval-Augmented Generation'}
    assert conflict['kind'] == 'conflict' and conflict['quote'] == 'Models run locally.' and conflict['other']['title'] == 'Claim · Dan'
    assert conflict['answer'] == 'pending'
    other_side = content.hooks['suggestions']('s2')
    assert [s['quote'] for s in other_side] == ['Models run in a cloud service.']
    # Not defined anywhere, but spelled out in passing: the fix uses that phrase and says where it comes from.
    [mentioned] = content.hooks['suggestions']('s3')
    assert mentioned['fix'] == {'find': 'SME', 'replace': 'subject matter experts (SME)',
                                'label': 'Spell it out as subject matter experts, as DT603 Part A · 1 does'}


def test_parse_record():
    assert parse_record('# Title\n\nBody text.\n') == ('Title', 'Body text.')
    trailer = '# Claim · Dan\n\nCurrently: it runs.\n\nInterview input SHA-256: ' + 'a' * 64 + '\n'
    assert parse_record(trailer) == ('Claim · Dan', 'Currently: it runs.')
    for bad in ('No heading here.', '# Title only\n', ''):
        with pytest.raises(ValueError):
            parse_record(bad)


def test_a_record_approved_from_its_document_is_enabled_and_rejecting_excludes_it(sales):
    client, app, root = sales
    row = records(client)['limitations']
    assert not row['eligible']  # a fresh workspace: every record waits for the Human
    doc = client.get(f"/api/content/documents/{row['source_id']}").json()
    approved = client.post(f"/api/content/documents/{row['source_id']}/approve", json={'expected_sha': doc['published']['sha']})
    assert approved.status_code == 200, approved.text
    assert approved.json()['record']['eligible'] and records(client)['limitations']['eligible']
    assert '"decision": "approved"' in (root / 'core' / 'sales-review-history.jsonl').read_text()
    excluded = client.post(f"/api/content/documents/{row['source_id']}/reject", json={'expected_sha': doc['published']['sha']}).json()
    assert not excluded['record']['eligible'] and not records(client)['limitations']['eligible']


def test_open_suggestions_are_counted_per_document(sales):
    client, app, root = sales
    summary = client.get('/api/content/documents').json()
    counts, notes = summary['suggestions'], summary['suggestion_notes']
    assert counts and all(app.state.register.get(sid) for sid in counts)
    assert {sid: len(lines) for sid, lines in notes.items()} == counts
    assert all(line.endswith('.') or line.startswith(('Possible conflict', 'Says the same')) for lines in notes.values() for line in lines)
    for sid, n in counts.items():
        open_items = [s for s in client.get(f'/api/content/documents/{sid}/suggestions').json()['suggestions'] if not s['answer']]
        assert len(open_items) == n, sid


def test_the_library_starts_grouped_and_places_new_documents(sales):
    client, app, root = sales
    library = client.get('/api/content/library').json()
    groups = {g['id']: g for g in library['groups']}
    title = {g['id']: g['title'] for g in groups.values()}
    assert {'Product knowledge', 'How it works', 'Tibi', 'Conversation style', 'Evidence', 'DT603 paper'} <= set(title.values())
    nested = {g['title']: title.get((g['parent'] or ':').partition(':')[2]) for g in groups.values()}
    assert nested['How it works'] == 'Product knowledge' and nested['Conversation style'] == 'Tibi'
    rows = records(client)
    placements = library['placements']
    assert set(placements) == {s.id for s in app.state.register.list()}  # every document has a place

    def group_of(sid):
        return title.get(placements[sid]['parent'].partition(':')[2])
    for row in rows.values():
        if row.get('kind') == 'conversation':
            assert group_of(row['source_id']) == 'Conversation style'
    if 'governance-review' in rows and 'governance' in rows:  # a record under a record
        assert placements[rows['governance-review']['source_id']]['parent'] == f"source:{rows['governance']['source_id']}"
    evidence = [s for s in app.state.register.list() if s.id not in {r['source_id'] for r in rows.values()}]
    assert evidence and all(group_of(s.id) in ('DT603 paper', 'Repository and owner notes') for s in evidence)
    # The starting library is made once; after that it is the Human's. Removing a group lifts what it held.
    client.delete(f"/api/content/groups/{next(g for g in groups.values() if g['title'] == 'Tibi')['id']}")
    again = client.get('/api/content/library').json()
    assert len(again['groups']) == len(groups) - 1
    assert next(g for g in again['groups'] if g['title'] == 'Conversation style')['parent'] is None


def test_renaming_a_record_rewrites_its_heading_and_keeps_its_approval(sales):
    client, app, root = sales
    register = app.state.register
    rows = records(client)
    approved = rows['limitations']
    doc = client.get(f"/api/content/documents/{approved['source_id']}").json()
    client.post(f"/api/content/documents/{approved['source_id']}/approve", json={'expected_sha': doc['published']['sha']})
    renamed = client.post(f"/api/content/documents/{approved['source_id']}/rename", json={'title': 'What is out of scope'})
    assert renamed.status_code == 200, renamed.text
    body = renamed.json()
    assert body['source']['title'] == 'What is out of scope' and body['published']['text'].startswith('# What is out of scope\n')
    after = records(client)['limitations']
    assert after['title'] == 'What is out of scope' and after['text'] == approved['text']
    assert after['eligible'] and register.get(approved['source_id']).approval_status == 'approved'
    versions = client.get(f"/api/content/documents/{approved['source_id']}/versions").json()['versions']
    assert versions[0]['label'] == 'renamed' and 'What is out of scope' in versions[0]['note']
    # A record still waiting for the Human stays waiting.
    pending = next(r for r in rows.values() if r['id'] != 'limitations' and not r['eligible'])
    assert client.post(f"/api/content/documents/{pending['source_id']}/rename", json={'title': 'A new name'}).status_code == 200
    assert register.get(pending['source_id']).approval_status == 'pending' and not records(client)[pending['id']]['eligible']
    assert records(client)[pending['id']]['title'] == 'A new name'
    # A record with a draft is renamed in the draft.
    text = client.get(f"/api/content/documents/{pending['source_id']}").json()['published']['text']
    client.put(f"/api/content/documents/{pending['source_id']}/draft", json={'text': text + '\nMore.\n'})
    blocked = client.post(f"/api/content/documents/{pending['source_id']}/rename", json={'title': 'Another name'})
    assert blocked.status_code == 409 and 'draft' in blocked.json()['detail']


def open_suggestions(client, prefix):
    """(source id, suggestion) for every open suggestion whose key starts with ``prefix``."""
    out = []
    for sid in client.get('/api/content/documents').json()['suggestion_notes']:
        out += [(sid, s) for s in client.get(f'/api/content/documents/{sid}/suggestions').json()['suggestions']
                if s['key'].startswith(prefix) and not s['answer']]
    return out


def test_a_suggestion_kept_as_it_is_is_accepted_everywhere_and_can_be_reopened(sales):
    client, app, root = sales
    sid, suggestion = next(iter(open_suggestions(client, 'standard:') or open_suggestions(client, 'acronym:')))
    acronym = suggestion['acronyms'][0]
    url = f'/api/content/documents/{sid}/suggestions'
    state = client.post(f'{url}/accept', json={'key': suggestion['key'], 'note': 'Well known to the audience'})
    assert state.status_code == 200, state.text
    assert suggestion['key'] not in [s['key'] for s in state.json()['suggestions']]
    [accepted] = [s for s in state.json()['settled'] if s['outcome'] == 'accepted']
    assert accepted['key'] == suggestion['key'] and accepted['note'] == 'Well known to the audience'
    # Tibi and the Governance page no longer raise it for this document.
    agenda = app.state.governance_desk.agenda()['items']  # what Tibi's governance interview is given
    assert not any(ref['source_id'] == sid and acronym in (i.get('acronym'), *ref.get('standard', []))
                   for i in agenda if i['kind'] in ('acronym', 'standard') for ref in i['issues'])
    summary = client.get('/api/content/documents').json()
    assert summary['settled'][sid]['accepted'] == 1
    assert suggestion['text'] not in ' '.join(summary['suggestion_notes'].get(sid, []))
    assert '"kept_as_is"' in (root / 'core' / 'sales-review-history.jsonl').read_text()
    reopened = client.post(f"{url}/settled/{accepted['id']}/reopen").json()
    assert suggestion['key'] in [s['key'] for s in reopened['suggestions']]


def test_an_edit_that_spells_out_an_acronym_corrects_its_suggestion(sales):
    client, app, root = sales
    # Any acronym will do; the spell-out fix needs definitions from evidence CI does not have, so write one here.
    sid, suggestion = next(iter(open_suggestions(client, 'acronym:') or open_suggestions(client, 'standard:')))
    text = client.get(f'/api/content/documents/{sid}').json()['published']['text']
    fixed = text.rstrip('\n') + f"\n\nIn full: Some Long Name ({suggestion['acronyms'][0]}).\n"
    result = publish(client, sid, fixed)
    assert result.status_code == 200, result.text
    state = client.get(f'/api/content/documents/{sid}/suggestions').json()
    assert suggestion['key'] not in [s['key'] for s in state['suggestions']]
    corrected = next(s for s in state['settled'] if s['key'] == suggestion['key'])
    assert corrected['outcome'] == 'corrected' and corrected['version'] == 2 and corrected['actor'] == 'Kris Pochopien'


def test_edits_before_suggestions_were_recorded_are_credited_with_what_they_corrected(sales):
    from assistant.governance.intelligence import undefined_acronyms
    client, app, root = sales
    register = app.state.register
    row, acronym = next((r, sorted(undefined_acronyms(register.read_content(r['source_id']).decode()))[0])
                        for r in records(client).values() if undefined_acronyms(register.read_content(r['source_id']).decode()))
    text = register.read_content(row['source_id']).decode()
    # Published before anything asked for suggestions, as the Human's first edits were.
    assert publish(client, row['source_id'], text.rstrip('\n') + f"\n\nIn full: Some Long Name ({acronym}).\n").status_code == 200
    settled = client.get(f"/api/content/documents/{row['source_id']}/suggestions").json()['settled']
    assert [(s['outcome'], s['quote'], s['version']) for s in settled] == [('corrected', acronym, 2)]
