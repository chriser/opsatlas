"""Scope and dates of a statement (GOV S8): what is read from its words, and which pairs are set aside."""
from datetime import date

from test_governance_statements import Embedder, Judge, corpus

from assistant.governance import scope
from assistant.governance.statement_review import run_statement_review


def test_phases_dates_and_what_a_statement_applies_to_are_read_from_its_words():
    poc = scope.extract('The PoC uses anonymised data only.')
    assert poc.phases == {'proof_of_concept'} and not poc.start and not poc.end
    assert scope.extract("A real deployment would use the organisation's own data.").phases == {'real_deployment'}
    assert scope.extract('On day one, orders are keyed by hand.').phases == {'day_one'}
    # "poc" in lower case is not the acronym.
    assert not scope.extract('The poc of the meeting was late.').phases
    dated = scope.extract('From 1 April 2027 the national price list applies until 31 March 2028.')
    assert (dated.start, dated.end) == (date(2027, 4, 1), date(2028, 3, 31))
    assert scope.extract('Until Q1 2027 invoices are paired by hand.').end == date(2027, 3, 31)
    assert scope.extract('During 2026 the weekly review is kept.').start == date(2026, 1, 1)
    assert scope.extract('Manual checks apply for motorway sites only.').applies_to == ['motorway sites']
    assert 'motorway sites' in scope.extract('Manual checks apply for motorway sites only.').describe()
    assert dated.describe() == '1 April 2027 to 31 March 2028'
    assert scope.extract('Until Q1 2027 invoices are paired by hand.').describe() == 'up to 31 March 2027'
    assert scope.extract('From 1 April 2027 the PoC keeps prices.').describe() == '1 April 2027 onwards'
    assert scope.extract('Effective from 1 April 2027, prices are kept.').start == date(2027, 4, 1)


def test_only_the_scope_a_statement_opens_with_counts():
    # Mentioned later, a phase or date is being discussed; it is not the statement's scope (the 21 packs' role rows).
    row = 'Programme or rollout owner | Decides whether ingredient redesign is a day-one change or a later-phase improvement.'
    assert scope.extract(row).empty()
    assert scope.extract('The PoC keeps prices from 1 April 2027.').describe() == 'the proof of concept'
    assert not scope.extract('Stores print labels, as they did before 2027.').end
    assert scope.extract('Day-one fuel items are treated as service items.').phases == {'day_one'}
    assert scope.extract('In production, records are encrypted.').phases == {'real_deployment'}
    assert scope.extract("A real deployment would use the organisation's own data.").phases == {'real_deployment'}
    # A workspace's status label before the statement proper is looked past; a phase used as the label counts too.
    assert scope.extract('Currently: The proof of concept supports single sign-on.').phases == {'proof_of_concept'}
    assert scope.extract('Planned, not confirmed available: A real deployment adds SSO.').phases == {'real_deployment'}
    assert scope.extract('Currently: from 1 April 2027 prices are daily.').start == date(2027, 4, 1)
    assert scope.extract('Day one: orders are keyed by hand.').phases == {'day_one'}
    assert scope.extract('Owner | Currently: the proof of concept is reviewed.').empty()


def test_only_disjoint_dates_and_exclusive_phases_are_set_aside():
    before, after = scope.extract('Until 31 March 2027 prices are set weekly.'), scope.extract('From 1 April 2027 prices are set daily.')
    assert scope.separated(before, after) == 'dates'
    overlapping = scope.extract('From 1 March 2027 prices are set daily.')
    assert scope.separated(before, overlapping) is None
    # An undated statement may hold at any time, so it is judged against a dated one.
    assert scope.separated(before, scope.extract('Prices are set daily.')) is None
    poc, real = scope.extract('The PoC uses anonymised data.'), scope.extract('A real deployment uses live data.')
    assert scope.separated(poc, real) == 'phase'
    assert scope.separated(scope.extract('On day one, orders are keyed.'), scope.extract('In the end state, orders flow.')) == 'phase'
    # The same phase on both sides, or a statement spanning both, can still conflict.
    assert scope.separated(scope.extract('On day one, orders are keyed.'), scope.extract('On day one, orders flow.')) is None
    both = scope.extract('OpsAtlas is a proof of concept, not a production deployment.')
    assert scope.separated(both, real) is None
    # "Applies to" is never a reason to set a pair aside.
    assert scope.separated(scope.extract('Checks apply for motorway sites only.'), scope.extract('Checks never apply.')) is None


def test_a_sources_metadata_overrides_what_its_words_say():
    words = scope.extract('Unlike this proof of concept, the data would be live.')
    merged = scope.merge(words, {'phases': ['real_deployment'], 'effective_from': '2027-01-01'})
    assert merged.phases == {'real_deployment'} and merged.start == date(2027, 1, 1)
    assert scope.merge(words, None) is words and scope.merge(words, {}).phases == words.phases


