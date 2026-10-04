"""How busy this Mac is, for the Talk with Tibi page (TIBI E2 observability; the Human's request of 1 October 2026).

Tibi's voice is generated on the graphics processor that every local model shares. On 1 October the voice broke up
while another app's large model generated for four and a half minutes beside Tibi's note-taker, and nothing on the page
showed it. A reading says how busy the graphics processor is and who is using it (Tibi's voice, OpsAtlas's models,
another app's model, the browsers and the screen), how much memory is free and whether the Mac is swapping, the
processors' load, and the models OpsAtlas's model server has loaded.

Each app's share is its graphics-processor time over the interval since the last reading (ioreg's accumulatedGPUTime,
no administrator rights needed); a reading costs about 70 ms. macOS only: elsewhere a reading says it is unavailable.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
from collections import Counter
from pathlib import Path

import httpx

from assistant import settings

GROUPS = {
    'voice': "Tibi's voice",
    'models': "OpsAtlas's models",
    'other_models': "Another app's AI model",
    'screen': 'Browsers and the screen',
    'other': 'Other apps',
}
# What each of OpsAtlas's models does, for the page; a model not listed is shown by its name.
ROLES = {
    'qwen2.5:7b-instruct': "Tibi's conversation",
    'qwen3.5:35b-a3b': "Tibi's note-taker",
    'qwen3.5:4b': 'answers and checks',
    'nomic-embed-text': 'search',
    'qwen2.5:14b-instruct': 'governance judge',
}
SCREEN = re.compile(r'WindowServer|Google Chrome|Safari|WebKit|Firefox|Microsoft Edge|Claude|Brave', re.I)
RUNNER = re.compile(r'llama-server|ollama runner|/ollama\s+runner|mlx_lm|mlx-lm', re.I)
MAYBE_MODEL = re.compile(r'llama|ollama|python|mlx', re.I)  # worth reading the command line of, even when idle
# When the page says the Mac is strained or busy. Higgs speaks at about 1.36x real time on a quiet machine and fell to
# 1.05-1.10x with one other model generating beside it (29 September): a fifth of the processor taken by another app is
# enough to make the voice stutter.
OTHER_MODEL_SHARE = 20
FULL = 85
LOW_FREE = 20
STALE = 30.0      # seconds: an older reading is no baseline for shares
SETTLE = 0.5      # seconds between two readings when there is no baseline
RECENT = 0.4      # seconds: a reading this fresh is returned again rather than taken anew


def _run(*command: str) -> str:
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=3, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return ''


def on_macos() -> bool:
    return Path('/usr/sbin/ioreg').exists()


def gpu_time() -> dict[int, tuple[str, int]]:
    """Each process's accumulated graphics-processor time, in nanoseconds: {pid: (name, ns)}."""
    out = _run('ioreg', '-r', '-c', 'AGXDeviceUserClient', '-w0', '-l')
    used: Counter = Counter()
    names: dict[int, str] = {}
    for block in out.split('+-o AGXDeviceUserClient')[1:]:
        who = re.search(r'"IOUserClientCreator" = "pid (\d+), ([^"]+)"', block)
        if who:
            pid = int(who.group(1))
            names[pid] = who.group(2)
            used[pid] += sum(int(t) for t in re.findall(r'"accumulatedGPUTime"=(\d+)', block))
    return {pid: (names[pid], used[pid]) for pid in names}


def commands(pids) -> dict[int, tuple[str, int]]:
    """{pid: (command line, resident memory in KB)} for the given processes."""
    pids = sorted({int(p) for p in pids})
    if not pids:
        return {}
    out = _run('ps', '-o', 'pid=,rss=,command=', '-p', ','.join(map(str, pids)))
    found = {}
    for line in out.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            found[int(parts[0])] = (parts[2], int(parts[1]))
    return found


def store() -> Path:
    """OpsAtlas's model store: the Ollama app's own, unless OLLAMA_MODELS says otherwise."""
    return Path(settings.get('OLLAMA_MODELS') or Path.home() / '.ollama' / 'models')


