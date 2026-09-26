"""Statement-level governance for the OpsAtlas Sales records (GOV S9, sales first).

On 26 September 2026 the Human approved statement-level governance, chose local judging as the default, and moved
governance onto the sales data: the records Tibi speaks from and the claims contributed in interviews. This module
runs assistant.governance.statement_review over that data with four sales rules, fixed before the first run:

* the records are governed; the evidence they cite (DT603 sections, repository files, interview accounts) and a
  record's earlier versions are not (GovernedSources);
* a claim is checked before it is approved: pending sources are governed, rejected ones (withdrawn, superseded,
  disputed) are not;
* a record's status is its scope: the judge sees "Path to production (planned)", so a planned capability is not
  read as contradicting an available one;
* conversation-style records are compared only with each other, product records only with product records;
* a record's phase comes from corpus/record_scope.json (GOV S8): statements about the proof of concept and about a
  real deployment are set aside, never judged against each other. A contributed claim is scoped only by its own
  words, never by the topic it was filed under: a claim filed under "real deployment" that states something about the
  proof of concept must still meet the proof-of-concept records.

The judge is local by default (qwen2.5:14b-instruct, with qwen3.5:35b-a3b thinking as a second opinion on each
conflict). A frontier judge (SALES_GOVERNANCE_JUDGE=anthropic:<model>) is used only when the workspace's data owner
has approved sending its records (SALES_GOVERNANCE_FRONTIER_APPROVED=yes); every request is then audited.
"""

from __future__ import annotations

import dataclasses
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from assistant.governance.statement_judge import AnthropicJudge, OllamaJudge
from assistant.governance.statement_review import run_statement_review
from assistant.retrieval.embedder import OllamaEmbedder

from .governance import GovernedSources

RESULT = 'sales-statement-review.json'
RECORD_SCOPE = Path(__file__).parent / 'corpus' / 'record_scope.json'
LOCAL_JUDGE, LOCAL_REVIEWER, EMBED = 'qwen2.5:14b-instruct', 'qwen3.5:35b-a3b', 'nomic-embed-text'


def profile() -> dict:
    """The judge this workspace uses, and where its records go."""
    choice = os.environ.get('SALES_GOVERNANCE_JUDGE', 'local').strip() or 'local'
    if choice.startswith('anthropic:') and os.environ.get('SALES_GOVERNANCE_FRONTIER_APPROVED', '').lower() == 'yes':
        return {'name': choice, 'judge': choice.split(':', 1)[1], 'reviewer': None, 'data_leaves': True,
                'where': 'api.anthropic.com, approved by the workspace data owner'}
    return {'name': 'local', 'judge': LOCAL_JUDGE, 'reviewer': LOCAL_REVIEWER, 'data_leaves': False, 'where': 'this Mac only',
            **({'note': 'A frontier judge was requested without the data owner\'s approval; local judging is used.'}
               if choice != 'local' else {})}


def _anthropic_key(root: Path) -> str:
    env = root / '.env'
    for line in (env.read_text().splitlines() if env.exists() else []):
        if line.strip().startswith('ANTHROPIC_API_KEY='):
            return line.split('=', 1)[1].strip()
    raise ValueError('ANTHROPIC_API_KEY is not set in .env')


