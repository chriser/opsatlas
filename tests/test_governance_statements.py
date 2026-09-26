"""Statement-level governance (GOV S5-S7): statements, the candidate index and the cached judge."""
import hashlib
import json
import math
import re

from assistant.governance.statement_index import StatementIndex
from assistant.governance.statement_judge import PROMPT, JudgementCache, OllamaJudge, judge_candidates, pair_key
from assistant.governance.statement_review import run_statement_review
from assistant.governance.statements import StatementStore, extract, statement_id, units
from assistant.ingestion.service import ingest_source
from assistant.ingestion.store import SectionStore
from assistant.sources.register import SourceRegister
from assistant.sources.service import register_upload

SUPPLIER = """# Supplier pack

Source basis: workshop transcript segment on supplier setup.
Content has been anonymised for internal learning use.

## 1. Process overview

The supplier process starts with a request from a business team and ends with a usable supplier.

## 3. Roles and responsibilities

| Role | Responsibility |
|---|---|
| Accounts payable team | Performs the due diligence and credit checks before the supplier is created. |

## 4. Key business rules

- Due diligence and credit checks must be completed before the supplier can move forward.
- A commercial contract is required before the supplier can be used in downstream processes.

## 7. Realistic Q&A pairs

| Question | Answer |
|---|---|
| Q1. When are credit checks done? | Credit checks must be completed before the supplier can move forward. |
"""
CONTRACTS = """# Contracts pack

Content has been anonymised for internal learning use.

## 1. Process overview

Contracts give a supplier its ordering, service and payment behaviour in downstream processes.

## 4. Key business rules

- Due diligence and credit checks can be completed after the supplier has been activated.
- A commercial contract is required before the supplier can be used in downstream processes.
"""
PRICING = """# Pricing pack

Content has been anonymised for internal learning use.

## 1. Process overview

Price lists decide which price a store receives for each item in the estate.

## 4. Key business rules

- The national price list applies whenever no more specific price list overrides it.
"""


class Embedder:
    """Hashed bag of words: sentences sharing most words are close, as with a real embedding model."""

    def __init__(self):
        self.calls = 0

    def embed(self, texts):
        self.calls += len(texts)
        out = []
        for text in texts:
            vector = [0.0] * 256
            for word in re.findall(r'[a-z]+', text.lower()):
                vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % 256] += 1.0
            norm = math.sqrt(sum(x * x for x in vector)) or 1.0
            out.append([x / norm for x in vector])
        return out


class Judge:
    """Before against after is a conflict; the same words are a duplicate; anything else is neither."""

    def __init__(self):
        self.calls = []

    def judge(self, a, b):
        self.calls.append((a['text'], b['text']))
        ta, tb = a['text'].lower(), b['text'].lower()
        if ('before' in ta and 'after' in tb) or ('after' in ta and 'before' in tb):
            return {'relation': 'conflict', 'reason': 'Before against after.'}
        if set(re.findall(r'[a-z]+', ta)) == set(re.findall(r'[a-z]+', tb)):
            return {'relation': 'duplicate', 'reason': 'Same guidance.'}
        return {'relation': 'neither', 'reason': 'Compatible.'}


def corpus(tmp_path, packs=(('supplier.md', 'Supplier pack', SUPPLIER), ('contracts.md', 'Contracts pack', CONTRACTS),
                             ('pricing.md', 'Pricing pack', PRICING))):
    register = SourceRegister(tmp_path)
    sections = SectionStore(tmp_path)
    ids = {}
    for name, title, text in packs:
        source = register_upload(register, name, text.encode(), title)
        ingest_source(register, sections, source.id)
        register.update(source.id, approval_status='approved')
        ids[title] = source.id
    return register, sections, ids


def test_units_are_bullets_rows_and_sentences_without_table_headers():
    found = units('| Role | Responsibility |\n|---|---|\n| Accounts payable team | Performs the credit checks for the supplier. |\n'
                  '- A contract is required before the supplier is used.\nShort line.\n'
                  'The first sentence has enough words here. The second sentence also has enough words.\n')
    assert [(kind, text) for _, kind, text in found] == [
        ('row', 'Accounts payable team | Performs the credit checks for the supplier.'),
        ('bullet', 'A contract is required before the supplier is used.'),
        ('sentence', 'The first sentence has enough words here.'),
        ('sentence', 'The second sentence also has enough words.')]