_blobs: dict[str, str] = {}


def model_name(blob: str) -> str:
    """The model a blob in OpsAtlas's store belongs to, from the store's manifests ("" if none names it)."""
    if blob not in _blobs:
        for manifest in (store() / 'manifests').glob('*/*/*/*'):
            try:
                layers = json.loads(manifest.read_text()).get('layers', [])
            except (OSError, ValueError):
                continue
            name = f'{manifest.parent.name}:{manifest.name}'
            for layer in layers:
                if str(layer.get('mediaType', '')).endswith('.model'):
                    _blobs[str(layer.get('digest', '')).replace(':', '-')] = name
        _blobs.setdefault(blob, '')
    return _blobs[blob]


def classify(name: str, command: str) -> tuple[str, str]:
    """Which group a graphics-processor user belongs to, and the model it runs (for a model server's runner)."""
    if 'sme_interviewer/worker.py' in command:
        return 'voice', ''
    if RUNNER.search(command) or RUNNER.search(name):
        model = re.search(r'--model\s+(\S+)', command)
        path = model.group(1) if model else ''
        if path.startswith(str(store()) + os.sep):
            return 'models', model_name(Path(path).name)
        return 'other_models', ''
    if SCREEN.search(name) or SCREEN.search(command):
        return 'screen', ''
    return 'other', ''


def memory() -> dict | None:
    out = _run('sysctl', '-n', 'hw.memsize', 'kern.memorystatus_level', 'kern.memorystatus_vm_pressure_level', 'vm.swapusage')
    lines = out.splitlines()
    if len(lines) < 4 or not lines[0].strip().isdigit():
        return None
    swap = re.search(r'used = ([\d.]+)M', lines[3])
    pressure = {'1': 'normal', '2': 'warning', '4': 'critical'}.get(lines[2].strip(), 'normal')
    return {'total_gb': round(int(lines[0]) / 1024 ** 3), 'free_pct': int(lines[1]), 'pressure': pressure,
            'swap_used_gb': round(float(swap.group(1)) / 1024, 1) if swap else None}


def swapouts() -> int | None:
    found = re.search(r'Swapouts:\s+(\d+)', _run('vm_stat'))
    return int(found.group(1)) if found else None


def loaded_models() -> list[dict] | None:
    """The models OpsAtlas's model server holds now: name, what it does, and its size."""
    try:
        with httpx.Client(timeout=1.0, trust_env=False) as client:
            rows = client.get(settings.get('KP_OLLAMA_URL').rstrip('/') + '/api/ps').json().get('models', [])
    except (httpx.HTTPError, ValueError, OSError):
        return None
    return [{'name': m.get('name', ''), 'role': ROLES.get(m.get('name', ''), ''),
             'gb': round((m.get('size_vram') or m.get('size') or 0) / 1e9, 1)} for m in rows]


def judge(gpu: dict, mem: dict | None, swapping: bool) -> tuple[str, str]:
    """ok, busy or strained, and what to do about it, in plain words."""
    shares = {u['group']: u for u in gpu['users']}
    other = shares.get('other_models')
    held = f" Another app's AI model holds {other['gb']} GB." if other and other.get('gb') else ''
    if other and other['share'] >= OTHER_MODEL_SHARE:
        return 'strained', (f"Another app's AI model is using {other['share']}% of the graphics processor. Tibi's voice "
                            "may break up while it runs: pausing that app's work will help.")
    if mem and swapping and mem['free_pct'] < LOW_FREE:
        return 'strained', ('Memory is short and the Mac is swapping, so replies and the voice slow down.' + held +
                            ' Closing other apps or unloading other models will help.')
    if gpu['busy'] >= FULL:
        return 'busy', "The graphics processor is nearly full: Tibi's voice may slow down."
    if other:
        return 'busy', (f"Another app's AI model is loaded ({other['gb']} GB). " if other.get('gb') else
                        "Another app's AI model is loaded. ") + "It is idle now; when it runs, Tibi's voice may break up."
    if mem and mem['pressure'] != 'normal':
        return 'busy', 'Memory is under pressure: replies may slow down.'
    return 'ok', ''


