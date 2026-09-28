"""A process interview on the process map and in the registry (TIBI E5, PI F5/F6): one converter, one flow."""
import os

import pytest

from assistant.process.interview_map import capture_markdown, diagram_payload, model_from_capture
from assistant.process.maps import build_process_map
from assistant.process.parser import parse_process
from services.process_diagram.engine import render_process_chart
from services.process_diagram.models import ProcessChartRenderRequest
from services.sme_interviewer import process_model as pm


def interviewed():
    """A made-up interview: Sam at BeePee describes ordering parts, with a £5,000 decision, a check and an exception."""
    model = pm.new_model('beepee', 'BeePee')
    changes = [
        {'op': 'participant', 'field': 'name', 'value': 'Sam Patel', 'quote': "I'm Sam Patel"},
        {'op': 'participant', 'field': 'role', 'value': 'operations manager', 'quote': 'I run operations'},
        {'op': 'process', 'ref': 'p', 'name': 'Ordering parts', 'quote': 'ordering parts'},
        {'op': 'process_detail', 'process': 'p', 'field': 'trigger', 'value': 'stock falls below the minimum',
         'quote': 'when stock falls below the minimum'},
        {'op': 'step', 'ref': 'a', 'process': 'p', 'after': 'start', 'kind': 'task', 'label': 'Check stock report',
         'who': 'store manager', 'system': 'SAP', 'quote': 'the store manager checks the stock report in SAP'},
        {'op': 'step', 'ref': 'b', 'process': 'p', 'after': 'a', 'kind': 'task', 'label': 'Raise purchase order',
         'who': 'store manager', 'system': 'SAP', 'quote': 'raises a purchase order'},
        {'op': 'decision', 'ref': 'd', 'process': 'p', 'after': 'b', 'question': 'Is the order over £5,000?',
         'quote': 'if it is over five thousand pounds'},
        {'op': 'step', 'ref': 'c', 'process': 'p', 'after': 'd', 'kind': 'task', 'label': 'Approve large order',
         'who': 'regional director', 'system': '', 'quote': 'the regional director approves it'},
        {'op': 'step', 'ref': 'e', 'process': 'p', 'after': 'd', 'kind': 'task', 'label': 'Approve order',
         'who': 'finance', 'system': '', 'quote': 'otherwise finance approves it'},
        {'op': 'branch', 'decision': 'd', 'condition': 'Over £5,000', 'to': 'c', 'quote': 'if it is over five thousand pounds'},
        {'op': 'branch', 'decision': 'd', 'condition': 'Otherwise', 'to': 'e', 'quote': 'otherwise finance approves it'},
        {'op': 'control', 'process': 'p', 'at': 'e', 'text': 'Two signatures over £1,000', 'quote': 'two signatures over a thousand'},
        {'op': 'exception', 'process': 'p', 'at': 'a', 'text': 'Stock report is late', 'handling': 'call the warehouse',
         'quote': 'if the stock report is late we call the warehouse'},
    ]
    answer = ("I'm Sam Patel, I run operations. Mainly ordering parts, when stock falls below the minimum. "
              "The store manager checks the stock report in SAP and raises a purchase order; if it is over five thousand pounds "
              "the regional director approves it, otherwise finance approves it, with two signatures over a thousand. "
              "If the stock report is late we call the warehouse.")
    model, log = pm.apply(model, changes, answer, 1)
    assert not log['dropped'], log['dropped']
    model, _ = pm.apply(model, [{'op': 'confirm', 'items': ['s1', 's2']}], 'Yes.', 2)
    return model


def test_the_live_map_draws_roles_the_trigger_the_decision_and_an_open_end_and_the_service_accepts_it():
    payload = diagram_payload(interviewed())
    nodes = {n['id']: n for n in payload['process_model']['nodes']}
    assert payload['process_model']['title'] == 'Ordering parts'
    assert [n['label'] for n in nodes.values() if n['type'] == 'lane'] == ['Store manager', 'Regional director', 'Finance']
    assert nodes['start']['label'] == 'Stock falls below the minimum'
    gateway = next(n for n in nodes.values() if n['type'] == 'gateway')
    edges = payload['process_model']['edges']
    assert sorted(e['label'] for e in edges if e['from'] == gateway['id']) == ['Otherwise', 'Over £5,000']
    assert nodes['end']['label'] == 'Still being described' and {e['label'] for e in edges if e['to'] == 'end'} == {'…'}
    assert nodes['s1']['metadata']['status'] == 'confirmed' and nodes['s4']['metadata']['status'] == 'heard'
    assert {n['label'] for n in nodes.values() if n['type'] == 'system'} == {'SAP'}
    assert any(n['type'] == 'control' for n in nodes.values()) and any(n['type'] == 'risk' for n in nodes.values())
    chart = render_process_chart(ProcessChartRenderRequest(**payload))  # the diagram service's own validation and layout
    assert {n.id for n in chart.nodes} >= {'start', 's1', 's2', gateway['id'], 'end'}


