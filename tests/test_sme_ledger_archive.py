"""More than 50 conversations: older ended ones are archived, never deleted, and stay readable (audit F11)."""
import json
import uuid

import pytest

from services.sme_interviewer import ledger as ledger_module
from services.sme_interviewer.evidence import FixtureEvidence
from services.sme_interviewer.ledger import Ledger

SCOPE = {'region': 'unknown', 'variant': 'unknown', 'date': ''}


def start(store):
    return store.create(FixtureEvidence().snapshot(), SCOPE, str(uuid.uuid4()))


def test_sixty_start_and_end_cycles_all_work_and_nothing_is_deleted(tmp_path):
    store = Ledger(tmp_path / 'ledger.db')
    ids = []
    for _ in range(60):
        session = start(store)
        store.pause(session['id'])  # End
        ids.append(session['id'])
    assert store.capacity() == {'working': 50, 'archived': 10, 'limit': 50}
    assert len(store.list()) == 50 and ids[0] not in {s['id'] for s in store.list()}
    assert store.get(ids[0])['id'] == ids[0] and store.events(ids[0])  # archived, still whole
    assert len(store.list(include_archived=True, limit=None)) == 60


def test_a_full_working_set_of_live_conversations_says_so_plainly(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger_module, 'WORKING', 3)
    store = Ledger(tmp_path / 'ledger.db')
    live = [start(store) for _ in range(3)]
    with pytest.raises(ValueError, match='in use at once'):
        start(store)
    # A conversation left open on a closed page for over an hour counts as abandoned, and is archived first.
    with store.connection() as connection:
        session = json.loads(connection.execute('SELECT data FROM sessions WHERE id=?', (live[0]['id'],)).fetchone()['data'])
        session['updated_at'] = '2026-01-01T00:00:00+00:00'
        connection.execute('UPDATE sessions SET data=? WHERE id=?', (json.dumps(session), live[0]['id']))
    start(store)
    assert store.capacity()['archived'] == 1 and store.get(live[0]['id'])['status'] == 'active'
