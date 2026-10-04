"""The machine indicator on the Talk with Tibi page (TIBI E2): who is using the graphics processor, memory, the
processors and OpsAtlas's loaded models, with plain advice when Tibi's voice is at risk (1 October 2026)."""
import pytest

from services.opsatlas_sales import machine


def ioreg(*clients):
    """ioreg's listing of graphics-processor clients: (pid, name, accumulated GPU time in ns) each."""
    return ''.join(f'+-o AGXDeviceUserClient  <class AGXDeviceUserClient>\n  {{\n    "IOUserClientCreator" = "pid {pid}, '
                   f'{name}"\n    "AppUsage" = ({{"accumulatedGPUTime"={ns},"API"="Metal"}})\n  }}\n'
                   for pid, name, ns in clients)


@pytest.fixture
def mac(monkeypatch, tmp_path):
    """A Mac whose readings the test sets: graphics-processor time per client, processes, memory and swap."""
    store = tmp_path / 'models'
    (store / 'manifests/registry.ollama.ai/library/qwen3.5').mkdir(parents=True)
    (store / 'manifests/registry.ollama.ai/library/qwen3.5/35b-a3b').write_text(
        '{"layers": [{"mediaType": "application/vnd.ollama.image.model", "digest": "sha256:aaa"}]}')
    monkeypatch.setenv('OLLAMA_MODELS', str(store))
    monkeypatch.setattr(machine, '_blobs', {})
    state = {'gpu': [], 'swap': 100}
    commands = {
        11: (f'/Applications/Ollama.app/Contents/Resources/llama-server --model {store}/blobs/sha256-aaa --port 1', 22_000_000),
        12: ('/Applications/Ollama.app/Contents/Resources/llama-server --model /elsewhere/blobs/sha256-bbb', 27_000_000),
        13: ('/repo/services/sme_interviewer/.venv/bin/python /repo/services/sme_interviewer/worker.py higgs /x', 9_000_000),
        14: ('/System/Library/PrivateFrameworks/SkyLight.framework/Resources/WindowServer', 50_000),
    }

    def run(*command):
        if command[0] == 'ioreg':
            return ioreg(*state['gpu'])
        if command[0] == 'ps':
            pids = [int(p) for p in command[-1].split(',')]
            return ''.join(f'{pid} {commands[pid][1]} {commands[pid][0]}\n' for pid in pids if pid in commands)
        if command[0] == 'sysctl':
            return ('68719476736\n' f"{state.get('free', 40)}\n" f"{state.get('pressure', 1)}\n"
                    'total = 8192.00M  used = 6656.00M  free = 1536.00M  (encrypted)\n')
        if command[0] == 'vm_stat':
            return f'Swapouts:                            {state["swap"]}.\n'
        return ''
    monkeypatch.setattr(machine, '_run', run)
    monkeypatch.setattr(machine, 'loaded_models', lambda: [{'name': 'qwen3.5:35b-a3b', 'role': "Tibi's note-taker", 'gb': 22.5}])
    monkeypatch.setattr(machine.time, 'sleep', lambda s: None)
    monkeypatch.setattr(machine, 'on_macos', lambda: True)
    clock = {'now': 1000.0}
    monkeypatch.setattr(machine.time, 'monotonic', lambda: clock['now'])
    return state, clock


class Log:
    def __init__(self):
        self.lines = []

    def write(self, kind, **fields):
        self.lines.append((kind, fields))


def test_each_app_gets_its_share_of_the_graphics_processor_and_the_voice_at_risk_is_said(mac):
    state, clock = mac
    log = Log()
    reader = machine.Machine(log)
    state['gpu'] = [(11, 'llama-server', 0), (12, 'llama-server', 0), (13, 'python3.12', 0), (14, 'WindowServer', 0)]
    reader.read()  # the baseline (a first reading takes two, half a second apart)
    clock['now'] += 2.0
    # Over two seconds: the other app's model 1.4 s of GPU time, OpsAtlas's note-taker 0.3 s, Tibi's voice 0.2 s.
    state['gpu'] = [(11, 'llama-server', 300_000_000), (12, 'llama-server', 1_400_000_000),
                    (13, 'python3.12', 200_000_000), (14, 'WindowServer', 20_000_000)]
    reading = reader.read()
    users = {u['group']: u for u in reading['gpu']['users']}
    assert users['other_models']['share'] == 70 and users['other_models']['gb'] == 25.7
    assert users['models']['share'] == 15 and users['models']['models'] == ['qwen3.5:35b-a3b']
    assert users['voice']['share'] == 10 and users['screen']['share'] == 1
    assert reading['gpu']['busy'] == 96
    assert reading['level'] == 'strained' and "Another app's AI model is using 70%" in reading['advice']
    assert reading['memory'] == {'total_gb': 64, 'free_pct': 40, 'pressure': 'normal', 'swap_used_gb': 6.5, 'swapping': False}
    assert reading['models'][0]['role'] == "Tibi's note-taker"
    # The change of level is in the activity log, so a broken-up interview can be traced to it.
    assert log.lines[-1][0] == 'machine' and log.lines[-1][1]['event'] == 'machine strained'
    assert log.lines[-1][1]['top'][0] == {'who': "Another app's AI model", 'share': 70}


def test_an_idle_model_of_another_app_and_swapping_are_said_plainly(mac):
    state, clock = mac
    reader = machine.Machine()
    state['gpu'] = [(11, 'llama-server', 0), (12, 'llama-server', 0)]
    reader.read()
    clock['now'] += 3.0
    reading = reader.read()
    assert reading['level'] == 'busy'
    assert reading['advice'].startswith("Another app's AI model is loaded (25.7 GB). It is idle now")
    # Short of memory and swapping now: strained, whatever the graphics processor is doing.
    state.update(free=12, swap=180)
    clock['now'] += 3.0
    reading = reader.read()
    assert reading['memory']['swapping'] and reading['level'] == 'strained'
    assert 'swapping' in reading['advice'] and "Another app's AI model holds 25.7 GB" in reading['advice']


def test_a_reading_this_fresh_is_given_again_and_a_quiet_mac_says_nothing(mac):
    state, clock = mac
    reader = machine.Machine()
    state['gpu'] = [(14, 'WindowServer', 0)]
    first = reader.read()
    clock['now'] += 0.1
    assert reader.read() is first
    clock['now'] += 3.0
    state['gpu'] = [(14, 'WindowServer', 60_000_000)]
    reading = reader.read()
    assert reading['level'] == 'ok' and reading['advice'] == '' and reading['gpu']['busy'] == 2


def test_readings_are_unavailable_off_macos(monkeypatch):
    monkeypatch.setattr(machine, 'on_macos', lambda: False)
    assert machine.Machine().read() == {'available': False, 'reason': 'Readings are available on macOS only.'}


def test_the_machine_reading_needs_the_operator_sign_in(tmp_path, monkeypatch):
    import os

    from fastapi.testclient import TestClient
    from iam_helpers import sign_in

    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    os.environ['SME_TIBI_VOICE_URL'] = 'http://127.0.0.1:9'
    monkeypatch.setattr(machine.Machine, 'read', lambda self: {'available': False, 'reason': 'test'})
    app = create_sales_app(tmp_path / 'sales')
    with TestClient(app) as client:
        assert client.get('/api/tibi/machine').status_code == 401
        token = sign_in(client, app)
        response = client.get('/api/tibi/machine', headers={'Authorization': f'Bearer {token}'})
        assert response.status_code == 200 and response.json() == {'available': False, 'reason': 'test'}
