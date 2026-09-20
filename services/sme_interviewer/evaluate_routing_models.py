"""Labelled routing development probes; no holdout or naturalness claim."""

import argparse
import asyncio
import json
import time
from pathlib import Path

from . import turn_interpreter

CASES = [
    ('related-detour', 'Where was the repair logged?', 'The technician replaced a cracked seal.',
     'The pump was repaired after an inspection.', 'responsive', 'reported_practice', 'none', True),
    ('agreement', 'Was approval followed by activation?', 'Yes, that sequence is correct.',
     'The manager approved it and I activated it.', 'responsive', 'reported_practice', 'none', True),
    ('unrelated', 'Who approved activation?', 'Purple bananas play chess on the moon.', '', 'off_topic', None, 'none', True),
    ('unknown', 'Which checks were performed?', 'I do not know.', '', 'unknown', 'uncertain', 'none', True),
    ('policy', 'What does the policy require?', 'The policy requires approval before activation.', '',
     'responsive', 'reported_policy', 'none', True),
    ('pause', 'Who approved activation?', 'Please pause the interview.', '', None, None, 'pause', True),
    ('hesitation', 'What happened next?', 'Then the manager was about to', '', 'unclear', None, 'none', False),
    ('exception', 'What checks happened?', 'We skipped the checks because the order was urgent.', '',
     'responsive', 'reported_practice', 'none', True),
    ('correction', 'Who approved it?', 'I said Finance earlier, but it was Operations.', 'Finance approved it.',
     'responsive', 'reported_practice', 'none', True),
    ('negation', 'Was it approved?', 'No, it was not approved.', '', 'responsive', 'reported_practice', 'none', True),
    ('forgotten', 'Who made the decision?', "I can't remember.", '', 'unknown', 'uncertain', 'none', True),
    ('proposal', 'How could this improve?', 'I suggest adding a second check.', '', 'responsive', 'proposal', 'none', True),
    ('hypothetical', 'What could happen in an urgent case?', 'Hypothetically, we could ask Operations to decide.', '',
     'responsive', 'hypothetical', 'none', True),
    ('recap', 'What happened next?', "Let's review the recap now.", '', None, None, 'recap', True),
    ('quoted-pause', 'What did the manager say?', 'The manager said to pause the work until the checks were finished.', '',
     'responsive', 'reported_practice', 'none', True),
    ('quoted-finish', 'How did the shift end?', 'We finished the work and went home.', '',
     'responsive', 'reported_practice', 'none', True),
    ('conflicting-status', 'What was the status?', 'The same record was both active and on hold at exactly the same time.', '',
     'inconsistent', None, 'none', True),
    ('garbled', 'Who approved it?', 'Before the after yes because and was.', '', 'unclear', None, 'none', False),
    ('amount-correction', 'What was the limit?', 'Fifteen thousand pounds, not fifty thousand.', '',
     'responsive', 'reported_practice', 'none', True),
]


async def main(models, output, combined=False):
    records = []
    for model in models:
        turn_interpreter.MODEL = model
        for name, question, answer, history, category, kind, command, complete in CASES:
            start = time.perf_counter()
            if combined:
                from .evidence import FixtureEvidence
                from .turn_planner import prepare_turn
                q = {'id': 'q1', 'key': 'story', 'text': question}
                session = {'scope': {'region': 'unknown', 'variant': 'unknown', 'date': ''},
                           'evidence': FixtureEvidence().snapshot(), 'segments': [], 'questions': [q], 'current_question': q}
                if history:
                    session['segments'].append({'id': 'prior', 'revision': 1, 'state': 'provisional',
                                                'kind': 'reported_practice', 'text': history,
                                                'question_id': 'q1', 'question_key': 'story'})
                result = (await prepare_turn(session, answer, 'new'))['route']
            else:
                result = await turn_interpreter.interpret(question, answer, history)
            expected = {'category': category, 'kind': kind, 'command': command, 'complete': complete}
            errors = {k: {'expected': v, 'actual': result.get(k)} for k, v in expected.items()
                      if v is not None and result.get(k) != v}
            records.append({'model': model, 'case': name, 'ms': round((time.perf_counter()-start)*1000),
                            'expected': expected, 'result': result, 'errors': errors})
            print(model, name, 'ok' if not errors else errors, flush=True)
    output.write_text(json.dumps({'method': 'Labelled development probes, not an untouched holdout.',
                                  'records': records}, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--combined', action='store_true', help='Use the pinned combined production planner, not candidate routers.')
    parser.add_argument('--models', nargs='+', default=['qwen3.5:35b-a3b', 'qwen3.5:4b'])
    parser.add_argument('--output', type=Path, default=Path(__file__).parent/'.runtime/routing-models.json')
    args = parser.parse_args()
    asyncio.run(main([turn_interpreter.MODEL] if args.combined else args.models, args.output, args.combined))
