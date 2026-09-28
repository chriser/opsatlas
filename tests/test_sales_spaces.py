"""Knowledge spaces (KS F1): each space a partition, each request one space, the OpsAtlas family placed and kept."""
import json
import os

import pytest

from services.opsatlas_sales.spaces import FAMILY, PLAYBOOK, PRODUCT, SYSTEM, library_chain


@pytest.fixture
def sales(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    os.environ['SME_TIBI_VOICE_URL'] = 'http://127.0.0.1:9'
    os.environ['SALES_GOVERNANCE_AUTO_REVIEW'] = '0'
    root = tmp_path / 'sales'
    app = create_sales_app(root)
    app.state.retrieval.embedder = None
    with TestClient(app) as client:
        token = client.post('/api/auth/login', json={'password': (root / 'local-access.key').read_text().strip()}).json()['token']
        client.headers.update({'Authorization': f'Bearer {token}'})
        yield client, app, root


def upload(client, name, text, space=None):
    headers = {'X-OpsAtlas-Space': space} if space else {}
    response = client.post('/api/sources/upload', files={'file': (name, text.encode(), 'text/markdown')}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()['id'] if 'id' in response.json() else response.json()['source']['id']


def ids(client, space=None):
    headers = {'X-OpsAtlas-Space': space} if space else {}
    return {s['id'] for s in client.get('/api/sources', headers=headers).json()}


def test_the_family_spaces_exist_each_on_its_own_partition(sales):
    client, app, root = sales
    listed = {s['id']: s for s in client.get('/api/spaces').json()['spaces']}
    assert set(listed) == set(FAMILY)
    assert listed[PRODUCT]['kind'] == 'product' and listed[PLAYBOOK]['kind'] == 'playbook' and listed[SYSTEM]['kind'] == 'system'
    partitions = {s: app.state.cores[s].state.register.base_dir.resolve() for s in FAMILY}
    assert partitions[PRODUCT] == (root / 'core').resolve()  # the guide keeps the workspace's original directory
    assert len(set(partitions.values())) == 3 and all(p.is_relative_to(root.resolve()) for p in partitions.values())


def test_a_space_sees_only_its_own_documents_and_an_unknown_space_is_refused(sales):
    client, app, root = sales
    guide = upload(client, 'guide.md', '# How to approve\n\nOpen the document and choose Approve.\n')
    playbook = upload(client, 'pricing.md', '# Pricing notes\n\nInternal only.\n', PLAYBOOK)
    assert guide in ids(client) and guide not in ids(client, PLAYBOOK)
    assert playbook in ids(client, PLAYBOOK) and playbook not in ids(client)  # no header: the Product Guide
    assert client.get(f'/api/content/documents/{playbook}').status_code == 404  # not from the guide's core
    assert client.get(f'/api/content/documents/{playbook}', headers={'X-OpsAtlas-Space': PLAYBOOK}).status_code == 200
    assert client.get('/api/sources', headers={'X-OpsAtlas-Space': 'org-unknown'}).status_code == 404
    # Workspace routes are the same whatever space is named.
    assert client.get('/api/spaces', headers={'X-OpsAtlas-Space': PLAYBOOK}).status_code == 200


def test_records_carry_their_space_and_tibis_evidence_spans_the_family(sales):
    client, app, root = sales
    rows = {r['id']: r for r in client.get('/api/tibi/knowledge').json()['records']}
    assert rows['commercial']['space'] == PLAYBOOK and rows['overview']['space'] == PRODUCT
    assert all(r['space'] == SYSTEM for r in rows.values() if r.get('kind') == 'conversation')
    # A guide record's evidence sits in the playbook and still counts: the record can be enabled.
    overview = rows['overview']
    assert {app.state.family_register.space_of(ref['source_id']) for ref in overview['references']} == {PLAYBOOK}
    enabled = client.post('/api/tibi/knowledge/overview/review', json={'expected_hash': overview['sha256'], 'approve': True}).json()
    assert enabled['eligible']


def test_a_transfer_moves_the_whole_document_and_it_arrives_unapproved(sales):
    client, app, root = sales
    sid = upload(client, 'faq.md', '# FAQ\n\nThe guide answers common questions.\n')
    assert client.post(f'/api/governance/sources/{sid}/approve').status_code == 200
    assert app.state.family_register.get(sid).approval_status == 'approved'
    client.post(f'/api/content/documents/{sid}/comments', json={'quote': 'common questions', 'text': 'Keep this short.'})
    moved = client.post('/api/spaces/transfer', json={'source_id': sid, 'to': PLAYBOOK})
    assert moved.status_code == 200, moved.text
    assert moved.json()['approval'] == 'pending' and sid not in ids(client) and sid in ids(client, PLAYBOOK)
    playbook = {'X-OpsAtlas-Space': PLAYBOOK}
    comments = client.get(f'/api/content/documents/{sid}/comments', headers=playbook).json()['comments']
    assert [c['text'] for c in comments] == ['Keep this short.']  # its history went with it
    activity = client.get(f'/api/content/documents/{sid}/activity', headers=playbook).json()['activity']
    assert activity[0]['action'] == 'transferred'
    assert client.post('/api/spaces/transfer', json={'source_id': sid, 'to': PLAYBOOK}).status_code == 409
    assert client.post('/api/spaces/transfer', json={'source_id': sid, 'to': 'nowhere'}).status_code == 404
    assert '"transferred"' in (root / 'core' / 'sales-review-history.jsonl').read_text()


def test_the_layout_places_each_document_once_keeps_folders_and_prunes_only_what_it_emptied(sales):
    from services.opsatlas_sales.spaces import apply_family_layout, move_document
    client, app, root = sales
    family, knowledge = app.state.family_register, app.state.sales
    sections = knowledge.sections
    # The Human moves a guide record's document to the playbook: a restart's layout leaves it there.
    record = next(r for r in knowledge.records() if r['id'] == 'overview')
    move_document(record['source_id'], (family.registers[PRODUCT], sections.stores[PRODUCT]),
                  (family.registers[PLAYBOOK], sections.stores[PLAYBOOK]), keep_approval=True)
    assert apply_family_layout(knowledge, family, sections, app.state.spaces) == []
    assert family.space_of(record['source_id']) == PLAYBOOK
    # Evidence moved into the playbook kept a folder there; the guide lost no folder the Human made.
    evidence = next(ref['source_id'] for r in knowledge.records() for ref in r['references'])
    assert [title for _, title in library_chain(family.registers[PLAYBOOK].base_dir, evidence)]


def test_a_legacy_workspace_is_split_into_the_family_spaces_with_approvals_and_folders(tmp_path, monkeypatch):
    # A workspace from before spaces: every document in core, with folders. Its first start places them.
    from fastapi.testclient import TestClient

    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    os.environ['SME_TIBI_VOICE_URL'] = 'http://127.0.0.1:9'
    os.environ['SALES_GOVERNANCE_AUTO_REVIEW'] = '0'
    root = tmp_path / 'sales'
    app = create_sales_app(root)
    family = app.state.family_register
    # Put everything back in core, as before spaces, with a folder around the evidence.
    for space in (PLAYBOOK, SYSTEM):
        for source in list(family.registers[space].list()):
            from services.opsatlas_sales.spaces import move_document
            move_document(source.id, (family.registers[space], app.state.sales.sections.stores[space]),
                          (family.registers[PRODUCT], app.state.sales.sections.stores[PRODUCT]), keep_approval=True,
                          folder=['Evidence', 'DT603 paper'] if space == PLAYBOOK else ['Tibi', 'Conversation style'])
    approved = next(s for s in family.registers[PRODUCT].list() if s.title and 'Commercial' in s.title)
    family.registers[PRODUCT].update(approved.id, approval_status='approved')
    (root / 'spaces.json').unlink()
    again = create_sales_app(root)
    family = again.state.family_register
    rows = {r['id']: r for r in again.state.sales.records()}
    assert family.space_of(rows['commercial']['source_id']) == PLAYBOOK
    assert family.get(rows['commercial']['source_id']).approval_status == 'approved'  # the migration keeps approvals
    assert all(family.space_of(r['source_id']) == SYSTEM for r in rows.values() if r.get('kind') == 'conversation')
    conversation = next(r for r in rows.values() if r.get('kind') == 'conversation')
    assert [t for _, t in library_chain(family.registers[SYSTEM].base_dir, conversation['source_id'])] == ['Tibi', 'Conversation style']
    with TestClient(again) as client:
        token = client.post('/api/auth/login', json={'password': (root / 'local-access.key').read_text().strip()}).json()['token']
        titles = {g['title'] for g in client.get('/api/content/library', headers={'Authorization': f'Bearer {token}'}).json()['groups']}
    assert 'Conversation style' not in titles and 'DT603 paper' not in titles  # emptied by the move, so removed
    assert json.loads((root / 'spaces.json').read_text())['placed']


def test_an_organisation_space_is_created_served_at_once_and_kept_apart(sales):
    client, app, root = sales
    created = client.post('/api/spaces', json={'name': 'BeePee', 'about': 'A made-up organisation'})
    assert created.status_code == 200, created.text
    space = created.json()
    assert (space['id'], space['kind'], space['documents']) == ('beepee', 'organisation', 0)
    assert (root / 'spaces' / 'beepee' / 'core').is_dir()
    # Served without a restart, and nothing of it reaches the other spaces or Tibi's product knowledge.
    sid = upload(client, 'ordering.md', '# Ordering\n\nThe store manager raises the order.\n', 'beepee')
    assert sid in ids(client, 'beepee') and sid not in ids(client) and sid not in ids(client, PLAYBOOK)
    assert all(r.get('space') != 'beepee' for r in client.get('/api/tibi/knowledge').json()['records'])
    assert client.post('/api/spaces', json={'name': 'beepee'}).status_code == 409  # the name is taken
    assert client.post('/api/spaces', json={'name': '   '}).status_code == 400
    assert client.patch(f'/api/spaces/{PRODUCT}', json={'name': 'Renamed'}).status_code == 409  # the OpsAtlas spaces are fixed
    assert client.patch('/api/spaces/nowhere', json={'name': 'Renamed'}).status_code == 404


def test_an_organisation_space_is_renamed_archived_and_restored_with_its_documents(sales):
    from services.opsatlas_sales.app import create_sales_app
    client, app, root = sales
    client.post('/api/spaces', json={'name': 'BeePee'})
    sid = upload(client, 'returns.md', '# Returns\n\nA customer returns a part.\n', 'beepee')
    assert client.patch('/api/spaces/beepee', json={'name': 'BeePee Ltd'}).json()['name'] == 'BeePee Ltd'
    archived = client.patch('/api/spaces/beepee', json={'status': 'archived'})
    assert archived.status_code == 200 and archived.json()['status'] == 'archived'
    assert client.get('/api/sources', headers={'X-OpsAtlas-Space': 'beepee'}).status_code == 404  # not served
    listed = {s['id']: s for s in client.get('/api/spaces').json()['spaces']}
    assert listed['beepee']['status'] == 'archived'
    assert (root / 'spaces/beepee/core/sources' / sid).exists()  # the documents are kept
    # A restart does not serve an archived space; restoring serves it again, with its documents.
    assert 'beepee' not in create_sales_app(root).state.cores
    assert client.patch('/api/spaces/beepee', json={'status': 'active'}).status_code == 200
    assert sid in ids(client, 'beepee')
    assert json.loads((root / 'spaces.json').read_text())['placed']  # changing spaces keeps the family's placements
    assert client.patch('/api/spaces/beepee', json={'status': 'deleted'}).status_code == 400


def test_the_process_diagram_service_is_run_by_the_workspace_not_started_loose(sales):
    client, app, root = sales
    os.environ['PROCESS_DIAGRAM_SERVICE_URL'] = 'http://127.0.0.1:9'  # never the machine's own diagram service
    assert client.post('/api/services/restart', json={'which': 'everything'}).status_code == 400
    assert client.post('/api/services/start', json={'which': 'tibi'}).status_code == 400
    status = client.get('/api/process/diagrams/service/status').json()
    assert status['startable'] is False and 'Status' in status['message']
    assert 'data' not in status['log_path'].split(os.sep)
    started = client.post('/api/process/diagrams/service/start').json()
    assert started.get('started') is not True
