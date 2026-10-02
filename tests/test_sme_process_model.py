"""The working process model of a process interview (TIBI E5, PI F2/F3): checked, deterministic, no model calls."""
import pytest

from services.sme_interviewer import process_model as pm


def run(model, changes, answer, turn=1):
    return pm.apply(model, changes, answer, turn)


def ordering():
    """A made-up interview so far: Sam, ordering parts, three steps (two confirmed)."""
    model = pm.new_model('beepee', 'BeePee')
    model, _ = run(model, [{'op': 'participant', 'field': 'name', 'value': 'Sam Patel', 'quote': "I'm Sam Patel"},
                           {'op': 'participant', 'field': 'role', 'value': 'operations manager', 'quote': 'I run operations'}],
                   "Hi, I'm Sam Patel, I run operations.", 1)
    model, _ = run(model, [{'op': 'process', 'ref': 'n1', 'name': 'Ordering parts', 'quote': 'how we order parts'}],
                   'Mainly how we order parts.', 2)
    model, _ = run(model, [
        {'op': 'step', 'ref': 'n1', 'process': 'p1', 'after': 'start', 'kind': 'task', 'label': 'Check stock report',
         'who': 'store manager', 'system': 'SAP', 'quote': 'the store manager checks the stock report in SAP'},
        {'op': 'step', 'ref': 'n2', 'process': 'p1', 'after': 'n1', 'kind': 'task', 'label': 'Raise purchase order',
         'who': 'store manager', 'system': 'SAP', 'quote': 'then she raises a purchase order'},
        {'op': 'step', 'ref': 'n3', 'process': 'p1', 'after': 'n2', 'kind': 'task', 'label': 'Approve order',
         'who': 'finance', 'system': '', 'quote': 'finance approves it'},
    ], 'Every Monday the store manager checks the stock report in SAP, then she raises a purchase order and finance approves it.', 3)
    return model


def labels(model, process_id='p1'):
    return [s['label'] for s in pm.ordered_steps(pm.process(model, process_id))]


def test_who_they_are_and_what_they_want_to_cover_are_captured_with_their_words():
    model = ordering()
    assert model['participant']['name']['value'] == 'Sam Patel' and model['participant']['name']['quote'] == "I'm Sam Patel"
    [p] = model['processes']
    assert (p['id'], p['name'], p['status'], model['focus']) == ('p1', 'Ordering parts', 'active', 'p1')
    assert labels(model) == ['Check stock report', 'Raise purchase order', 'Approve order']


def test_a_change_whose_quote_is_not_in_the_answer_is_dropped():
    model, log = run(pm.new_model('beepee'), [{'op': 'participant', 'field': 'name', 'value': 'Sam', 'quote': 'My name is Sam'}],
                     "I'm Sam, hello.")
    assert model['participant'] == {} and log['dropped'][0]['why'] == 'the quote is not in the answer'
    # Case, spacing and punctuation do not matter; words do.
    model, log = run(pm.new_model('beepee'), [{'op': 'participant', 'field': 'name', 'value': 'Sam', 'quote': "i'm  SAM"}],
                     "I'm Sam, hello.")
    assert model['participant']['name']['value'] == 'Sam'


def test_a_decision_splits_the_flow_and_a_new_step_after_a_step_takes_over_what_came_next():
    model = ordering()
    answer = ('If the order is over five thousand pounds it actually goes to the regional director for approval, not finance. '
              'After approval the supplier confirms the delivery date by email.')
    model, log = run(model, [
        {'op': 'decision', 'ref': 'n1', 'process': 'p1', 'after': 's2', 'question': 'Is the order over £5,000?',
         'quote': 'If the order is over five thousand pounds'},
        {'op': 'step', 'ref': 'n2', 'process': 'p1', 'after': 'n1', 'kind': 'task', 'label': 'Approve large order',
         'who': 'regional director', 'system': '', 'quote': 'it actually goes to the regional director for approval'},
        {'op': 'branch', 'decision': 'n1', 'condition': 'Over £5,000', 'to': 'n2', 'quote': 'If the order is over five thousand pounds'},
        {'op': 'branch', 'decision': 'n1', 'condition': 'Otherwise', 'to': 's3', 'quote': 'not finance'},
        {'op': 'step', 'ref': 'n3', 'process': 'p1', 'after': 's3', 'kind': 'task', 'label': 'Confirm delivery date',
         'who': 'supplier', 'system': 'email', 'quote': 'the supplier confirms the delivery date by email'},
    ], answer, 4)
    p = pm.process(model, 'p1')
    decision = next(s for s in p['steps'] if s['kind'] == 'decision')
    assert pm.find(model, 's2')[1]['next'] == [{'to': decision['id'], 'label': ''}]
    assert sorted((n['label'], pm.find(model, n['to'])[1]['label']) for n in decision['next']) == [
        ('Otherwise', 'Approve order'), ('Over £5,000', 'Approve large order')]
    confirm = next(s for s in p['steps'] if s['label'] == 'Confirm delivery date')
    assert pm.find(model, 's3')[1]['next'] == [{'to': confirm['id'], 'label': ''}]  # after approval, then delivery
    assert labels(model)[:3] == ['Check stock report', 'Raise purchase order', 'Is the order over £5,000?']
    assert not log['dropped']


def test_a_contradiction_without_a_correction_is_a_conflict_to_raise_not_a_change():
    model = ordering()
    model, log = run(model, [{'op': 'conflict', 'item': 's3', 'field': 'who', 'now': 'regional director',
                              'quote': 'The regional director approves every order'}],
                     'The regional director approves every order before it goes out.', 4)
    step = pm.find(model, 's3')[1]
    assert step['who'] == 'finance' and step['status'] == 'disputed'  # nothing is overwritten
    [conflict] = [o for o in model['open'] if o['kind'] == 'conflict']
    assert (conflict['earlier'], conflict['now'], conflict['earlier_quote']) == ('finance', 'regional director', 'finance approves it')
    # The model tried to change it anyway, without a correction cue: still a conflict, the same one.
    model, log = run(model, [{'op': 'change', 'item': 's3', 'field': 'who', 'value': 'head office',
                              'quote': 'head office approves them'}], 'Head office approves them.', 5)
    assert pm.find(model, 's3')[1]['who'] == 'finance' and len([o for o in model['open'] if o['kind'] == 'conflict']) == 1
    # Tibi raises it first.
    assert pm.goals(model)[0]['key'] == f"conflict:{conflict['id']}"


def test_a_correction_changes_the_item_and_an_answer_to_a_raised_conflict_settles_it():
    model = ordering()
    model, log = run(model, [{'op': 'change', 'item': 's2', 'field': 'system', 'value': 'Excel, then SAP',
                              'quote': 'the order is typed into Excel first'}],
                     'No, sorry, the order is typed into Excel first.', 4)
    assert pm.find(model, 's2')[1]['system'] == 'Excel, then SAP' and log['corrected'][0]['was'] == 'SAP'
    model, _ = run(model, [{'op': 'conflict', 'item': 's3', 'field': 'who', 'now': 'regional director',
                            'quote': 'The regional director approves every order'}], 'The regional director approves every order.', 5)
    [goal] = [g for g in pm.goals(model) if g['key'].startswith('conflict:')]
    model = pm.asked(model, goal, 5)
    assert model['open'][0]['status'] == 'raised'
    model, log = run(model, [{'op': 'change', 'item': 's3', 'field': 'who', 'value': 'regional director',
                              'quote': 'It is the regional director these days'}], 'It is the regional director these days.', 6)
    assert pm.find(model, 's3')[1]['who'] == 'regional director' and model['open'][0]['status'] == 'resolved'
    assert log['resolved'] == [model['open'][0]['id']]


def test_the_same_step_again_adds_details_and_raises_a_different_owner():
    model = ordering()
    model, log = run(model, [{'op': 'step', 'ref': 'n1', 'process': 'p1', 'after': 's2', 'kind': 'task', 'label': 'approve order',
                              'who': 'regional director', 'system': 'Workflow',
                              'quote': 'the regional director approves the order in Workflow'}],
                     'Then the regional director approves the order in Workflow.', 4)
    step = pm.find(model, 's3')[1]
    assert len(pm.process(model, 'p1')['steps']) == 3  # not a second approval step
    assert step['system'] == 'Workflow' and step['who'] == 'finance'  # a new detail is added; a different owner is a conflict
    assert log['conflicts']


def test_a_read_back_confirms_its_steps_and_the_planner_reads_back_after_three():
    model = ordering()
    [readback] = [g for g in pm.goals(model, limit=10) if g['key'].startswith('readback:')]
    assert readback['readback'] == ['s1', 's2', 's3']
    model = pm.asked(model, readback, 4)
    assert all(pm.find(model, i)[1]['read'] for i in ('s1', 's2', 's3'))
    assert not any(g['key'].startswith('readback:') for g in pm.goals(model, limit=10))
    model, log = run(model, [{'op': 'confirm', 'items': ['s1', 's2', 's3', 'p1', 'nope']}], 'Yes, that is right.', 5)
    assert log['confirmed'] == ['s1', 's2', 's3'] and {s['status'] for s in pm.process(model, 'p1')['steps']} == {'confirmed'}


def test_dont_know_is_not_asked_again_and_a_goal_is_asked_at_most_twice():
    model = ordering()
    # Systems are asked about once for the process, naming the steps still without one.
    assert any(g['key'] == 'systems:p1' and '"Approve order"' in g['ask'] for g in pm.goals(model, limit=20))
    model, _ = run(model, [{'op': 'unknown', 'item': 's3', 'field': 'system'}], "Honestly I'm not sure.", 4)
    assert not any(g['key'].startswith('systems:') for g in pm.goals(model, limit=20))
    trigger = next(g for g in pm.goals(model, limit=20) if g['key'] == 'trigger:p1')
    model = pm.asked(pm.asked(model, trigger, 5), trigger, 6)
    assert not any(g['key'] == 'trigger:p1' for g in pm.goals(model, limit=20))


def test_the_interview_starts_with_the_person_then_the_agenda_then_the_process():
    model = pm.new_model('beepee')
    assert [g['key'] for g in pm.goals(model)] == ['name', 'role', 'agenda']
    model = ordering()
    keys = [g['key'] for g in pm.goals(model, limit=20)]
    assert keys.index('team') < keys.index('purpose:p1') < keys.index('trigger:p1')
    assert 'next:s3' in keys and 'walk:p1' not in keys  # it has steps: what happens after the last one


def test_moving_on_and_wrapping_up():
    model = ordering()
    model, _ = run(model, [{'op': 'process', 'ref': 'n1', 'name': 'Customer returns', 'quote': 'customer returns'}],
                   'And customer returns, later.', 4)
    model, _ = run(model, [{'op': 'step', 'ref': 'n1', 'process': 'p1', 'after': 's3', 'kind': 'end', 'label': 'End',
                            'who': '', 'system': '', 'quote': "that's the end of it"}], "And that's the end of it.", 5)
    move = next(g for g in pm.goals(model, limit=30) if g['key'].startswith('move:'))
    model = pm.asked(model, move, 6)
    assert model['focus'] == 'p1' and model['proposed'] == 'p2'  # offered, not yet moved
    declined = pm.settle_move(model, agreed=False)
    assert declined['focus'] == 'p1' and pm.process(declined, 'p2')['status'] == 'later' and 'proposed' not in declined
    assert any(g['key'] == 'wrap' for g in pm.goals(declined, limit=30))
    model = pm.settle_move(model, agreed=True)
    assert model['focus'] == 'p2' and pm.process(model, 'p1')['status'] == 'done' and pm.process(model, 'p2')['status'] == 'active'
    assert pm.goals(model)[0]['key'] == 'walk:p2' or any(g['key'] == 'walk:p2' for g in pm.goals(model, limit=5))


