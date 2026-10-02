"""Manage user-session launchd services independent of the invoking task shell."""
import argparse
import json
import os
import plistlib
import socket
import subprocess
import time
import urllib.request

from assistant import settings

from .workspace import REPO, workspace

SERVICES = {
    'core': (8780, REPO / '.venv/bin/python', 'services.opsatlas_sales.app'),
    'voice': (8773, REPO / 'services/sme_interviewer/.venv/bin/python', 'services.sme_interviewer.sales_preview'),
    # The process diagram service (PI F1): lays out process maps for every space; stateless, loopback only.
    'diagrams': (5300, REPO / '.venv/bin/python', 'services.process_diagram.app'),
}


def identity(name):
    return f'gui/{os.getuid()}/com.opsatlas.tiberius-sales.{name}'


def loaded(name):
    try:
        return subprocess.run(['launchctl', 'print', identity(name)], capture_output=True).returncode == 0
    except FileNotFoundError:  # not macOS (CI): nothing runs under launchd
        return False


def diagrams_healthy(opener=None):
    opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open('http://127.0.0.1:5300/health', timeout=2) as response:
        if json.load(response).get('service') != 'process-diagram':
            raise ValueError('Process diagram service unavailable')


def health():
    workspace()  # the folder exists and is the sales workspace
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    # The workspace names itself on every reply; the health check no longer borrows Tibi's credential (REF S12).
    with opener.open('http://127.0.0.1:8780/api/health', timeout=2) as response:
        if response.headers.get('X-OpsAtlas-Workspace') != 'opsatlas-sales':
            raise ValueError('Wrong Atlas workspace')
    # Tibi runs as its own service; the OpsAtlas control panel reaches it through its gateway.
    with opener.open('http://127.0.0.1:8773/api/health', timeout=2) as response:
        if json.load(response).get('service') != 'tibi':
            raise ValueError('Tibi service unavailable')
    with opener.open('http://127.0.0.1:8780/', timeout=2) as response:
        if 'OpsAtlas Sales' not in response.read().decode():
            raise ValueError('Wrong Control Panel')
    diagrams_healthy(opener)


def start(only=None):
    """Register this workspace's services with launchd and wait until they answer. ``only`` registers one service
    (the control panel starts the diagram service this way); running services are left alone."""
    workspace()
    logs = REPO / '.runtime/opsatlas-sales-logs'
    definitions = REPO / '.runtime/opsatlas-sales-launchd'
    logs.mkdir(exist_ok=True)
    definitions.mkdir(exist_ok=True)
    # Never adopt or kill an unrelated listener on these ports.
    chosen = {name: SERVICES[name] for name in ([only] if only else SERVICES)}
    for name, (port, _, _) in chosen.items():
        if not loaded(name):
            with socket.socket() as probe:
                if probe.connect_ex(('127.0.0.1', port)) == 0:
                    raise RuntimeError(f'Port {port} is already occupied by an unmanaged service; stop it explicitly first.')
    for name, (_, python, module) in chosen.items():
        if loaded(name):
            continue
        label = identity(name).split('/')[-1]
        definition = {
            'Label': label, 'ProgramArguments': [str(python), '-m', module],
            'WorkingDirectory': str(REPO),
            'EnvironmentVariables': {'PYTHONPATH': f'{REPO}/src:{REPO}', 'PYTHONUNBUFFERED': '1',
                                     # Opt-in voice setting passed through from the starting shell.
                                     **({'SME_HIGGS_BITS': settings.get('SME_HIGGS_BITS')}
                                        if settings.get('SME_HIGGS_BITS') else {})},
            'RunAtLoad': True, 'KeepAlive': {'SuccessfulExit': False}, 'ThrottleInterval': 10,
            # Voice/ASR are latency-sensitive user interaction, not background maintenance.
            'ProcessType': 'Interactive',
            'StandardOutPath': str(logs / f'{name}.log'), 'StandardErrorPath': str(logs / f'{name}.log'),
        }
        path = definitions / f'{label}.plist'
        path.write_bytes(plistlib.dumps(definition))
        subprocess.run(['launchctl', 'bootstrap', f'gui/{os.getuid()}', str(path)], check=True)
    for attempt in range(30):
        try:
            if only == 'diagrams':
                diagrams_healthy()
                return
            health()
            print('Running independently of this terminal/task.\n'
                  'OpsAtlas Sales: http://127.0.0.1:8780/\n'
                  'Talk with Tibi: http://127.0.0.1:8780/#tibi\n'
                  'Tibi knowledge: http://127.0.0.1:8780/#tibi-knowledge')
            return
        except (OSError, ValueError):
            if attempt == 29:
                raise RuntimeError(f'Services did not become healthy. Inspect {logs}') from None
            time.sleep(1)


def restart(name):
    """Restart one of this workspace's own services now; launchd starts it again at once. Nothing else is touched."""
    if name not in SERVICES:
        raise ValueError(f'Unknown service: {name}')
    if not loaded(name):
        raise RuntimeError(f'The {name} service is not running under launchd; start it with scripts/start-tiberius-sales.sh')
    subprocess.run(['launchctl', 'kickstart', '-k', identity(name)], check=True, capture_output=True)


def restart_later(name, delay=1):
    """Restart a service a moment from now, from a process of its own. The core restarts itself this way and can
    still answer the request that asked for it."""
    if name not in SERVICES:
        raise ValueError(f'Unknown service: {name}')
    if not loaded(name):
        raise RuntimeError(f'The {name} service is not running under launchd; start it with scripts/start-tiberius-sales.sh')
    subprocess.Popen(['/bin/sh', '-c', f'sleep {int(delay)}; exec launchctl kickstart -k "$0"', identity(name)],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def stop():
    for name in reversed(SERVICES):
        if loaded(name):
            subprocess.run(['launchctl', 'bootout', identity(name)], check=True)
        # bootout can return before the registration disappears. A following
        # start must not mistake that retiring registration for a running service.
        for _ in range(100):
            if not loaded(name):
                break
            time.sleep(0.1)
        else:
            raise RuntimeError(f'{name} is still shutting down; retry status before starting.')
    print('Tiberius sales services stopped. Workspace data preserved.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'stop', 'restart', 'status'], nargs='?', default='start')
    action = parser.parse_args().action
    if action == 'start':
        start()
    elif action == 'restart':
        for name in reversed(SERVICES):
            restart(name)
        start()  # waits until both answer again
    elif action == 'stop':
        stop()
    else:
        for name in SERVICES:
            print(f'{name}: {"registered with launchd" if loaded(name) else "not registered"}')
        health()
        print('All three URLs and the sales workspace identity verified.')


if __name__ == '__main__':
    main()
