"""Evaluate process interviews (TIBI E5, PI F7) with the real local models: a scripted, made-up participant answers
whatever Tibi asks, and the capture is scored against the truth.

The participant is deterministic: its answer depends on the goal Tibi's reply took (who does a step, what happens
next, a read-back…), so each run exercises the same pipeline (planner, reply model, note-taker, model checks).
It plants one contradiction (someone else raising the purchase order) and one correction (the supplier confirms by
phone, not email), and says "give me a moment" once.

    python -m services.sme_interviewer.evaluate_process_interview --out docs/.../evaluations/<file>.json

Scored: the steps captured (and their owners and systems), the £5,000 decision and its branches, the trigger,
the exception and the control; the contradiction raised and settled; the correction applied; repeated questions;
read-backs; reply and note-taking times. Nothing is saved to any workspace.
"""
import argparse
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from . import process_model as pm
from .engine import current as engine
from .process_interviewer import MODEL, NOTE_MODEL, ProcessInterviewer

INTRO = "Hi, I'm Sam Patel. I'm the operations manager at BiPi, looking after the three stores, for about four years now."
AGENDA = "Mainly how we order parts from suppliers. And customer returns, if there's time."
CHUNKS = [
    "Every Monday the store manager checks the stock report in SAP, and if anything is below the minimum "
    "she raises a purchase order, also in SAP.",
    "Then it needs approving. If the order is over five thousand pounds the regional director approves it by email; "
    "otherwise finance approves it in SAP.",
    "Once it is approved, the supplier confirms the delivery date by email.",
    "When the goods arrive, the warehouse team checks them against the order with the handheld scanner.",
    "And at the end finance pays the supplier's invoice in SAP. That's the end of it.",
]
TRUTH = [  # (what the step is about, its owner, its system) for scoring; keywords, case-insensitive
    ({'stock'}, 'store manager', 'sap'),
    ({'purchase order', 'raise', 'order'}, 'store manager', 'sap'),
    ({'regional director', 'approve'}, 'regional director', 'email'),
    ({'approve'}, 'finance', 'sap'),
    ({'delivery', 'confirm'}, 'supplier', 'phone'),  # phone after the correction
    ({'goods', 'check'}, 'warehouse', 'scanner'),
    ({'invoice', 'pay'}, 'finance', 'sap'),
]
CONTRADICTION = "There are two signatures on anything over a thousand pounds. The buyer raises the purchase orders, by the way."
SETTLE = "Sorry, I misspoke: it is the store manager who raises them. The buyer only helps with the big ones."
CORRECTION = "Oh, one thing: sorry, the supplier actually confirms the delivery date by phone, not by email."


class Participant:
    """Answers the goal Tibi's reply took, from the truth; keeps its place in the narrative."""

    def __init__(self):
        self.told = 0
        self.planted = self.corrected = self.waited = False
        self.processes_done = False

    def next_chunk(self):
        if self.told < len(CHUNKS):
            self.told += 1
            return CHUNKS[self.told - 1]
        return "That's the whole of it, really."

    def answer(self, goal, reply, turn):
        kind = (goal or 'follow').split(':', 1)[0]
        if turn == 6 and not self.waited:
            self.waited = True
            return 'Give me a moment.'
        if kind in ('name', 'role', 'team'):
            return INTRO if kind != 'team' else 'I work in the operations team at head office.'
        if kind in ('agenda', 'more_processes'):
            return AGENDA if kind == 'agenda' else "Let's start with ordering parts."
        if kind == 'purpose':
            return 'It keeps the three stores stocked with the parts customers need.'
        if kind == 'trigger':
            return 'It starts when the stock of a part falls below the minimum level.'
        if kind == 'conflict':
            said = reply.casefold()
            if 'buyer' in said or 'raise' in said:
                return SETTLE
            if 'director' in said or 'finance' in said:
                return 'Both: the regional director approves orders over five thousand pounds, and finance approves the rest.'
            return 'What I said first is right.'
        if kind == 'unclear':
            return 'I mean the store manager, at the store that needs the parts.'
        if kind in ('readback', 'summary'):
            if self.told >= 3 and not self.corrected:
                self.corrected = True
                return CORRECTION
            return "Yes, that's right."
        if kind == 'who':
            label = reply.casefold()
            for keys, who, _ in TRUTH:
                if any(k in label for k in keys):
                    return f'That is the {who}.'
            return 'The store manager does that.'
        if kind == 'system':
            label = reply.casefold()
            for keys, _, system in TRUTH:
                if any(k in label for k in keys):
                    return {'sap': 'That is done in SAP.', 'email': 'By email.', 'phone': 'By phone.',
                            'scanner': 'With the handheld scanner.'}[system]
            return 'In SAP.'
        if kind == 'branch':
            return 'Otherwise, for anything up to five thousand pounds, finance approves it in SAP.'
        if kind == 'exceptions':
            return 'Sometimes the goods arrive damaged; then the store manager raises a claim with the supplier.'
        if kind == 'controls':
            if not self.planted:
                self.planted = True
                return CONTRADICTION
            return 'The invoice is matched against the order and the delivery before it is paid.'
        if kind == 'outcome':
            return 'It ends when the invoice is paid and the stock is back above the minimum.'
        if kind in ('move', 'another'):
            self.processes_done = True
            return "No, that's enough for today. We can do returns another time."
        if kind == 'wrap':
            return "No, that's everything. Thank you."
        if kind == 'pname':
            return 'We call it ordering parts.'
        return self.next_chunk()