def test_recap_and_the_welcome_back_come_from_the_model():
    model = ordering()
    # Told as the story of the work (PI F26): what the same person does runs on, a place said twice is said once.
    assert pm.recap(model) == ('Let me walk you through Ordering parts as I have it, and stop me at any point. The store '
                               'manager checks the stock report and raises the purchase order in SAP. Then finance approves '
                               'the order. What happens after that is still to be described.')
    assert pm.resume_line(model) == ('Welcome back, Sam. We were on Ordering parts, just after "Approve order". '
                                     'Shall we carry on from there?')
    assert 'no steps' not in pm.recap(pm.new_model('beepee')) and 'start' in pm.recap(pm.new_model('beepee'))


def test_steps_described_before_the_process_is_named_wait_for_a_name():
    model, _ = run(pm.new_model('beepee'), [{'op': 'step', 'ref': 'n1', 'process': '', 'after': 'start', 'kind': 'task',
                                           'label': 'Log the return', 'who': 'customer service', 'system': 'Zendesk',
                                           'quote': 'customer service logs the return in Zendesk'}],
                   'First customer service logs the return in Zendesk.', 1)
    assert [p['name'] for p in model['processes']] == [''] and any(g['key'] == 'pname:p1' for g in pm.goals(model, limit=10))
    model, _ = run(model, [{'op': 'process', 'ref': 'n1', 'name': 'Customer returns', 'quote': 'we call it customer returns'}],
                   'We call it customer returns.', 2)
    assert [p['name'] for p in model['processes']] == ['Customer returns'] and labels(model) == ['Log the return']


def test_the_view_for_the_note_taker_lists_ids_status_and_open_conflicts():
    model = ordering()
    model, _ = run(model, [{'op': 'conflict', 'item': 's3', 'field': 'who', 'now': 'regional director',
                            'quote': 'The regional director approves'}], 'The regional director approves.', 4)
    text = pm.view(model)
    assert 'participant: name: Sam Patel, role: operations manager' in text
    assert 's3 task "Approve order" who: finance with: - system: - [disputed]' in text
    assert 'o1 open conflict s3.who: "finance" vs "regional director"' in text


def test_keeping_the_first_account_settles_a_raised_conflict_without_a_change():
    model = ordering()
    model, _ = run(model, [{'op': 'conflict', 'item': 's2', 'field': 'who', 'now': 'buyer', 'quote': 'the buyer raises the orders'}],
                   'The buyer raises the orders.', 4)
    model = pm.asked(model, pm.goals(model)[0], 5)
    model, log = run(model, [{'op': 'change', 'item': 's2', 'field': 'who', 'value': 'store manager',
                              'quote': 'it is the store manager'}], 'Sorry, it is the store manager; the buyer only helps.', 6)
    step = pm.find(model, 's2')[1]
    assert step['who'] == 'store manager' and step['status'] == 'heard' and model['open'][0]['status'] == 'resolved'
    assert log['resolved'] == ['o1'] and not log['corrected']


def test_a_branch_listed_before_its_step_and_a_same_named_step_on_another_branch_both_hold():
    model = ordering()
    answer = ('If it is over five thousand pounds the regional director approves the order by email; otherwise finance '
              'approves the order in SAP.')
    model, log = run(model, [
        {'op': 'branch', 'decision': 'n1', 'condition': 'Over £5,000', 'to': 'n2', 'quote': 'If it is over five thousand pounds'},
        {'op': 'branch', 'decision': 'n1', 'condition': 'Otherwise', 'to': 'n3', 'quote': 'otherwise finance'},
        {'op': 'decision', 'ref': 'n1', 'process': 'p1', 'after': 's2', 'question': 'Is it over £5,000?',
         'quote': 'If it is over five thousand pounds'},
        {'op': 'step', 'ref': 'n2', 'process': 'p1', 'after': 'n1', 'kind': 'task', 'label': 'Approve order',
         'who': 'regional director', 'system': 'email', 'quote': 'the regional director approves the order by email'},
        {'op': 'step', 'ref': 'n3', 'process': 'p1', 'after': 'n1', 'kind': 'task', 'label': 'Approve order',
         'who': 'finance', 'system': 'SAP', 'quote': 'finance approves the order in SAP'},
    ], answer, 4)
    assert not log['dropped'] and not log['conflicts']
    decision = next(s for s in pm.process(model, 'p1')['steps'] if s['kind'] == 'decision')
    owners = sorted((n['label'], pm.find(model, n['to'])[1]['who']) for n in decision['next'] if n['label'])
    assert owners == [('Otherwise', 'finance'), ('Over £5,000', 'regional director')]


def test_a_read_back_says_exactly_what_was_captured_in_plain_sentences():
    model = ordering()
    answer = 'If it is over five thousand pounds the regional director approves it by email, otherwise finance approves it.'
    model, _ = run(model, [
        {'op': 'decision', 'ref': 'd', 'process': 'p1', 'after': 's2', 'question': 'Is it over £5,000?',
         'quote': 'If it is over five thousand pounds'},
        {'op': 'step', 'ref': 'a', 'process': 'p1', 'after': 'd', 'kind': 'task', 'label': 'Approve order', 'who': 'regional director',
         'system': 'email', 'quote': 'the regional director approves it by email'},
        {'op': 'branch', 'decision': 'd', 'condition': 'Over £5,000', 'to': 'a', 'quote': 'If it is over five thousand pounds'},
        {'op': 'branch', 'decision': 'd', 'condition': 'Otherwise', 'to': 's3', 'quote': 'otherwise finance approves it'},
    ], answer, 4)
    ids = [s['id'] for s in pm.ordered_steps(pm.process(model, 'p1'))]
    text = pm.readback_text(model, ids)
    assert text.startswith('Let me check I have this right. First the store manager checks the stock report and raises the '
                           'purchase order in SAP. Then there is a decision, is it over £5,000: Over £5,000, the regional '
                           'director approves the order by email; Otherwise, finance approves the order.')
    assert text.count('regional director') == 1 and text.endswith('Is that right?')  # branch steps are not repeated


def test_two_paths_that_continue_to_the_same_step_join_there_when_the_participant_says_so():
    model = ordering()
    answer = ('If it is over five thousand the regional director approves it. After approval the supplier confirms delivery. '
              'Once finance approves, the supplier confirms delivery too.')
    model, log = run(model, [
        {'op': 'decision', 'ref': 'd', 'process': 'p1', 'after': 's2', 'question': 'Is it over £5,000?',
         'quote': 'If it is over five thousand'},
        {'op': 'step', 'ref': 'a', 'process': 'p1', 'after': 'd', 'kind': 'task', 'label': 'Approve large order',
         'who': 'regional director', 'system': '', 'quote': 'the regional director approves it'},
        {'op': 'branch', 'decision': 'd', 'condition': 'Over £5,000', 'to': 'a', 'quote': 'If it is over five thousand'},
        {'op': 'step', 'ref': 'c1', 'process': 'p1', 'after': 'a', 'kind': 'task', 'label': 'Confirm delivery', 'who': 'supplier',
         'system': '', 'quote': 'After approval the supplier confirms delivery'},
        {'op': 'join', 'from': 's3', 'to': 'c1', 'quote': 'Once finance approves, the supplier confirms delivery too'},
    ], answer, 4)
    p = pm.process(model, 'p1')
    confirms = [s for s in p['steps'] if s['label'] == 'Confirm delivery']
    assert len(confirms) == 1 and not log['dropped']
    large = next(s for s in p['steps'] if s['label'] == 'Approve large order')
    for before in (pm.find(model, 's3')[1], large):  # both approvals continue to the one delivery step
        assert [n['to'] for n in before['next']] == [confirms[0]['id']]


def test_a_correction_about_the_process_never_changes_who_the_participant_is():
    model = ordering()
    model, log = run(model, [{'op': 'participant', 'field': 'role', 'value': 'buyer', 'quote': 'it is the store manager who raises them'}],
                     'Sorry, I misspoke: it is the store manager who raises them.', 4)
    assert model['participant']['role']['value'] == 'operations manager' and log['dropped'][0]['why'] == 'not about themselves'
    model, log = run(model, [{'op': 'participant', 'field': 'role', 'value': 'head of operations', 'quote': "I'm head of operations"}],
                     "Sorry, I'm head of operations now, not the operations manager.", 5)
    assert model['participant']['role']['value'] == 'head of operations'


def test_more_detail_is_taken_less_detail_changes_nothing_and_a_comment_on_a_step_corrects_it():
    model = ordering()
    model, log = run(model, [{'op': 'change', 'item': 's3', 'field': 'system', 'value': 'SAP', 'quote': 'in SAP'}],
                     'Finance approves it in SAP.', 4)
    model, log = run(model, [{'op': 'change', 'item': 's3', 'field': 'system', 'value': 'SAP approval queue',
                              'quote': 'the approval queue in SAP'}], 'Finance uses the approval queue in SAP.', 5)
    assert pm.find(model, 's3')[1]['system'] == 'SAP approval queue' and not log['conflicts']
    model, log = run(model, [{'op': 'change', 'item': 's3', 'field': 'system', 'value': 'SAP', 'quote': 'it is in SAP'}],
                     'Yes, it is in SAP.', 6)
    assert pm.find(model, 's3')[1]['system'] == 'SAP approval queue' and not log['conflicts']
    model, log = run(model, [{'op': 'change', 'item': 's3', 'field': 'who', 'value': 'head office',
                              'quote': 'Head office approves it'}], 'About the step "Approve order": Head office approves it.', 7)
    assert pm.find(model, 's3')[1]['who'] == 'head office' and log['corrected'][0]['was'] == 'finance'


def test_removing_or_moving_a_step_is_proposed_first_and_made_only_when_agreed():
    model = ordering()
    model, log = run(model, [{'op': 'remove', 'item': 's2', 'quote': 'take the purchase order step out'}],
                     'Please take the purchase order step out.', 4)
    assert labels(model) == ['Check stock report', 'Raise purchase order', 'Approve order']  # nothing changed yet
    [goal] = pm.goals(model, limit=1)
    assert goal['key'].startswith('change:') and goal['ask'] == 'So you would like me to remove "Raise purchase order". Shall I?'
    model, said = pm.edit(model, model['proposed_change']['ops'][0], 5)
    assert said == 'removed "Raise purchase order"' and labels(model) == ['Check stock report', 'Approve order']
    assert pm.find(model, 's1')[1]['next'] == [{'to': 's3', 'label': ''}]  # what led to it now leads on
    model, said = pm.edit(model, {'op': 'move', 'item': 's1', 'after': 's3'}, 6)
    assert labels(model) == ['Approve order', 'Check stock report'] and pm.process(model, 'p1')['start'] == 's3'
    assert said == 'moved "Check stock report" to after "Approve order"'


