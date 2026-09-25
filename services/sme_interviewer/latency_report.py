"""Real headset latency from the live Tiberius service, against the agreed budget.

    services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.latency_report [--sessions 5]

Reads the browser timing records the live service stores (end of speech to playback start for
microphone turns) and reports p50/p95 per recent session, so drift in real use is visible, not only in replay.
"""
import argparse
import json
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TIMINGS = REPO / '.runtime/opsatlas-sales/voice/timings.sqlite'
BUDGET = REPO / 'docs/initiatives/sme-interviewer/latency-budget.json'


def percentile(values, q):
    values = sorted(values)
    return round(values[min(len(values) - 1, round(q / 100 * (len(values) - 1)))]) if values else None


def sessions(path=None):
    """{session: [end of speech to playback ms, ...]} for completed microphone turns, in recording order."""
    path = path or TIMINGS
    if not path.exists():
        return {}
    rows = sqlite3.connect(f'file:{path}?mode=ro', uri=True).execute('select session, data from timings order by rowid')
    result = {}
    for session, raw in rows:
        record = json.loads(raw)
        marks = record.get('marks') or {}
        if record.get('source') != 'microphone' or record.get('status') != 'complete':
            continue
        if marks.get('speech_end') is None or marks.get('playback_start') is None:
            continue
        result.setdefault(session, []).append(marks['playback_start'] - marks['speech_end'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--sessions', type=int, default=5, help='most recent sessions to show')
    args = parser.parse_args()
    budget = json.loads(BUDGET.read_text())['headset']['budget']
    recent = list(sessions().items())[-args.sessions:]
    if not recent:
        print('No headset turns recorded yet.')
        return 0
    print(f'Headset latency, end of speech to playback (budget p50 {budget["p50"]} ms, p95 {budget["p95"]} ms)')
    for session, values in recent:
        print(f'  session {session[:8]}: {len(values):3} turns  p50 {percentile(values, 50)} ms  p95 {percentile(values, 95)} ms')
    # The verdict is on the latest session with enough turns; earlier rows show the trend.
    session, values = next(((s, v) for s, v in reversed(recent) if len(v) >= 5), recent[-1])
    p50, p95 = percentile(values, 50), percentile(values, 95)
    over = [k for k, v in (('p50', p50), ('p95', p95)) if v > budget[k]]
    verdict = ('over budget: ' + ', '.join(over)) if over else 'within budget'
    print(f'Latest session {session[:8]} ({len(values)} turns): {verdict}.')
    return 1 if over else 0


if __name__ == '__main__':
    raise SystemExit(main())