def test_statement_ids_are_stable_and_derived_sections_are_marked(tmp_path):
    register, sections, ids = corpus(tmp_path)
    source = register.get(ids['Supplier pack'])
    statements = extract(source, sections.list_for_source(source.id))
    by_text = {s.text: s for s in statements}
    rule = by_text['Due diligence and credit checks must be completed before the supplier can move forward.']
    assert not rule.derived and rule.kind == 'bullet' and rule.heading.startswith('4.')
    assert rule.id == statement_id(source.id, rule.heading, '**Due diligence** and credit checks must be completed before the '
                                                            'supplier can move forward.')  # emphasis does not change the ID
    # The preamble before numbered sections and the Q&A pairs restate the pack: kept, not governed.
    assert by_text['Content has been anonymised for internal learning use.'].derived
    assert any(s.derived and s.heading.startswith('7.') for s in statements)
    # The same text under the same heading keeps its ID when the source is re-ingested with a new section order.
    shifted = SUPPLIER.replace('## 1. Process overview', '## 0. Scope\n\nThis pack covers supplier setup from request to use.\n\n'
                                                         '## 1. Process overview')
    register.write_content(source.id, shifted.encode())
    ingest_source(register, sections, source.id)
    again = {s.text: s for s in extract(register.get(source.id), sections.list_for_source(source.id))}
    assert again[rule.text].id == rule.id and again[rule.text].section != rule.section


def test_the_store_re_extracts_only_changed_sources(tmp_path):
    register, sections, ids = corpus(tmp_path)
    store = StatementStore(tmp_path)
    statements, sync = store.sync(register, sections)
    assert len(sync['extracted']) == 3 and statements
    assert store.sync(register, sections)[1]['extracted'] == []
    register.update(ids['Pricing pack'], content_sha256='changed', version=2)
    assert store.sync(register, sections)[1]['extracted'] == [ids['Pricing pack']]
    register.update(ids['Pricing pack'], approval_status='rejected')
    assert store.sync(register, sections)[1]['removed'] == [ids['Pricing pack']]


def test_the_index_keeps_template_text_and_cited_evidence_out(tmp_path):
    register, sections, ids = corpus(tmp_path)
    statements, _ = StatementStore(tmp_path).sync(register, sections)
    embedder = Embedder()
    index = StatementIndex(tmp_path, embedder, 'fake-embed')
    candidates, stats = index.candidates(statements, k=3, min_cosine=0.5)
    texts = {(c.a.text, c.b.text) for c in candidates} | {(c.b.text, c.a.text) for c in candidates}
    assert ('Due diligence and credit checks must be completed before the supplier can move forward.',
            'Due diligence and credit checks can be completed after the supplier has been activated.') in texts
    assert stats['template_lines'] == 1  # "Content has been anonymised ..." is in all three packs
    assert not any('anonymised' in c.a.text or 'anonymised' in c.b.text for c in candidates)
    assert not any(c.a.derived or c.b.derived for c in candidates)
    # Embeddings are cached by model and text: a second call embeds nothing; another model embeds again.
    calls = embedder.calls
    index.candidates(statements, k=3, min_cosine=0.5)
    assert embedder.calls == calls
    StatementIndex(tmp_path, embedder, 'another-model').candidates(statements, k=3, min_cosine=0.5)
    assert embedder.calls > calls
    # Evidence the caller names is never a candidate.
    evidence = {ids['Contracts pack']}
    kept, _ = index.candidates(statements, k=3, min_cosine=0.5, exclude_sources=evidence)
    assert not any(c.a.source_id in evidence or c.b.source_id in evidence for c in kept)