def test_a_misheard_word_is_corrected_everywhere_and_joins_the_interview_vocabulary():
    model = pm.new_model('beepee', 'BeePee')
    model, _ = run(model, [{'op': 'step', 'ref': 'n1', 'process': '', 'after': 'start', 'kind': 'task',
                            'label': 'Ask for product behind tail', 'who': 'customer', 'system': '', 'quote': 'asks behind the tail'},
                           {'op': 'step', 'ref': 'n2', 'process': '', 'after': 'n1', 'kind': 'task', 'label': 'Scan on tail',
                            'who': 'cashier', 'system': 'tail', 'quote': 'scans it on the tail'}],
                   'The customer asks behind the tail and the cashier scans it on the tail.', 1)
    model, log = run(model, [{'op': 'term', 'heard': 'tail', 'means': 'till', 'quote': "it's till, not tail"}],
                     "It's till, not tail. T-I-L-L.", 2)
    assert labels(model) == ['Ask for product behind till', 'Scan on till'] and pm.find(model, 's2')[1]['system'] == 'till'
    assert len(log['corrected']) == 3
    words = pm.vocabulary(model)
    assert words.startswith('BeePee') and 'till' in words and 'cashier' in words


def test_one_owner_for_the_process_fills_the_steps_and_rewording_is_not_a_conflict():
    model = pm.new_model('beepee', 'BeePee')
    model, _ = run(model, [{'op': 'step', 'ref': 'n1', 'process': '', 'after': 'start', 'kind': 'task', 'label': 'Check ID',
                            'who': '', 'system': '', 'quote': 'check the ID'}], 'Then you check the ID.', 1)
    assert pm.goals(model, limit=10)[0]['key'] != 'who:s1' and any(g['key'] == 'owners:p1' for g in pm.goals(model, limit=10))
    model, _ = run(model, [{'op': 'process_detail', 'process': 'p1', 'field': 'owner', 'value': 'cashier',
                            'quote': "it's the cashier throughout"}], "It's the cashier throughout.", 2)
    assert pm.find(model, 's1')[1]['who'] == 'cashier'
    model, log = run(model, [{'op': 'change', 'item': 's1', 'field': 'label', 'value': 'Check customer ID',
                              'quote': 'check the customer ID'}], 'They check the customer ID.', 3)
    assert not log['conflicts'] and not model['open'] and pm.find(model, 's1')[1]['label'] == 'Check ID'


def test_a_branch_added_on_the_map_splits_after_that_step_and_keeps_the_usual_path():
    model = ordering()
    model, said = pm.edit(model, {'op': 'branch', 'item': 's1', 'question': 'Is it an energy drink?',
                                  'condition': 'Energy drink', 'first': 'Check customer looks over 16'}, 4)
    decision = pm.find(model, 's1')[1]['next'][0]['to']
    links = pm.find(model, decision)[1]['next']
    assert [(n['label'], pm.find(model, n['to'])[1]['label']) for n in links] == [
        ('Energy drink', 'Check customer looks over 16'), ('Otherwise', 'Raise purchase order')]
    assert said == 'added a branch after "Check stock report": Energy drink, "Check customer looks over 16"'
    # The new branch's end: Tibi asks whether it joins back.
    assert any(g['key'].startswith('next:') and 'join back' in g['ask'] for g in pm.goals(model, limit=20))


def test_a_correction_lands_only_on_a_step_the_answer_is_about():
    model = ordering()
    answer = 'The approval is done in the Workflow tool, not in SAP.'
    model, log = run(model, [{'op': 'change', 'item': 's1', 'field': 'system', 'value': 'Workflow', 'quote': 'not in SAP'},
                             {'op': 'change', 'item': 's3', 'field': 'system', 'value': 'Workflow',
                              'quote': 'The approval is done in the Workflow tool'}], answer, 4)
    assert pm.find(model, 's1')[1]['system'] == 'SAP' and pm.find(model, 's3')[1]['system'] == 'Workflow'
    assert log['dropped'] == [{'op': 'change', 'why': 'the answer is not about that step'}]
    # A read-back names the steps: an answer to it may correct any of them.
    model, _ = run(model, [{'op': 'change', 'item': 's1', 'field': 'system', 'value': 'Excel', 'quote': 'the first one is Excel'}],
                   'No, the first one is Excel.', 5)
    assert pm.find(model, 's1')[1]['system'] == 'SAP'
    model, _ = pm.apply(model, [{'op': 'change', 'item': 's1', 'field': 'system', 'value': 'Excel', 'quote': 'the first one is Excel'}],
                        'No, the first one is Excel.', 6, question='So the store manager checks the stock report in SAP. Right?')
    assert pm.find(model, 's1')[1]['system'] == 'Excel'


def test_a_nearly_heard_name_is_written_as_the_interview_knows_it():
    model = pm.new_model('beepee', 'BeePee')
    assert pm.snap("I'm the manager at the BeePea high street shop.", model) == "I'm the manager at the BeePee high street shop."
    assert pm.snap('We keep bees and pea plants.', model) == 'We keep bees and pea plants.'  # ordinary words stay


def test_a_correction_that_names_its_step_lands_only_there_even_after_a_read_back_of_several():
    model = pm.new_model('beepee', 'BeePee')
    model, _ = run(model, [{'op': 'step', 'ref': 'a', 'process': '', 'after': 'start', 'kind': 'task', 'label': 'Check receipt on till',
                            'who': 'assistant', 'system': 'till', 'quote': 'checks the receipt on the till'},
                           {'op': 'step', 'ref': 'b', 'process': '', 'after': 'a', 'kind': 'task', 'label': 'Refund customer on till',
                            'who': 'assistant', 'system': 'till', 'quote': 'refunds the customer on the till'}],
                   'The assistant checks the receipt on the till and refunds the customer on the till.', 1)
    readback = 'Let me check I have this right. First the assistant checks receipt on till. Then the assistant refunds customer on till.'
    model, log = pm.apply(model, [{'op': 'change', 'item': 's1', 'field': 'system', 'value': 'card machine', 'quote': 'not on the till'},
                                  {'op': 'change', 'item': 's2', 'field': 'system', 'value': 'card machine',
                                   'quote': 'The refund is done on the card machine'}],
                          'The refund is done on the card machine, not on the till.', 2, question=readback)
    assert pm.find(model, 's1')[1]['system'] == 'till' and pm.find(model, 's2')[1]['system'] == 'card machine'
    assert pm.find(model, 's2')[1]['label'] == 'Refund customer on card machine'


RETURNS = ("A return starts when a customer brings an item back to the service desk. The sales assistant checks the receipt "
           "on the till. If the item is damaged, the assistant calls the duty manager. Otherwise the assistant refunds the "
           "customer. Then the item goes back onto the shelf.")


def returns():
    """The spoken replay's made-up process (PI F13): a decision, the refund on its "No" branch, the shelf after it."""
    model = pm.new_model('beepee', 'BeePee')
    model, _ = run(model, [{'op': 'process', 'ref': 'n1', 'name': 'Customer returns', 'quote': 'A return starts'}], RETURNS, 1)
    step = {'op': 'step', 'process': 'p1', 'kind': 'task', 'system': ''}
    model, _ = run(model, [
        {**step, 'ref': 'n1', 'after': 'start', 'label': 'Customer brings item to service desk', 'who': '',
         'quote': 'a customer brings an item back'},
        {**step, 'ref': 'n2', 'after': 'n1', 'label': 'Check receipt', 'who': 'sales assistant', 'system': 'till',
         'quote': 'checks the receipt on the till'},
        {'op': 'decision', 'ref': 'n3', 'process': 'p1', 'after': 'n2', 'question': 'Is the item damaged?',
         'quote': 'If the item is damaged'},
        {**step, 'ref': 'n4', 'after': 'n3', 'label': 'Call duty manager', 'who': 'sales assistant',
         'quote': 'calls the duty manager'},
        {'op': 'branch', 'decision': 'n3', 'condition': 'Yes', 'to': 'n4', 'quote': 'If the item is damaged'},
        {**step, 'ref': 'n5', 'after': 'n3', 'label': 'Refund customer', 'who': 'sales assistant',
         'quote': 'refunds the customer'},
        {'op': 'branch', 'decision': 'n3', 'condition': 'No', 'to': 'n5', 'quote': 'Otherwise'},
        {**step, 'ref': 'n6', 'after': 'n5', 'label': 'Put item back on shelf', 'who': '',
         'quote': 'the item goes back onto the shelf'},
    ], RETURNS, 2)
    return model


def by_label(model, label):
    return next(s for s in pm.process(model, 'p1')['steps'] if s['label'] == label)


def test_a_step_moved_before_one_on_a_branch_stays_on_that_branch_just_before_it():
    """PI F14: "the shelf before the refund" had been placed before the decision, so damaged items went back on the shelf."""
    model = returns()
    shelf, refund = by_label(model, 'Put item back on shelf'), by_label(model, 'Refund customer')
    decision = by_label(model, 'Is the item damaged?')
    answer = 'And the item goes back onto the shelf before the refund, not after it.'
    model, _ = run(model, [{'op': 'move', 'item': shelf['id'], 'before': refund['id'],
                            'quote': 'goes back onto the shelf before the refund'}], answer, 3)
    [goal] = pm.goals(model, limit=1)
    assert goal['ask'] == 'So you would like me to move "Put item back on shelf" to just before "Refund customer". Shall I?'
    model, said = pm.edit(model, model['proposed_change']['ops'][0], 4)
    assert said == 'moved "Put item back on shelf" to just before "Refund customer"'
    assert by_label(model, 'Is the item damaged?')['next'] == [
        {'to': by_label(model, 'Call duty manager')['id'], 'label': 'Yes'}, {'to': shelf['id'], 'label': 'No'}]
    assert by_label(model, 'Put item back on shelf')['next'] == [{'to': refund['id'], 'label': ''}]
    assert by_label(model, 'Refund customer')['next'] == [] and decision['id'] != shelf['id']
    # Before the very first step: it becomes the start.
    first = by_label(model, 'Customer brings item to service desk')
    model, _ = pm.edit(model, {'op': 'move', 'item': refund['id'], 'before': first['id']}, 5)
    assert pm.process(model, 'p1')['start'] == refund['id']


def test_a_move_before_a_missing_step_or_itself_is_dropped():
    model = returns()
    shelf = by_label(model, 'Put item back on shelf')
    answer = 'The shelf step comes before that.'
    for before in ('s99', shelf['id']):
        model, log = run(model, [{'op': 'move', 'item': shelf['id'], 'before': before, 'quote': 'The shelf step comes before'}],
                         answer, 3)
        assert log['dropped'] and not model.get('proposed_change')


def test_a_step_that_names_its_own_subject_is_read_back_as_it_is():
    """PI F14: "Customer brings item to service desk" was read back as "someone customers brings item…"."""
    model = returns()
    first = by_label(model, 'Customer brings item to service desk')
    assert pm.readback_sentences(model, [first['id']]) == 'First the customer brings item to service desk'
    say = lambda label, who='': pm._say({'label': label, 'who': who, 'system': ''})  # noqa: E731
    assert say('Order arrives at store') == 'the order arrives at store'
    assert say('Finance approves payment') == 'finance approves payment'
    assert say('Sam brings the float', 'Sam') == 'Sam brings the float'
    assert say('Process returns') == 'someone processes returns'  # starts with a verb: an instruction
    assert say('Records sales') == 'someone records sales'  # already said that way
    assert say('Put item back on shelf') == 'someone puts item back on shelf'


