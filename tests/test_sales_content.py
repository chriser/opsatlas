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


def test_records_that_cite_edited_evidence_follow_it_and_are_reported(sales):
    client, app, root = sales
    register = app.state.register
    rows = records(client)
    record = next(r for r in rows.values() if any(register.get(ref['source_id']).filename.endswith('.md') for ref in r['references']))
    ref = next(ref for ref in record['references'] if register.get(ref['source_id']).filename.endswith('.md'))
    enabled = client.post(f"/api/tibi/knowledge/{record['id']}/review", json={'expected_hash': record['sha256'], 'approve': True}).json()
    assert enabled['eligible']
    evidence = client.get(f"/api/content/documents/{ref['source_id']}").json()
    assert any(c['id'] == record['id'] for c in evidence['cited_by']) and evidence['record'] is None
    result = publish(client, ref['source_id'], evidence['published']['text'] + '\nA clarifying sentence added by the operator.\n')
    assert result.status_code == 200, result.text
    assert record['id'] in [c['id'] for c in result.json()['records_citing']]
    after = records(client)[record['id']]
    assert after['eligible']  # the record follows the approved evidence
    assert after['references'][[r['source_id'] for r in after['references']].index(ref['source_id'])]['sha256'] == \
        register.get(ref['source_id']).content_sha256
    stored = next(r for r in json.loads((root / 'core' / 'sales-records.json').read_text()) if r['id'] == record['id'])
    assert stored['governance'][-1]['evidence_edited']


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