def score(model, replies, goals, reply_ms, note_ms, drops):
    p = next((q for q in model['processes'] if 'order' in q['name'].casefold()), model['processes'][0] if model['processes'] else None)
    steps = [s for s in pm.ordered_steps(p)] if p else []
    tasks = [s for s in steps if s['kind'] == 'task']
    found, owners, systems = [], 0, 0
    used = set()
    for keys, who, system in TRUTH:
        # A step about this (its label or owner names it), preferring one with the right owner.
        about = [s for s in tasks if s['id'] not in used and any(k in f"{s['label']} {s['who']}".casefold() for k in keys)]
        match = next((s for s in about if who.split()[0] in s['who'].casefold()), about[0] if about else None)
        if match is not None:
            used.add(match['id'])
            found.append(match['label'])
            owners += who.split()[0] in match['who'].casefold()
            systems += system in match['system'].casefold()
    decision = next((s for s in steps if s['kind'] == 'decision'), None)
    raised = [g for g in goals if g and g.startswith('conflict:')]
    conflicts = [o for o in model['open'] if o['kind'] == 'conflict']
    order_step = next((s for s in tasks if 'purchase' in s['label'].casefold() or 'raise' in s['label'].casefold()), None)
    delivery = next((s for s in tasks if 'deliver' in s['label'].casefold() or 'confirm' in s['label'].casefold()), None)
    repeated = sum(1 for a, b in zip(replies, replies[1:]) if a.strip().casefold() == b.strip().casefold())
    counts = {}
    for g in goals:
        if g:
            counts[g] = counts.get(g, 0) + 1

    def pct(values, q):
        values = sorted(values)
        return round(values[min(len(values) - 1, int(q * len(values)))], 1) if values else None
    return {
        'participant': {k: v['value'] for k, v in model['participant'].items()},
        'processes': [q['name'] for q in model['processes']],
        'steps_captured': len(tasks), 'steps_found': f'{len(found)}/{len(TRUTH)}', 'owners_right': f'{owners}/{len(TRUTH)}',
        'systems_right': f'{systems}/{len(TRUTH)}',
        'trigger': (p or {}).get('details', {}).get('trigger', {}).get('value', '') if p else '',
        'decision': {'question': decision['label'], 'branches': [n['label'] for n in decision['next']]} if decision else None,
        'exceptions': [x['text'] for x in (p or {}).get('exceptions', [])],
        'controls': [c['text'] for c in (p or {}).get('controls', [])],
        'contradiction_raised': bool(raised), 'contradiction_recorded': bool(conflicts),
        'contradiction_settled': any(o['status'] == 'resolved' for o in conflicts),
        'order_raised_by': (order_step or {}).get('who'),
        'correction_applied': 'phone' in (delivery or {}).get('system', '').casefold(),
        'readbacks': sum(1 for g in goals if g and g.startswith(('readback:', 'summary:'))),
        'repeated_questions_in_a_row': repeated, 'goals_asked_over_twice': [g for g, n in counts.items() if n > 2],
        'dropped_changes': drops,
        'reply_ms': {'p50': pct(reply_ms, 0.5), 'p95': pct(reply_ms, 0.95), 'n': len(reply_ms)},
        'notes_ms': {'p50': pct(note_ms, 0.5), 'p95': pct(note_ms, 0.95), 'n': len(note_ms)},
    }


async def run(max_turns):
    session = {'id': 'evaluation', 'evidence': {'process_interview': {'space': 'bipi', 'space_name': 'BiPi'}}}
    tibi = ProcessInterviewer(session, 'none', 'http://127.0.0.1:9')
    await tibi.warm()
    await tibi.warm_notes()
    person = Participant()
    transcript = [{'role': 'assistant', 'content': tibi.opening}]
    replies, goals, reply_ms, note_ms, drops = [tibi.opening], [None], [], [], []
    reply, goal = tibi.opening, 'name'
    for turn in range(1, max_turns + 1):
        text = person.answer(goal, reply, turn)
        started = time.perf_counter()
        result = await tibi.respond(text)
        reply_ms.append((time.perf_counter() - started) * 1000)
        tibi.commit(text, result['reply'])
        reply, goal = result['reply'], result['process_turn']['goal']
        transcript += [{'role': 'user', 'content': text}, {'role': 'assistant', 'content': reply, 'goal': goal}]
        replies.append(reply)
        goals.append(goal)
        if result['process_turn']['notes']:
            # The reply started the notes for this answer (noted first when quick); they finish before the next answer,
            # as they do while a real participant speaks.
            log = await tibi.finish_notes(result['process_turn']['turn'])
            note_ms.append(log['seconds'] * 1000)
            drops += [{'turn': log['turn'], **d} for d in log['dropped']]
            transcript[-2]['notes'] = {k: log[k] for k in ('applied', 'corrected', 'conflicts', 'resolved', 'confirmed')}
        if result['phase'] == 'closed' or goal == 'wrap' or (person.processes_done and goal in (None, 'wrap', 'another')):
            break
    await tibi.release()  # as the interview closing does: Tibi's chat is not slowed afterwards
    return tibi.model, transcript, score(tibi.model, replies, goals, reply_ms, note_ms, drops)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--turns', type=int, default=40)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    model, transcript, result = asyncio.run(run(args.turns))
    report = {'at': datetime.now(timezone.utc).isoformat(), 'engine': engine(), 'models': {'reply': MODEL, 'notes': NOTE_MODEL},
              'data': 'made-up (BiPi, a fictional parts distributor)', 'result': result, 'transcript': transcript,
              'model': model}
    print(json.dumps(result, indent=1, ensure_ascii=False))
    for line in transcript:
        print(f"{'TIBI' if line['role'] == 'assistant' else 'SAM '} {line.get('goal') or '':<22} {line['content']}")
    if args.out:
        args.out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + '\n')
        print('Evidence:', args.out)


if __name__ == '__main__':
    main()