def test_a_correction_mistaken_for_a_misheard_word_lands_only_on_the_step_it_names():
    """PI F14: "The refund is done on the card machine, not on the till" came back from the note-taker as a misheard word,
    and every "till" became "card machine", the receipt check's too. A misheard word sounds like the right one."""
    model = returns()
    refund = by_label(model, 'Refund customer')
    model, _ = pm.edit(model, {'op': 'system', 'item': refund['id'], 'value': 'till'}, 3)
    answer = 'Sorry, one correction. The refund is done on the card machine, not on the till.'
    model, log = run(model, [{'op': 'term', 'heard': 'till', 'means': 'card machine', 'quote': 'not on the till'}], answer, 4)
    assert by_label(model, 'Refund customer')['system'] == 'card machine'
    assert by_label(model, 'Check receipt')['system'] == 'till' and not model.get('glossary')
    model, log = run(model, [{'op': 'term', 'heard': 'till', 'means': 'card machine', 'quote': 'not the till'}],
                     'It is the card machine, not the till.', 5)  # names no step: nothing to correct
    assert log['dropped'][0]['why'] == 'not a misheard word' and by_label(model, 'Check receipt')['system'] == 'till'
    assert pm.sounds_alike('tail', 'till') and pm.sounds_alike('Tabaku', 'tobacco') and not pm.sounds_alike('SAP', 'Excel')


# PI F19, after the Human's interview of 29 September at 21:44: three options, the second described later, both roles.
TILL = ("The customer comes to the till and asks for a product. There are three choices: tobacco, other age-restricted "
        "products, or anything without limits. For tobacco, the cashier checks the customer's ID.")


def till():
    model = pm.new_model('beepee', 'BeePee')
    model, _ = run(model, [{'op': 'process', 'ref': 'n1', 'name': 'Carrying out cashiering', 'quote': 'The customer comes'}],
                   TILL, 1)
    model, log = run(model, [
        {'op': 'process_detail', 'process': 'p1', 'field': 'trigger', 'value': 'Customer comes to the till and asks for a product',
         'quote': 'The customer comes to the till and asks for a product'},
        {'op': 'decision', 'ref': 'n1', 'process': 'p1', 'after': 'start', 'question': 'What kind of product is asked for?',
         'quote': 'There are three choices'},
        {'op': 'step', 'ref': 'n2', 'process': 'p1', 'after': 'n1', 'kind': 'task', 'label': 'Check customer ID',
         'who': 'cashier', 'with': 'customer', 'system': '', 'quote': "the cashier checks the customer's ID"},
        {'op': 'branch', 'decision': 'n1', 'condition': 'Tobacco', 'to': 'n2', 'quote': 'For tobacco'},
        {'op': 'branch', 'decision': 'n1', 'condition': 'Other age-restricted product', 'to': 'open',
         'quote': 'other age-restricted products'},
        {'op': 'branch', 'decision': 'n1', 'condition': 'No age limit', 'to': 'open', 'quote': 'anything without limits'},
        {'op': 'step', 'ref': 'n3', 'process': 'p1', 'after': 'n2', 'kind': 'task', 'label': 'Scan product', 'who': 'cashier',
         'with': '', 'system': 'till', 'quote': "the cashier checks the customer's ID"},
    ], TILL, 2)
    assert not log['dropped'], log['dropped']
    return model


def labelled(model, label):
    return [s for s in pm.process(model, 'p1')['steps'] if s['label'] == label]


def test_options_named_before_they_are_described_each_get_a_path_of_their_own():
    model = till()
    [decision] = [s for s in pm.process(model, 'p1')['steps'] if s['kind'] == 'decision']
    paths = {n['label']: pm.find(model, n['to'])[1] for n in decision['next']}
    assert list(paths) == ['Tobacco', 'Other age-restricted product', 'No age limit']
    assert paths['Tobacco']['label'] == 'Check customer ID' and paths['Tobacco']['with'] == 'customer'
    assert paths['No age limit']['kind'] == 'open' and paths['Other age-restricted product']['kind'] == 'open'
    # Described later: its first step takes the open path's place; the same action on this path is a step of its own.
    open_id = paths['No age limit']['id']
    answer = 'For no age limit, the cashier just scans it on the till and the till adds it to the basket.'
    model, log = run(model, [
        {'op': 'step', 'ref': 'n1', 'process': 'p1', 'after': open_id, 'kind': 'task', 'label': 'Scan product', 'who': 'cashier',
         'with': '', 'system': 'till', 'quote': 'the cashier just scans it on the till'},
        {'op': 'step', 'ref': 'n2', 'process': 'p1', 'after': 'n1', 'kind': 'task', 'label': 'Add product to basket', 'who': 'till',
         'with': '', 'system': 'till', 'quote': 'the till adds it to the basket'}], answer, 3)
    assert len(labelled(model, 'Scan product')) == 2  # one on each path, not joined (the 29 September fault)
    [decision] = [s for s in pm.process(model, 'p1')['steps'] if s['kind'] == 'decision']
    third = pm.find(model, next(n['to'] for n in decision['next'] if n['label'] == 'No age limit'))[1]
    assert third['label'] == 'Scan product' and pm.find(model, open_id)[1] is None
    assert [n['to'] for n in third['next']] == [labelled(model, 'Add product to basket')[0]['id']]


def test_paths_meet_only_where_the_participant_says_so():
    model = till()
    [scan] = labelled(model, 'Scan product')
    [decision] = [s for s in pm.process(model, 'p1')['steps'] if s['kind'] == 'decision']
    open_id = next(n['to'] for n in decision['next'] if n['label'] == 'Other age-restricted product')
    answer = 'For other age-restricted products the cashier checks they look over 25, and from there it is the same, they scan it.'
    model, log = run(model, [
        {'op': 'step', 'ref': 'n1', 'process': 'p1', 'after': open_id, 'kind': 'task', 'label': 'Check customer looks over 25',
         'who': 'cashier', 'with': 'customer', 'system': '', 'quote': 'the cashier checks they look over 25'},
        {'op': 'join', 'from': 'n1', 'to': scan['id'], 'quote': 'from there it is the same'}], answer, 3)
    [look] = labelled(model, 'Check customer looks over 25')
    assert [n['to'] for n in look['next']] == [scan['id']] and len(labelled(model, 'Scan product')) == 1


def test_whether_one_or_several_paths_apply_is_asked_and_recorded():
    model = till()
    [decision] = [s for s in pm.process(model, 'p1')['steps'] if s['kind'] == 'decision']
    goal = next(g for g in pm.goals(model, limit=12) if g['key'] == f'kind:{decision["id"]}')
    assert '"Tobacco", "Other age-restricted product", "No age limit"' in goal['ask'] and 'only ever one' in goal['ask']
    model, _ = run(model, [{'op': 'gateway', 'decision': decision['id'], 'kind': 'or', 'quote': 'They could ask for several'}],
                   'They could ask for several at once.', 3)
    assert pm.find(model, decision['id'])[1]['gateway'] == 'or'
    assert not any(g['key'].startswith('kind:') for g in pm.goals(model, limit=12))
    model, said = pm.edit(model, {'op': 'gateway', 'item': decision['id'], 'value': 'xor'}, 4)
    assert pm.find(model, decision['id'])[1]['gateway'] == 'xor' and 'only one path' in said


def test_steps_on_the_wrong_path_are_moved_to_the_right_one_when_agreed():
    model = till()
    [scan] = labelled(model, 'Scan product')
    [decision] = [s for s in pm.process(model, 'p1')['steps'] if s['kind'] == 'decision']
    open_id = next(n['to'] for n in decision['next'] if n['label'] == 'No age limit')
    answer = 'No, the scan belongs under the no age limit option.'
    model, _ = run(model, [{'op': 'repath', 'items': [scan['id']], 'path': open_id, 'condition': 'No age limit',
                            'quote': 'the scan belongs under the no age limit option'}], answer, 3)
    [goal] = pm.goals(model, limit=1)
    assert goal['ask'] == 'So you would like me to move "Scan product" to the path "No age limit". Shall I?'
    model, said = pm.edit(model, model['proposed_change']['ops'][0], 4)
    [decision] = [s for s in pm.process(model, 'p1')['steps'] if s['kind'] == 'decision']
    assert pm.find(model, next(n['to'] for n in decision['next'] if n['label'] == 'No age limit'))[1]['label'] == 'Scan product'
    assert pm.find(model, labelled(model, 'Check customer ID')[0]['id'])[1]['next'] == []
    assert said == 'moved "Scan product" to the path "No age limit"'


def test_the_process_is_read_back_path_by_path_or_one_path_on_request():
    model = till()
    whole = pm.path_readback(model)
    assert whole.startswith('Let me walk you through Carrying out cashiering as I have it, and stop me at any point. It '
                            'starts when a customer comes to the till')
    assert ('What happens next depends on what kind of product is asked for, and there are three ways it can go. On the '
            'map, they are the three columns under that question.') in whole
    assert ('First: tobacco. The cashier checks the customer ID and scans the product on the till. That is the left-hand '
            'column.') in whole
    assert 'Third: no age limit. It is not described yet. That is the right-hand column.' in whole
    assert whole.endswith('Is that right?')
    second = pm.path_readback(model, 2)
    assert second == 'Second: other age-restricted product. It is not described yet. Is that right?'
    assert 'no option 5' in pm.path_readback(model, 5)


def test_a_role_is_never_the_process_s_own_name_and_the_trigger_is_not_taken_from_one_path():
    model = till()
    answer = 'Cashiering checks the receipt. For no limits the customer requests the product.'
    model, _ = run(model, [
        {'op': 'step', 'ref': 'n1', 'process': 'p1', 'after': labelled(model, 'Scan product')[0]['id'], 'kind': 'task',
         'label': 'Check receipt', 'who': 'Cashiering', 'with': '', 'system': '', 'quote': 'Cashiering checks the receipt'},
        {'op': 'process_detail', 'process': 'p1', 'field': 'trigger', 'value': 'Customer requests a product with no limits',
         'quote': 'the customer requests the product'}], answer, 3)
    assert labelled(model, 'Check receipt')[0]['who'] == ''
    assert pm.process(model, 'p1')['details']['trigger']['value'] == 'Customer comes to the till and asks for a product'


def _paths(p):
    """Each path of a process's first decision, as its labels in order."""
    by_id = {s['id']: s for s in p['steps']}
    decision = by_id[p['start']]
    paths = {}
    for link in decision['next']:
        labels, step, seen = [], by_id.get(link['to']), set()
        while step is not None and step['id'] not in seen:
            seen.add(step['id'])
            labels.append(step['label'])
            step = by_id.get(step['next'][0]['to']) if step['next'] else None
        paths[link['label']] = labels
    return decision, paths