def test_the_engine_sets_aside_separated_pairs_and_judges_the_rest_as_before(tmp_path):
    rule = '# {0}\n\n## 4. Rules\n\n- {1} credit checks are done {2} the supplier is created.\n'.format
    packs = (('old.md', 'Old rules', rule('Old rules', 'Until 31 March 2027', 'before')),
             ('new.md', 'New rules', rule('New rules', 'From 1 April 2027', 'after')),
             ('poc.md', 'PoC', rule('PoC', 'For motorway sites only', 'before')))
    register, sections, ids = corpus(tmp_path, packs)
    seen = []

    class Recording(Judge):
        def judge(self, a, b):
            seen.append((a, b))
            return super().judge(a, b)
    result = run_statement_review(register, sections, tmp_path, Embedder(), 'e', Recording(), 'j', min_cosine=0.3)
    assert result['set_aside_by_scope']['by_reason'] == {'dates': 1, 'phase': 0}
    aside = result['set_aside_by_scope']['pairs'][0]
    assert {s['source_title'] for s in aside['statements']} == {'Old rules', 'New rules'}
    # The dated pair was never judged; the others were, with the benchmark's payload only. Scope goes with the finding.
    assert not any({a['document'], b['document']} == {'Old rules', 'New rules'} for a, b in seen)
    assert seen and all(set(x) == {'document', 'section', 'text'} for pair in seen for x in pair)
    assert result['raised']['conflict'] == 1
    assert sorted(result['findings'][0]['applies_to']) == ['1 April 2027 onwards', 'motorway sites']
    # A source's metadata can place it in a phase: then its pairs with the other phase are set aside too.
    phased = run_statement_review(register, sections, tmp_path, Embedder(), 'e', Judge(), 'j', min_cosine=0.3,
                                  scope_metadata={ids['PoC']: {'phases': ['proof_of_concept']},
                                                  ids['New rules']: {'phases': ['real_deployment']}})
    assert phased['set_aside_by_scope']['by_reason'] == {'dates': 1, 'phase': 1}


def test_statements_keep_their_scope_and_sources_carry_theirs(tmp_path):
    from assistant.governance.statements import StatementStore
    rule = '# {0}\n\n## 4. Rules\n\n- {1} credit checks are done {2} the supplier is created.\n'.format
    register, sections, ids = corpus(tmp_path, (('old.md', 'Old rules', rule('Old rules', 'Until 31 March 2027', 'before')),
                                                ('new.md', 'New rules', rule('New rules', 'Every day', 'after'))))
    statements, _ = StatementStore(tmp_path).sync(register, sections)
    dated = next(s for s in statements if s.source_id == ids['Old rules'])
    assert dated.scope == {'phases': [], 'effective_from': None, 'effective_to': '2027-03-31', 'applies_to': []}
    # A source's own fields: in force from 1 April 2027, so its undated statements meet the old rules' dates.
    register.update(ids['New rules'], effective_from='2027-04-01', phases=['real_deployment', 'not-a-phase'])
    source = register.get(ids['New rules'])
    assert source.effective_from == '2027-04-01' and scope.of_source(source)['phases'] == ['real_deployment', 'not-a-phase']
    assert scope.merge(scope.Scope(), scope.of_source(source)).phases == {'real_deployment'}  # unknown phases are ignored
    result = run_statement_review(register, sections, tmp_path, Embedder(), 'e', Judge(), 'j', min_cosine=0.3)
    assert result['set_aside_by_scope']['by_reason']['dates'] == 1 and result['raised']['conflict'] == 0


def test_a_superseded_source_is_not_governed_while_its_replacement_is(tmp_path):
    rule = '# {0}\n\n## 4. Rules\n\n- Credit checks are done {1} the supplier is created.\n'.format
    register, sections, ids = corpus(tmp_path, (('v1.md', 'Rules v1', rule('Rules v1', 'before')),
                                                ('v2.md', 'Rules v2', rule('Rules v2', 'after'))))
    assert run_statement_review(register, sections, tmp_path, Embedder(), 'e', Judge(), 'j', min_cosine=0.3)['raised']['conflict'] == 1
    register.update(ids['Rules v2'], supersedes=[ids['Rules v1']])
    result = run_statement_review(register, sections, tmp_path, Embedder(), 'e', Judge(), 'j', min_cosine=0.3)
    assert result['raised']['conflict'] == 0 and result['settings']['superseded_sources'] == [ids['Rules v1']]
    # A replacement that is itself not governed (rejected) supersedes nothing.
    register.update(ids['Rules v2'], approval_status='rejected')
    register.update(ids['Rules v1'], approval_status='approved')
    assert run_statement_review(register, sections, tmp_path, Embedder(), 'e', Judge(), 'j', min_cosine=0.3)['settings'][
        'superseded_sources'] == []


def test_a_new_extractor_re_extracts_once_and_keeps_every_statement_id(tmp_path):
    import json

    from assistant.governance.statements import StatementStore
    register, sections, _ = corpus(tmp_path)
    store = StatementStore(tmp_path)
    before, _ = store.sync(register, sections)
    stored = json.loads(store.path.read_text())
    for entry in stored.values():  # as written by the first extractor: no scope, old fingerprint
        entry['fingerprint'] = entry['fingerprint'].rsplit(':', 1)[0]
        for row in entry['statements']:
            row.pop('scope')
    store.path.write_text(json.dumps(stored))
    after, sync = store.sync(register, sections)
    assert len(sync['extracted']) == 3 and [s.id for s in after] == [s.id for s in before]
    assert all(s.scope is not None for s in after)
    assert store.sync(register, sections)[1]['extracted'] == []
