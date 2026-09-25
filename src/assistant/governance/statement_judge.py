"""One judgement per candidate pair of statements (GOV S7).

The prompt is the governance pair benchmark's, fixed on 25 September 2026 before any model ran and not tuned
since (tests/evaluation/governance_pair_benchmark.json). With it, qwen2.5:14b-instruct found 25/25 planted
conflicts and 12/12 duplicates and re-flagged none of the 31 findings a person had dismissed; the document-pair
engine around the same model found 6/25, 0/12 and re-flagged 17/31. There are no domain-specific guards.

Judgements are cached per prompt version, model and statement pair (both statements' document, section and
text, in either order), so an unchanged corpus re-runs from the cache and an edit re-judges only its own pairs.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROMPT_VERSION = 'governance-pair-v1'
PROMPT = """You review an organisation's governed process documents for knowledge-governance issues.
You are given two statements, each from a different document or section. Classify their relationship:
- "conflict": they cannot both be followed or both be true for the same subject, scope and time, for example
  different values, owners, order of steps or methods, or one requires what the other rules out.
- "duplicate": they give the same substantive guidance, so one could replace the other.
- "neither": anything else: they are about different subjects, processes, item types, phases, sites or dates;
  one is an exception to, or a later phase of, the other; or they add different, compatible information.
Judge only what the statements say. Different wording alone is not a conflict.
Return JSON: {"relation": "conflict" | "duplicate" | "neither", "reason": "<one sentence>"}"""
SCHEMA = {'type': 'object', 'properties': {'relation': {'type': 'string', 'enum': ['conflict', 'duplicate', 'neither']},
                                           'reason': {'type': 'string'}},
          'required': ['relation', 'reason']}
RELATIONS = ('conflict', 'duplicate', 'neither')


class OllamaJudge:
    """A local model through Ollama's chat API, standard library only."""

    def __init__(self, model: str = 'qwen2.5:14b-instruct', base_url: str = 'http://127.0.0.1:11434', timeout: float = 120.0,
                 think: bool = False, think_tokens: int = 16384) -> None:
        # A reasoning model thinking about two long table rows ran past 4,096 tokens and gave no answer (5 of 9
        # real-corpus conflicts on 25 September 2026); the budget is room to finish, not part of the decision.
        self.model, self.base_url, self.timeout, self.think = model, base_url.rstrip('/'), timeout, think
        self.think_tokens = think_tokens

    def judge(self, a: dict, b: dict) -> dict:
        payload = {'model': self.model, 'stream': False, 'keep_alive': '10m', 'format': SCHEMA, 'think': self.think,
                   'options': {'temperature': 0, 'num_ctx': self.think_tokens + 1024 if self.think else 4096,
                               'num_predict': self.think_tokens if self.think else 160},
                   'messages': [{'role': 'system', 'content': PROMPT},
                                {'role': 'user', 'content': json.dumps({'statement_a': a, 'statement_b': b})}]}
        request = urllib.request.Request(f'{self.base_url}/api/chat', data=json.dumps(payload).encode(),
                                         headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            data = json.loads(response.read())
        value = json.loads(data['message']['content'])
        relation = value.get('relation')
        if relation not in RELATIONS:
            raise ValueError(f'Unexpected relation: {relation!r}')
        return {'relation': relation, 'reason': str(value.get('reason', ''))[:500],
                'prompt_tokens': data.get('prompt_eval_count'), 'output_tokens': data.get('eval_count')}


def pair_key(model: str, a: dict, b: dict) -> str:
    sides = sorted(json.dumps([x['document'], x['section'], x['text']]) for x in (a, b))
    return hashlib.sha256('\u0000'.join([PROMPT_VERSION, model, *sides]).encode()).hexdigest()


class JudgementCache:
    def __init__(self, base_dir: str | Path) -> None:
        self.path = Path(base_dir) / 'governance' / 'judgements.json'
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.lock = threading.Lock()

    def get(self, key: str) -> dict | None:
        return self.data.get(key)

    def put(self, key: str, value: dict) -> None:
        with self.lock:
            self.data[key] = value

    def save(self, keep: set[str] | None = None, model: str | None = None) -> None:
        """Write the cache; with ``keep`` and ``model``, drop that model's judgements of pairs that no longer exist."""
        with self.lock:
            if keep is not None:
                self.data = {k: v for k, v in self.data.items()
                             if k in keep or v.get('model') != model or v.get('prompt_version') != PROMPT_VERSION}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data))


def judge_candidates(candidates, judge, cache: JudgementCache, model: str, workers: int = 4, progress=None) -> tuple[list[dict], dict]:
    """Judge every candidate, from the cache where possible. Returns (judgements in candidate order, statistics)."""
    keys = [pair_key(model, c.a.payload(), c.b.payload()) for c in candidates]
    todo = [(n, c, k) for n, (c, k) in enumerate(zip(candidates, keys)) if cache.get(k) is None]
    errors, done = [], [0]

    def one(item):
        n, candidate, key = item
        started = time.perf_counter()
        try:
            value = judge.judge(candidate.a.payload(), candidate.b.payload())
        except Exception as exc:  # recorded and retried on the next run, never hidden
            errors.append({'index': n, 'error': str(exc)[:200]})
            return
        cache.put(key, {**value, 'model': model, 'prompt_version': PROMPT_VERSION,
                        'seconds': round(time.perf_counter() - started, 3)})
        done[0] += 1
        if progress and done[0] % 50 == 0:
            progress(done[0], len(todo))
            cache.save()

    started = time.perf_counter()
    with ThreadPoolExecutor(max(1, workers)) as pool:
        list(pool.map(one, todo))
    cache.save(keep=set(keys), model=model)
    judgements = [cache.get(k) for k in keys]
    return judgements, {'candidates': len(candidates), 'judged': len(todo) - len(errors), 'from_cache': len(candidates) - len(todo),
                        'errors': errors, 'judge_seconds': round(time.perf_counter() - started, 1)}