def test_three_paths_described_in_one_answer_each_start_at_their_first_step():
    """PI F21: the note-taker's own changes for the Human's description of 1 October. It named each path by its LAST
    step, left two options open before describing them, and put the first option's first step beside the decision: the
    map looped from the basket back to the start, and two paths hung on nothing."""
    import json
    from pathlib import Path
    recorded = json.loads((Path(__file__).resolve().parents[1] / 'evaluation/sets/tibi/notes-2026-10-01-cashiering.json').read_text())
    model, log = pm.apply(recorded['model'], recorded['changes'], recorded['answer'], 4, recorded['question'])
    p = model['processes'][0]
    decision, paths = _paths(p)
    assert decision['kind'] == 'decision' and log['dropped'] == []
    assert paths == {
        'E-cigarette or Tobacco product': ['Request ID from customer', 'Ask customer for specific tobacco product type',
                                           'Locate product in dedicated drawer', 'Scan product on point of sale',
                                           'Confirm age verification on point of sale', 'Add product to basket'],
        'Age restricted non-Tobacco product': ['Locate product', 'Scan product on point of sale',
                                               'Carry out age verification check on point of sale',
                                               'Close verification prompt on point of sale', 'Add product to basket'],
        'Product not requiring age verification': ['Locate product', 'Scan product on point of sale',
                                                   'Review ticket on point of sale', 'Add product to basket']}
    assert not any(s['kind'] == 'open' for s in p['steps'])
    assert len({s['id'] for s in p['steps']}) == 1 + 6 + 5 + 4  # every step on exactly one path, none left over


def test_a_path_named_by_its_last_step_or_twice_is_named_once_by_its_first():
    answer = 'If it is tobacco I check the ID and then I scan it. If it is an energy drink I scan it and check the ID.'
    changes = [
        {'op': 'decision', 'ref': 'n1', 'after': 'start', 'question': 'What is it?', 'quote': 'If it is tobacco'},
        {'op': 'step', 'ref': 'n2', 'after': 'n1', 'kind': 'task', 'label': 'Check ID', 'who': 'cashier', 'quote': 'I check the ID'},
        {'op': 'step', 'ref': 'n3', 'after': 'n2', 'kind': 'task', 'label': 'Scan product', 'who': 'cashier', 'quote': 'then I scan it'},
        {'op': 'branch', 'decision': 'n1', 'condition': 'Tobacco', 'to': 'n2', 'quote': 'If it is tobacco'},
        {'op': 'branch', 'decision': 'n1', 'condition': 'Tobacco product', 'to': 'n3', 'quote': 'If it is tobacco'},
        {'op': 'step', 'ref': 'n4', 'after': 'n1', 'kind': 'task', 'label': 'Scan drink', 'who': 'cashier', 'quote': 'I scan it and'},
        {'op': 'step', 'ref': 'n5', 'after': 'n4', 'kind': 'task', 'label': 'Check ID', 'who': 'cashier', 'quote': 'check the ID'},
        {'op': 'branch', 'decision': 'n1', 'condition': 'Energy drink', 'to': 'n5', 'quote': 'If it is an energy drink'}]
    model, _ = pm.apply(pm.new_model('b', 'B'), [{'op': 'process', 'ref': 'p', 'name': 'Selling', 'quote': 'it'}, *changes], answer, 1)
    _, paths = _paths(model['processes'][0])
    assert paths == {'Tobacco': ['Check ID', 'Scan product'], 'Energy drink': ['Scan drink', 'Check ID']}


def test_open_options_take_the_paths_described_after_them_in_order():
    answer = 'There are two choices, card or cash. For card they tap. For cash I count the change.'
    changes = [
        {'op': 'decision', 'ref': 'n1', 'after': 'start', 'question': 'How do they pay?', 'quote': 'two choices'},
        {'op': 'branch', 'decision': 'n1', 'condition': 'Card', 'to': 'open', 'quote': 'card or cash'},
        {'op': 'branch', 'decision': 'n1', 'condition': 'Cash', 'to': 'open', 'quote': 'card or cash'},
        {'op': 'step', 'ref': 'n2', 'after': 'n1', 'kind': 'task', 'label': 'Tap card', 'who': 'customer', 'quote': 'For card they tap'},
        {'op': 'step', 'ref': 'n3', 'after': 'n1', 'kind': 'task', 'label': 'Count change', 'who': 'cashier',
         'quote': 'I count the change'}]
    model, _ = pm.apply(pm.new_model('b', 'B'), [{'op': 'process', 'ref': 'p', 'name': 'Paying', 'quote': 'card'}, *changes], answer, 1)
    p = model['processes'][0]
    assert _paths(p)[1] == {'Card': ['Tap card'], 'Cash': ['Count change']} and not any(s['kind'] == 'open' for s in p['steps'])


def test_a_branch_to_a_step_from_an_earlier_answer_is_left_as_it_is():
    before = [{'op': 'branch', 'decision': 's9', 'condition': 'x', 'to': 's3', 'quote': 'q'}]
    assert pm._paths_from_heads(before) == before


def test_a_step_added_on_the_map_goes_after_the_chosen_step_or_takes_an_open_path():
    """PI F21: "I cannot really add anything where I want" (1 October)."""
    model, said = pm.edit(till(), {'op': 'add', 'item': 's2', 'value': 'Ask which brand', 'who': 'cashier'}, 5)
    p = model['processes'][0]
    by_label = {s['label']: s for s in p['steps']}
    assert said == 'added "Ask which brand" after "Check customer ID"'
    assert [n['to'] for n in by_label['Check customer ID']['next']] == [by_label['Ask which brand']['id']]
    assert [n['to'] for n in by_label['Ask which brand']['next']] == [by_label['Scan product']['id']]
    assert by_label['Ask which brand']['status'] == 'confirmed' and by_label['Ask which brand']['who']
    model, said = pm.edit(till(), {'op': 'add', 'item': 's4', 'value': 'Check they look over 16', 'who': ''}, 5)
    p = model['processes'][0]
    assert said == 'added "Check they look over 16" on the path "Other age-restricted product"'
    decision = next(s for s in p['steps'] if s['kind'] == 'decision')
    first = next(s for s in p['steps'] if s['label'] == 'Check they look over 16')
    assert {'to': first['id'], 'label': 'Other age-restricted product'} in decision['next']
    assert not any(s['id'] == 's4' for s in p['steps'])
    try:
        pm.edit(till(), {'op': 'add', 'item': 's1', 'value': 'Something'}, 5)
        raise AssertionError('a step after a decision is a path')
    except ValueError:
        pass


# ---- PI F23: triggers, a step made a trigger, and paths that meet (the Human's interview of 1 October, 16:08) ----------

def described_till():
    """The till with all three paths described, each ending on its own: as the Human's map stood at 16:17."""
    model = till()
    [decision] = [s for s in pm.process(model, 'p1')['steps'] if s['kind'] == 'decision']
    opened = {n['label']: n['to'] for n in decision['next']}
    answer = ('For other age-restricted products the cashier checks they look over 25 and scans it. For no age limit '
              'the cashier scans it and the till adds it to the basket.')
    model, log = run(model, [
        {'op': 'step', 'ref': 'n1', 'process': 'p1', 'after': opened['Other age-restricted product'], 'kind': 'task',
         'label': 'Check customer looks over 25', 'who': 'cashier', 'with': 'customer', 'system': '',
         'quote': 'the cashier checks they look over 25'},
        {'op': 'step', 'ref': 'n2', 'process': 'p1', 'after': 'n1', 'kind': 'task', 'label': 'Scan product',
         'who': 'cashier', 'with': '', 'system': 'till', 'quote': 'and scans it'},
        {'op': 'step', 'ref': 'n3', 'process': 'p1', 'after': opened['No age limit'], 'kind': 'task', 'label': 'Scan product',
         'who': 'cashier', 'with': '', 'system': 'till', 'quote': 'the cashier scans it'},
        {'op': 'step', 'ref': 'n4', 'process': 'p1', 'after': 'n3', 'kind': 'task', 'label': 'Add product to basket',
         'who': 'till', 'with': '', 'system': 'till', 'quote': 'the till adds it to the basket'}], answer, 3)
    assert not log['dropped'], log['dropped']
    return model


def ends(model):
    return [s['label'] for s in pm._open_ends(pm.process(model, 'p1'))]


def test_a_trigger_is_added_after_a_step_and_is_said_as_a_trigger():
    """"Can we add a check verification trigger under the second path, after scan product on point of sale?" was noted
    as a decision, "Is there a check verification trigger needed?" (1 October, 16:13)."""
    before = till()
    [scan] = labelled(before, 'Scan product')
    answer = 'Can we add an age verification trigger after the scan product step?'
    model, log = run(before, [{'op': 'step', 'ref': 'n1', 'process': 'p1', 'after': scan['id'], 'kind': 'event',
                               'label': 'Age verification required', 'who': 'cashier', 'with': 'customer', 'system': 'till',
                               'quote': 'add an age verification trigger'}], answer, 3)
    [trigger] = labelled(model, 'Age verification required')
    assert trigger['kind'] == 'event' and (trigger['who'], trigger['with'], trigger['system']) == ('', '', '')
    assert [n['to'] for n in pm.find(model, scan['id'])[1]['next']] == [trigger['id']]
    assert pm.what_changed(before, model) == ['added the trigger "Age verification required" after "Scan product"']
    assert 'scans the product on the till. Then comes a trigger: age verification required.' in pm.path_readback(model)
    assert '(a trigger)' in pm.view(model)
    keys = [g['key'] for g in pm.goals(model, limit=20)]
    assert f'next:{trigger["id"]}' in keys  # what follows a trigger is asked, as after a step
    owners = next((g['ask'] for g in pm.goals(model, limit=20) if g['key'].startswith('owners:')), '')
    assert 'Age verification required' not in owners  # nobody "does" a trigger


def test_a_step_is_made_a_trigger_when_asked_never_renamed_and_back_on_the_map():
    """"Could you change carry out verification check into a trigger rather than step" renamed it "Trigger age
    verification check" (1 October, 16:15)."""
    before = till()
    [check] = labelled(before, 'Check customer ID')
    answer = 'Could you change check customer ID into a trigger rather than a step?'
    model, log = run(before, [{'op': 'change', 'item': check['id'], 'field': 'kind', 'value': 'event',
                               'quote': 'change check customer ID into a trigger'}], answer, 3)
    [check] = labelled(model, 'Check customer ID')
    assert check['kind'] == 'event' and log['applied'] == [f"{check['id']}.kind"]
    assert pm.what_changed(before, model) == ['made "Check customer ID" a trigger']
    model, said = pm.edit(model, {'op': 'kind', 'item': check['id'], 'value': 'task'}, 4)
    assert said == 'made "Check customer ID" a step' and pm.find(model, check['id'])[1]['kind'] == 'task'
    model, said = pm.edit(model, {'op': 'kind', 'item': check['id'], 'value': 'event'}, 5)
    assert said == 'made "Check customer ID" a trigger'
    with pytest.raises(ValueError):
        pm.edit(model, {'op': 'kind', 'item': 's1', 'value': 'event'}, 5)  # a decision is neither
    # A trigger is added on the map as a step is.
    model, said = pm.edit(till(), {'op': 'add', 'item': 's2', 'value': 'ID checked', 'kind': 'event', 'who': 'cashier'}, 5)
    [added] = labelled(model, 'ID checked')
    assert said == 'added the trigger "ID checked" after "Check customer ID"' and added['kind'] == 'event' and not added['who']