class Machine:
    """Readings of this Mac, each against the one before it; safe to call from several requests at once."""

    def __init__(self, activity=None):
        self.activity = activity
        self.lock = threading.Lock()
        self.last: tuple[float, dict, int | None] | None = None  # (when, gpu time, swapouts)
        self.reading: dict | None = None
        self.level = 'ok'

    def read(self) -> dict:
        with self.lock:
            now = time.monotonic()
            if self.reading is not None and self.last is not None and now - self.last[0] < RECENT:
                return self.reading
            if not on_macos():
                return {'available': False, 'reason': 'Readings are available on macOS only.'}
            if self.last is None or now - self.last[0] > STALE:
                self.last = (now, gpu_time(), swapouts())
                time.sleep(SETTLE)
                now = time.monotonic()
            then, before, swapped = self.last
            after, swapped_now = gpu_time(), swapouts()
            self.last = (now, after, swapped_now)
            self.reading = self._reading(now - then, before, after, swapped, swapped_now)
            self._record(self.reading)
            return self.reading

    def _reading(self, window, before, after, swapped, swapped_now) -> dict:
        # A client opened during the interval did all its work in it; one closed loses its time (never below zero).
        users = {pid: ns - before.get(pid, (name, 0))[1] for pid, (name, ns) in after.items()}
        users = {pid: ns for pid, ns in users.items() if ns > 0}
        found = commands(set(users) | {pid for pid, (name, _) in after.items() if MAYBE_MODEL.search(name)})
        groups: dict[str, dict] = {}
        for pid, (name, _) in after.items():
            command, rss = found.get(pid, ('', 0))
            group, model = classify(name, command)
            share = 100 * users.get(pid, 0) / 1e9 / window if window > 0 else 0
            if group in ('models', 'other_models') or share >= 0.5:
                entry = groups.setdefault(group, {'group': group, 'label': GROUPS[group], 'share': 0.0, 'models': [], 'gb': 0.0})
                entry['share'] += share
                if model and model not in entry['models']:
                    entry['models'].append(model)
                if group == 'other_models':
                    entry['gb'] += rss / 1024 ** 2
        users_out = []
        for entry in sorted(groups.values(), key=lambda e: -e['share']):
            entry['share'] = min(100, round(entry['share']))
            entry['gb'] = round(entry['gb'], 1) or None
            if not entry['models']:
                entry.pop('models')
            if entry['share'] or entry['group'] in ('models', 'other_models'):
                users_out.append(entry)
        gpu = {'busy': min(100, sum(u['share'] for u in users_out)), 'users': users_out}
        mem = memory()
        swapping = swapped is not None and swapped_now is not None and swapped_now > swapped
        if mem is not None:
            mem['swapping'] = swapping
        load = os.getloadavg()[0]
        cores = os.cpu_count() or 1
        level, advice = judge(gpu, mem, swapping)
        return {'available': True, 'window': round(window, 1), 'gpu': gpu, 'memory': mem,
                'cpu': {'load': round(load, 1), 'cores': cores, 'busy': min(100, round(100 * load / cores))},
                'models': loaded_models(), 'level': level, 'advice': advice}

    def _record(self, reading):
        """A change of level goes to the activity log, so a slow or broken-up interview can be traced to it later."""
        if reading['level'] == self.level or self.activity is None:
            self.level = reading['level']
            return
        self.level = reading['level']
        top = [{'who': u['label'], 'share': u['share'], **({'models': u['models']} if u.get('models') else {})}
               for u in reading['gpu']['users'][:3]]
        self.activity.write('machine', event=f'machine {reading["level"]}', gpu=reading['gpu']['busy'], top=top,
                            memory=reading['memory'], advice=reading['advice'] or None)