def test_judgements_are_cached_per_pair_and_an_edit_re_judges_only_its_pairs(tmp_path):
    register, sections, ids = corpus(tmp_path)
    judge = Judge()
    first = run_statement_review(register, sections, tmp_path, Embedder(), 'fake-embed', judge, 'fake-judge', min_cosine=0.5, workers=2)
    assert first['judging']['judged'] == len(judge.calls) > 0
    conflicts = [f for f in first['findings'] if f['relation'] == 'conflict']
    assert conflicts and all(len(f['statements']) == 2 for f in conflicts)
    assert first['raised']['duplicate'] >= 1  # the contract rule is written the same way in two packs
    # A second run over the unchanged corpus is served from the cache.
    judge.calls.clear()
    second = run_statement_review(register, sections, tmp_path, Embedder(), 'fake-embed', judge, 'fake-judge', min_cosine=0.5)
    assert judge.calls == [] and second['judging']['from_cache'] == second['judging']['candidates']
    assert [f['key'] for f in second['findings']] == [f['key'] for f in first['findings']]
    # Editing one statement re-judges only the pairs that involve it.
    edited = CONTRACTS.replace('after the supplier has been activated.', 'after the supplier has been activated and approved.')
    register.write_content(ids['Contracts pack'], edited.encode())
    register.update(ids['Contracts pack'], content_sha256='edited', version=2)
    ingest_source(register, sections, ids['Contracts pack'])
    third = run_statement_review(register, sections, tmp_path, Embedder(), 'fake-embed', judge, 'fake-judge', min_cosine=0.5)
    assert judge.calls and all('activated and approved' in a + b for a, b in judge.calls)
    assert third['sync']['extracted'] == [ids['Contracts pack']] and third['judging']['from_cache'] > 0
    assert json.loads((tmp_path / 'governance' / 'statement-review-latest.json').read_text())['engine'] == 'statement-review'


def test_a_document_restating_itself_is_not_a_duplicate_but_contradicting_itself_is_a_conflict(tmp_path):
    pack = SUPPLIER.replace('## 7. Realistic Q&A pairs', '## 5. Controls\n\n- Due diligence and credit checks can be completed after '
                                                        'the supplier can move forward.\n- A commercial contract is required before the '
                                                        'supplier can be used in downstream processes.\n\n## 7. Realistic Q&A pairs')
    register, sections, _ = corpus(tmp_path, (('supplier.md', 'Supplier pack', pack),))
    result = run_statement_review(register, sections, tmp_path, Embedder(), 'fake-embed', Judge(), 'fake-judge', min_cosine=0.5)
    assert any(f['relation'] == 'conflict' and f['same_document'] for f in result['findings'])
    assert not any(f['relation'] == 'duplicate' for f in result['findings'])
    assert result['restated_within_a_document'] >= 1


def test_the_judge_uses_the_pre_registered_benchmark_prompt(monkeypatch):
    import scripts.evaluate_governance_pairs as benchmark
    assert benchmark.PROMPT == PROMPT
    sent = {}

    class Response:
        def __init__(self, body):
            self.body = body

        def read(self):
            return self.body

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def urlopen(request, timeout):
        sent.update(json.loads(request.data))
        return Response(json.dumps({'message': {'content': '{"relation": "conflict", "reason": "Different owners."}'},
                                    'prompt_eval_count': 300, 'eval_count': 20}).encode())
    monkeypatch.setattr('urllib.request.urlopen', urlopen)
    value = OllamaJudge('qwen2.5:14b-instruct').judge({'document': 'A', 'section': 's', 'text': 'x'},
                                                      {'document': 'B', 'section': 's', 'text': 'y'})
    assert value['relation'] == 'conflict' and sent['messages'][0]['content'] == PROMPT and sent['options']['temperature'] == 0
    # The cache key does not depend on the order of the two statements.
    a, b = {'document': 'A', 'section': 's', 'text': 'x'}, {'document': 'B', 'section': 's', 'text': 'y'}
    assert pair_key('m', a, b) == pair_key('m', b, a) != pair_key('other', a, b)


def test_judge_errors_are_recorded_and_retried(tmp_path):
    register, sections, _ = corpus(tmp_path)
    statements, _ = StatementStore(tmp_path).sync(register, sections)
    candidates, _ = StatementIndex(tmp_path, Embedder(), 'fake-embed').candidates(statements, min_cosine=0.5)

    class Broken:
        def judge(self, a, b):
            raise TimeoutError('model busy')
    judgements, stats = judge_candidates(candidates, Broken(), JudgementCache(tmp_path), 'fake-judge')
    assert all(j is None for j in judgements) and len(stats['errors']) == len(candidates)
    judgements, stats = judge_candidates(candidates, Judge(), JudgementCache(tmp_path), 'fake-judge')
    assert all(j is not None for j in judgements) and stats['judged'] == len(candidates)


