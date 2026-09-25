"""The OpsAtlas product ontology: governed product facts for Tibi and the sales pitch."""
import json

import pytest

from services.opsatlas_sales import claims
from services.opsatlas_sales.ontology import CONTENT, ProductOntology

FOUNDATION = json.loads((CONTENT.parent / 'foundation.json').read_text())
CURATED = json.loads(CONTENT.read_text())


def rows(disabled=()):
    return [{**r, 'eligible': r['id'] not in disabled, 'sha256': r['id'] * 2, 'source_id': 's-' + r['id']}
            for r in FOUNDATION]


@pytest.fixture
def ontology(tmp_path):
    graph = ProductOntology(tmp_path / 'product-ontology.db')
    graph.ensure(rows())
    return graph


def test_curated_objects_rest_on_foundation_records_and_links_name_known_objects():
    ids = {r['id'] for r in FOUNDATION}
    objects = {o['id']: o for o in CURATED['objects']}
    for item in CURATED['objects']:
        assert item['type'] == 'topic' or (item['evidence'] and set(item['evidence']) <= ids), item['id']
    for kind, source, target in CURATED['links']:
        assert source in objects and target in objects, (kind, source, target)


def test_every_fact_stays_within_the_records_it_rests_on(ontology):
    # Curated wording must not add a figure, standard or claim term that the records do not state.
    text = ' '.join(r['title'] + '. ' + r['text'] for r in FOUNDATION)
    for item in ontology.graph['objects'].values():
        if fact := ontology.fact(item):
            assert not claims.unsupported(fact, text), (item['id'], claims.unsupported(fact, text))
    for question in ('What is delivered and what is planned?', 'Does it run locally?', 'What are the limitations?',
                     'What components is it built with?'):
        for fact in ontology.overview(question.lower()):
            assert not claims.unsupported(fact, text), fact


def test_built_in_the_platform_store_and_only_from_enabled_records(tmp_path):
    graph = ProductOntology(tmp_path / 'product-ontology.db')
    built = graph.ensure(rows())
    assert built['unusable'] == []
    assert built['counts']['objects']['record'] == len(FOUNDATION)
    assert graph.store.get('capability:enterprise_activity_model').properties['status'] == 'delivered'
    # Withdrawing a record withdraws everything that rests on it, and a topic needs two usable aspects.
    built = graph.ensure(rows(disabled={'real-deployment', 'deployment', 'security'}))
    missing = {u['id'] for u in built['unusable']}
    assert {'own-data', 'security-data', 'security-hosting', 'security-controls', 'anam', 'digital-sme'} <= missing
    assert 'security' in missing and graph.store.get('topic:security') is None
    assert graph.store.get('capability:own_data') is None and graph.match('Is it secure enough?')['topic'] is None
    # Same enabled records, same graph: no rebuild on every request.
    before = graph.graph
    assert graph.ensure(rows(disabled={'real-deployment', 'deployment', 'security'})) is before


def test_product_part_names_are_routing_signals_and_general_words_are_not(ontology):
    assert {n['alias'] for n in ontology.match('What is the ontology layer?')['names']} >= {'ontology layer'}
    assert ontology.match('What is an ontology?')['names'] == []
    assert ontology.match('Good morning Tibi!')['names'] == []
    eam = ontology.match('Where can I find the enterprise activity model?')
    assert eam['records'][:2] == ['activity-model', 'architecture']
    assert 'Web control panel' in eam['facts'][0]
    assert not any(f.startswith('Local language models') for f in eam['facts'])  # "model" was spent on the name


def test_broad_topic_without_an_aspect_is_a_clarification_signal(ontology):
    broad = ontology.match('Is it secure enough for a bank?')
    assert broad['topic']['id'] == 'topic:security' and broad['aspects'] == [] and broad['records'] == []
    assert len(broad['topic']['aspects']) == 4
    precise = ontology.match('Is my data secure?')
    assert [a['id'] for a in precise['aspects']][:1] == ['aspect:security_data']
    assert precise['records'] == ['data', 'real-deployment']


def test_real_use_questions_bring_the_real_deployment_record(ontology):
    found = ontology.match('When adopted by an organization like a bank, it will actually hold real data. Is that correct?')
    assert found['records'][:2] == ['real-deployment', 'data']
    assert any('planned' in f and 'own data' in f for f in found['facts'])


def test_whole_product_questions_get_overview_facts(ontology):
    status = ontology.match('What is delivered and what is planned?')['facts']
    assert any(f.startswith('Delivered:') and 'Planned:' in f for f in status)
    hosting = ' '.join(ontology.match('Does it run locally or in the cloud?')['facts'])
    assert 'Runs locally' in hosting and 'Managed external service: Anam avatar rendering' in hosting
    assert sum(len(f) for f in ontology.match('What are the limitations and components?')['facts']) <= 900


def test_sales_api_serves_the_ontology_and_matches_it_on_search(tmp_path, monkeypatch):
    import os

    from fastapi.testclient import TestClient

    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    root = tmp_path / 'sales'
    app = create_sales_app(root)
    app.state.retrieval.embedder = None  # hermetic: lexical ranking only
    headers = {'x-sales-token': (root / 'local-access.key').read_text()}
    with TestClient(app) as c:
        assert c.get('/api/sales/ontology').status_code == 403
        assert c.get('/api/sales/ontology', headers=headers).json()['objects'] == []  # nothing enabled yet
        rows = {r['id']: r for r in c.get('/api/sales/knowledge', headers=headers).json()['records']}
        c.post('/api/sales/knowledge/limitations/review', headers=headers,
               json={'approve': True, 'expected_hash': rows['limitations']['sha256']})
        graph = c.get('/api/sales/ontology', headers=headers).json()
        assert 'limitation:no_sso' in {o['id'] for o in graph['objects']}
        assert all(o['evidence'] == ['limitations'] for o in graph['objects'])
        found = c.post('/api/sales/search', headers=headers, json={'q': 'Does it support single sign-on?'}).json()
        assert 'No enterprise identity or single sign-on (proof of concept).' in found['ontology']['facts']
    assert (root / 'core/product-ontology.db').exists() and (root / 'core/ontology.db').exists()
