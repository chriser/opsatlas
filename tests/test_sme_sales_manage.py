import pytest

from services.opsatlas_sales import manage


def test_stop_waits_until_retiring_registrations_disappear(monkeypatch):
    states = {'voice': iter([True, True, True, False]), 'core': iter([True, True, False])}
    events = []
    monkeypatch.setattr(manage, 'loaded', lambda name: next(states[name]))
    monkeypatch.setattr(manage.subprocess, 'run', lambda args, **kw: events.append(args))
    monkeypatch.setattr(manage.time, 'sleep', lambda delay: events.append(delay))
    manage.stop()
    assert events.count(0.1) == 3
    assert events[0][1] == 'bootout' and events[-2][1] == 'bootout'


def test_stop_does_not_report_success_when_registration_remains(monkeypatch):
    monkeypatch.setattr(manage, 'loaded', lambda name: True)
    monkeypatch.setattr(manage.subprocess, 'run', lambda *a, **kw: None)
    monkeypatch.setattr(manage.time, 'sleep', lambda delay: None)
    with pytest.raises(RuntimeError, match='still shutting down'):
        manage.stop()