class SalesStatementReview:
    def __init__(self, register, sections, knowledge, *, embedder=None, judge=None, reviewer=None, judge_name=None,
                 reviewer_name=None, ollama: str = 'http://127.0.0.1:11434') -> None:
        self.register, self.sections, self.knowledge = register, sections, knowledge
        self.base_dir = Path(register.base_dir)
        self.path = self.base_dir / 'governance' / RESULT
        self.ollama = ollama
        self._injected = (embedder, judge, reviewer, judge_name, reviewer_name)
        self.lock = threading.Lock()
        self.thread = None
        self.state = {'status': 'idle', 'started_at': None, 'progress': None, 'error': None}

    # ---- the judges ----------------------------------------------------------------------

    def _judges(self):
        embedder, judge, reviewer, judge_name, reviewer_name = self._injected
        if judge is not None:
            return embedder, judge, judge_name or 'injected', reviewer, reviewer_name
        chosen = profile()
        embedder = embedder or OllamaEmbedder(EMBED, self.ollama)
        if chosen['data_leaves']:
            root = Path(__file__).resolve().parents[2]
            return embedder, AnthropicJudge(chosen['judge'], _anthropic_key(root)), chosen['name'], None, None
        return (embedder, OllamaJudge(LOCAL_JUDGE, self.ollama), LOCAL_JUDGE,
                OllamaJudge(LOCAL_REVIEWER, self.ollama, timeout=1200, think=True), LOCAL_REVIEWER + '+think')

    # ---- a review --------------------------------------------------------------------------

    def records(self) -> dict:
        return {r['source_id']: r for r in self.knowledge.records()}

    def scope_metadata(self, records: dict) -> dict:
        """Source id -> the scope its curated record carries; contributed claims carry none."""
        scopes = {k: v for k, v in json.loads(RECORD_SCOPE.read_text()).items() if not k.startswith('_')}
        return {source_id: scopes[record['id']] for source_id, record in records.items()
                if record['id'] in scopes and not record.get('provenance')}

    def run(self, progress=None) -> dict:
        records = self.records()
        evidence = GovernedSources(self.register, self.knowledge).evidence()

        def describe(statement):
            record = records.get(statement.source_id)
            return dataclasses.replace(statement, source_title=f"{record['title']} ({record['status']})") if record else statement

        def group(statement):
            record = records.get(statement.source_id)
            return (record.get('kind') or 'product') if record else 'document'

        embedder, judge, judge_name, reviewer, reviewer_name = self._judges()
        result = run_statement_review(
            self.register, self.sections, self.base_dir, embedder, EMBED, judge, judge_name,
            exclude_sources=evidence, describe=describe, group=group, include=lambda s: s.approval_status != 'rejected',
            scope_metadata=self.scope_metadata(records),
            reviewer=reviewer, reviewer_model=reviewer_name, progress=progress, result_name=RESULT)
        if hasattr(judge, 'audit'):
            result['audit'] = judge.audit()
        result['profile'] = profile() if self._injected[1] is None else {'name': judge_name, 'data_leaves': False}
        self.path.write_text(json.dumps(result, indent=1))
        return result

    def start(self) -> dict:
        """Run in the background; a second request while one runs is not queued twice."""
        with self.lock:
            if self.thread and self.thread.is_alive():
                return self.status()
            self.state = {'status': 'running', 'started_at': datetime.now(timezone.utc).isoformat(), 'progress': None, 'error': None}

            def work():
                started = time.perf_counter()
                try:
                    self.run(progress=lambda done, total: self.state.update(progress={'judged': done, 'total': total}))
                    self.state.update(status='finished', seconds=round(time.perf_counter() - started, 1))
                except Exception as exc:  # reported to the page, never hidden
                    self.state.update(status='failed', error=str(exc)[:300])
            self.thread = threading.Thread(target=work, name='sales-statement-review', daemon=True)
            self.thread.start()
            return self.status()

    def status(self) -> dict:
        latest = self.latest()
        summary = None
        if latest:
            summary = {k: latest.get(k) for k in ('finished_at', 'judge_model', 'raised', 'total_seconds', 'profile')}
            summary.update(candidates=latest['judging']['candidates'], statements=latest['index'].get('governed'),
                           set_aside_by_scope=(latest.get('set_aside_by_scope') or {}).get('by_reason'),
                           errors=len(latest['judging'].get('errors', [])),
                           dismissed_by_second_opinion=len(latest.get('dismissed_by_second_opinion', [])))
        return {**self.state, 'profile': profile(), 'latest': summary}

    def latest(self) -> dict | None:
        return json.loads(self.path.read_text()) if self.path.exists() else None

    def findings(self) -> list[dict]:
        """Findings of the latest review whose statements still belong to governed records, with the records named."""
        latest = self.latest()
        if not latest:
            return []
        records = self.records()
        out = []
        for finding in latest['findings']:
            sides = []
            for statement in finding['statements']:
                record = records.get(statement['source_id'])
                source = self.register.get(statement['source_id'])
                if not record or not source or source.approval_status == 'rejected':
                    break  # the record was withdrawn or replaced since the review: the finding no longer stands
                sides.append({'record_id': record['id'], 'title': record['title'], 'status': record['status'],
                              'kind': record.get('kind') or 'product', 'contributor': (record.get('provenance') or {}).get('contributor'),
                              'source_id': statement['source_id'], 'statement_id': statement['id'], 'text': statement['text']})
            if len(sides) == 2:
                for side, applies in zip(sides, finding.get('applies_to') or ['', '']):
                    side['applies_to'] = applies
                out.append({**{k: finding[k] for k in ('key', 'relation', 'reason', 'cosine', 'same_document')},
                            'second_opinion': finding.get('second_opinion'), 'statements': sides})
        return out
