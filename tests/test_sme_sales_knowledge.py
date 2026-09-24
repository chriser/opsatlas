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
