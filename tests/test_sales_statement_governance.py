"""Statement-level governance of the OpsAtlas Sales records (GOV S9): review, agenda, decision, approval, records."""
import hashlib
import json
import math
import re

import pytest

from assistant.ingestion.service import ingest_source
from assistant.ingestion.store import SectionStore
from assistant.sources.register import SourceRegister
from assistant.sources.service import register_upload
from services.opsatlas_sales import statement_governance
from services.opsatlas_sales.governance import GovernanceDesk
from services.opsatlas_sales.knowledge import Knowledge
from services.opsatlas_sales.statement_governance import SalesStatementReview
from services.opsatlas_sales.workspace import workspace
from tests.door_helpers import decided


class Embedder:
    def embed(self, texts):
        out = []
        for text in texts:
            vector = [0.0] * 256
            for word in re.findall(r'[a-z]+', text.lower()):
                vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % 256] += 1.0
            norm = math.sqrt(sum(x * x for x in vector)) or 1.0
            out.append([x / norm for x in vector])
        return out


class Judge:
    """"does not support X" against "supports X" is a conflict; the same words are a duplicate."""

    def __init__(self):
        self.seen = []

    def judge(self, a, b):
        self.seen.append((a['document'], b['document']))
        ta, tb = a['text'].lower(), b['text'].lower()
        if ('not' in ta.split()) != ('not' in tb.split()) and 'sign-on' in ta and 'sign-on' in tb:
            return {'relation': 'conflict', 'reason': 'One says single sign-on is supported, the other that it is not.'}
        if set(re.findall(r'[a-z]+', ta)) == set(re.findall(r'[a-z]+', tb)):
            return {'relation': 'duplicate', 'reason': 'The same guidance twice.'}
        return {'relation': 'neither', 'reason': 'Compatible.'}


class Actions:
    def __init__(self, holder):
        self.calls, self.holder = [], holder

    def execute(self, name, params, actor):
        self.calls.append((name, params))
        self.holder['desk'].accepted.accept(params['source_id'], params['check'], params['detail'])
        return type('Result', (), {'outcome': 'ok'})()


RECORDS = [
    ('security', 'Security controls in the proof of concept', 'available', None,
     'The proof of concept does not support single sign-on with a corporate directory today.'),
    ('sso-claim', 'Security · Chris', 'available', 'Chris',
     'The proof of concept supports single sign-on with a corporate directory today.'),
    ('governance', 'Knowledge governance and lifecycle', 'available', None,
     'Every record is approved by a person before Tibi uses it in an answer.'),
    ('approval', 'Approval of records', 'available', None,
     'Every record is approved by a person before Tibi uses it in an answer.'),
    ('next-steps', 'Path to production', 'planned', None,
     "A production deployment would connect to the organisation's own identity provider for single sign-on."),
]


