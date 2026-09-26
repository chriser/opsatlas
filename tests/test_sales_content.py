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
