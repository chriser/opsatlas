import pytest

from services.opsatlas_sales import manage


def test_stop_waits_until_retiring_registrations_disappear(monkeypatch):
    states = {'diagrams': iter([True, False]), 'voice': iter([True, True, True, False]), 'core': iter([True, True, False])}
    events = []
    monkeypatch.setattr(manage, 'loaded', lambda name: next(states[name]))
    monkeypatch.setattr(manage.subprocess, 'run', lambda args, **kw: events.append(args))
    monkeypatch.setattr(manage.time, 'sleep', lambda delay: events.append(delay))
    manage.stop()
    assert events.count(0.1) == 3
    assert events[0][1] == 'bootout' and events[-2][1] == 'bootout'
    assert [e[-1].rsplit('.', 1)[-1] for e in events if isinstance(e, list)] == ['diagrams', 'voice', 'core']


def test_stop_does_not_report_success_when_registration_remains(monkeypatch):
    monkeypatch.setattr(manage, 'loaded', lambda name: True)
    monkeypatch.setattr(manage.subprocess, 'run', lambda *a, **kw: None)
    monkeypatch.setattr(manage.time, 'sleep', lambda delay: None)
    with pytest.raises(RuntimeError, match='still shutting down'):
        manage.stop()


def test_restart_touches_only_this_workspaces_own_services(monkeypatch):
    runs, spawned = [], []
    monkeypatch.setattr(manage, 'loaded', lambda name: True)
    monkeypatch.setattr(manage.subprocess, 'run', lambda args, **kw: runs.append(args))
    monkeypatch.setattr(manage.subprocess, 'Popen', lambda args, **kw: spawned.append((args, kw)))
    manage.restart('voice')
    assert runs == [['launchctl', 'kickstart', '-k', manage.identity('voice')]]
    assert manage.identity('voice').endswith('/com.opsatlas.tiberius-sales.voice')
    manage.restart_later('core')
    [(args, kw)] = spawned
    assert args[-1] == manage.identity('core') and 'kickstart -k' in args[2] and kw['start_new_session'] is True
    with pytest.raises(ValueError):
        manage.restart('ollama')


def test_restart_refuses_a_service_launchd_does_not_run(monkeypatch):
    monkeypatch.setattr(manage, 'loaded', lambda name: False)
    with pytest.raises(RuntimeError, match='not running under launchd'):
        manage.restart('voice')
    with pytest.raises(RuntimeError, match='not running under launchd'):
        manage.restart_later('core')