@pytest.fixture
def sales(tmp_path):
    root = workspace(tmp_path / 'sales')
    register = SourceRegister(root / 'core')
    sections = SectionStore(register.base_dir)
    paper_text = b'# 3.2 Walkthrough\n\nEvery record is approved by a person before Tibi uses it in an answer.\n'
    paper = register_upload(register, 'paper.md', paper_text, 'DT603 Part A, section 3.2')
    ingest_source(register, sections, paper.id)
    decided(register, paper.id, approval_status='approved')
    rows = []
    for identifier, title, status, contributor, text in RECORDS:
        source = register_upload(register, identifier + '.md', f'# {title}\n\n{text}\n'.encode(), title)
        ingest_source(register, sections, source.id)
        # Seeded records are approved; a contributed claim waits for the Human.
        decided(register, source.id, approval_status='pending' if contributor else 'approved')
        rows.append({'id': identifier, 'title': title, 'text': text, 'status': status, 'topics': [identifier], 'source_id': source.id,
                     'sha256': 'x', 'references': [{'path': 'paper:03-2.md', 'source_id': paper.id, 'sha256': 'y'}]
                     if identifier == 'governance' else [], 'versions': [],
                     **({'provenance': {'contributor': contributor, 'topic': 'security'}} if contributor else {})})
    conversation = register_upload(register, 'style.md', b'# Tibi style\n\nTibi does not support crude jokes or single sign-on talk.\n',
                                   'Tibi style')
    ingest_source(register, sections, conversation.id)
    decided(register, conversation.id, approval_status='approved')
    rows.append({'id': 'style', 'title': 'Tibi style', 'text': 'x', 'status': 'available', 'kind': 'conversation', 'topics': [],
                 'source_id': conversation.id, 'sha256': 'x', 'references': [], 'versions': []})
    (register.base_dir / 'sales-records.json').write_text(json.dumps(rows))
    knowledge = Knowledge(register)
    holder = {}
    desk = GovernanceDesk(register, sections, None, Actions(holder), knowledge)
    holder['desk'] = desk
    judge = Judge()
    desk.statements = SalesStatementReview(register, sections, knowledge, embedder=Embedder(), judge=judge, judge_name='fake')
    return desk, register, knowledge, judge, paper


def test_the_review_finds_conflicts_and_duplicates_between_records_not_their_evidence(sales):
    desk, register, knowledge, judge, paper = sales
    result = desk.statements.run()
    assert result['raised'] == {'conflict': 1, 'duplicate': 1}
    # The pending contribution is governed before approval; the cited paper and conversation style never meet product records.
    items = [i for i in desk.agenda()['items'] if i['kind'] == 'statement']
    assert [i['relation'] for i in items] == ['conflict', 'duplicate']  # conflicts lead the agenda
    conflict = items[0]
    assert {s['record_id'] for s in conflict['statements']} == {'security', 'sso-claim'}
    assert any(s['contributor'] == 'Chris' for s in conflict['statements'])
    assert not any(paper.id in (i['source_id'], i['source_b_id']) for i in items)
    # The judge saw each record's status as its scope, and never paired conversation style with product records.
    assert judge.seen and all(re.search(r'\((available|planned)\)$', doc) for pair in judge.seen for doc in pair)
    assert not any('Tibi style' in doc for pair in judge.seen for doc in pair)
    assert desk.statements.status()['latest']['raised'] == {'conflict': 1, 'duplicate': 1}


def test_an_approved_supersede_withdraws_the_other_record_and_closes_the_finding(sales):
    desk, register, knowledge, _, _ = sales
    desk.statements.run()
    conflict = next(i for i in desk.agenda()['items'] if i.get('relation') == 'conflict')
    keep = 'a' if conflict['statements'][0]['record_id'] == 'security' else 'b'
    with pytest.raises(ValueError, match='Choose how to settle'):
        desk.propose({'issue_key': conflict['key'], 'contributor': 'Chris', 'session_id': 's', 'answer': 'Merge them.',
                      'resolution': {'decision': 'merge', 'keep': keep}})
    answer = desk.propose({'issue_key': conflict['key'], 'contributor': 'Chris', 'session_id': 's',
                           'answer': 'The security record is right; single sign-on is not in the proof of concept.',
                           'resolution': {'decision': 'supersede', 'keep': keep}})
    assert answer['status'] == 'pending' and 'will be withdrawn' in answer['verification'][0]['message']
    assert len(answer['statements']) == 2
    # Nothing changes until the Human approves.
    claim = next(r for r in knowledge.records() if r['id'] == 'sso-claim')
    assert register.get(claim['source_id']).approval_status == 'pending'
    desk.review(answer['id'], answer['text_sha256'], True)
    assert register.get(claim['source_id']).approval_status == 'rejected'
    claim = next(r for r in knowledge.records() if r['id'] == 'sso-claim')
    assert claim['governance'][-1]['withdrawn'] and claim['governance'][-1]['kept'] == 'security'
    assert register.get(next(r for r in knowledge.records() if r['id'] == 'security')['source_id']).approval_status == 'approved'
    assert not any(i.get('relation') == 'conflict' for i in desk.agenda()['items'])
    # A later review no longer governs the withdrawn claim.
    assert desk.statements.run()['raised']['conflict'] == 0


