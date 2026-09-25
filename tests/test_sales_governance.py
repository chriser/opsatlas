"""Governance interviews, core side: the agenda, source verification and pending answers."""
import os

import pytest

from assistant.ingestion.service import ingest_source
from assistant.ingestion.store import SectionStore
from assistant.sources.register import SourceRegister
from assistant.sources.service import register_upload
from services.opsatlas_sales.governance import GovernanceDesk, definitions_in, mentions_in, same_expansion, spoken_title
from services.opsatlas_sales.knowledge import Knowledge
from services.opsatlas_sales.workspace import workspace

LONG = ' '.join(['This sentence keeps going with many words to make it far too long for anyone to read comfortably'] * 1)
SOURCES = {
    'glossary.md': ('Glossary', '# Glossary\n\nRetrieval-Augmented Generation (RAG) retrieves passages. '
                                'We also use Ontology-Augmented Generation for structured questions.\n'),
    'design.md': ('Design notes', '# Design\n\nThe EAM and the RAG pipeline use OAG and AI. '
                                  'See [notes](notes.md) for detail.\n\n' + ' '.join(
                                      [LONG + ' and then it continues for a good while longer still, clause after clause, '
                                       'so that the readability check counts it as dense prose.'] * 3) + '\n'),
}


class Actions:
    def __init__(self, desk_holder):
        self.calls, self.holder = [], desk_holder

    def execute(self, name, params, actor):
        self.calls.append((name, params))
        self.holder['desk'].accepted.accept(params['source_id'], params['check'], params['detail'])
        return type('Result', (), {'outcome': 'ok'})()


@pytest.fixture
def desk(tmp_path):
    root = workspace(tmp_path / 'sales')
    register = SourceRegister(root / 'core')
    sections = SectionStore(register.base_dir)
    for name, (title, text) in SOURCES.items():
        source = register_upload(register, name, text.encode(), title)
        ingest_source(register, sections, source.id)
    holder = {}
    value = GovernanceDesk(register, sections, None, Actions(holder), Knowledge(register))
    holder['desk'] = value
    return value


def test_definitions_mentions_and_spoken_titles():
    assert ('RAG', 'Retrieval-Augmented Generation') in definitions_in('Retrieval-Augmented Generation (RAG) works.')
    assert ('SME', 'subject matter expert') in definitions_in('SME (subject matter expert) interviews.')
    assert mentions_in('We use Ontology-Augmented Generation. Ontology-Augmented Generation helps.', 'OAG')[0] == (
        'Ontology-Augmented Generation', 2)
    assert same_expansion('Retrieval Augmented Generation', 'retrieval-augmented generation')
    assert spoken_title('DT603 Part A · 3.1 Implemented solution architecture') == (
        'DT603 Part A, section 3.1 Implemented solution architecture')


def test_agenda_groups_acronyms_batches_standard_ones_and_puts_correctness_first(desk):
    agenda = desk.agenda()
    kinds = [(i['kind'], i['check'], i.get('acronym')) for i in agenda['items']]
    assert kinds[0] == ('issue', 'broken_link', None)  # correctness before tidiness
    acronyms = {i['acronym']: i for i in agenda['items'] if i['kind'] == 'acronym'}
    assert set(acronyms) == {'EAM', 'OAG', 'RAG'}
    assert [k['expansion'] for k in acronyms['RAG']['known']] == ['Retrieval-Augmented Generation']
    assert [m['phrase'] for m in acronyms['OAG']['mentions']] == ['Ontology-Augmented Generation']
    standard = next(i for i in agenda['items'] if i['kind'] == 'standard')
    assert standard['acronyms'] == ['AI'] and standard['meanings'] == {'AI': 'artificial intelligence'}
    checks = [i['check'] for i in agenda['items']]
    readability = next(i for i in agenda['items'] if i['check'] == 'readability')
    assert readability['examples'] and checks.index('readability') > checks.index('undefined_acronym')
    runs = []
    original = desk.intelligence.run
    desk.intelligence.run = lambda: runs.append(1) or original()
    desk.agenda()
    assert not runs  # the scan is cached until sources or accepted issues change


def test_answers_are_verified_against_the_sources(desk):
    rag, oag = desk.item('acronym:RAG'), desk.item('acronym:OAG')
    define = lambda item, value: {'decision': 'define', 'definitions': [{'acronym': item['acronym'], 'expansion': value}]}  # noqa: E731
    assert desk.verify(rag, define(rag, 'Retrieval-Augmented Generation'), 'x')[0]['status'] == 'matches'
    wrong = desk.verify(rag, define(rag, 'Red Amber Green'), 'x')
    assert wrong[0]['status'] == 'conflicts' and wrong[0]['expected'] == 'Retrieval-Augmented Generation'
    assert desk.verify(oag, define(oag, 'Ontology-Augmented Generation'), 'x')[0]['status'] == 'matches'
    assert desk.verify(oag, define(oag, 'Open Answer Generation'), 'x')[0]['status'] == 'conflicts'
    eam = desk.item('acronym:EAM')
    found = desk.verify(eam, define(eam, 'Enterprise Activity Model'), 'x')
    assert found[0]['status'] == 'not_found'
    assert [f['status'] for f in desk.verify(eam, define(eam, 'Energy Model'), 'x')] == ['not_found', 'check']
    link = desk.agenda()['items'][0]
    claim = desk.verify(link, {'decision': 'accept'}, 'It is fine. It is 95 percent accurate.')
    assert claim and claim[0]['status'] == 'unverified' and '95%' in claim[0]['message']


