import json

import pytest

from assistant.ingestion.store import SectionStore
from assistant.sources.register import SourceRegister
from services.opsatlas_sales.knowledge import Knowledge
from services.opsatlas_sales.workspace import workspace


def test_isolation_seed_and_approval_lifecycle(tmp_path):
    original = tmp_path / 'original'
    original.mkdir()
    sentinel = original / 'sentinel'
    sentinel.write_text('existing knowledge')
    root = workspace(tmp_path / 'sales')
    k = Knowledge(SourceRegister(root / 'core'))
    records = k.seed()
    assert len(records) == 8 and all(not r['eligible'] for r in records)
    count = len(k.register.list())
    assert len(k.seed()) == 8 and len(k.register.list()) == count
    row = records[0]
    assert k.decide(row['id'], row['sha256'], True)['eligible']
    assert SectionStore(root / 'core').list_for_source(row['source_id'])
    assert not k.eligible({**k.catalog()[0], 'text': 'Invented replacement wording'})
    assert not k.decide(row['id'], row['sha256'], False)['eligible']
    assert k.decide(row['id'], row['sha256'], True)['eligible']
    k.register.write_content(row['source_id'], b'changed maliciously')
    assert not k.catalog()[0]['eligible']
    with pytest.raises(ValueError):
        k.decide(row['id'], row['sha256'], True)
    assert sentinel.read_text() == 'existing knowledge'
    assert list(original.iterdir()) == [sentinel]


def test_supporting_source_change_and_deletion_invalidates(tmp_path):
    k = Knowledge(SourceRegister(workspace(tmp_path / 'sales') / 'core'))
    row = k.seed()[0]
    k.decide(row['id'], row['sha256'], True)
    ref = row['references'][0]['source_id']
    k.register.update(ref, approval_status='rejected')
    assert not k.catalog()[0]['eligible']
    k.register.remove(ref)
    assert not k.catalog()[0]['eligible']


def test_workspace_rejects_unknown_state_and_links(tmp_path):
    old = tmp_path / 'old'
    old.mkdir()
    (old / 'data').write_text('old')
    with pytest.raises(ValueError):
        workspace(old)
    link = tmp_path / 'link'
    link.symlink_to(old, target_is_directory=True)
    with pytest.raises(ValueError):
        workspace(link)
    root = workspace(tmp_path / 'sales')
    (root / 'core/outside').symlink_to(old, target_is_directory=True)
    with pytest.raises(ValueError):
        workspace(root)


def test_restart_keeps_identity_and_credentials(tmp_path):
    root = workspace(tmp_path / 'sales')
    key = (root / 'local-access.key').read_text()
    assert workspace(root) == root
    assert (root / 'local-access.key').read_text() == key
    assert json.loads((root / 'workspace.json').read_text())['workspace'] == 'opsatlas-sales'


def test_core_api_origin_auth_and_native_approval(tmp_path, monkeypatch):
    # Keep environment changes within this test, including dotenv defaults.
    import os

    from fastapi.testclient import TestClient

    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    original = tmp_path / 'existing'
    original.mkdir()
    (original / 'sentinel').write_text('unchanged')
    monkeypatch.setenv('KP_DATA_DIR', str(original))
    root = tmp_path / 'sales'
    app = create_sales_app(root)
    headers = {'x-sales-token': (root / 'local-access.key').read_text()}
    with TestClient(app) as c:
        assert c.get('/api/sales/knowledge').status_code == 403
        assert c.get('/api/sales/knowledge', headers={**headers, 'origin': 'http://evil.test'}).status_code == 403
        records = c.get('/api/sales/knowledge', headers=headers).json()['records']
        row = records[0]
        r = c.post('/api/sales/knowledge/overview/review', headers=headers,
                   json={'approve': True, 'expected_hash': row['sha256']})
        assert r.status_code == 200 and r.json()['eligible']
        assert (root / 'core/sales-review-history.jsonl').exists()
        r = c.post('/api/sales/knowledge/overview/review', headers=headers,
                   json={'approve': False, 'expected_hash': row['sha256']})
        assert r.status_code == 200 and not r.json()['eligible']
    assert list(original.iterdir()) == [original / 'sentinel']
    assert (original / 'sentinel').read_text() == 'unchanged'


def test_governance_is_the_single_source_of_approval(tmp_path):
    k = Knowledge(SourceRegister(workspace(tmp_path / 'sales') / 'core'))
    row = k.seed()[0]
    k.register.update(row['source_id'], approval_status='approved')
    assert k.records()[0]['approval'] == 'pending'  # legacy cache must not block native approval
    assert k.catalog()[0]['approval'] == 'approved' and k.catalog()[0]['eligible']
    k.register.update(row['source_id'], approval_status='rejected')
    assert k.catalog()[0]['approval'] == 'rejected' and not k.catalog()[0]['eligible']
    k.register.update(row['source_id'], approval_status='approved')
    k.register.write_content(row['source_id'], b'Unreviewed changed content')
    assert not k.catalog()[0]['eligible']


