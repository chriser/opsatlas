"""The working process model of a process interview (TIBI E5, PI F2/F3): checked, deterministic, no model calls."""
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
    assert pm.recap(model).startswith('So far for Ordering parts: store manager check stock report in SAP')
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
    assert 's3 task "Approve order" who: finance system: - [disputed]' in text
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
    assert text.startswith('Let me check I have this right. First the store manager checks stock report in SAP. '
                           'Then the store manager raises purchase order in SAP. Then there is a decision, is it over £5,000: '
                           'Over £5,000, the regional director approves order by email; Otherwise, finance approves order.')
    assert text.count('regional director') == 1 and text.endswith('Is that right?')  # branch steps are not repeated


def test_two_paths_that_continue_to_the_same_step_join_there():
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
        {'op': 'step', 'ref': 'c2', 'process': 'p1', 'after': 's3', 'kind': 'task', 'label': 'Confirm delivery', 'who': 'supplier',
         'system': '', 'quote': 'Once finance approves, the supplier confirms delivery too'},
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