def _supersede(desk):
    desk.statements.run()
    conflict = next(i for i in desk.agenda()['items'] if i.get('relation') == 'conflict')
    keep = 'a' if conflict['statements'][0]['record_id'] == 'security' else 'b'
    return desk.propose({'issue_key': conflict['key'], 'contributor': 'Chris', 'session_id': 's',
                         'answer': 'The security record is correct; withdraw the conflicting claim.',
                         'resolution': {'decision': 'supersede', 'keep': keep}})


def test_an_old_decision_is_not_applied_to_a_record_corrected_since(sales):
    # Audit F05: the claim is corrected to agree, and approved, before the old supersede answer is approved.
    desk, register, knowledge, _, _ = sales
    answer = _supersede(desk)
    rows = knowledge.records()
    claim = next(r for r in rows if r['id'] == 'sso-claim')
    claim['text'] = 'The proof of concept does not support single sign-on with a corporate directory today.'
    body = ('# ' + claim['title'] + '\n\n' + claim['text'] + '\n').encode()
    claim['sha256'] = hashlib.sha256(body).hexdigest()
    knowledge._save(rows)
    register.write_content(claim['source_id'], body)
    decided(register, claim['source_id'], content_sha256=claim['sha256'], version=2, approval_status='approved')
    ingest_source(register, desk.sections, claim['source_id'])
    # The finding was about the old wording: it no longer stands.
    assert not any(f['relation'] == 'conflict' for f in desk.statements.findings())
    with pytest.raises(ValueError, match='changed after it was proposed'):
        desk.review(answer['id'], answer['text_sha256'], True)
    assert register.get(claim['source_id']).approval_status == 'approved'  # the corrected record is untouched
    stale = next(a for a in desk.answers() if a['id'] == answer['id'])
    assert stale['status'] == 'stale' and stale['stale']['changed']
    with pytest.raises(ValueError):
        desk.review(answer['id'], answer['text_sha256'], True)  # and it cannot be approved later either


def test_a_withdrawn_or_deleted_record_also_stops_an_old_decision(sales):
    desk, register, knowledge, _, _ = sales
    answer = _supersede(desk)
    security = next(r for r in knowledge.records() if r['id'] == 'security')
    decided(register, security['source_id'], approval_status='rejected')
    with pytest.raises(ValueError, match='changed after it was proposed'):
        desk.review(answer['id'], answer['text_sha256'], True)
    claim = next(r for r in knowledge.records() if r['id'] == 'sso-claim')
    assert register.get(claim['source_id']).approval_status == 'pending'


def test_a_failed_decision_closes_no_issue(sales, monkeypatch):
    desk, register, knowledge, _, _ = sales
    answer = _supersede(desk)
    closed = []
    original = desk.actions.execute

    def execute(name, payload, actor):
        closed.append(name)
        return original(name, payload, actor)

    def settle(*args):
        raise ValueError('A record in this finding changed; refresh the review')

    monkeypatch.setattr(desk.actions, 'execute', execute)
    monkeypatch.setattr(knowledge, 'settle', settle)
    with pytest.raises(ValueError):
        desk.review(answer['id'], answer['text_sha256'], True)
    assert 'accept_issue' not in closed
    assert next(a for a in desk.answers() if a['id'] == answer['id'])['status'] == 'pending'