def test_paths_that_meet_carry_on_together_and_tibi_asks_what_follows():
    """"Yeah, it joins with the rest of the process and then there is another step after this" was asked again (1 October,
    16:17): each path ended on its own, and the map's "Still being described" could not be continued."""
    model = described_till()
    assert ends(model) == ['Scan product', 'Scan product', 'Add product to basket']
    keys = [g['key'] for g in pm.goals(model, limit=20)]
    assert 'meet:p1' in keys and keys.index('meet:p1') < min(i for i, k in enumerate(keys) if k.startswith('next:'))
    answer = 'Yeah, it joins with the rest of the process and then there is another step after this.'
    joined, log = run(model, [{'op': 'join', 'from': 'paths', 'to': 'next', 'quote': 'it joins with the rest of the process'}],
                      answer, 4)
    p = pm.process(joined, 'p1')
    meet = pm._meeting_point(p)
    assert meet is not None and ends(joined) == [] and len(log['applied']) == 3
    assert pm.what_changed(model, joined) == ['joined the paths where they meet']
    assert f'after:{meet["id"]}' in [g['key'] for g in pm.goals(joined, limit=20)]
    assert '(where the paths meet; what follows is not described yet)' in pm.view(joined)
    assert pm.path_readback(joined).endswith('The routes then come back together further down the map, and what happens '
                                             'after that is still to be described. Is that right?')
    # What follows takes the meeting point's place, after every path, and is read back once.
    answer = 'After that the cashier takes payment on the till.'
    paid, _ = run(joined, [{'op': 'step', 'ref': 'n1', 'process': 'p1', 'after': meet['id'], 'kind': 'task',
                            'label': 'Take payment', 'who': 'cashier', 'with': '', 'system': 'till',
                            'quote': 'the cashier takes payment'}], answer, 5)
    [pay] = labelled(paid, 'Take payment')
    into = [s for s in pm.process(paid, 'p1')['steps'] if any(n['to'] == pay['id'] for n in s['next'])]
    assert len(into) == 3 and pm._meeting_point(pm.process(paid, 'p1')) is None
    readback = pm.path_readback(paid)
    assert readback.count('takes the payment') == 1
    assert 'come back together further down the map, and after that the cashier takes the payment on the till.' in readback
    assert pm.what_changed(joined, paid) == ['added "Take payment" where the paths meet']


def test_a_step_said_to_follow_where_the_paths_meet_goes_after_every_path():
    model = described_till()
    answer = 'They all come back together and the cashier takes payment.'
    model, _ = run(model, [{'op': 'step', 'ref': 'n1', 'process': 'p1', 'after': 'paths', 'kind': 'task', 'label': 'Take payment',
                            'who': 'cashier', 'with': '', 'system': 'till', 'quote': 'the cashier takes payment'}], answer, 4)
    [pay] = labelled(model, 'Take payment')
    assert ends(model) == ['Take payment']
    assert len([s for s in pm.process(model, 'p1')['steps'] if any(n['to'] == pay['id'] for n in s['next'])]) == 3


def test_the_flow_is_continued_on_the_map_where_it_is_still_being_described():
    """"How can we move the Still being described box under the entire process map? I wanted to continue" (1 October)."""
    model, said = pm.edit(described_till(), {'op': 'continue', 'item': 'p1', 'value': 'Take payment', 'who': 'cashier'}, 6)
    assert said == 'added "Take payment" where the paths meet' and ends(model) == ['Take payment']
    model, said = pm.edit(model, {'op': 'continue', 'item': 'p1', 'value': 'Receipt printed', 'kind': 'event'}, 7)
    assert said == 'added the trigger "Receipt printed" after "Take payment"' and ends(model) == ['Receipt printed']
    # A meeting point already noted is taken over.
    joined, _ = run(described_till(), [{'op': 'join', 'from': 'paths', 'to': 'next', 'quote': 'they meet'}], 'They meet.', 4)
    model, said = pm.edit(joined, {'op': 'continue', 'item': 'p1', 'value': 'Take payment'}, 6)
    assert said == 'added "Take payment" where the paths meet' and pm._meeting_point(pm.process(model, 'p1')) is None
    with pytest.raises(ValueError):
        pm.edit(described_till(), {'op': 'continue', 'item': 'p1', 'value': ''}, 6)


def test_steps_moved_to_a_path_that_meets_the_others_stay_before_the_meeting_point():
    model, _ = pm.edit(described_till(), {'op': 'continue', 'item': 'p1', 'value': 'Take payment', 'who': 'cashier'}, 6)
    p = pm.process(model, 'p1')
    stray = next(s for s in p['steps'] if s['label'] == 'Add product to basket')
    decision = next(s for s in p['steps'] if s['kind'] == 'decision')
    model, said = pm.edit(model, {'op': 'repath', 'item': stray['id'], 'items': [stray['id']], 'path': decision['id'],
                                  'condition': 'Tobacco'}, 7)
    p = pm.process(model, 'p1')
    by_id = {s['id']: s for s in p['steps']}
    tobacco = pm._chain(by_id, next(n['to'] for n in decision['next'] if n['label'] == 'Tobacco'), None, pm.meets(p))
    assert [s['label'] for s in tobacco] == ['Check customer ID', 'Scan product', 'Add product to basket']
    assert by_id[tobacco[-1]['next'][0]['to']]['label'] == 'Take payment'


def test_a_long_quote_missing_a_word_still_counts_and_a_stitched_one_does_not():
    """1 October, 16:13: the note-taker quoted "…after scan product on point sale step" for "…on point of sale step", and the
    trigger asked for was dropped as not said."""
    answer = ('Okay, this is good. However, can we add a check verification trigger under the second path, which is '
              'age-restricted non-tabaco product, after scan product on point of sale step?')
    assert pm.quoted('add a check verification trigger under the second path, which is age-restricted non-tabaco product, '
                     'after scan product on point sale step', answer)
    assert not pm.quoted('add a check on point sale', answer)  # short quotes stay exact
    assert not pm.quoted('this is good add a check verification trigger after scan product on point of sale step', answer)


def test_each_path_said_to_join_the_rest_of_the_process_meets_at_one_point():
    """The note-taker's own wording of 16:17, "join from each path's last step to paths", is taken as the paths meeting."""
    model = described_till()
    tails = [s['id'] for s in pm._open_ends(pm.process(model, 'p1'))]
    answer = 'Yeah, it joins with the rest of the process and then there is another step after this'
    model, log = run(model, [{'op': 'join', 'from': t, 'to': 'paths', 'quote': 'it joins with the rest of the process'}
                             for t in tails], answer, 4)
    p = pm.process(model, 'p1')
    meet = pm._meeting_point(p)
    assert meet is not None and not log['dropped'] and ends(model) == []
    assert len([s for s in p['steps'] if any(n['to'] == meet['id'] for n in s['next'])]) == 3


# ---- PI F25: steps where the paths merge, paths named by their trigger, and nothing the participant did not ask for --
# (the Human's interview of 1 October, 21:35, on engine 1.8.3)

def reviewed_till():
    """The till as the Human's map stood at 21:44: a review and a quantity-limit question added after the first path
    only, with a branch of their own."""
    model = described_till()
    [first_end] = [s for s in pm._open_ends(pm.process(model, 'p1')) if s['label'] == 'Scan product'][:1]
    answer = ('And then there is a new step called review. If the product has a quantity limit, that is checked by a '
              'cashier on the point of sale.')
    model, log = run(model, [
        {'op': 'step', 'ref': 'n1', 'process': 'p1', 'after': first_end['id'], 'kind': 'task', 'label': 'Review product',
         'who': 'cashier', 'with': '', 'system': '', 'quote': 'a new step called review'},
        {'op': 'decision', 'ref': 'n2', 'process': 'p1', 'after': 'n1', 'question': 'Does the product have a quantity limit?',
         'quote': 'If the product has a quantity limit'},
        {'op': 'step', 'ref': 'n3', 'process': 'p1', 'after': 'n2', 'kind': 'task', 'label': 'Check quantity limit',
         'who': 'cashier', 'with': '', 'system': 'point of sale', 'quote': 'that is checked by a cashier on the point of sale'},
        {'op': 'branch', 'decision': 'n2', 'condition': 'Has quantity limit', 'to': 'n3', 'quote': 'If the product has a quantity limit'},
    ], answer, 5)
    assert not log['dropped'], log['dropped']
    return model


def test_a_step_and_what_follows_it_move_below_where_the_paths_meet():
    """"I want this step review product to be moved below all three paths" was moved after one path, three times (21:44)."""
    model = reviewed_till()
    answer = 'I want this step review product to be moved below all three paths'
    asked, log = run(model, [{'op': 'move', 'item': labelled(model, 'Review product')[0]['id'], 'after': 'paths',
                              'quote': 'moved below all three paths'}], answer, 6)
    [goal] = pm.goals(asked, limit=1)
    assert goal['ask'] == ('So you would like me to move "Review product", and what follows it, to where the paths meet. '
                           'Shall I?')
    model, said = pm.edit(asked, asked['proposed_change']['ops'][0], 7)
    assert said == 'moved "Review product", and what follows it, to where the paths meet'
    p = pm.process(model, 'p1')
    [review] = labelled(model, 'Review product')
    into = sorted(s['label'] for s in p['steps'] if any(n['to'] == review['id'] for n in s['next']))
    assert into == ['Add product to basket', 'Scan product', 'Scan product']  # every path, once
    assert [s['label'] for s in pm._open_ends(p)] == ['Check quantity limit']  # its own branch never loops back
    readback = pm.path_readback(model)
    assert readback.count('reviews the product') == 1
    assert 'come back together further down the map, and after that the cashier reviews the product' in readback


def test_paths_merged_into_a_step_already_described_never_loop_back_from_its_branches():
    """"We need to merge all those different options into single step" (21:46)."""
    model = reviewed_till()
    [review] = labelled(model, 'Review product')
    answer = 'So we need to merge all those different options into single step, the review.'
    model, log = run(model, [{'op': 'join', 'from': 'paths', 'to': review['id'], 'quote': 'merge all those different options'}],
                     answer, 6)
    p = pm.process(model, 'p1')
    assert len([s for s in p['steps'] if any(n['to'] == review['id'] for n in s['next'])]) == 3
    assert [s['label'] for s in pm._open_ends(p)] == ['Check quantity limit']
    assert not any(n['to'] == review['id'] for n in labelled(model, 'Check quantity limit')[0]['next'])


def test_a_step_or_trigger_put_before_another_stays_on_that_path():
    """"Add additional step before locate product on the third path" (21:39) became a step called "Add additional step"."""
    model = described_till()
    [decision] = [s for s in pm.process(model, 'p1')['steps'] if s['kind'] == 'decision']
    third = pm.find(model, decision['next'][2]['to'])[1]
    answer = 'It is a trigger step which needs to go before scan product on the third path: the product is requested.'
    model, log = run(model, [{'op': 'step', 'ref': 'n1', 'process': 'p1', 'before': third['id'], 'kind': 'event',
                              'label': 'Product requested', 'who': '', 'with': '', 'system': '',
                              'quote': 'the product is requested'}], answer, 4)
    [added] = labelled(model, 'Product requested')
    [decision] = [s for s in pm.process(model, 'p1')['steps'] if s['kind'] == 'decision']
    assert decision['next'][2] == {'to': added['id'], 'label': 'No age limit'} and added['next'] == [{'to': third['id'], 'label': ''}]
    junk, log = run(model, [{'op': 'step', 'ref': 'n1', 'process': 'p1', 'after': third['id'], 'kind': 'task',
                             'label': 'Add additional step', 'who': '', 'with': '', 'system': '',
                             'quote': 'add additional step'}], 'Now I want to add additional step before locate product.', 5)
    assert log['dropped'] == [{'op': 'step', 'why': 'no label'}] and not labelled(junk, 'Add additional step')


