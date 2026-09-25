"""Manage user-session launchd services independent of the invoking task shell."""
import argparse
import json
import os
import plistlib
import socket
import subprocess
import time
import urllib.request

from .workspace import REPO, workspace

SERVICES = {
    'core': (8780, REPO / '.venv/bin/python', 'services.opsatlas_sales.app'),
    'voice': (8773, REPO / 'services/sme_interviewer/.venv/bin/python', 'services.sme_interviewer.sales_preview'),
}


def identity(name):
    return f'gui/{os.getuid()}/com.opsatlas.tiberius-sales.{name}'


def loaded(name):
    return subprocess.run(['launchctl', 'print', identity(name)], capture_output=True).returncode == 0


def health():
    root = workspace()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request('http://127.0.0.1:8780/api/sales/knowledge',
                                    headers={'x-sales-token': (root / 'local-access.key').read_text().strip()})
    with opener.open(request, timeout=2) as response:
        if json.load(response).get('workspace') != 'opsatlas-sales':
            raise ValueError('Wrong Atlas workspace')
    # Tibi runs as its own service; the OpsAtlas control panel reaches it through its gateway.
    with opener.open('http://127.0.0.1:8773/api/health', timeout=2) as response:
        if json.load(response).get('service') != 'tibi':
            raise ValueError('Tibi service unavailable')
    with opener.open('http://127.0.0.1:8780/', timeout=2) as response:
        if 'OpsAtlas Sales' not in response.read().decode():
            raise ValueError('Wrong Control Panel')


def start():
    workspace()
    logs = REPO / '.runtime/opsatlas-sales-logs'
    definitions = REPO / '.runtime/opsatlas-sales-launchd'
    logs.mkdir(exist_ok=True)
    definitions.mkdir(exist_ok=True)
    # Never adopt or kill an unrelated listener on these ports.
    for name, (port, _, _) in SERVICES.items():
        if not loaded(name):
            with socket.socket() as probe:
                if probe.connect_ex(('127.0.0.1', port)) == 0:
                    raise RuntimeError(f'Port {port} is already occupied by an unmanaged service; stop it explicitly first.')
    for name, (_, python, module) in SERVICES.items():
        if loaded(name):
            continue
        label = identity(name).split('/')[-1]
        definition = {
            'Label': label, 'ProgramArguments': [str(python), '-m', module],
            'WorkingDirectory': str(REPO),
            'EnvironmentVariables': {'PYTHONPATH': f'{REPO}/src:{REPO}', 'PYTHONUNBUFFERED': '1',
                                     # Opt-in voice setting passed through from the starting shell.
                                     **({'SME_HIGGS_BITS': os.environ['SME_HIGGS_BITS']}
                                        if os.environ.get('SME_HIGGS_BITS') else {})},
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
    parser.add_argument('action', choices=['start', 'stop', 'status'], nargs='?', default='start')
    action = parser.parse_args().action
    if action == 'start':
        start()
    elif action == 'stop':
        stop()
    else:
        for name in SERVICES:
            print(f'{name}: {"registered with launchd" if loaded(name) else "not registered"}')
        health()
        print('All three URLs and the sales workspace identity verified.')


if __name__ == '__main__':
    main()