def test_a_dispute_withdraws_both_and_other_decisions_change_no_approval(sales):
    desk, register, knowledge, _, _ = sales
    desk.statements.run()
    items = {i['relation']: i for i in desk.agenda()['items'] if i['kind'] == 'statement'}
    duplicate = desk.propose({'issue_key': items['duplicate']['key'], 'contributor': 'Dan', 'session_id': 's',
                              'answer': 'Both are intended: one explains governance, the other approval.',
                              'resolution': {'decision': 'intended'}})
    desk.review(duplicate['id'], duplicate['text_sha256'], True)
    assert all(register.get(r['source_id']).approval_status == 'approved'
               for r in knowledge.records() if r['id'] in ('governance', 'approval'))
    dispute = desk.propose({'issue_key': items['conflict']['key'], 'contributor': 'Chris', 'session_id': 's',
                            'answer': 'Not sure which is right; Dan needs to confirm.', 'resolution': {'decision': 'dispute'}})
    desk.review(dispute['id'], dispute['text_sha256'], True)
    pair = [r for r in knowledge.records() if r['id'] in ('security', 'sso-claim')]
    assert all(r.get('disputed') and register.get(r['source_id']).approval_status == 'rejected' for r in pair)
    assert all(knowledge.review_block(r) == 'Resolve the dispute before enabling this record' for r in pair)


def test_local_judging_is_the_default_and_a_frontier_judge_needs_the_data_owners_approval(monkeypatch):
    monkeypatch.delenv('SALES_GOVERNANCE_JUDGE', raising=False)
    assert statement_governance.profile()['name'] == 'local' and not statement_governance.profile()['data_leaves']
    monkeypatch.setenv('SALES_GOVERNANCE_JUDGE', 'anthropic:claude-opus-5-5')
    monkeypatch.delenv('SALES_GOVERNANCE_FRONTIER_APPROVED', raising=False)
    chosen = statement_governance.profile()
    assert chosen['name'] == 'local' and 'without the data owner' in chosen['note']
    monkeypatch.setenv('SALES_GOVERNANCE_FRONTIER_APPROVED', 'yes')
    chosen = statement_governance.profile()
    assert chosen['judge'] == 'claude-opus-5-5' and chosen['data_leaves']


def test_the_review_runs_in_the_background_once(sales):
    desk, *_ = sales
    first = desk.statements.start()
    second = desk.statements.start()
    assert first['status'] == 'running' and second['status'] in ('running', 'finished')
    desk.statements.thread.join(10)
    assert desk.statements.status()['status'] == 'finished'


def test_changes_during_a_review_are_reviewed_by_one_follow_up_run(sales):
    # Audit F06: requests while a review runs are not dropped, and several coalesce into one follow-up.
    import threading
    desk, register, knowledge, _, _ = sales
    original = desk.statements.run
    started, release, calls = threading.Event(), threading.Event(), []

    def held(progress=None):
        calls.append(desk.statements.revision())
        if len(calls) == 1:
            started.set()
            release.wait(5)
        return original(progress)

    desk.statements.run = held
    desk.statements.start()
    started.wait(5)
    claim = next(r for r in knowledge.records() if r['id'] == 'sso-claim')
    decided(register, claim['source_id'], approval_status='approved')  # a change arriving mid-review
    for _ in range(3):
        assert desk.statements.start()['queued']
    release.set()
    for _ in range(100):
        if desk.statements.status()['status'] == 'finished' and not desk.statements.running:
            break
        threading.Event().wait(0.05)
    status = desk.statements.status()
    assert len(calls) == 2 and calls[0] != calls[1]  # one follow-up, reading the newest revision
    assert status['status'] == 'finished' and not status['queued'] and status['up_to_date']


def test_a_failed_review_keeps_a_queued_change_visible(sales):
    import threading
    desk, *_ = sales
    started, release = threading.Event(), threading.Event()

    def failing(progress=None):
        started.set()
        release.wait(5)
        raise RuntimeError('the judge is unavailable')

    desk.statements.run = failing
    desk.statements.start()
    started.wait(5)
    desk.statements.start()
    release.set()
    desk.statements.thread.join(5)
    status = desk.statements.status()
    assert status['status'] == 'failed' and status['queued'] and not status['up_to_date']