def test_a_trigger_at_the_start_of_a_path_names_the_path():
    """"The third path actually starts with the trigger when the customer asks for an age restricted product, but it's
    non-tobacco" (21:38): Tibi asked where the path splits off, then proposed moving its first step to the start."""
    model = described_till()
    [decision] = [s for s in pm.process(model, 'p1')['steps'] if s['kind'] == 'decision']
    decision['next'][2]['label'] = ''  # as Tibi had it that night: "otherwise"
    first = decision['next'][2]['to']
    answer = ("Almost. The third path actually starts with the trigger when the customer asks for age restricted product but "
              "it's non-tobacco.")
    named, log = run(model, [{'op': 'branch', 'decision': decision['id'], 'condition': 'Age restricted non-tobacco product',
                              'to': first, 'quote': 'customer asks for age restricted product'}], answer, 4)
    assert pm.what_changed(model, named) == ['named the path "Age restricted non-tobacco product"']
    model['processes'][0]['steps'][0]['next'][2]['label'] = 'Otherwise'
    named, _ = run(model, [{'op': 'branch', 'decision': decision['id'], 'condition': 'Age restricted non-tobacco product',
                            'to': first, 'quote': 'customer asks for age restricted product'}], answer, 4)
    assert pm.what_changed(model, named) == ['named the path "Age restricted non-tobacco product" (it was "Otherwise")']
    assert f'path 3 "Age restricted non-tobacco product": {first}' in pm.view(named)
    assert f'{first} task "Scan product" (first step of path 3)' in pm.view(named)


def test_nothing_is_moved_removed_or_set_that_the_answer_does_not_ask_for():
    """"That's the end of it." drew a move of a step to the start (the process replay of 1 October, 22:13), and a guess
    at who does it."""
    model = reviewed_till()
    [review] = labelled(model, 'Review product')
    answer = "That's the end of it."
    question = 'Who is responsible for reviewing the product?'  # the step is the one asked about
    model2, log = pm.apply(model, [{'op': 'move', 'item': review['id'], 'after': 'start', 'quote': "That's the end of it."},
                                   {'op': 'remove', 'item': review['id'], 'quote': "That's the end of it."},
                                   {'op': 'change', 'item': review['id'], 'field': 'who', 'value': 'sales assistant',
                                    'quote': "That's the end of it."}], answer, 6, question)
    assert [d['why'] for d in log['dropped']] == ['the answer does not ask for it', 'the answer does not ask for it',
                                                  'the answer does not say that']
    assert model2.get('proposed_change') is None and labelled(model2, 'Review product')[0]['who'] == 'cashier'
    assert pm.said_in('card machine', 'The refund is done on the card machine, not on the till.') and pm.said_in('IT', 'No.')


def test_one_step_said_to_follow_all_the_paths_is_one_step_where_they_meet():
    """"All will be added to the basket. And then after the basket, there is a single step ... So we need to merge all
    those different options into single step" (21:46) was noted as three "Confirm quantity limit", one per basket, and a
    second quantity-limit question after the first."""
    model = reviewed_till()
    p = pm.process(model, 'p1')
    ends = [s['id'] for s in pm._open_ends(p) if s['label'] != 'Check quantity limit']
    [question] = [s for s in p['steps'] if s['label'] == 'Does the product have a quantity limit?']
    answer = ('All will be added to the basket. And then after the basket, there is a single step, which is, we need to '
              'confirm, if the product has any quantity limit. So we need to merge all those different options into single step.')
    changes = [{'op': 'decision', 'ref': 'n1', 'process': 'p1', 'after': question['id'],
                'question': 'Does the product have a quantity limit?', 'quote': 'if the product has any quantity limit'}]
    changes += [{'op': 'step', 'ref': f'n{i + 2}', 'process': 'p1', 'after': end, 'kind': 'task', 'label': 'Confirm quantity limit',
                 'who': 'cashier', 'with': '', 'system': '', 'quote': 'we need to confirm'} for i, end in enumerate(ends)]
    merged, log = run(model, changes, answer, 6)
    p = pm.process(merged, 'p1')
    assert len([s for s in p['steps'] if s['kind'] == 'decision' and 'quantity' in s['label']]) == 1
    [confirm] = labelled(merged, 'Confirm quantity limit')
    assert sorted(s['id'] for s in p['steps'] if any(n['to'] == confirm['id'] for n in s['next'])) == sorted(ends)
    assert len(log['merged']) == len(ends) - 1
    # Without "merge", the same action after each path stays a step of each path (PI F19).
    separate, _ = run(model, changes[1:], 'Each is added to the basket, and then we need to confirm the quantity limit.', 6)
    assert len(labelled(separate, 'Confirm quantity limit')) == len(ends)


def test_a_quote_of_pieces_joined_by_dots_counts_and_a_move_to_where_it_is_does_not():
    answer = ("You have to remember that all three paths, at the end of the day, regardless of which product the customer "
              "asks for, at the end of the day, all will be added to the basket.")
    assert pm.quoted('all three paths... at the end of the day... all will be added to the basket', answer)
    assert not pm.quoted('all will be added to the basket... all three paths', answer)  # out of order
    model = described_till()
    [decision] = [s for s in pm.process(model, 'p1')['steps'] if s['kind'] == 'decision']
    first, second = (pm.find(model, n['to'])[1] for n in decision['next'][1:3])
    after = second['next'][0]['to']  # the third path's second step
    _, log = run(model, [{'op': 'move', 'item': after, 'after': second['id'], 'quote': 'it goes after the scan'}],
                 'It goes after the scan.', 4)
    assert [d['why'] for d in log['dropped']] == ['already there']


def test_on_the_map_a_trigger_goes_just_before_a_path_s_first_step():
    """The way to "add that trigger to the third path at the beginning" (21:38) on the map."""
    model = described_till()
    [decision] = [s for s in pm.process(model, 'p1')['steps'] if s['kind'] == 'decision']
    first = decision['next'][2]['to']
    model, said = pm.edit(model, {'op': 'add', 'item': first, 'value': 'Customer asks for a product with no age limit',
                                  'kind': 'event', 'before': True}, 5)
    [trigger] = labelled(model, 'Customer asks for a product with no age limit')
    [decision] = [s for s in pm.process(model, 'p1')['steps'] if s['kind'] == 'decision']
    assert said == 'added the trigger "Customer asks for a product with no age limit" just before "Scan product"'
    assert decision['next'][2] == {'to': trigger['id'], 'label': 'No age limit'} and trigger['next'] == [{'to': first, 'label': ''}]


def test_several_steps_for_where_the_paths_meet_are_asked_about_not_listed():
    """21:46: one explanation became six moves said back as one question."""
    model = reviewed_till()
    review, check = labelled(model, 'Review product')[0], labelled(model, 'Check quantity limit')[0]
    answer = 'So we need to merge all those different options into single step, after the basket.'
    model, log = run(model, [{'op': 'move', 'item': review['id'], 'after': 'paths', 'quote': 'merge all those different options'},
                             {'op': 'move', 'item': check['id'], 'after': 'paths', 'quote': 'into single step'}], answer, 6)
    assert model.get('proposed_change') is None
    assert {'op': 'move', 'why': 'several steps for where the paths meet'} in log['dropped']
    assert [g['key'] for g in pm.goals(model, limit=1)][0].startswith('unclear:')
    assert 'Which step do the paths lead into' in pm.goals(model, limit=1)[0]['ask']


# ---- PI F26: read-backs told as the story of the work, with the map following (the Human, 1 October, 23:50) -----------

def merged_till():
    """The till's three ways meeting at a review, then a quantity-limit question (the map the Human wanted at 21:44)."""
    model = reviewed_till()
    review = labelled(model, 'Review product')[0]
    model, _ = pm.edit(model, {'op': 'move', 'item': review['id'], 'after': 'paths'}, 7)
    return model


def test_a_read_back_tells_the_story_with_signposts_to_the_map():
    """"It is very much reading precisely what each step is ... at speed with many steps can get confusing ... it should
    use natural language ... like a narrator that pays attention where we are on the map." """
    model = merged_till()
    story = pm.narrate(model)
    text = story['text']
    assert text.startswith('Let me walk you through Carrying out cashiering as I have it, and stop me at any point. It '
                           'starts when a customer comes to the till and asks for a product.')
    assert ('What happens next depends on what kind of product is asked for, and there are three ways it can go. On the map, '
            'they are the three columns under that question.') in text
    # What the same person does runs on; a place said twice is said once; "it" for the same thing again.
    assert 'First: tobacco. The cashier checks the customer ID and scans the product on the till.' in text
    assert 'Third: no age limit. The cashier scans the product on the till.' in text
    assert all(f'That is the {side} column.' in text for side in ('left-hand', 'middle', 'right-hand'))
    assert ('The routes then come back together further down the map, and after that the cashier reviews the product.'
            in text)
    assert 'Then the question is: does the product have a quantity limit? There is one way so far.' in text
    assert text.endswith('Is that right?') and 'The first path' not in text
    # Nothing left out: every step of the map is told, each said once.
    told = [i for part in story['parts'] for i in part['steps']]
    steps = [s for s in pm.process(model, 'p1')['steps'] if s['kind'] in ('task', 'event', 'decision')]
    assert {s['id'] for s in steps} <= set(told)
    assert text.count('reviews the product') == 1 and text.count('checks the quantity limit') == 1


def test_the_map_follows_the_story_part_by_part():
    model = merged_till()
    parts = pm.narrate(model)['parts']
    assert parts[0] == {'text': 'Let me walk you through Carrying out cashiering as I have it, and stop me at any point.',
                        'steps': []}
    assert parts[1]['steps'] == ['start']  # what starts it: the map's first box
    [decision] = [s for s in pm.process(model, 'p1')['steps'] if s['kind'] == 'decision' and 'kind of product' in s['label']]
    assert parts[2]['steps'] == [decision['id']]
    first_way = next(p for p in parts if p['text'].startswith('First: tobacco.'))
    column = next(p for p in parts if p['text'] == 'That is the left-hand column.')
    assert first_way['steps'] == column['steps'] and len(first_way['steps']) >= 2  # named, the whole way lights up
    between = parts[parts.index(first_way) + 1:parts.index(column)]
    assert all(set(p['steps']) < set(first_way['steps']) for p in between)  # then each sentence its own steps
    assert all(len(p['text']) <= 500 for p in parts)


def test_checks_and_watch_points_are_told_where_they_belong():
    """As the Classic Digital SME's walkthrough did: "This step is governed by ...", "Watch point: ..."."""
    model = ordering()
    answer = 'Orders over a thousand need two signatures. If the stock report is late we call the warehouse.'
    model, log = run(model, [
        {'op': 'control', 'process': 'p1', 'at': 's2', 'text': 'Two signatures over £1,000', 'quote': 'need two signatures'},
        {'op': 'exception', 'process': 'p1', 'at': 's1', 'text': 'Stock report is late', 'handling': 'call the warehouse',
         'quote': 'If the stock report is late we call the warehouse'},
        {'op': 'control', 'process': 'p1', 'at': '', 'text': 'Monthly stock audit', 'quote': 'Orders over a thousand'}], answer, 4)
    assert not log['dropped'], log['dropped']
    text = pm.narrate(model)['text']
    assert ('The store manager checks the stock report and raises the purchase order in SAP. Watch point: stock report is '
            'late, and then call the warehouse. There is a check there: two signatures over £1,000.') in text
    assert text.endswith('There is a check there: monthly stock audit. Is that right?')


