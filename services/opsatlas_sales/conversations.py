"""The conversation log (OBS F2): every Tibi turn, for review and continued improvement.

The Tibi service writes one JSON line per turn to ``<workspace>/logs/conversations/<date>.jsonl``: the session, the
mode, the engine version, what was heard, the reply, the route and why, the records and guidance used, the timings,
and any issue. The Human reviews sessions here and marks turns as good, odd or wrong with a note; the marks
(``logs/conversation-reviews.jsonl``, the latest per turn counts) are the list of things to improve.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

VERDICTS = ('good', 'odd', 'wrong')
_lock = threading.Lock()


def _directory(root) -> Path:
    return Path(root) / 'logs' / 'conversations'


def _lines(path: Path):
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        try:
            yield json.loads(line)
        except ValueError:
            continue


def append(root, entry: dict) -> None:
    """Write one turn (the Tibi service calls this after each reply). A logging failure never breaks the turn."""
    try:
        directory = _directory(root)
        directory.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry, ensure_ascii=False, default=str)
        with _lock, (directory / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl").open('a', encoding='utf-8') as out:
            out.write(line + '\n')
    except OSError:
        pass


def forget(root, session: str) -> int:
    """Take a deleted conversation's turns out of the log (PI F15): the Human deleted it, so what was said is not kept.
    Marks on its turns stay in the reviews file but no longer show, as no turn matches them. Returns the turns removed."""
    removed = 0
    directory = _directory(root)
    if not directory.exists():
        return 0
    with _lock:
        for path in sorted(directory.glob('*.jsonl')):
            text = path.read_text(encoding='utf-8', errors='replace')
            if session not in text:
                continue
            kept = []
            for line in text.splitlines():
                try:
                    mine = json.loads(line).get('session') == session
                except (ValueError, AttributeError):
                    mine = False
                removed += mine
                if not mine:
                    kept.append(line)
            temporary = path.with_suffix('.rewrite')
            temporary.write_text(''.join(line + '\n' for line in kept), encoding='utf-8')
            os.replace(temporary, path)
    return removed


def turns(root, days: int = 30) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%d')
    out = []
    for path in sorted(_directory(root).glob('*.jsonl')):
        if path.stem >= cutoff:
            out.extend(_lines(path))
    return sorted(out, key=lambda t: t.get('at', ''))


def reviews(root) -> dict:
    """The latest mark per (session, turn)."""
    path = Path(root) / 'logs' / 'conversation-reviews.jsonl'
    latest = {}
    if path.exists():
        for row in _lines(path):
            latest[(row['session'], row['turn'])] = row
    return {key: row for key, row in latest.items() if row.get('verdict') in VERDICTS}


def review(root, session: str, turn: int, verdict: str | None, note: str = '', actor: str = 'operator') -> dict:
    """Mark a turn; a verdict of None clears the mark."""
    if verdict is not None and verdict not in VERDICTS:
        raise ValueError('Mark a turn as good, odd or wrong')
    if not any(t.get('session') == session and t.get('turn') == turn for t in turns(root, days=365)):
        raise LookupError('No such turn')
    row = {'session': session, 'turn': turn, 'verdict': verdict, 'note': ' '.join(str(note or '').split())[:1000] or None,
           'actor': actor, 'at': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    path = Path(root) / 'logs' / 'conversation-reviews.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock, path.open('a', encoding='utf-8') as out:
        out.write(json.dumps(row, ensure_ascii=False) + '\n')
    return row


def sessions(root, days: int = 30) -> list[dict]:
    """Sessions, newest first: when, how many turns, the engine versions and modes, and the marks."""
    marks = reviews(root)
    grouped: dict = {}
    for t in turns(root, days):
        grouped.setdefault(t.get('session'), []).append(t)
    out = []
    for session, rows in grouped.items():
        verdicts = [marks[(session, r.get('turn'))]['verdict'] for r in rows if (session, r.get('turn')) in marks]
        reasoning = [r['timings'].get('first_segment') for r in rows if isinstance(r.get('timings'), dict)
                     and r['timings'].get('first_segment') is not None]
        out.append({'session': session, 'started': rows[0].get('at'), 'last': rows[-1].get('at'), 'turns': len(rows),
                    'modes': sorted({r.get('mode') for r in rows if r.get('mode')}),
                    'engines': sorted({(r.get('engine') or {}).get('version') for r in rows if r.get('engine')} - {None}),
                    'first': (rows[0].get('heard') or '')[:120],
                    'marks': {v: verdicts.count(v) for v in VERDICTS if v in verdicts},
                    'issues': sum(1 for r in rows if r.get('issue') not in (None, 'none') or r.get('interrupted')),
                    'median_first_segment_ms': sorted(reasoning)[len(reasoning) // 2] if reasoning else None})
    return sorted(out, key=lambda s: s['last'] or '', reverse=True)


def session(root, identifier: str) -> dict:
    marks = reviews(root)
    rows = [t for t in turns(root, days=365) if t.get('session') == identifier]
    if not rows:
        raise LookupError('No such conversation')
    return {'session': identifier, 'turns': [{**t, 'review': marks.get((identifier, t.get('turn')))} for t in rows]}


def flagged(root, days: int = 90) -> list[dict]:
    """Turns marked odd or wrong, newest first: the improvement list."""
    marks = reviews(root)
    by_key = {(t.get('session'), t.get('turn')): t for t in turns(root, days)}
    out = [{**by_key[key], 'review': mark} for key, mark in marks.items() if mark['verdict'] in ('odd', 'wrong') and key in by_key]
    return sorted(out, key=lambda t: t['review']['at'], reverse=True)


def transcript(conversation: dict) -> str:
    """A conversation as Markdown, for its owner to keep (REF S14): when, then each turn's words. Timings, routes and
    records stay in the log."""
    turns = conversation.get('turns', [])
    lines = [f"# Conversation {conversation.get('session', '')}", '']
    if turns:
        lines += [f"{turns[0].get('at', '')} to {turns[-1].get('at', '')}, {len(turns)} turns", '']
    for t in turns:
        lines += [f"**You:** {t.get('heard') or ''}", '', f"**Tibi:** {t.get('reply') or ''}", '']
    return '\n'.join(lines)