def _enabled(tmp_path, ids=('overview', 'limitations', 'tiberius', 'commercial')):
    k = Knowledge(SourceRegister(workspace(tmp_path / 'sales') / 'core'))
    for row in k.seed():
        if row['id'] in ids:
            k.decide(row['id'], row['sha256'], True)
    return k


class FakeEmbedder:
    def embed(self, texts):
        return [[1.0, float('offline' in t.lower()), float('price' in t.lower() or 'pricing' in t.lower())] for t in texts]


def test_rank_uses_only_enabled_records_and_never_truncates(tmp_path):
    from assistant.retrieval.embedder import EmbeddingCache
    from assistant.retrieval.service import RetrievalService

    k = _enabled(tmp_path)
    retrieval = RetrievalService(k.register, k.sections, embedder=FakeEmbedder(), cache=EmbeddingCache(tmp_path),
                                 min_similarity=0.9)
    ranked = k.rank('What is the pricing?', retrieval)
    assert ranked['mode'] == 'hybrid'
    assert {r['id'] for r in ranked['results']} == {'overview', 'limitations', 'tiberius', 'commercial'}
    assert ranked['results'][0]['id'] == 'commercial' and ranked['results'][0]['relevant']
    lexical_only = k.rank('pricing', None)
    assert lexical_only['mode'] == 'lexical' and len(lexical_only['results']) == 4
    assert k.rank('   ', retrieval) == {'mode': 'empty', 'results': []}


def test_spoken_answers_are_checked_pending_until_reviewed_and_bound_to_the_record(tmp_path):
    k = _enabled(tmp_path)
    before = k.digest()
    with pytest.raises(ValueError, match='goes beyond'):
        k.add_spoken('commercial', 'It costs 500 pounds per seat.', 'test')
    with pytest.raises(ValueError, match='Enable the record'):
        k.add_spoken('process', 'OpsAtlas includes process diagrams.', 'test')
    variant = k.add_spoken('tiberius', 'Tibi is the local voice companion for this sales workspace.', 'test')
    # The experimental record's qualification is added when the draft drops it.
    assert variant['status'] == 'pending' and variant['text'].startswith('That part is still experimental.')
    assert k.add_spoken('tiberius', 'Tibi is the local voice companion for this sales workspace.', 'test') == variant
    assert not k.spoken_catalog()[0]['usable'] and k.digest() == before
    with pytest.raises(ValueError):
        k.review_spoken(variant['id'], 'wrong', True)
    assert k.review_spoken(variant['id'], variant['text_sha256'], True)['status'] == 'approved'
    assert k.spoken_catalog()[0]['usable'] and k.digest() != before
    tiberius = next(r for r in k.catalog() if r['id'] == 'tiberius')
    k.decide('tiberius', tiberius['sha256'], False)
    assert not k.spoken_catalog()[0]['usable']  # a withdrawn record withdraws its spoken wording


def test_core_search_digest_and_spoken_endpoints(tmp_path, monkeypatch):
    import os

    from fastapi.testclient import TestClient

    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    root = tmp_path / 'sales'
    app = create_sales_app(root)
    app.state.retrieval.embedder = None  # hermetic: lexical ranking only
    headers = {'x-sales-token': (root / 'local-access.key').read_text()}
    with TestClient(app) as c:
        assert c.post('/api/sales/search', json={'q': 'pricing'}).status_code == 403
        assert c.post('/api/sales/search', headers=headers, json={'q': 'pricing'}).json()['results'] == []
        rows = {r['id']: r for r in c.get('/api/sales/knowledge', headers=headers).json()['records']}
        before = c.get('/api/sales/digest', headers=headers).json()['digest']
        c.post('/api/sales/knowledge/commercial/review', headers=headers,
               json={'approve': True, 'expected_hash': rows['commercial']['sha256']})
        after = c.get('/api/sales/digest', headers=headers).json()['digest']
        assert after != before
        found = c.post('/api/sales/search', headers=headers, json={'q': 'What is the pricing?'}).json()
        assert found['digest'] == after and [r['id'] for r in found['results']] == ['commercial']
        bad = c.post('/api/sales/spoken', headers=headers, json={'record_id': 'commercial', 'text': 'It costs £9 a seat.'})
        assert bad.status_code == 409
        good = c.post('/api/sales/spoken', headers=headers, json={
            'record_id': 'commercial', 'text': "I don't have approved pricing or guaranteed savings to share yet."}).json()
        assert good['status'] == 'pending'
        r = c.post(f"/api/sales/spoken/{good['id']}/review", headers=headers,
                   json={'approve': True, 'expected_hash': good['text_sha256']})
        assert r.status_code == 200
        variants = c.get('/api/sales/spoken', headers=headers).json()['variants']
        assert variants[0]['usable'] and c.get('/api/sales/digest', headers=headers).json()['digest'] != after
