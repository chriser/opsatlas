"""Local diagnostic timings, separate from transcript revisions and claim evidence."""

import json
import math
import sqlite3
from collections import Counter

MARKS = (
    'capture_start', 'speech_end', 'endpoint', 'encoded', 'asr_requested', 'final_transcript',
    'confirmation_start', 'confirmed', 'plan_requested', 'first_token', 'question_ready',
    'tts_requested', 'audio_ready', 'first_audio', 'playback_start',
)
STATUSES = {'open', 'complete', 'text_only', 'failed', 'interrupted', 'abandoned'}
FIELDS = {'version', 'id', 'page_id', 'generation_id', 'revision', 'sequence', 'source', 'runtime',
          'endpoint_kind', 'status', 'marks'}


def validate(data):
    if not isinstance(data, dict) or set(data) != FIELDS or data['version'] != 1:
        raise ValueError('Invalid timing record')
    for key in ('id', 'page_id', 'generation_id'):
        value = data[key]
        if not isinstance(value, str) or not 1 <= len(value) <= 80 or not all(c.isalnum() or c in '-_' for c in value):
            raise ValueError('Invalid timing identity')
    for key in ('revision', 'sequence'):
        if type(data[key]) is not int or not 0 <= data[key] <= 100000:
            raise ValueError('Invalid timing sequence')
    if (data['source'] not in ('microphone', 'typed', 'replay') or data['runtime'] not in ('unknown', 'cold', 'warm')
            or data['endpoint_kind'] not in ('manual_stop', 'capture_limit', 'recorder_stop', 'detected', 'none')
            or data['status'] not in STATUSES):
        raise ValueError('Invalid timing category')
    marks = data['marks']
    if not isinstance(marks, dict) or set(marks) != set(MARKS):
        raise ValueError('Invalid timing milestones')
    previous = -1
    for key in MARKS:
        value = marks[key]
        if value is None:
            continue
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 86400000 or value < previous:
            raise ValueError('Timings must be finite, ordered milliseconds on one browser clock')
        previous = value
    if data['status'] == 'complete' and marks['playback_start'] is None:
        raise ValueError('Completed timing requires observed playback')
    return data


def distribution(values):
    values = sorted(values)
    return {'n': len(values), 'p50_ms': values[math.ceil(len(values) * .5) - 1] if values else None,
            'p95_ms': values[math.ceil(len(values) * .95) - 1] if values else None}


def report(records):
    groups = []
    pairs = {
        'speech_end_to_playback': ('speech_end', 'playback_start'),
        'manual_stop_to_playback': ('endpoint', 'playback_start'),
        'confirmation_wait': ('confirmation_start', 'confirmed'),
        'confirmed_to_playback': ('confirmed', 'playback_start'),
        'encoding': ('endpoint', 'encoded'),
        'recognition_delivery': ('asr_requested', 'final_transcript'),
        'planning': ('plan_requested', 'question_ready'),
        'synthesis_and_delivery': ('tts_requested', 'first_audio'),
        'audio_to_playback': ('first_audio', 'playback_start'),
    }
    for source, runtime in sorted({(r['source'], r['runtime']) for r in records}):
        subset = [r for r in records if (r['source'], r['runtime']) == (source, runtime)]
        metrics = {}
        for name, (start, end) in pairs.items():
            eligible = [r for r in subset if r['status'] == 'complete' and r['marks'][start] is not None
                        and r['marks'][end] is not None]
            if name == 'speech_end_to_playback':
                eligible = [r for r in eligible if r['source'] == 'microphone' and r['endpoint_kind'] == 'detected']
            elif name == 'manual_stop_to_playback':
                eligible = [r for r in eligible if r['source'] == 'microphone' and r['endpoint_kind'] == 'manual_stop']
            metrics[name] = distribution([round(r['marks'][end] - r['marks'][start], 3) for r in eligible])
        groups.append({'source': source, 'runtime': runtime, 'attempts': len(subset),
                       'outcomes': dict(Counter(r['status'] for r in subset)), 'metrics': metrics})
    return {'version': 1, 'attempts': len(records), 'groups': groups, 'records': records,
            'measurement': 'Browser monotonic timestamps. Playback is a browser event, not measured acoustic output. '
                           'Missing milestones are null. Unknown residency is never counted as warm. '
                           'Open records may indicate disconnect; failures are retained outside success percentiles.'}


class TimingStore:
    def __init__(self, path):
        self.path = path

    def connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path, timeout=5)
        self.path.chmod(0o600)
        con.execute('CREATE TABLE IF NOT EXISTS timings(session TEXT, id TEXT, data TEXT, PRIMARY KEY(session,id))')
        return con

    def save(self, session, data):
        validate(data)
        con = self.connection()
        try:
            with con:
                con.execute('BEGIN IMMEDIATE')
                row = con.execute('SELECT data FROM timings WHERE session=? AND id=?', (session, data['id'])).fetchone()
                if row:
                    old = json.loads(row[0])
                    if data['sequence'] <= old['sequence']:
                        return {'saved': False}
                    fixed = ('page_id', 'generation_id', 'revision', 'source', 'runtime')
                    if any(data[key] != old[key] for key in fixed) or any(
                        value is not None and data['marks'][key] != value for key, value in old['marks'].items()
                    ) or old['status'] != 'open':
                        raise ValueError('Timing history cannot be rewritten')
                elif con.execute('SELECT count(*) FROM timings WHERE session=?', (session,)).fetchone()[0] >= 2000:
                    raise ValueError('Session timing limit reached')
                con.execute('INSERT INTO timings VALUES(?,?,?) ON CONFLICT(session,id) DO UPDATE SET data=excluded.data',
                            (session, data['id'], json.dumps(data)))
            return {'saved': True}
        finally:
            con.close()

    def export(self, session):
        con = self.connection()
        try:
            records = [json.loads(row[0]) for row in con.execute('SELECT data FROM timings WHERE session=? ORDER BY rowid', (session,))]
            return report(records)
        finally:
            con.close()