def test_the_capture_reads_well_and_the_registry_gets_the_same_steps_and_flow():
    model = interviewed()
    title, text = capture_markdown(model, 'p1', organisation='BeePee', interview='abc123', captured='28 September 2026')
    assert title == 'Ordering parts · BeePee'
    assert 'Captured in a process interview with Sam Patel, operations manager, 28 September 2026.' in text
    assert '1. Check stock report (by store manager, in SAP)' in text and '_(heard)_' in text
    assert '3. **Decision: Is the order over £5,000?** Over £5,000 → step 4; Otherwise → step 5' in text
    assert '- **What starts it:** stock falls below the minimum' in text
    record = parse_process('src1', title, text)
    assert record.name == 'Ordering parts' and record.roles == ['store manager', 'regional director', 'finance']
    assert record.systems == ['SAP'] and record.process_model == model_from_capture(text)
    draft = build_process_map(record)
    assert [s.label for s in draft.steps][:3] == ['Check stock report', 'Raise purchase order', 'Is the order over £5,000?']
    assert sorted(e.label for e in draft.edges if e.source == 's3') == ['Otherwise', 'Over £5,000']
    # The registry's map is drawn by the same converter as the live one.
    assert diagram_payload(record.process_model)['process_model']['nodes'] == diagram_payload(model)['process_model']['nodes']


def test_a_document_without_a_model_block_is_parsed_as_before():
    assert parse_process('s', 'Pack', '# Pack\n\n## Key business rules\n\n- A rule.\n').process_model is None
    assert model_from_capture('## Process model\n\n```json\n{"schema": "other"}\n```') is None


@pytest.fixture
def sales(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    os.environ.update(SME_TIBI_VOICE_URL='http://127.0.0.1:9', SALES_GOVERNANCE_AUTO_REVIEW='0',
                      PROCESS_DIAGRAM_SERVICE_URL='http://127.0.0.1:9')
    root = tmp_path / 'sales'
    app = create_sales_app(root)
    app.state.retrieval.embedder = None
    with TestClient(app) as client:
        token = client.post('/api/auth/login', json={'password': (root / 'local-access.key').read_text().strip()}).json()['token']
        client.headers.update({'Authorization': f'Bearer {token}'})
        client.post('/api/spaces', json={'name': 'BeePee'})
        yield client


def test_a_saved_capture_waits_for_approval_in_the_organisation_then_feeds_its_registry(sales):
    bipi = {'X-OpsAtlas-Space': 'beepee'}
    model = interviewed()
    live = sales.post('/api/process/interview-map', json={'process_model': model}, headers=bipi).json()
    assert live['status'] == 'unavailable' and 'Start it from Status' in live['message']  # no diagram service in tests
    saved = sales.post('/api/process/captures', headers=bipi, json={'process_model': model, 'process': 'p1',
                                                                    'interview': 'abc123', 'organisation': 'BeePee'})
    assert saved.status_code == 200, saved.text
    source = saved.json()['source_id']
    assert saved.json()['approval_status'] != 'approved'
    assert source in {s['id'] for s in sales.get('/api/sources', headers=bipi).json()}
    assert source not in {s['id'] for s in sales.get('/api/sources').json()}  # the organisation's, not the guide's
    assert sales.get('/api/process/registry', headers=bipi).json() == []  # not until the Human approves it
    assert sales.post(f'/api/governance/sources/{source}/approve', headers=bipi).status_code == 200
    [record] = sales.get('/api/process/registry', headers=bipi).json()
    assert record['name'] == 'Ordering parts' and record['process_model']['processes'][0]['name'] == 'Ordering parts'
    assert sales.get(f'/api/process/diagrams/{source}', headers=bipi).json()['status'] == 'unavailable'
    assert sales.post('/api/process/captures', headers=bipi, json={'process_model': model, 'process': 'p9', 'interview': 'x',
                                                                   'organisation': 'BeePee'}).status_code == 400
    assert sales.post('/api/process/interview-map', headers=bipi, json={'process_model': {}}).status_code == 400