def test_a_pending_answer_closes_its_issues_only_when_the_human_approves(desk):
    with pytest.raises(ValueError):
        desk.propose({'issue_key': 'acronym:RAG', 'contributor': 'Mallory', 'session_id': 's', 'answer': 'x',
                      'resolution': {'decision': 'accept'}})
    first = desk.propose({'issue_key': 'acronym:RAG', 'contributor': 'Chris', 'session_id': 's1', 'answer': 'RAG is fine',
                          'resolution': {'decision': 'accept'}})
    second = desk.propose({'issue_key': 'acronym:RAG', 'contributor': 'Chris', 'session_id': 's1',
                           'answer': 'It stands for Retrieval-Augmented Generation',
                           'resolution': {'decision': 'define', 'definitions': [
                               {'acronym': 'RAG', 'expansion': 'Retrieval-Augmented Generation'}]}})
    statuses = {a['id']: a['status'] for a in desk.answers()}
    assert statuses[first['id']] == 'superseded' and statuses[second['id']] == 'pending'
    assert second['verification'][0]['status'] == 'matches'
    assert desk.item('acronym:RAG')['answer']['status'] == 'pending'
    # The design notes list EAM, OAG and RAG: approving RAG alone does not close that issue.
    desk.review(second['id'], second['text_sha256'], True)
    design_issue = next(r for r in second['issues'] if r['source_title'] == 'Design notes')
    assert not desk.accepted.is_accepted(design_issue['source_id'], design_issue['check'], design_issue['detail'])
    for acronym, expansion in (('EAM', 'Enterprise Activity Model'), ('OAG', 'Ontology-Augmented Generation')):
        answer = desk.propose({'issue_key': 'acronym:' + acronym, 'contributor': 'Chris', 'session_id': 's1',
                               'answer': expansion, 'resolution': {'decision': 'define', 'definitions': [
                                   {'acronym': acronym, 'expansion': expansion}]}})
        desk.review(answer['id'], answer['text_sha256'], True)
    assert not desk.accepted.is_accepted(design_issue['source_id'], design_issue['check'], design_issue['detail'])  # AI
    standard = next(i for i in desk.agenda()['items'] if i['kind'] == 'standard')
    answer = desk.propose({'issue_key': standard['key'], 'contributor': 'Chris', 'session_id': 's1', 'answer': 'yes',
                           'resolution': {'decision': 'define',
                                          'definitions': [{'acronym': 'AI', 'expansion': 'artificial intelligence'}]}})
    desk.review(answer['id'], answer['text_sha256'], True)
    assert desk.accepted.is_accepted(design_issue['source_id'], design_issue['check'], design_issue['detail'])
    assert not any(i['check'] == 'undefined_acronym' for i in desk.agenda()['items'])
    with pytest.raises(ValueError):
        desk.review(answer['id'], answer['text_sha256'], True)  # already reviewed


def test_rejected_answers_leave_the_issue_open(desk):
    link = desk.agenda()['items'][0]
    answer = desk.propose({'issue_key': link['key'], 'contributor': 'Dan', 'session_id': 's2', 'answer': 'Leave it',
                           'resolution': {'decision': 'accept'}})
    desk.review(answer['id'], answer['text_sha256'], False)
    assert desk.item(link['key'])['answer'] is None and not desk.actions.calls


def test_sales_api_governance_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    root = tmp_path / 'sales'
    app = create_sales_app(root)
    app.state.retrieval.embedder = None
    headers = {'x-sales-token': (root / 'local-access.key').read_text()}
    with TestClient(app) as c:
        assert c.get('/api/sales/governance/agenda').status_code == 403
        agenda = c.get('/api/sales/governance/agenda', headers=headers).json()
        assert agenda['workspace'] == 'opsatlas-sales' and agenda['total'] >= 1
        item = agenda['items'][0]
        checked = c.post('/api/sales/governance/verify', headers=headers,
                         json={'issue_key': item['key'], 'resolution': {'decision': 'accept'}, 'answer': 'Fine as it is.'})
        assert checked.status_code == 200 and 'verification' in checked.json()
        saved = c.post('/api/sales/governance/answers', headers=headers, json={
            'issue_key': item['key'], 'contributor': 'Chris', 'session_id': 's', 'answer': 'Fine as it is.',
            'resolution': {'decision': 'accept'}}).json()
        assert saved['status'] == 'pending'
        reviewed = c.post(f"/api/sales/governance/answers/{saved['id']}/review", headers=headers,
                          json={'expected_hash': saved['text_sha256'], 'approve': True}).json()
        assert reviewed['status'] == 'approved'
        after = c.get('/api/sales/governance/agenda', headers=headers).json()
        assert item['key'] not in {i['key'] for i in after['items']} or item['kind'] != 'issue'


def test_the_agenda_still_builds_when_embeddings_are_unavailable(desk):
    class Broken:
        embedder = object()

        class cache:
            @staticmethod
            def get_or_embed(embedder, texts):
                raise ConnectionError('Ollama is not running')
    desk.retrieval = Broken()
    assert desk.agenda()['items'][0]['check'] == 'broken_link'
