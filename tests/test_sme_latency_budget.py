"""The latency budget guards against speed creeping back (review 2 follow-up)."""
import json
import sqlite3

from services.sme_interviewer import latency_report, replay_latency


def test_replay_fails_when_first_audio_exceeds_the_budget():
    budget = json.loads(replay_latency.BUDGET.read_text())['replay']['budget']
    assert replay_latency.check_budget({'p50': budget['p50'] - 1, 'p95': budget['p95'] - 1}) == []
    breaches = replay_latency.check_budget({'p50': budget['p50'] + 100, 'p95': budget['p95'] - 1})
    assert len(breaches) == 1 and breaches[0].startswith('p50')


def test_headset_report_judges_the_latest_session(tmp_path, monkeypatch, capsys):
    path = tmp_path / 'timings.sqlite'
    con = sqlite3.connect(path)
    con.execute('CREATE TABLE timings(session TEXT, id TEXT, data TEXT, PRIMARY KEY(session,id))')

    def turn(session, index, ms, source='microphone', status='complete'):
        data = {'source': source, 'status': status, 'marks': {'speech_end': 1000, 'playback_start': 1000 + ms}}
        con.execute('INSERT INTO timings VALUES(?,?,?)', (session, f'{session}-{index}', json.dumps(data)))

    for i in range(6):
        turn('old', i, 9000)
    for i in range(6):
        turn('new', i, 1800)
    turn('new', 99, 99999, status='interrupted')
    con.commit()
    monkeypatch.setattr(latency_report, 'TIMINGS', path)
    monkeypatch.setattr('sys.argv', ['latency_report'])
    assert latency_report.main() == 0
    assert 'Latest session new' in capsys.readouterr().out
    assert latency_report.sessions(path)['old'] == [9000] * 6