def test_a_proposed_claim_starts_a_review_of_its_own_pairs(tmp_path, monkeypatch):
    import os

    from fastapi.testclient import TestClient

    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    started = []
    monkeypatch.setattr(Knowledge, 'propose', lambda self, data: {'id': 'claim', 'eligible': False})
    monkeypatch.setattr(SalesStatementReview, 'start', lambda self: started.append(True) or {'status': 'running'})
    root = tmp_path / 'sales'
    app = create_sales_app(root)
    key = {'x-sales-token': (root / 'local-access.key').read_text().strip()}
    with TestClient(app) as client:
        os.environ['SALES_GOVERNANCE_AUTO_REVIEW'] = '1'
        assert client.post('/api/sales/proposals', json={'any': 'claim'}, headers=key).json()['id'] == 'claim'
        assert started == [True]
        os.environ['SALES_GOVERNANCE_AUTO_REVIEW'] = '0'
        client.post('/api/sales/proposals', json={'any': 'claim'}, headers=key)
        assert started == [True]


def test_the_proof_of_concept_and_a_real_deployment_are_never_judged_against_each_other(sales):
    desk, register, knowledge, judge, _ = sales
    rows = json.loads((register.base_dir / 'sales-records.json').read_text())
    text = 'A real deployment does not support single sign-on with a corporate directory today.'
    source = register_upload(register, 'real-deployment.md', f'# Real deployment\n\n{text}\n'.encode(), 'Real deployment')
    ingest_source(register, desk.sections, source.id)
    decided(register, source.id, approval_status='approved')
    rows.append({'id': 'real-deployment', 'title': 'Real deployment', 'text': text, 'status': 'planned', 'topics': [],
                 'source_id': source.id, 'sha256': 'x', 'references': [], 'versions': []})
    # A claim filed under the real-deployment topic that speaks about the proof of concept is scoped by its own words.
    claim = next(r for r in rows if r['id'] == 'sso-claim')
    claim['provenance']['topic'] = 'real-deployment'
    (register.base_dir / 'sales-records.json').write_text(json.dumps(rows))
    result = desk.statements.run()
    aside = result['set_aside_by_scope']
    assert aside['by_reason']['phase'] >= 1
    assert all('Real deployment (planned)' in [s['source_title'] for s in p['statements']] for p in aside['pairs'])
    assert not any('Real deployment (planned)' in pair for pair in judge.seen)
    # The contributed claim still meets the proof-of-concept security record, and the page shows each side's scope.
    conflict = next(f for f in desk.statements.findings() if f['relation'] == 'conflict')
    assert {s['record_id'] for s in conflict['statements']} == {'security', 'sso-claim'}
    assert all(s['applies_to'] == 'the proof of concept' for s in conflict['statements'])
    assert desk.statements.status()['latest']['set_aside_by_scope']['phase'] >= 1


def test_a_withdrawal_goes_through_the_audited_action_so_the_facts_map_is_rebuilt(sales):
    """REF S4: settling a conflict withdraws the losing record through reject_source, whose side effects rebuild the
    process registry and the facts map; before, the register was changed directly and the map kept the record."""
    desk, register, knowledge, _, _ = sales

    class Recorder:
        def __init__(self):
            self.calls = []

        def execute(self, name, params, actor):
            self.calls.append((name, params['source_id'], actor.type))
            decided(register, params['source_id'], approval_status='rejected' if name == 'reject_source' else 'approved')
            return type('Result', (), {'outcome': 'ok', 'message': ''})()

    knowledge.actions = Recorder()
    answer = _supersede(desk)
    desk.review(answer['id'], answer['text_sha256'], True)
    claim = next(r for r in knowledge.records() if r['id'] == 'sso-claim')
    assert ('reject_source', claim['source_id'], 'operator') in knowledge.actions.calls
    assert register.get(claim['source_id']).approval_status == 'rejected'
