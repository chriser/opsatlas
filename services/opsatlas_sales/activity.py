"""The control panel's activity log (OBS F1): what happened, from every side, as JSON lines anyone can read.

Three sources write to ``<workspace>/logs/activity/<source>-<date>.jsonl``:

* ``core``: every request to OpsAtlas (method, path, status, time taken, the page it came from), sign-ins, restarts,
  and the live voice socket to Tibi (opened, refused, the state and error messages Tibi sent, closed and why);
* ``browser``: what the operator did in the control panel (pages, buttons, Tibi's microphone and socket events,
  errors the page met), sent in small batches;
* ``tibi``: the Tibi service's own lifecycle (session start, warm-up per model, worker and turn failures).

Nothing secret is written: passwords, tokens, keys and cookies are replaced by "[redacted]", and the workspace key
never appears. Conversation wording belongs in the conversation log, not here. Files older than 14 days are removed.

Read it with ``scripts/opsatlas-activity`` (for example ``--since 30m --no-polls``) or open the files directly.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

KEEP_DAYS = 14
SECRET_KEYS = re.compile(r"pass(word)?|token|secret|key|authori[sz]ation|cookie|credential", re.I)
MAX_TEXT = 500
# Status checks the control panel repeats (every 30 seconds; the machine reading every few seconds on the Talk with
# Tibi page): kept, but marked so a reader can hide them.
POLLS = ('/api/health', '/api/tibi/status', '/services/tibi/api/health', '/api/tibi/machine')


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def redact(value, secrets=()):
    """A copy of ``value`` safe to write: secret fields replaced, long text cut, known secret strings removed."""
    if isinstance(value, dict):
        return {k: '[redacted]' if SECRET_KEYS.search(str(k)) else redact(v, secrets) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v, secrets) for v in value[:50]]
    if isinstance(value, str):
        for secret in secrets:
            if secret and secret in value:
                value = value.replace(secret, '[redacted]')
        return value if len(value) <= MAX_TEXT else value[:MAX_TEXT] + '…'
    return value


class ActivityLog:
    def __init__(self, root, source: str, secrets=()):
        self.directory = Path(root) / 'logs' / 'activity'
        self.source = source
        self.secrets = tuple(s for s in secrets if s)
        self.lock = threading.Lock()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.prune()

    def path(self, day: str | None = None) -> Path:
        return self.directory / f"{self.source}-{day or datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"

    def write(self, kind: str, **fields) -> None:
        """Append one event. A logging failure never breaks what was being logged."""
        entry = {'at': now(), 'source': self.source, 'kind': kind, **redact(fields, self.secrets)}
        try:
            line = json.dumps(entry, default=str, ensure_ascii=False)
            with self.lock, self.path().open('a', encoding='utf-8') as out:
                out.write(line + '\n')
        except OSError:
            pass

    def prune(self) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)).strftime('%Y-%m-%d')
        for path in self.directory.glob('*.jsonl'):
            day = path.stem.rsplit('-', 3)[-3:]
            if '-'.join(day) < cutoff:
                path.unlink(missing_ok=True)


# ---- reading --------------------------------------------------------------------------------------------------


def since(value: str) -> datetime:
    """"30m", "2h", "1d" or an ISO time."""
    match = re.fullmatch(r'(\d+)([smhd])', value.strip())
    if match:
        seconds = int(match.group(1)) * {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}[match.group(2)]
        return datetime.now(timezone.utc) - timedelta(seconds=seconds)
    moment = datetime.fromisoformat(value)
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def read(root, start: datetime | None = None, sources=None, kinds=None, text=None, polls=True) -> list[dict]:
    """Events from every source, oldest first."""
    directory = Path(root) / 'logs' / 'activity'
    events = []
    for path in sorted(directory.glob('*.jsonl')):
        if sources and path.stem.split('-')[0] not in sources:
            continue
        for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if start and datetime.fromisoformat(event['at']) < start:
                continue
            if kinds and event.get('kind') not in kinds:
                continue
            if not polls and event.get('poll'):
                continue
            if text and text.lower() not in line.lower():
                continue
            events.append(event)
    return sorted(events, key=lambda e: e['at'])


def describe(event: dict) -> str:
    """One readable line."""
    at = datetime.fromisoformat(event['at']).astimezone().strftime('%H:%M:%S.%f')[:-3]
    rest = {k: v for k, v in event.items() if k not in ('at', 'source', 'kind')}
    if event.get('kind') == 'http':
        detail = f"{rest.pop('method', '')} {rest.pop('path', '')} → {rest.pop('status', '')} in {rest.pop('ms', '')} ms"
        rest.pop('poll', None)
        rest.pop('request', None)
    else:
        detail = rest.pop('event', '') or rest.pop('name', '')
    extra = ' '.join(f'{k}={json.dumps(v, ensure_ascii=False)}' for k, v in rest.items() if v not in (None, '', [], {}))
    return f"{at} {event['source']:<7} {event['kind']:<10} {detail} {extra}".rstrip()


def main(argv=None):
    from .workspace import ROOT

    parser = argparse.ArgumentParser(description='Read the OpsAtlas Sales activity log.')
    parser.add_argument('--since', default='2h', help='30m, 2h, 1d or an ISO time (default 2h)')
    parser.add_argument('--source', action='append', choices=['core', 'browser', 'tibi'])
    parser.add_argument('--kind', action='append', help='http, auth, socket, tibi, page, action, error, ...')
    parser.add_argument('--grep', help='only events containing this text')
    parser.add_argument('--no-polls', action='store_true', help='hide the 30-second status checks')
    parser.add_argument('--json', action='store_true', help='print the JSON lines')
    parser.add_argument('--follow', action='store_true', help='keep printing new events')
    parser.add_argument('--root', default=str(ROOT))
    args = parser.parse_args(argv)
    start = since(args.since)
    seen = 0
    while True:
        events = read(args.root, start, args.source, args.kind, args.grep, polls=not args.no_polls)
        for event in events[seen:]:
            print(json.dumps(event, ensure_ascii=False) if args.json else describe(event))
        seen = len(events)
        if not args.follow:
            return 0
        sys.stdout.flush()
        time.sleep(1)


if __name__ == '__main__':
    raise SystemExit(main())