def test_a_second_opinion_dismisses_a_conflict_only_when_it_disagrees(tmp_path):
    register, sections, _ = corpus(tmp_path)

    class Agrees(Judge):
        pass

    class Disagrees:
        def __init__(self):
            self.calls = 0

        def judge(self, a, b):
            self.calls += 1
            return {'relation': 'neither', 'reason': 'Different phases.'}

    class Silent:
        def judge(self, a, b):
            raise TimeoutError('no answer')

    kept = run_statement_review(register, sections, tmp_path / 'a', Embedder(), 'e', Judge(), 'j', min_cosine=0.5,
                                reviewer=Agrees(), reviewer_model='r')
    assert kept['raised']['conflict'] >= 1 and not kept['dismissed_by_second_opinion']
    assert all(f['second_opinion']['relation'] == 'conflict' for f in kept['findings'] if f['relation'] == 'conflict')
    reviewer = Disagrees()
    dismissed = run_statement_review(register, sections, tmp_path / 'b', Embedder(), 'e', Judge(), 'j', min_cosine=0.5,
                                     reviewer=reviewer, reviewer_model='r')
    assert dismissed['raised']['conflict'] == 0 and len(dismissed['dismissed_by_second_opinion']) == reviewer.calls >= 1
    assert dismissed['raised']['duplicate'] == kept['raised']['duplicate']  # only conflicts get a second opinion
    silent = run_statement_review(register, sections, tmp_path / 'c', Embedder(), 'e', Judge(), 'j', min_cosine=0.5,
                                  reviewer=Silent(), reviewer_model='r')
    assert silent['raised']['conflict'] == kept['raised']['conflict']  # no answer: the first verdict stands


def test_the_claude_judge_sends_only_the_prompt_and_two_statements_to_the_fixed_host():
    import io
    import urllib.error

    from assistant.governance.statement_judge import AnthropicJudge
    seen = []

    class Opener:
        def __init__(self):
            self.calls = 0

        def open(self, request, timeout):
            self.calls += 1
            seen.append(request)
            if self.calls == 1:  # busy once: retried
                raise urllib.error.HTTPError(request.full_url, 429, 'busy', {'retry-after': '0'}, io.BytesIO(b''))
            reply = {'content': [{'type': 'text', 'text': 'Here: {"relation": "conflict", "reason": "Different owners."}'}],
                     'usage': {'input_tokens': 470, 'output_tokens': 60}}
            return io.BytesIO(json.dumps(reply).encode())
    judge = AnthropicJudge('claude-opus-5-5', 'sk-test-secret')
    judge.opener = Opener()
    value = judge.judge({'document': 'A', 'section': 's', 'text': 'x'}, {'document': 'B', 'section': 's', 'text': 'y'})
    assert value == {'relation': 'conflict', 'reason': 'Different owners.', 'prompt_tokens': 470, 'output_tokens': 60}
    request = seen[-1]
    body = json.loads(request.data)
    assert request.full_url == 'https://api.anthropic.com/v1/messages' and request.headers['X-api-key'] == 'sk-test-secret'
    assert b'sk-test-secret' not in request.data and set(body) == {'model', 'max_tokens', 'system', 'messages'}
    assert body['system'] == PROMPT and json.loads(body['messages'][0]['content'])['statement_b']['text'] == 'y'
    assert judge.audit()['requests'] == 2 and judge.audit()['retried'] == 1 and judge.audit()['bytes_sent'] == 2 * len(request.data)


def test_a_claude_reply_cut_off_in_its_reason_still_gives_its_verdict():
    import io

    from assistant.governance.statement_judge import AnthropicJudge

    class Opener:
        def open(self, request, timeout):
            reply = {'content': [{'type': 'text', 'text': '```json\n{"relation": "neither", "reason": "Both are compatible overv'}],
                     'usage': {'input_tokens': 470, 'output_tokens': 300}}
            return io.BytesIO(json.dumps(reply).encode())
    judge = AnthropicJudge('claude-opus-5-5', 'sk-test-key-2026')
    judge.opener = Opener()
    verdict = judge.judge({'document': 'A', 'section': 's', 'text': 'x'}, {'document': 'B', 'section': 's', 'text': 'y'})
    assert verdict['relation'] == 'neither'