def test_a_short_check_back_runs_on_and_a_way_called_otherwise_does_too():
    model = described_till()
    p = pm.process(model, 'p1')
    third = [s['id'] for s in pm.ordered_steps(p) if s['label'] in ('Scan product', 'Add product to basket')][-2:]
    assert pm.readback_text(model, third) == (
        'Let me check I have this right. First the cashier scans the product on the till. Then the till adds the product '
        'to the basket. Is that right?')
    [decision] = [s for s in p['steps'] if s['kind'] == 'decision']
    decision['next'][2]['label'] = 'Otherwise'
    assert 'Otherwise, the cashier scans the product on the till.' in pm.narrate(model)['text']


# The Human's answers of 2 October, 08:12-08:15 (interview c29a70dc), word for word; the changes in the tests below are
# what the note-taker made of them.
MORNING = {
    'options': ("Yeah, that is correct. And then under the review if quantity is exceeded, you have also two options. One "
                "option is customer don't want to continue with the purchase or customer want to continue with the purchase."),
    'steps': ("Yes, under the customer don't want to continue with the purchase then the cashier initiates a step to return "
              "product to the display and then after that it ensures the product is removed from the basket on point of "
              "sale and then this basically ends there because product is not added to the virtual ticket"),
    'wrong': 'No, you put it in the wrong place. This entire step should go under customer does not want to continue.',
    'move': 'so that those steps need to move and the customer does not want to continue.',
}
NOT_CONTINUING = 'Customer does not want to continue'


def continuing_till(ended=False):
    """The till's quantity-limit question with two ways, and after the check a question with two options (08:12).
    ``ended``: the first option said to end at once, as engine 1.8.6 had it without being told."""
    model = merged_till()
    [question] = [s for s in pm.process(model, 'p1')['steps'] if s['kind'] == 'decision' and 'quantity' in s['label']]
    model, log = run(model, [{'op': 'branch', 'decision': question['id'], 'condition': 'No quantity limit', 'to': 'open',
                              'quote': 'the product has no quantity limit'}], 'Or the product has no quantity limit.', 8)
    check = labelled(model, 'Check quantity limit')[0]
    model, log = run(model, [
        {'op': 'decision', 'ref': 'n1', 'process': 'p1', 'after': check['id'],
         'question': 'Does the customer want to continue with the purchase?',
         'quote': "you have also two options. One option is customer don't want to continue with the purchase or customer "
                  "want to continue with the purchase"},
        {'op': 'branch', 'decision': 'n1', 'condition': NOT_CONTINUING, 'to': 'end',
         'quote': "customer don't want to continue with the purchase"},
        {'op': 'branch', 'decision': 'n1', 'condition': 'Customer wants to continue', 'to': 'open',
         'quote': 'customer want to continue with the purchase'}], MORNING['options'] + (' That one ends there.' if ended else ''), 9)
    assert not log['dropped'], log['dropped']
    return model


def way(model, condition):
    """A way of a question, step by step: "kind:label"."""
    p = pm.process(model, 'p1')
    [link] = [n for s in p['steps'] if s['kind'] == 'decision' for n in s['next'] if n['label'] == condition]
    by_id, out, at = {s['id']: s for s in p['steps']}, [], link['to']
    while at and len(out) < 10:
        out.append(f"{by_id[at]['kind']}:{by_id[at]['label']}")
        at = by_id[at]['next'][0]['to'] if by_id[at]['next'] and by_id[at]['kind'] != 'decision' else None
    return out


def described(model, after):
    """The note-taker's notes of the 08:13 answer: the two steps, the first after ``after``."""
    return [
        {'op': 'step', 'ref': 'n1', 'process': 'p1', 'after': after, 'kind': 'task', 'label': 'Return product to display',
         'who': 'cashier', 'with': '', 'system': '', 'quote': 'the cashier initiates a step to return product to the display'},
        {'op': 'step', 'ref': 'n2', 'process': 'p1', 'after': 'n1', 'kind': 'task',
         'label': 'Remove product from basket on point of sale', 'who': 'cashier', 'with': '', 'system': 'point of sale',
         'quote': 'it ensures the product is removed from the basket on point of sale'}]


RETURNED = ['task:Return product to display', 'task:Remove product from basket on point of sale']


def test_an_option_only_named_waits_for_its_steps_and_they_go_on_its_path():
    """08:12: "One option is customer don't want to continue … or customer want to continue". The first option was
    ended at once, without a word of its ending, and the steps described for it next were lost (PI F27)."""
    model = continuing_till()
    assert way(model, NOT_CONTINUING) == [f'open:{NOT_CONTINUING}']
    assert not [s for s in pm.process(model, 'p1')['steps'] if s['kind'] == 'end']
    opened = labelled(model, NOT_CONTINUING)[0]
    model, log = run(model, [*described(model, opened['id']),
                             {'op': 'step', 'ref': 'n3', 'process': 'p1', 'after': 'n2', 'kind': 'end', 'label': 'End process',
                              'who': '', 'with': '', 'system': '',
                              'quote': 'this basically ends there because product is not added to the virtual ticket'}],
                     MORNING['steps'], 10)
    assert not log['dropped'], log['dropped']
    assert way(model, NOT_CONTINUING) == [*RETURNED, 'end:End process']
    assert way(model, 'No quantity limit') == ['open:No quantity limit']
    assert way(model, 'Customer wants to continue') == ['open:Customer wants to continue']


def test_steps_described_after_an_option_that_ends_go_before_its_end_never_on_another_path():
    """08:13, as engine 1.8.6 had the map: the note-taker put the option's steps after its end, and they went under
    "Product without quantity limit", the other question's way still only named (PI F27)."""
    model = continuing_till(ended=True)
    [end] = [s for s in pm.process(model, 'p1')['steps'] if s['kind'] == 'end']
    assert way(model, NOT_CONTINUING) == ['end:End']
    model, log = run(model, [*described(model, end['id']),
                             {'op': 'change', 'item': end['id'], 'field': 'kind', 'value': 'end',
                              'quote': 'this basically ends there because product is not added to the virtual ticket'}],
                     MORNING['steps'], 10)
    assert way(model, NOT_CONTINUING) == [*RETURNED, 'end:End']
    assert way(model, 'No quantity limit') == ['open:No quantity limit']
    assert pm.what_changed(continuing_till(ended=True), model)[0] == (
        f'added "Return product to display" on the path "{NOT_CONTINUING}"')


def misplaced_till():
    """The map at 08:14: the option's steps under "No quantity limit"."""
    model = continuing_till(ended=True)
    model, log = run(model, described(model, labelled(model, 'No quantity limit')[0]['id']), MORNING['steps'], 10)
    assert way(model, 'No quantity limit') == RETURNED
    return model


def test_steps_said_to_go_under_an_option_move_there_with_those_after_them_when_agreed():
    """08:15: "so that those steps need to move and the customer does not want to continue" was proposed as a move to
    after the quantity question (PI F27)."""
    model = misplaced_till()
    [question] = [s for s in pm.process(model, 'p1')['steps'] if s['kind'] == 'decision' and 'quantity' in s['label']]
    back, remove = (labelled(model, label)[0] for label in ('Return product to display', 'Remove product from basket on point of sale'))
    moves = [{'op': 'move', 'item': back['id'], 'after': question['id'], 'quote': 'so that those steps need to move'},
             {'op': 'move', 'item': remove['id'], 'after': back['id'], 'quote': 'so that those steps need to move'}]
    asked, log = run(model, moves, MORNING['move'], 11)
    [change] = asked['proposed_change']['ops']
    assert pm.describe(change, asked) == (f'move "Return product to display" and "Remove product from basket on point of '
                                          f'sale" to the path "{NOT_CONTINUING}"')
    assert way(asked, 'No quantity limit') == RETURNED  # nothing moves before a yes
    moved, said = pm.edit(asked, change, 12)
    assert way(moved, NOT_CONTINUING) == [*RETURNED, 'end:End']
    assert way(moved, 'No quantity limit') == ['open:No quantity limit']  # named still, and still to describe
    # Asked again once they are there: nothing to propose.
    again, log = run({**moved, 'proposed_change': None}, moves, MORNING['move'], 13)
    assert again['proposed_change'] is None and 'already there' in [d['why'] for d in log['dropped']]


def test_put_in_the_wrong_place_moves_the_steps_just_added_to_the_option_named():
    """08:14: "No, you put it in the wrong place. This entire step should go under customer does not want to continue."
    The note-taker named the end as the step and the other option as the path (PI F27)."""
    model = misplaced_till()
    [end] = [s for s in pm.process(model, 'p1')['steps'] if s['kind'] == 'end']
    other = labelled(model, 'Customer wants to continue')[0]
    asked, log = run(model, [{'op': 'repath', 'items': [end['id']], 'path': other['id'], 'condition': NOT_CONTINUING,
                              'quote': 'This entire step should go under customer does not want to continue'}],
                     MORNING['wrong'], 11)
    [change] = asked['proposed_change']['ops']
    assert pm.describe(change, asked) == (f'move "Return product to display" and "Remove product from basket on point of '
                                          f'sale" to the path "{NOT_CONTINUING}"')
    moved, _ = pm.edit(asked, change, 12)
    assert way(moved, NOT_CONTINUING) == [*RETURNED, 'end:End']


def test_an_option_is_named_by_its_words_and_its_not():
    model = continuing_till()
    p = pm.process(model, 'p1')
    for answer, named in (("this should go under customer doesn't want to continue", NOT_CONTINUING),
                          ('No, put it under customer wants to continue', 'Customer wants to continue'),
                          ('move it under the customer wants to continue', 'Customer wants to continue'),
                          ('those steps need to move', None)):
        found = pm._way_named(p, answer)
        assert (found[1]['label'] if found else None) == named, answer


def test_only_an_answer_that_says_so_ends_an_option():
    assert not pm.ENDS.search(MORNING['options'])
    assert not pm.ENDS.search('at the end of the day, all will be added to the basket')
    assert pm.ENDS.search(MORNING['steps']) and pm.ENDS.search("the customer leaves and that's it")


def test_an_option_described_and_then_said_to_end_ends_after_its_steps():
    """"…and then this basically ends there": a branch to the end for an option already described ends it after its
    last step, never as a second option of the same name."""
    model = continuing_till()
    opened = labelled(model, NOT_CONTINUING)[0]
    model, _ = run(model, described(model, opened['id']), MORNING['steps'], 10)
    [decision] = [s for s in pm.process(model, 'p1')['steps'] if s['label'] == 'Does the customer want to continue with the purchase?']
    model, log = run(model, [{'op': 'branch', 'decision': decision['id'], 'condition': NOT_CONTINUING, 'to': 'end',
                              'quote': 'this basically ends there'}], MORNING['steps'], 11)
    assert not log['dropped'], log['dropped']
    assert way(model, NOT_CONTINUING) == [*RETURNED, 'end:End']
    assert [n['label'] for n in decision['next']] == [NOT_CONTINUING, 'Customer wants to continue']
