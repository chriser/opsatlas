"""The working process model of a process interview (TIBI E5, PI F3): what the participant has said, as a model.

The note-taker (a local model, off the voice path) reads each answer and returns *changes*; this module checks and
applies them deterministically, and plans what to ask next from the model's gaps (PI F2). Nothing here calls a model.

* Every change quotes the answer it came from; a change whose quote is not in the answer is dropped.
* A change to something already said is applied only when the answer signals a correction ("no", "actually",
  "not…"), or when it settles a conflict Tibi has just raised. Otherwise it becomes a **conflict**, which Tibi raises
  before anything else: the participant decides, Tibi never picks one account over the other.
* Items are *heard* until the participant confirms a read-back (*confirmed*); an item with an open conflict is
  *disputed*.

The model is plain JSON (``opsatlas.process-model.v1``), saved with the interview after every turn.
"""
from __future__ import annotations

import copy
import difflib
import re

SCHEMA_ID = 'opsatlas.process-model.v1'
PARTICIPANT_FIELDS = ('name', 'role', 'team', 'tenure')
PROCESS_FIELDS = ('purpose', 'trigger', 'outcome', 'frequency', 'owner')
STEP_FIELDS = ('label', 'who', 'system', 'with')  # with: anyone else taking part (PI F19)
LIMITS = {'processes': 8, 'steps': 60, 'open': 60, 'notes': 40}
CORRECTION = re.compile(r"\b(?:no|not|nope|actually|sorry|correction|i meant|i mean|wrong|rather|instead|about the step|"
                        r"isn'?t|wasn'?t|doesn'?t|don'?t|mistake|scratch that|let me correct)\b", re.I)
KINDS = ('xor', 'or', 'and')  # a decision: only one path followed, any number (shown as ANY), or all of them
# A step is an action someone does (a task, green on the map) or a trigger: something that happens, or a state reached,
# that sets off what follows (an event, purple). Either can be turned into the other, on the map or by asking (PI F23).
STEP_KINDS = ('task', 'event')
JOIN_LABEL = 'After the paths meet'
# What a change asks of the map must be in the answer (1 October, the process replay of 22:13: "That's the end of it."
# drew a move of a step to the start, and a guess at who does it). A move or a removal needs words that ask for one; a
# step's new who, system, with or name needs a word the participant said (PI F25).
MOVE_CUE = re.compile(r"\b(?:before|after|first|last|start|beginning|earlier|later|then|move[ds]?|moving|put|comes?|came|"
                      r"goes|go|happens?|swap|switch|order|ahead|instead|between|below|above|under|underneath|beneath|"
                      r"merg\w*|join\w*)\b", re.I)
REMOVE_CUE = re.compile(r"\b(?:remove|delete|(?:take|leave|cross)\b.{0,40}?\bout|drop|not needed|isn'?t needed|"
                        r"doesn'?t happen|don'?t (?:do|need)|no longer|skip|scrap|get rid|cut)\b", re.I)
# A step named only with the request's own words: "Add additional step" (1 October, 21:39).
REQUEST_WORDS = {'add', 'adding', 'insert', 'put', 'include', 'new', 'another', 'additional', 'extra', 'one', 'more', 'a',
                 'an', 'the', 'step', 'steps', 'trigger', 'box', 'activity', 'task'}
# Paths said to merge into one step: "So we need to merge all those different options into single step" (21:46).
MERGE_CUE = re.compile(r"\b(?:merg\w*|join\w*|come (?:back )?together|single step|one step)\b", re.I)
READBACK_AFTER = 3  # heard steps not yet read back before Tibi reads them back
COMMON = {'with', 'from', 'that', 'this', 'then', 'when', 'into', 'onto', 'back', 'have', 'does', 'done', 'they', 'their',
          'there', 'what', 'which', 'after', 'before'}
DEPARTMENTS = {'finance', 'purchasing', 'procurement', 'accounts', 'accounting', 'marketing', 'sales', 'operations', 'it',
               'hr', 'legal', 'payroll', 'logistics', 'security', 'management', 'compliance', 'engineering', 'support',
               'customer service', 'someone'}
# Verbs common in process steps. A label whose second word is one of them with an -s ("Customer brings item") names its
# own subject and is read back as it is; "Process returns" starts with a verb, so it is an instruction.
VERBS = {'accept', 'add', 'agree', 'approve', 'arrive', 'ask', 'book', 'bring', 'buy', 'call', 'check', 'choose', 'close',
         'collect', 'come', 'complete', 'confirm', 'contact', 'count', 'create', 'decide', 'deliver', 'drop', 'email', 'end',
         'enter', 'fill', 'find', 'finish', 'get', 'give', 'go', 'hand', 'handle', 'hold', 'inform', 'issue', 'keep', 'leave',
         'log', 'look', 'make', 'move', 'need', 'notify', 'open', 'order', 'pack', 'pay', 'phone', 'pick', 'place', 'prepare',
         'print', 'process', 'put', 'raise', 'read', 'receive', 'record', 'refund', 'reject', 'remove', 'request', 'return',
         'review', 'scan', 'see', 'sell', 'send', 'set', 'ship', 'sign', 'start', 'store', 'submit', 'take', 'tell', 'update',
         'use', 'wait', 'want', 'write'}
ARRIVING = {'arrive', 'come', 'go', 'end', 'finish', 'start', 'wait', 'leave'}  # "Order arrives": the noun is the subject
ABOUT_THEMSELVES = re.compile(r"\b(?:i'?m|i am|my (?:name|role|job|title|team)|i work|i look after|i run|i manage|i've been|i have been|"
                              r"call me)\b", re.I)


def new_model(space_id: str, space_name: str = '') -> dict:
    return {'schema': SCHEMA_ID, 'space': {'id': space_id, 'name': space_name}, 'participant': {}, 'processes': [],
            'open': [], 'focus': None, 'asked': {}, 'readback': None, 'wrapped': False, 'turns': 0, 'glossary': {},
            'proposed_change': None,
            'next': {'p': 1, 's': 1, 'o': 1, 'x': 1, 'c': 1}}


def _norm(text: str) -> str:
    return ' '.join(re.sub(r"[^\w£$€%'&/-]+", ' ', str(text).casefold().replace('’', "'")).split())


def quoted(quote: str, answer: str) -> bool:
    """The quote is an excerpt of the answer, ignoring case, spacing and punctuation. A long quote may miss a word in ten
    (the note-taker quoted "after scan product on point sale step" for "…on point of sale step", and the trigger asked
    for was lost, 1 October): its words are then found in the answer in order, close together."""
    q, a = _norm(quote), _norm(answer)
    if not q or q in a:
        return bool(q)
    # Pieces of the answer joined by "..." (21:46: "all three paths... at the end of the day... all will be added to the
    # basket"): each piece exact, in the answer's order.
    pieces = [_norm(x) for x in re.split(r'\.{3,}|…', str(quote)) if _norm(x)]
    if len(pieces) > 1 and all(len(x.split()) >= 2 for x in pieces):
        at = 0
        for piece in pieces:
            at = a.find(piece, at)
            if at < 0:
                return False
            at += len(piece)
        return True
    words = q.split()
    if len(words) < 8:
        return False
    blocks = [b for b in difflib.SequenceMatcher(None, words, a.split(), autojunk=False).get_matching_blocks() if b.size]
    found = sum(b.size for b in blocks)
    span = blocks[-1].b + blocks[-1].size - blocks[0].b if blocks else 0
    return found >= 0.9 * len(words) and span <= len(words) + max(2, len(words) // 5)


# A correction of the process as a whole starts a sentence ("No, it starts when…", "Actually…"). A "no" inside a
# description ("a product with no limits") corrected the trigger on 29 September (PI F19).
PROCESS_CORRECTION = re.compile(r"(?:^|[.!?;]\s+)(?:no|nope|actually|sorry|correction|i meant|i mean|let me correct|scratch that|"
                                r"that'?s not right|that'?s wrong|not quite)\b", re.I)


def said_in(value, answer) -> bool:
    """A new value the answer itself gives: one of its own words (four letters or more) is in the answer, or it has
    none ("IT", "HR")."""
    words = [w for w in _norm(value).split() if len(w) >= 4 and w not in COMMON]
    heard = _norm(answer)
    return not words or any(w[:5] in heard for w in words)


def corrects(answer: str) -> bool:
    return bool(CORRECTION.search(answer.replace('’', "'")))


def _new_id(model, kind):
    number = model['next'][kind]
    model['next'][kind] = number + 1
    return f'{kind}{number}'


def process(model, process_id):
    return next((p for p in model['processes'] if p['id'] == process_id), None)


def find(model, item_id):
    """(process, item, kind) for a step, exception or control id; (process, process, 'process') for a process."""
    for p in model['processes']:
        if p['id'] == item_id:
            return p, p, 'process'
        for kind in ('steps', 'exceptions', 'controls'):
            for item in p[kind]:
                if item['id'] == item_id:
                    return p, item, kind[:-1]
    return None, None, None


def ordered_steps(p) -> list[dict]:
    """The steps in flow order from the start (branches depth first), then any not yet connected."""
    by_id = {s['id']: s for s in p['steps']}
    seen, out = set(), []

    def walk(step_id):
        stack = [step_id]
        while stack:
            current = stack.pop()
            if current in seen or current not in by_id:
                continue
            seen.add(current)
            out.append(by_id[current])
            stack.extend(link['to'] for link in reversed(by_id[current]['next']))
    if p.get('start'):
        walk(p['start'])
    for s in p['steps']:
        if s['id'] not in seen:
            walk(s['id'])
    return out


def _quote(item, text, turn):
    item.setdefault('quotes', []).append({'text': text, 'turn': turn})
    item['quotes'] = item['quotes'][-6:]


def _field(value, quote, turn):
    return {'value': value, 'quote': quote, 'turn': turn, 'status': 'heard'}


def _open(model, kind, turn, **fields):
    for item in model['open']:  # one open item per question about the same thing
        if item['status'] != 'resolved' and item['kind'] == kind and item.get('item') == fields.get('item') \
                and item.get('field') == fields.get('field'):
            item.update({k: v for k, v in fields.items() if v}, turn=turn)
            return item
    if len([o for o in model['open'] if o['status'] != 'resolved']) >= LIMITS['open']:
        return None
    item = {'id': _new_id(model, 'o'), 'kind': kind, 'status': 'open', 'turn': turn, **fields}
    model['open'].append(item)
    return item


def _current(item, kind, field):
    """The value and its quote as the model holds them now."""
    if kind == 'process':
        held = item['details'].get(field) or {}
        return held.get('value', ''), held.get('quote', '')
    if kind == 'participant':
        held = item.get(field) or {}
        return held.get('value', ''), held.get('quote', '')
    return item.get(field, ''), (item.get('quotes') or [{}])[0].get('text', '')


def _pending_conflict(model, item_id, field):
    """A conflict Tibi has raised about this item and field: the next answer about it settles it. One not yet raised
    is not settled by chance; another version only updates it."""
    return next((o for o in model['open'] if o['kind'] == 'conflict' and o['status'] == 'raised'
                 and o.get('item') == item_id and o.get('field') == field), None)


def _set(model, owner, kind, item_id, field, value, quote, answer, turn, log):
    """Set a field: new information is added; a different value replaces the old one only when the participant is
    correcting it, or settling a conflict Tibi raised. Otherwise it is a conflict for Tibi to raise."""
    value = ' '.join(str(value).split())[:160]
    old, old_quote = _current(owner, kind, field)
    settling = _pending_conflict(model, item_id, field)
    different = bool(old) and _norm(old) != _norm(value)
    # More detail about the same thing ("SAP" -> "SAP approval queue") is taken, not a conflict; less detail changes nothing.
    refined = different and _norm(old) in _norm(value)
    if different and _norm(value) in _norm(old) and not settling:
        return
    correcting = PROCESS_CORRECTION.search(answer.strip()) if kind == 'process' else corrects(answer)
    if different and not refined and not settling and not correcting:
        if field not in ('who', 'system'):
            return  # another wording of the same thing: what was said first stands, and nothing is asked
        conflict = _open(model, 'conflict', turn, item=item_id, field=field, earlier=old, earlier_quote=old_quote,
                         now=value, quote=quote)
        if kind not in ('process', 'participant'):
            owner['status'] = 'disputed'
        log['conflicts'].append(conflict['id'] if conflict else f'{item_id}.{field}')
        return
    if old and _norm(old) == _norm(value):
        if settling:  # they kept what they said first: the conflict is settled, nothing changes
            settling.update(status='resolved', resolution=value, resolved_turn=turn)
            log['resolved'].append(settling['id'])
            if kind not in ('process', 'participant'):
                owner['status'] = 'heard'
        return
    if kind == 'participant':
        owner[field] = _field(value, quote, turn)
    elif kind == 'process':
        owner['details'][field] = _field(value, quote, turn)
        if field == 'owner':
            for step in owner['steps']:
                if step['kind'] == 'task' and not step['who']:
                    step['who'] = value
    else:
        owner[field] = value
        owner['status'] = 'heard'
        owner['read'] = False
        _quote(owner, quote, turn)
        if field == 'system' and old and re.search(r'\b' + re.escape(old) + r'\b', owner['label'], re.I):
            # "Refund on till", corrected to the card machine: the name follows ("Refund on card machine").
            owner['label'] = re.sub(r'\b' + re.escape(old) + r'\b', value, owner['label'], flags=re.I)
    if old:
        log['corrected'].append({'item': item_id, 'field': field, 'was': old, 'now': value})
    if settling:
        settling.update(status='resolved', resolution=value, resolved_turn=turn)
        log['resolved'].append(settling['id'])
    log['applied'].append(f'{item_id}.{field}')


def _role(p, who) -> str:
    """A role as said, unless it is the process's own name (a capture once had "Cashiering" doing every step of "Carry
    out cashiering")."""
    who = _clean(who)
    words, name = set(_norm(who).split()), set(_norm(p.get('name') or '').split())
    # Whole words: "Cashiering" is the process's name, "cashier" is a role.
    return '' if words and name and words <= name else who


def _link_after(p, step, after, by_id):
    """Put a new step into the flow after ``after``: the first step, after a task (taking over what came next), on a
    decision's branch (linked by a branch change), or at the end of the flow."""
    if not p['steps'] or not p.get('start'):
        p['start'] = step['id']
        return 'start'
    if after == 'start':
        step['next'] = [{'to': p['start'], 'label': ''}]
        p['start'] = step['id']
        return 'start'
    if after == 'paths':
        # "Then they all come back together and…" (PI F23): the step follows every path that has not ended, where they
        # meet; a meeting point already noted ("it joins the rest of the process") is taken over.
        meet = _meeting_point(p)
        if meet is not None:
            _take_over(p, meet, step)
            return 'paths'
        ends = _open_ends(p, step)
        for tail in ends:
            tail['next'] = [{'to': step['id'], 'label': ''}]
        return 'paths' if ends else 'loose'
    anchor = by_id.get(after)
    if anchor is not None and anchor['kind'] == 'decision':
        return 'branch'  # linked by its branch, or below if none names it
    if anchor is None or anchor['kind'] == 'end':
        tails = [s for s in ordered_steps(p) if not s['next'] and s['kind'] != 'end' and s is not step]
        anchor = tails[-1] if tails else None
        if anchor is None:
            return 'loose'
    step['next'] = anchor['next'] if step['kind'] != 'end' else []
    anchor['next'] = [{'to': step['id'], 'label': ''}]
    return anchor['id']


def _link_before(p, step, target):
    """Put a step straight before ``target``: whatever led to the target now leads to the step, which leads to it. A
    target on a decision's branch keeps the step on that branch ("the shelf before the refund" stays on the refund's
    path, not before the decision)."""
    for other in p['steps']:
        if other is step:
            continue
        other['next'] = [{'to': step['id'], 'label': link['label']} if link['to'] == target['id'] else link
                         for link in other['next']]
    step['next'] = [{'to': target['id'], 'label': ''}]
    if p.get('start') == target['id']:
        p['start'] = step['id']


def about(item, text, strict=False) -> bool:
    """The answer (or Tibi's question) refers to this step or process: one of its own words is there. A correction for
    "the refund" does not land on "Check receipt on till" because both mention the till. ``strict``: a step with no
    distinctive word is not taken as named."""
    # Its own words, not its attributes: "Check receipt on till" is named by "receipt", not by "till" (its system).
    attributes = set(_norm(f"{item.get('system', '')} {item.get('who', '')}").split())
    words = {w for w in _norm(item.get('label') or item.get('name') or '').split()
             if len(w) >= 4 and w not in COMMON and w not in attributes}
    if not words:
        return not strict
    heard = _norm(text).split()
    return any(h[:5] == w[:5] for w in words for h in heard if len(h) >= 4)


def apply(model: dict, changes: list, answer: str, turn: int, question: str = '') -> tuple[dict, dict]:
    """Apply the note-taker's changes for one answer. Returns the new model and a log of what was applied, dropped
    (with why), corrected, resolved and found in conflict."""
    model = copy.deepcopy(model)
    log = {'applied': [], 'dropped': [], 'corrected': [], 'conflicts': [], 'resolved': [], 'confirmed': []}
    refs: dict[str, str] = {}
    placed_after_decision: list[tuple[str, str]] = []
    created: list[str] = []  # steps and decisions made from this answer, in order

    def drop(change, why):
        log['dropped'].append({'op': change.get('op'), 'why': why})

    def ref(value):
        value = str(value or '').strip()
        return refs.get(value, value)

    def focus_process(change):
        pid = ref(change.get('process'))
        p = process(model, pid) if pid else None
        if p is None and model['focus']:
            p = process(model, model['focus'])
        if p is None and model['processes']:
            p = model['processes'][-1]
        if p is None:  # steps before the process was named: a process to name later
            p = _add_process(model, '', '', turn)
        return p

    # What a change points at is made first, whatever order the note-taker listed them in: the participant and
    # processes, then steps and decisions (in their own order), then branches, then everything else.
    rank = {'participant': 0, 'process': 0, 'process_detail': 1, 'step': 2, 'decision': 2, 'branch': 3}
    # The steps the answer itself names ("the refund"): a correction lands only on those. When it names none ("No, the
    # first one is Excel"), the question it answers says which steps it may be about.
    named = {s['id'] for p in model['processes'] for s in p['steps'] if s['kind'] != 'end' and about(s, answer, strict=True)}

    def meant(item):
        if item.get('kind') is None or 'steps' in item:  # a process as a whole
            return about(item, f'{answer} {question}')
        return item['id'] in named if named else about(item, question or answer)
    listed = _paths_from_heads([c for c in changes if isinstance(c, dict)] if isinstance(changes, list) else [])
    for change in sorted(listed, key=lambda c: rank.get(c.get('op'), 4)):
        op = change.get('op')
        quote = ' '.join(str(change.get('quote', '')).split())
        if op not in ('confirm', 'unknown') and not quoted(quote, answer):
            drop(change, 'the quote is not in the answer')
            continue
        if op == 'participant':
            field = change.get('field')
            if field in model['participant'] and not ABOUT_THEMSELVES.search(answer):
                # Who they are changes only when they speak about themselves, never from a correction about the process.
                drop(change, 'not about themselves')
                continue
            if field in PARTICIPANT_FIELDS and str(change.get('value', '')).strip():
                _set(model, model['participant'], 'participant', 'participant', field, change['value'], quote, answer, turn, log)
            else:
                drop(change, 'no participant field')
        elif op == 'process':
            name = ' '.join(str(change.get('name', '')).split())[:80]
            if not name:
                drop(change, 'no name')
                continue
            existing = next((p for p in model['processes'] if _norm(p['name']) == _norm(name)), None)
            unnamed = next((p for p in model['processes'] if not p['name']), None)
            if existing is None and unnamed is not None:
                unnamed.update(name=name, quote=quote)
                existing = unnamed
            if existing is None:
                if len(model['processes']) >= LIMITS['processes']:
                    drop(change, 'too many processes')
                    continue
                existing = _add_process(model, name, quote, turn)
            if change.get('ref'):
                refs[str(change['ref'])] = existing['id']
            log['applied'].append(existing['id'])
        elif op == 'process_detail':
            p = focus_process(change)
            if change.get('field') in PROCESS_FIELDS and str(change.get('value', '')).strip():
                _set(model, p, 'process', p['id'], change['field'], change['value'], quote, answer, turn, log)
            else:
                drop(change, 'no process field')
        elif op in ('step', 'decision'):
            p = focus_process(change)
            label = ' '.join(str(change.get('question') if op == 'decision' else change.get('label', '')).split())[:120]
            if not label or (op == 'step' and set(_norm(label).split()) <= REQUEST_WORDS):
                drop(change, 'no label')
                continue
            kind = 'decision' if op == 'decision' else change.get('kind') if change.get('kind') in ('end', 'event') else 'task'
            after = ref(change.get('after'))
            same = next((s for s in p['steps'] if s['kind'] == kind and _norm(s['label']) == _norm(label)), None)
            anchor = next((s for s in p['steps'] if s['id'] == after), None)
            if same is not None and anchor is same:
                anchor = None  # put after itself ("the quantity limit question" after that question): the same one
            before_same = [s['id'] for s in p['steps'] if same is not None and any(n['to'] == same['id'] for n in s['next'])]
            new_who = _role(p, change.get('who'))
            other_role = bool(new_who and same and same['who'] and _norm(new_who) != _norm(same['who']))
            if same is not None and anchor is not None and (
                    after not in before_same or (anchor['kind'] == 'decision' and other_role)):
                # The same action on another path (or on another branch, by someone else) is a step of its own: each
                # path of the organisation's maps has its own "Scan the product". Paths meet only where the participant
                # says they do: a join (PI F19). Joining same-named steps put a second option's steps under the first on
                # 29 September. Described again where it already is, it is the same step: new details, or a conflict.
                same = None
            if same is not None:  # the step they already described: new details, or a conflict
                if change.get('ref'):
                    refs[str(change['ref'])] = same['id']
                for field in ('who', 'system', 'with'):
                    value = _role(p, change.get(field)) if field in ('who', 'with') else change.get(field, '')
                    if str(value or '').strip() and value != '-':
                        _set(model, same, 'step', same['id'], field, value, quote, answer, turn, log)
                continue
            if len(p['steps']) >= LIMITS['steps']:
                drop(change, 'too many steps')
                continue
            who = '' if kind != 'task' else _role(p, change.get('who')) or (p['details'].get('owner') or {}).get('value', '')
            also = _role(p, change.get('with')) if kind == 'task' else ''
            step = {'id': _new_id(model, 's'), 'kind': kind, 'label': label, 'next': [], 'status': 'heard', 'read': False,
                    'who': who, 'with': '' if _norm(also) == _norm(who) else also,
                    'system': '' if kind != 'task' else _clean(change.get('system')), 'quotes': [], 'unknown': [],
                    **({'gateway': ''} if kind == 'decision' else {})}
            _quote(step, quote, turn)
            by_id = {s['id']: s for s in p['steps']}
            p['steps'].append(step)
            created.append(step['id'])
            if change.get('ref'):
                refs[str(change['ref'])] = step['id']
            before = next((s for s in p['steps'] if s['id'] == ref(change.get('before')) and s is not step), None) \
                if op == 'step' and change.get('before') else None
            if before is not None:
                # "Before locate product on the third path" (1 October, 21:39): just before it, on its path (PI F25).
                _link_before(p, step, before)
                log['applied'].append(step['id'])
                continue
            if anchor is not None and anchor['kind'] == 'open':
                # The first step of a path that was only named so far: it takes the path's place (PI F19).
                _take_over(p, anchor, step)
                log['applied'].append(step['id'])
                continue
            where = _link_after(p, step, after, by_id)
            if where == 'branch':
                placed_after_decision.append((ref(change.get('after')), step['id']))
            if kind == 'decision' and where not in ('start', 'loose', 'branch'):
                pass  # it took over what came next: that continuation stays as a branch until one is named
            log['applied'].append(step['id'])
        elif op == 'branch':
            p, decision, kind = find(model, ref(change.get('decision')))
            target = ref(change.get('to'))
            if decision is None or kind != 'step' or decision['kind'] != 'decision':
                drop(change, 'no such decision')
                continue
            condition = ' '.join(str(change.get('condition', '')).split())[:80]
            if target == 'end':
                target = _end_step(model, p, turn, quote)['id']
            elif target in ('open', '') and condition:
                # An option named before it is described ("there are three choices"): a path of its own, still open.
                if any(n['label'] and _norm(n['label']) == _norm(condition) for n in decision['next']):
                    log['applied'].append(f"{decision['id']}->({condition})")
                    continue
                target = _open_path(model, p, condition, quote, turn)['id']
            elif not any(s['id'] == target for s in p['steps']):
                drop(change, 'no such step')
                continue
            link = next((n for n in decision['next'] if n['to'] == target), None)
            if link is None:
                decision['next'].append({'to': target, 'label': condition})
            else:
                link['label'] = condition or link['label']
            _quote(decision, quote, turn)
            log['applied'].append(f"{decision['id']}->{target}")
        elif op == 'join':
            # "From there it's the same as the other path": this path continues into a step already described. "They all
            # come back together", with nothing said yet of what follows: every path that has not ended meets at a point
            # still to be described, from = "paths", to = "next", and Tibi asks what happens then (PI F23).
            source_ref, target_ref = ref(change.get('from')), ref(change.get('to'))
            p, source, kind = (focus_process(change), None, 'step') if source_ref == 'paths' else find(model, source_ref)
            if p is None or kind != 'step' or (source_ref != 'paths' and source is None):
                drop(change, 'no such step')
                continue
            if target_ref in ('next', 'paths'):  # "paths": the note-taker's other way of saying where they meet
                target = _meeting_point(p)
            else:
                _, target, target_kind = find(model, target_ref)
                if target is None or target_kind != 'step':
                    drop(change, 'no such step')
                    continue
            sources = _open_ends(p, target) if source_ref == 'paths' else [source]
            joined = [s for s in sources if s is not target and all(n['to'] == (target or {}).get('id') for n in s['next'])]
            if not joined:
                drop(change, 'that step already continues elsewhere')
                continue
            if target is None:
                target = _new_meeting_point(model, p, quote, turn)
            for s in joined:
                s['next'] = [{'to': target['id'], 'label': ''}]
                log['applied'].append(f"{s['id']}->{target['id']}")
        elif op == 'gateway':
            _, decision, kind = find(model, ref(change.get('decision')))
            value = str(change.get('kind', '')).strip().lower()
            if decision is None or kind != 'step' or decision['kind'] != 'decision' or value not in KINDS:
                drop(change, 'no such decision or kind')
                continue
            decision['gateway'] = value
            _quote(decision, quote, turn)
            log['applied'].append(f"{decision['id']}.gateway")
        elif op == 'repath':
            # "Those steps belong under the second option": said back first, made only on a yes (like a move).
            p, _, _ = find(model, ref(change.get('path')))
            items = [ref(i) for i in (change.get('items') or []) if isinstance(i, str)]
            steps = [s for s in (p['steps'] if p else []) if s['id'] in items and s['kind'] == 'task']
            _, path, path_kind = find(model, ref(change.get('path')))
            if not steps or path is None or path_kind != 'step' or path['kind'] not in ('open', 'decision'):
                drop(change, 'no such steps or path')
                continue
            proposal = {'op': 'repath', 'item': steps[0]['id'], 'items': [s['id'] for s in steps], 'path': path['id'],
                        'condition': ' '.join(str(change.get('condition', '')).split())[:80], 'quote': quote}
            model['proposed_change'] = {'id': f"c{turn}", 'ops': [*((model.get('proposed_change') or {}).get('ops') or []), proposal],
                                        'turn': turn}
            log['applied'].append(f"repath:{','.join(proposal['items'])}?")
        elif op == 'change':
            p, item, kind = find(model, ref(change.get('item')))
            field = change.get('field')
            if item is not None and not _pending_conflict(model, item['id'], field) and not meant(item):
                drop(change, 'the answer is not about that step')
                continue
            if item is not None and kind == 'step' and field in STEP_FIELDS and not said_in(change.get('value', ''), answer):
                drop(change, 'the answer does not say that')
                continue
            if item is not None and kind == 'step' and field == 'kind':
                # "Could you change that step into a trigger?" (PI F23; 1 October it was renamed "Trigger …" instead).
                value = str(change.get('value', '')).strip().lower()
                if item['kind'] not in STEP_KINDS or value not in STEP_KINDS:
                    drop(change, 'only a step or a trigger turns into the other')
                elif item['kind'] != value:
                    item.update(kind=value, status='heard', read=False)
                    _quote(item, quote, turn)
                    log['applied'].append(f"{item['id']}.kind")
            elif item is not None and kind == 'step' and field in STEP_FIELDS:
                _set(model, item, 'step', item['id'], field, change.get('value', ''), quote, answer, turn, log)
            elif item is not None and kind == 'process' and field in PROCESS_FIELDS:
                _set(model, item, 'process', item['id'], field, change.get('value', ''), quote, answer, turn, log)
            else:
                drop(change, 'no such step or field')
        elif op == 'settle':
            # Their answer to a conflict Tibi raised: keep what they said first, the new version, or both (in different
            # cases). Never guessed: only a conflict that is open, answered in their words.
            o = next((o for o in model['open'] if o['id'] == ref(change.get('open')) and o['kind'] == 'conflict'
                      and o['status'] != 'resolved'), None)
            keep = change.get('keep')
            if o is None or keep not in ('earlier', 'now', 'both'):
                drop(change, 'no such open conflict')
                continue
            owner, item, kind = find(model, o['item'])
            if keep == 'now' and item is not None:
                if kind == 'process':
                    item['details'][o['field']] = _field(o['now'], o.get('quote', quote), turn)
                elif o['field'] in STEP_FIELDS:
                    item[o['field']] = o['now']
                    _quote(item, quote, turn)
                log['corrected'].append({'item': o['item'], 'field': o['field'], 'was': o.get('earlier', ''), 'now': o['now']})
            if item is not None and kind == 'step':
                item['status'] = 'heard'
                item['read'] = False
            o.update(status='resolved', resolution=keep, resolved_turn=turn)
            log['resolved'].append(o['id'])
        elif op in ('exception', 'control'):
            p = focus_process(change)
            text = ' '.join(str(change.get('text', '')).split())[:200]
            bucket = p['exceptions' if op == 'exception' else 'controls']
            if not text or any(_norm(x['text']) == _norm(text) for x in bucket) or len(bucket) >= LIMITS['notes']:
                drop(change, 'empty, repeated or too many')
                continue
            at = ref(change.get('at'))
            entry = {'id': _new_id(model, 'x' if op == 'exception' else 'c'), 'text': text,
                     'at': at if any(s['id'] == at for s in p['steps']) else '', 'status': 'heard', 'quotes': []}
            if op == 'exception':
                entry['handling'] = ' '.join(str(change.get('handling', '')).split())[:200]
            _quote(entry, quote, turn)
            bucket.append(entry)
            log['applied'].append(entry['id'])
        elif op == 'confirm':
            items = change.get('items') if isinstance(change.get('items'), list) else []
            for item_id in items:
                p, item, kind = find(model, ref(item_id))
                if item is not None and kind != 'process' and item.get('status') == 'heard':
                    item['status'] = 'confirmed'
                    log['confirmed'].append(item['id'])
        elif op == 'conflict':
            item_id = ref(change.get('item'))
            p, item, kind = find(model, item_id)
            field = change.get('field')
            if item is None:
                drop(change, 'no such item')
                continue
            if not meant(item):
                drop(change, 'the answer is not about that step')
                continue
            if kind == 'step' and field in STEP_FIELDS and not said_in(change.get('now', ''), answer):
                drop(change, 'the answer does not say that')
                continue
            if kind == 'process' and field in PROCESS_FIELDS:
                _set(model, item, 'process', item_id, field, change.get('now', ''), quote, '', turn, log)
            elif kind == 'step' and field in STEP_FIELDS:
                _set(model, item, 'step', item_id, field, change.get('now', ''), quote, '', turn, log)
            else:
                drop(change, 'no such field')
        elif op == 'unclear':
            item_id = ref(change.get('item'))
            text = ' '.join(str(change.get('text', '')).split())[:200]
            if text:
                _open(model, 'unclear', turn, item=item_id if find(model, item_id)[1] else '', field='', text=text, quote=quote)
                log['applied'].append('unclear')
        elif op in ('remove', 'move'):
            p, item, kind = find(model, ref(change.get('item')))
            before = ref(change.get('before')) if op == 'move' and change.get('before') else ''
            target = ref(change.get('after')) if op == 'move' and not before else ''
            ids = [t['id'] for t in p['steps']] if p else []
            where_ok = (before in ids and before != (item or {}).get('id')) if before else target in ('start', 'paths', *ids)
            if item is None or kind != 'step' or (op == 'move' and not where_ok):
                drop(change, 'no such step')
                continue
            if not (MOVE_CUE if op == 'move' else REMOVE_CUE).search(answer):
                drop(change, 'the answer does not ask for it')
                continue
            anchor = next((s for s in p['steps'] if s['id'] == (before or target)), None) if op == 'move' else None
            if anchor is not None and _norm(anchor['label']) == _norm(item['label']):
                drop(change, 'next to a step of the same name')  # "move Locate product to just before Locate product"
                continue
            if anchor is not None and (any(n['to'] == item['id'] for n in anchor['next']) if target else
                                       any(n['to'] == anchor['id'] for n in item['next'])):
                drop(change, 'already there')
                continue
            # Changing the shape of the process is said back first, and made only when they agree.
            where = {'before': before} if before else {'after': target} if op == 'move' else {}
            proposal = {'op': op, 'item': item['id'], **where, 'quote': quote}
            model['proposed_change'] = {'id': f"c{turn}", 'ops': [*((model.get('proposed_change') or {}).get('ops') or []), proposal],
                                        'turn': turn}
            log['applied'].append(f'{op}:{item["id"]}?')
        elif op == 'term':
            heard, means = _clean(change.get('heard')), _clean(change.get('means'))
            if not heard or not means or _norm(heard) == _norm(means):
                drop(change, 'no word')
                continue
            if not sounds_alike(heard, means):
                # "On the card machine, not on the till" corrects what was said about a step; it is not a misheard word,
                # so it is not replaced everywhere, only in the system of the steps the answer names (PI F14: the
                # receipt check had become "on card machine" too).
                targets = [s for p in model['processes'] for s in p['steps']
                           if s['id'] in named and s['system'] and _norm(heard) in _norm(s['system'])]
                if not targets:
                    drop(change, 'not a misheard word')
                    continue
                for step in targets:
                    _set(model, step, 'step', step['id'], 'system', means, quote, answer, turn, log)
                continue
            model.setdefault('glossary', {})[_norm(heard)] = means
            log['corrected'].extend(_replace_word(model, heard, means))
            log['applied'].append(f'term:{means}')
        elif op == 'unknown':
            p, item, kind = find(model, ref(change.get('item')))
            field = str(change.get('field', '')).strip().split()[0] if str(change.get('field', '')).strip() else ''
            if item is not None and field:
                item.setdefault('unknown', [])
                if field not in item['unknown']:
                    item['unknown'].append(field)
                log['applied'].append(f"{item['id']}.{field}?")
        else:
            drop(change, 'unknown change')
    # A step placed after a decision that no branch names: on that decision's path, to be labelled.
    if MERGE_CUE.search(answer):
        _merge_copies(model, created, log)
    proposal = model.get('proposed_change')
    meeting = [c for c in (proposal or {}).get('ops') or [] if c.get('op') == 'move' and c.get('after') == 'paths']
    if len(meeting) > 1:
        # Several steps proposed for where the paths meet, from one answer (21:46: six moves in one question): asked
        # instead, never said back as a list (PI F25).
        proposal['ops'] = [c for c in proposal['ops'] if c not in meeting]
        if not proposal['ops']:
            model['proposed_change'] = None
        _open(model, 'unclear', turn, item='', field='', text='Which step do the paths lead into, once they meet?', quote='')
        log['dropped'].append({'op': 'move', 'why': 'several steps for where the paths meet'})
    for decision_id, step_id in placed_after_decision:
        p, decision, _ = find(model, decision_id)
        if decision is not None and not any(n['to'] == step_id for n in decision['next']):
            decision['next'].append({'to': step_id, 'label': ''})
    model['turns'] = max(model['turns'], turn)
    return model, log


def what_changed(before: dict, after: dict) -> list[str]:
    """What a change did to the maps, said plainly: steps added (after which step, or on which path), taken out and
    renamed (PI F21: a requested change is said back, with undo offered, after "you broke it")."""
    said, old = [], {s['id']: s for p in before['processes'] for s in p['steps']}
    for p in after['processes']:
        into = {link['to']: (s, link['label']) for s in p['steps'] for link in s['next']}
        by_id = {s['id']: s for s in p['steps']}
        for step in p['steps']:
            if step['kind'] == 'open':
                if step.get('join') and step['id'] not in old:
                    said.append('joined the paths where they meet')
                continue
            if step['id'] not in old:
                came, label = into.get(step['id'], (None, ''))
                sources = [s for s in p['steps'] if s['kind'] != 'decision' and any(n['to'] == step['id'] for n in s['next'])]
                where = (' where the paths meet' if len(sources) > 1 else
                         f' on the path "{label}"' if came and came['kind'] == 'decision' and label else
                         f' after "{came["label"]}"' if came and came['kind'] != 'decision' else '')
                said.append(f'added {"the trigger " if step["kind"] == "event" else ""}"{step["label"]}"{where}')
            elif old[step['id']]['kind'] != step['kind'] and step['kind'] in STEP_KINDS:
                said.append(f'made "{step["label"]}" a {"trigger" if step["kind"] == "event" else "step"}')
            elif old[step['id']]['label'] != step['label']:
                said.append(f'renamed "{old[step["id"]]["label"]}" to "{step["label"]}"')
            elif not old[step['id']]['next'] and step['next'] and step['kind'] != 'decision':
                target = by_id.get(step['next'][0]['to'])
                if target is not None and target['id'] in old and target['kind'] != 'open':
                    said.append(f'joined "{step["label"]}" to "{target["label"]}"')
            elif step['kind'] == 'decision':
                # A path given its name ("the third path starts when the customer asks for an age-restricted product").
                was = {n['to']: n['label'] for n in old[step['id']]['next']}
                said += [f'named the path "{n["label"]}"' + (f' (it was "{was[n["to"]]}")' if was[n['to']] else '')
                         for n in step['next'] if n['to'] in was and n['label'] and was[n['to']] != n['label']]
            else:
                for field, word in (('who', 'who does'), ('with', 'who else takes part in'), ('system', 'the system for'),
                                    ('gateway', 'the kind of')):
                    if (old[step['id']].get(field) or '') != (step.get(field) or '') and step.get(field):
                        said.append(f'set {word} "{step["label"]}" to "{step[field]}"')
        was = next((q for q in before['processes'] if q['id'] == p['id']), None)
        for field, detail in p['details'].items():
            then = ((was or {}).get('details', {}).get(field) or {}).get('value')
            if detail.get('value') and detail.get('value') != then:
                said.append(f'set the {field} to "{detail["value"]}"')
    now = {s['id'] for p in after['processes'] for s in p['steps']}
    said += [f'taken out "{s["label"]}"' for i, s in old.items() if i not in now and s['kind'] != 'open']
    return said


def _paths_from_heads(changes: list) -> list:
    """The note-taker's habits with several paths described in one answer (PI F21; the Human's description of
    1 October): the first option's first step put "after start" beside its decision, options left "open" and then
    described under the decision, and a branch for every option naming that path's LAST step, one path named twice.
    Each branch is re-pointed to the first step of its path, an open option takes the path described for it, a path
    named twice keeps its first branch, and a first step a branch names is put under its decision. Only steps made in
    this answer are touched; paths that no branch names take the open options in the order both were given."""
    changes = [dict(c) for c in changes]
    made = {c['ref']: c for c in changes if c.get('op') in ('step', 'decision') and c.get('ref')}
    decisions = {r for r, c in made.items() if c['op'] == 'decision'}
    for c in changes:  # a first step "after start" beside its decision, which the branch names, is on its path
        target, d = made.get(c.get('to')), made.get(c.get('decision'))
        if c.get('op') == 'branch' and target and d and target['op'] == 'step' \
                and target.get('after') == 'start' and d.get('after') == 'start':
            target['after'] = c['decision']

    def head(ref, decision):
        seen = set()
        while ref in made and ref not in seen:
            seen.add(ref)
            if made[ref].get('after') == decision:
                return ref
            ref = made[ref].get('after')
        return None
    kept, named, opened = [], set(), {}
    for c in changes:
        d = c.get('decision')
        if c.get('op') != 'branch' or d not in decisions:
            kept.append(c)
            continue
        if c.get('to') in ('open', ''):
            opened.setdefault(d, []).append(c)
            kept.append(c)
            continue
        first = head(c.get('to'), d)
        if first is None:
            kept.append(c)
            continue
        if (d, first) in named:  # the same path named again
            continue
        named.add((d, first))
        same = next((o for o in opened.get(d, []) if _norm(o.get('condition', '')) == _norm(c.get('condition', ''))), None)
        if same is not None:  # the open option, now described
            opened[d].remove(same)
            same['to'] = first
            continue
        kept.append({**c, 'to': first})
    for d, open_options in opened.items():  # described paths no branch names take the open options, in order
        unnamed = [r for r, c in made.items() if c['op'] == 'step' and c.get('after') == d and (d, r) not in named]
        if open_options and len(unnamed) == len(open_options):
            for option, first in zip(open_options, unnamed):
                option['to'] = first
    return kept


def _replace_word(model, heard, means):
    """A misheard word, corrected ("tail" is "till"): replaced wherever it was written down."""
    pattern = re.compile(r'\b' + re.escape(heard) + r'\b', re.I)
    changed = []
    for p in model['processes']:
        for step in p['steps']:
            for field in STEP_FIELDS:
                if step.get(field) and pattern.search(step[field]):
                    was = step[field]
                    step[field] = pattern.sub(means, was)
                    changed.append({'item': step['id'], 'field': field, 'was': was, 'now': step[field]})
        for field, held in p['details'].items():
            if held.get('value') and pattern.search(held['value']):
                held['value'] = pattern.sub(means, held['value'])
        if pattern.search(p['name']):
            p['name'] = pattern.sub(means, p['name'])
    return changed


def edit(model: dict, change: dict, turn: int) -> tuple[dict, str]:
    """A change made on the map by hand, or a proposed change they agreed to: applied as it is, no quote needed. The
    Human's own edit counts as confirmed. Returns the new model and a plain description of what changed."""
    model = copy.deepcopy(model)
    op = change.get('op')
    if op == 'clear':
        return clear(model, change.get('item', ''))
    if op == 'continue':
        return _continue(model, change)
    p, item, kind = find(model, change.get('item', ''))
    if item is None or kind != 'step':
        raise ValueError('No such step')
    label = item['label']
    if op == 'gateway':
        kind_value = str(change.get('value', '')).strip().lower()
        if item['kind'] != 'decision' or kind_value not in KINDS:
            raise ValueError('Choose XOR, ANY or AND for a decision')
        item['gateway'] = kind_value
        item['status'] = 'confirmed'
        return model, f'"{label}" set to {GATEWAY_WORDS[kind_value]}'
    if op == 'repath':
        return _repath(model, p, change)
    if op == 'kind':
        value = str(change.get('value', '')).strip().lower()
        if item['kind'] not in STEP_KINDS or value not in STEP_KINDS:
            raise ValueError('Only a step or a trigger can be turned into the other')
        item.update(kind=value, status='confirmed')
        return model, f'made "{label}" a {"trigger" if value == "event" else "step"}'
    if op in ('label', 'who', 'system', 'with'):
        value = ' '.join(str(change.get('value', '')).split())[:160]
        if op == 'label' and not value:
            raise ValueError('A step needs a name')
        item[op] = value
        item['status'] = 'confirmed'
        return model, f'{op} of "{label}" set to "{value}"' if value else f'{op} of "{label}" cleared'
    if op == 'add':
        # A step added on the map after this one (PI F21: "I cannot really add anything where I want"): it takes over what
        # came next, as a step described there would; on a path only named so far, it takes the path's place.
        name = ' '.join(str(change.get('value', '')).split())[:120]
        if not name:
            raise ValueError('A step needs a name')
        if item['kind'] in ('decision', 'end'):
            raise ValueError('After a decision, add a path instead')
        added = _new_step(model, p, name, change)
        by_id = {s['id']: s for s in p['steps']}
        p['steps'].append(added)
        what = f'{"the trigger " if added["kind"] == "event" else ""}"{name}"'
        if change.get('before') and item['kind'] in STEP_KINDS:
            # "At the beginning of the third path": just before its first step, on that path (PI F25).
            _link_before(p, added, item)
            return model, f'added {what} just before "{label}"'
        if item['kind'] == 'open':
            _take_over(p, item, added)
            return model, f'added {what} ' + ('where the paths meet' if item.get('join') else f'on the path "{label}"')
        _link_after(p, added, item['id'], by_id)
        return model, f'added {what} after "{label}"'
    if op == 'remove':
        _detach(p, item)
        p['steps'] = [s for s in p['steps'] if s['id'] != item['id']]
        for bucket in ('exceptions', 'controls'):
            for note in p[bucket]:
                if note.get('at') == item['id']:
                    note['at'] = ''
        model['open'] = [o for o in model['open'] if o.get('item') != item['id']]
        return model, f'removed "{label}"'
    if op == 'move' and change.get('after') == 'paths':
        return _to_meeting(model, p, item)
    if op == 'move' and change.get('before'):
        target = next((s for s in p['steps'] if s['id'] == change['before']), None)
        if target is None or target['id'] == item['id']:
            raise ValueError('No such step to move it before')
        _detach(p, item)
        _link_before(p, item, target)
        item['status'] = 'confirmed'
        return model, f'moved "{label}" to just before "{target["label"]}"'
    if op == 'move':
        after = change.get('after', '')
        anchor = next((s for s in p['steps'] if s['id'] == after), None)
        if after != 'start' and (anchor is None or anchor['id'] == item['id']):
            raise ValueError('No such step to move it after')
        _detach(p, item)
        item['next'] = []
        by_id = {s['id']: s for s in p['steps'] if s['id'] != item['id']}
        _link_after(p, item, after, by_id)
        item['status'] = 'confirmed'
        return model, f'moved "{label}" to ' + ('the start' if after == 'start' else f'after "{anchor["label"]}"')
    if op == 'branch':
        # "Add a branch here": a decision after this step, its named case to a new first step, the usual case
        # to what already follows.
        question = ' '.join(str(change.get('question', '')).split())[:120] or 'Which way does it go?'
        first = ' '.join(str(change.get('first', '')).split())[:120]
        condition = ' '.join(str(change.get('condition', '')).split())[:80] or 'Otherwise'
        if not first:
            raise ValueError('Name the first step of the new branch')
        decision = {'id': _new_id(model, 's'), 'kind': 'decision', 'label': question, 'next': list(item['next']),
                    'status': 'confirmed', 'read': True, 'who': '', 'system': '', 'quotes': [], 'unknown': []}
        for link in decision['next']:
            link['label'] = link['label'] or 'Otherwise'
        step = {'id': _new_id(model, 's'), 'kind': 'task', 'label': first, 'next': [], 'status': 'confirmed', 'read': True,
                'who': '', 'system': '', 'quotes': [], 'unknown': []}
        decision['next'].insert(0, {'to': step['id'], 'label': condition})
        item['next'] = [{'to': decision['id'], 'label': ''}]
        p['steps'].extend([decision, step])
        return model, f'added a branch after "{label}": {condition}, "{first}"'
    raise ValueError('Unknown change')


GATEWAY_WORDS = {'xor': 'only one path (XOR)', 'or': 'any number of paths (ANY)', 'and': 'all paths (AND)'}


def _new_step(model, p, name, change):
    """A step or a trigger added by hand: confirmed, as the Human's own edit."""
    kind = 'event' if change.get('kind') == 'event' else 'task'
    return {'id': _new_id(model, 's'), 'kind': kind, 'label': name, 'next': [], 'status': 'confirmed', 'read': False,
            'who': (_role(p, change.get('who')) or '') if kind == 'task' else '', 'with': '', 'system': '', 'quotes': [],
            'unknown': []}


def _continue(model, change):
    """A step added where the flow is still being described (the map's "Still being described"): after every path that
    has not ended, where they meet (PI F23: "how can we move the Still being described box under the entire process
    map, as I wanted to continue with the process map")."""
    p = process(model, change.get('item', '')) or process(model, model.get('focus') or '')
    if p is None:
        raise ValueError('No such process')
    name = ' '.join(str(change.get('value', '')).split())[:120]
    if not name:
        raise ValueError('A step needs a name')
    step = _new_step(model, p, name, change)
    meet, ends = _meeting_point(p), _open_ends(p)
    if p['steps'] and meet is None and not ends:
        raise ValueError('Every path has ended: add the step after one of them instead')
    p['steps'].append(step)
    what = f'{"the trigger " if step["kind"] == "event" else ""}"{name}"'
    if meet is not None:
        _take_over(p, meet, step)
        return model, f'added {what} where the paths meet'
    if not ends:
        p['start'] = step['id']
        return model, f'added {what} as the first step'
    for tail in ends:
        tail['next'] = [{'to': step['id'], 'label': ''}]
    return model, f'added {what} ' + ('where the paths meet' if len(ends) > 1 else f'after "{ends[0]["label"]}"')


def _open_ends(p, exclude=None):
    """The steps the flow stops at for now: the last step of every path that has not ended (a path only named counts),
    never a decision, an end or a meeting point still to be described. ``exclude``: the step the paths are to lead to,
    left out with everything after it, so its own branches never lead back into it."""
    skip = _below(p, exclude) if exclude is not None else set()
    return [s for s in ordered_steps(p) if not s['next'] and s is not exclude and s['id'] not in skip
            and s['kind'] not in ('end', 'decision') and not s.get('join')]


def _merge_copies(model, created, log):
    """One step said to come after several paths, noted once for each ("all three paths ... after the basket there is a
    single step ... merge all those different options into single step": three "Confirm quantity limit", one after each
    basket, 1 October 21:46). Only when the answer says they merge; otherwise the same action on each path stays a step
    of its own (PI F19)."""
    for p in model['processes']:
        made = [s for s in p['steps'] if s['id'] in created and s['kind'] in STEP_KINDS]
        groups: dict = {}
        for s in made:
            groups.setdefault((s['kind'], _norm(s['label'])), []).append(s)
        for copies in groups.values():
            keep = copies[0]
            for copy_ in copies[1:]:
                for other in p['steps']:
                    other['next'] = [{'to': keep['id'], 'label': n['label']} if n['to'] == copy_['id'] else n
                                     for n in other['next']]
                keep['next'] = keep['next'] or [n for n in copy_['next'] if n['to'] != keep['id']]
                p['steps'] = [x for x in p['steps'] if x is not copy_]
                log['applied'] = [keep['id'] if a == copy_['id'] else a for a in log['applied']]
                log.setdefault('merged', []).append(f"{copy_['id']}={keep['id']}")
    # Each kept step is said once in the log.
    log['applied'] = list(dict.fromkeys(log['applied']))


def _below(p, step):
    """The ids of a step and of every step after it."""
    by_id = {s['id']: s for s in p['steps']}
    seen, stack = set(), [step['id']]
    while stack:
        current = stack.pop()
        if current in seen or current not in by_id:
            continue
        seen.add(current)
        stack.extend(n['to'] for n in by_id[current]['next'])
    return seen


def _to_meeting(model, p, item):
    """A step, and what follows it, moved to where the paths meet: every path that has not ended now leads to it (PI
    F25; 1 October, 21:44: "the review product step with everything below should move after all three paths merging
    together"). It leaves the path it was on, unless that path starts with it."""
    label = item['label']
    below = _below(p, item)
    for s in p['steps']:
        if s['id'] not in below and s['kind'] != 'decision':
            s['next'] = [n for n in s['next'] if n['to'] != item['id']]
    meet = _meeting_point(p)
    if meet is not None:
        _take_over(p, meet, item)
    ends = _open_ends(p, item)
    if meet is None and not ends:
        raise ValueError('There are no paths to bring together before it')
    for tail in ends:
        tail['next'] = [{'to': item['id'], 'label': ''}]
    item['status'] = 'confirmed'
    return model, f'moved "{label}", and what follows it, to where the paths meet'


def _meeting_point(p):
    return next((s for s in p['steps'] if s['kind'] == 'open' and s.get('join')), None)


def _new_meeting_point(model, p, quote, turn):
    """Where the paths meet before what follows them is described: a placeholder the next step takes over."""
    meet = {'id': _new_id(model, 's'), 'kind': 'open', 'join': True, 'label': JOIN_LABEL, 'next': [], 'status': 'heard',
            'read': True, 'who': '', 'with': '', 'system': '', 'quotes': [], 'unknown': []}
    _quote(meet, quote, turn)
    p['steps'].append(meet)
    return meet


def meets(p) -> set:
    """Steps two or more steps lead to: where paths meet."""
    count: dict = {}
    for s in p['steps']:
        for n in s['next']:
            count[n['to']] = count.get(n['to'], 0) + 1
    return {i for i, c in count.items() if c > 1}


def _repath(model, p, change):
    """Steps put on the wrong path, moved to the path they belong to: taken out where they are (what led to them now
    leads on), kept in their order, and placed where that path starts, or at its end if it has steps already."""
    order = {s['id']: n for n, s in enumerate(ordered_steps(p))}
    steps = sorted((s for s in p['steps'] if s['id'] in set(change.get('items') or []) and s['kind'] in STEP_KINDS),
                   key=lambda s: order.get(s['id'], 0))
    path = next((s for s in p['steps'] if s['id'] == change.get('path')), None)
    if not steps or path is None or path['kind'] not in ('open', 'decision'):
        raise ValueError('No such steps or path')
    for step in steps:
        _detach(p, step)
    for first, second in zip(steps, steps[1:]):
        first['next'] = [{'to': second['id'], 'label': ''}]
    steps[-1]['next'] = []
    for step in steps:
        step['status'] = 'confirmed'
    if path['kind'] == 'open':
        _take_over(p, path, steps[0])
        where = path['label']
    else:
        condition = ' '.join(str(change.get('condition', '')).split())[:80]
        link = next((n for n in path['next'] if condition and _norm(n['label']) == _norm(condition)), None)
        if link is None:
            path['next'].append({'to': steps[0]['id'], 'label': condition})
        else:
            by_id = {s['id']: s for s in p['steps']}
            joins = meets(p)  # a path's end is before the point where it meets the others
            tail = by_id.get(link['to'])
            while tail is not None and tail['next'] and tail['kind'] != 'open' and tail['next'][0]['to'] not in joins:
                tail = by_id.get(tail['next'][0]['to'])
            if tail is None or tail['kind'] == 'open':
                if tail is not None:
                    _take_over(p, tail, steps[0])
                else:
                    link['to'] = steps[0]['id']
            else:
                steps[-1]['next'] = list(tail['next'])
                tail['next'] = [{'to': steps[0]['id'], 'label': ''}]
        where = condition or path['label']
    names = ', '.join(f'"{s["label"]}"' for s in steps)
    return model, f'moved {names} to the path "{where}"'


def clear(model: dict, process_id: str) -> tuple[dict, str]:
    """Start a process again from scratch, once the participant has agreed (PI F21: "shall we start from scratch? Can
    you remove all those items?"). Its steps, details, exceptions and controls go, with what was raised or asked about
    them; the process's name and the participant stay."""
    model = copy.deepcopy(model)
    p = process(model, process_id)
    if p is None:
        raise ValueError('No such process')
    gone = {p['id'], *(s['id'] for s in p['steps']), *(x['id'] for x in p['exceptions']), *(c['id'] for c in p['controls'])}
    p.update(details={}, start=None, steps=[], exceptions=[], controls=[], unknown=[])
    raised = {o['id'] for o in model['open'] if o.get('item') in gone}
    model['open'] = [o for o in model['open'] if o['id'] not in raised]
    model['asked'] = {k: v for k, v in model['asked'].items() if k.split(':', 1)[-1] not in gone | raised}
    model.update(readback=None, proposed_change=None, wrapped=False)
    return model, f'cleared everything for "{p["name"] or "this process"}"'


def _detach(p, item):
    """Take a step out of the flow: whatever led to it now leads to what followed it."""
    following = item['next']
    for step in p['steps']:
        if step is item:
            continue
        links = []
        for link in step['next']:
            if link['to'] == item['id']:
                links.extend({'to': f['to'], 'label': link['label'] or f['label']} for f in following if f['to'] != step['id'])
            else:
                links.append(link)
        step['next'] = links
    if p.get('start') == item['id']:
        p['start'] = following[0]['to'] if following else next((s['id'] for s in p['steps'] if s is not item), None)


def describe(change: dict, model: dict) -> str:
    if change['op'] == 'clear':
        return f'clear everything captured for "{(process(model, change.get("item", "")) or {}).get("name") or "this process"}"'
    _, item, _ = find(model, change.get('item', ''))
    label = (item or {}).get('label', 'that step')
    if change['op'] == 'repath':
        names = ' and '.join(f'"{(find(model, i)[1] or {}).get("label", i)}"' for i in change.get('items') or [])
        _, path, _ = find(model, change.get('path', ''))
        where = change.get('condition') or (path or {}).get('label', 'that path')
        return f'move {names} to the path "{where}"'
    if change['op'] == 'remove':
        return f'remove "{label}"'
    if change.get('before'):
        _, anchor, _ = find(model, change['before'])
        return f'move "{label}" to just before "{(anchor or {}).get("label", "that step")}"'
    if change.get('after') == 'paths':
        return f'move "{label}", and what follows it, to where the paths meet'
    _, anchor, _ = find(model, change.get('after', ''))
    where = 'the start' if change.get('after') == 'start' else f'after "{(anchor or {}).get("label", "that step")}"'
    return f'move "{label}" to {where}'


def sounds_alike(heard: str, means: str) -> bool:
    """A misheard word is near the right one ("tail"/"till", "Tabaku"/"tobacco", "side stuff"/"site staff"); "till" for
    "card machine" is a different thing, not a mishearing."""
    a, b = _norm(heard), _norm(means)
    return _distance(a, b) <= max(2, (max(len(a), len(b)) + 1) // 2)


def _distance(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def snap(text: str, model: dict) -> str:
    """A name the recogniser nearly got ("BeePea" for "BeePee") is written as the interview knows it. Only names with
    capitals inside (BeePee, SAP, iPad), so ordinary words are never changed."""
    names = {w for term in vocabulary(model).split(', ') for w in term.split()
             if len(w) >= 4 and any(c.isupper() for c in w[1:])}
    if not names:
        return text

    def fix(match):
        word = match.group(0)
        for name in names:
            limit = 1 if len(name) <= 6 else 2
            if word != name and word[0].casefold() == name[0].casefold() and _distance(word.casefold(), name.casefold()) <= limit:
                return name
        return word
    return re.sub(r"[A-Za-z][A-Za-z'-]{2,}", fix, text)


def vocabulary(model: dict, limit: int = 380) -> str:
    """The interview's own words for the speech recogniser: the organisation, its processes, roles and systems, and
    every word the participant corrected."""
    terms = [model['space'].get('name', '')]
    terms += list((model.get('glossary') or {}).values())
    for p in model['processes']:
        terms.append(p['name'])
        for step in p['steps']:
            terms += [step.get('who', ''), step.get('system', '')]
    out, seen = [], set()
    for term in terms:
        term = ' '.join(str(term).split())
        if term and term.casefold() not in seen and len(', '.join([*out, term])) <= limit:
            seen.add(term.casefold())
            out.append(term)
    return ', '.join(out)


def _clean(value) -> str:
    value = ' '.join(str(value or '').split())[:80]
    return '' if value.casefold() in ('-', 'n/a', 'na', 'none', 'unknown') else value


def _add_process(model, name, quote, turn):
    p = {'id': _new_id(model, 'p'), 'name': name, 'status': 'planned', 'quote': quote, 'turn': turn, 'details': {},
         'start': None, 'steps': [], 'exceptions': [], 'controls': [], 'unknown': []}
    model['processes'].append(p)
    if model['focus'] is None:
        model['focus'] = p['id']
        p['status'] = 'active'
    return p


def _open_path(model, p, condition, quote, turn):
    """A path named but not yet described: a placeholder its first step will take over."""
    step = {'id': _new_id(model, 's'), 'kind': 'open', 'label': condition, 'next': [], 'status': 'heard', 'read': True,
            'who': '', 'with': '', 'system': '', 'quotes': [], 'unknown': []}
    _quote(step, quote, turn)
    p['steps'].append(step)
    return step


def _take_over(p, placeholder, step):
    """The step replaces an open path's placeholder: whatever led to the placeholder leads to the step."""
    for other in p['steps']:
        other['next'] = [{'to': step['id'], 'label': n['label']} if n['to'] == placeholder['id'] else n for n in other['next']]
    step['next'] = step['next'] or placeholder['next']
    p['steps'] = [s for s in p['steps'] if s['id'] != placeholder['id']]
    if p.get('start') == placeholder['id']:
        p['start'] = step['id']


def _end_step(model, p, turn, quote):
    end = next((s for s in p['steps'] if s['kind'] == 'end'), None)
    if end is None:
        end = {'id': _new_id(model, 's'), 'kind': 'end', 'label': 'End', 'next': [], 'status': 'heard', 'read': True,
               'who': '', 'system': '', 'quotes': [], 'unknown': []}
        _quote(end, quote, turn)
        p['steps'].append(end)
    return end


# ---- What the note-taker sees -------------------------------------------------------------------------------------

def view(model: dict) -> str:
    """The model as compact lines for the note-taker: ids, what each item says, its status and its quote."""
    people = model['participant']
    lines = ['participant: ' + (', '.join(f'{k}: {v["value"]}' for k, v in people.items()) or '(not yet known)')]
    for p in model['processes']:
        details = ''.join(f'; {k}: {v["value"]}' for k, v in p['details'].items())
        lines.append(f'{p["id"]} process "{p["name"] or "(unnamed)"}" [{p["status"]}]{details}')
        heads = {n['to']: (i, n['label']) for s in p['steps'] if s['kind'] == 'decision'
                 for i, n in enumerate(s['next'], start=1)}
        for s in ordered_steps(p):
            after = ', '.join((f'path {i} "{n["label"] or "otherwise"}": ' if s['kind'] == 'decision' else
                               f'{n["label"]}: ' if n['label'] else '') + n['to'] for i, n in enumerate(s['next'], start=1))
            quote = s['quotes'][0]['text'] if s['quotes'] else ''
            path = f' (first step of path {heads[s["id"]][0]})' if s['id'] in heads else ''
            who = (f' who: {s["who"] or "-"} with: {s.get("with") or "-"} system: {s["system"] or "-"}' if s['kind'] == 'task'
                   else f' kind: {s.get("gateway") or "not asked"}' if s['kind'] == 'decision'
                   else ' (a trigger)' if s['kind'] == 'event'
                   else ' (where the paths meet; what follows is not described yet)' if s.get('join')
                   else ' (a path named but not described yet)' if s['kind'] == 'open' else '')
            lines.append(f'  {s["id"]} {s["kind"]} "{s["label"]}"{path}{who} [{s["status"]}] next: {after or "-"} '
                         f'quote: "{quote[:120]}"')
        for x in p['exceptions']:
            lines.append(f'  {x["id"]} exception "{x["text"]}" at: {x["at"] or "-"}')
        for c in p['controls']:
            lines.append(f'  {c["id"]} control "{c["text"]}" at: {c["at"] or "-"}')
    for o in model['open']:
        if o['status'] != 'resolved':
            about = (f' {o["item"]}.{o["field"]}: "{o.get("earlier", "")}" vs "{o.get("now", "")}"' if o['kind'] == 'conflict'
                     else f' {o.get("text", "")}')
            lines.append(f'{o["id"]} open {o["kind"]}{about}')
    return '\n'.join(lines)


# ---- What Tibi asks next (PI F2) -----------------------------------------------------------------------------------

def _asked(model, key):
    return model['asked'].get(key, 0)


def _third_person(label):
    """"Check stock report" -> "checks stock report": the step's verb for a read-back sentence."""
    first, _, rest = label.strip().partition(' ')
    word = first.lower()
    if not word.isalpha():
        return label[0].lower() + label[1:]
    if _base(word) in VERBS:  # already said that way ("Records sales")
        verb = word
    elif word.endswith(('s', 'sh', 'ch', 'x', 'z', 'o')):
        verb = word + 'es'
    elif word.endswith('y') and len(word) > 1 and word[-2] not in 'aeiou':
        verb = word[:-1] + 'ies'
    else:
        verb = word + 's'
    return f'{verb} {rest}'.strip()


def _base(word):
    """"brings" -> "bring", "reaches" -> "reach", "carries" -> "carry"; "" when the word has no -s."""
    if len(word) < 4 or not word.endswith('s') or word.endswith('ss'):
        return ''
    if word.endswith('ies'):
        return word[:-3] + 'y'
    if word[:-2] in VERBS and word.endswith('es'):
        return word[:-2]
    return word[:-1]


def names_subject(label):
    """"Customer brings item to service desk" names who does it; "Check receipt on till" does not."""
    words = label.casefold().split()
    if len(words) < 2:
        return False
    verb = _base(words[1])
    return verb in VERBS and (words[0] not in VERBS or verb in ARRIVING)


def _say(step):
    label_words = step['label'].casefold().split()
    if names_subject(step['label']):
        # Said as it is, with "the" for a role ("the customer brings item…"), bare for a department or a named owner.
        first = step['label'].split()[0]
        named = step['who'][:1].isupper() and step['who'].split()[0].casefold() == first.casefold()
        if named or first.casefold() in DEPARTMENTS or label_words[0] in ('the', 'a', 'an'):
            return first + step['label'][len(first):] if named else step['label'][0].lower() + step['label'][1:]
        return 'the ' + step['label'][0].lower() + step['label'][1:]
    if label_words and step['who'] and label_words[0] in step['who'].casefold().split():
        # A label that names its owner ("Buyer helps with big orders") is said as it is.
        said = step['label'][0].lower() + step['label'][1:]
        return f'the {said}' if not said.startswith(('the ', 'a ', 'an ')) else said
    who = step['who'] or 'someone'
    # "the store manager", "the supplier", but "finance", "IT", "Sam": no article for a department or a name.
    if (not who.lower().startswith(('the ', 'a ', 'an ')) and not who[:1].isupper()
            and who.casefold() not in DEPARTMENTS):
        who = f'the {who}'
    by = step['system'] and step['system'].casefold() in ('email', 'e-mail', 'phone', 'telephone', 'post', 'letter', 'hand')
    system = f' {"by" if by else "in"} {step["system"]}' if step['system'] and _norm(step['system']) not in _norm(step['label']) else ''
    also = step.get('with') or ''
    together = f', with the {also},' if also and not also[:1].isupper() else f', with {also},' if also else ''
    return f'{who}{together} {_third_person(step["label"])}{system}'


def _trigger(step):
    """A trigger as part of a sentence: "it triggers age verification check"."""
    return f'it triggers {step["label"][0].lower() + step["label"][1:]}'


# ---- Read-backs told as the story of the work (PI F26) --------------------------------------------------------------
# The Human, 1 October: read-backs read "precisely what each step is ... at speed with many steps can get confusing ... it
# should use natural language to describe what is happening ... like a narrator that then pays attention where we are on
# the map to keep listener focused and not lost." Still made from the map by code, never by a model, so a read-back never
# adds or drops a step: what the same person does runs on in one sentence, a place said twice is said once, and signposts
# say where on the map we are. Each part of a read-back names the steps it tells, so the map can light them up while
# Tibi speaks.

ARTICLELESS = {'the', 'a', 'an', 'their', 'his', 'her', 'its', 'this', 'that', 'these', 'those', 'any', 'each', 'every',
               'some', 'all', 'it', 'them', 'what', 'which', 'who', 'whom', 'whose', 'whether', 'if', 'how', 'when', 'where',
               'one', 'no', 'another', 'our', 'your', 'my', 'both', 'either', 'they', 'he', 'she', 'we', 'you', 'more',
               'less', 'other', 'others', 'up', 'down', 'out', 'back', 'away', 'over', 'again', 'together', 'and', 'or'}
PLACES = {'on', 'in', 'into', 'onto', 'to', 'from', 'at', 'for', 'with', 'by', 'via', 'under', 'off', 'behind', 'inside',
          'within', 'through'}
PARTICLES = {'out', 'up', 'off', 'back', 'down', 'over', 'away', 'through'}
CONNECTORS = ('Then', 'After that,', 'Next,', 'Once that is done,')
COLUMNS = {2: ('left-hand', 'right-hand'), 3: ('left-hand', 'middle', 'right-hand')}
COUNTS = {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five', 6: 'six'}
WH = ('what', 'which', 'who', 'whom', 'whose', 'how', 'where', 'when', 'why', 'whether')
GATEWAYS = {'xor': 'Only one of them applies each time.', 'or': 'Any number of them can apply at once.',
            'and': 'All of them happen.'}


def _sentence(text):
    text = ' '.join(text.split())
    return text[:1].upper() + text[1:] + ('' if text.endswith(('.', '?', '!')) else '.')


def _lower_first(text):
    """"Customer comes to the till" -> "customer comes to the till"; "SAP" and "BeePee" keep their capitals."""
    first = text.split(' ', 1)[0]
    if len(first) > 1 and (first.isupper() or first[1:] != first[1:].lower()):
        return text
    return text[:1].lower() + text[1:]


def _scene(trigger):
    """What starts the process, as said after "It starts when": "customer comes to the till" -> "a customer comes to the
    till"."""
    said = _lower_first(trigger)
    first = said.split(' ', 1)[0].casefold()
    if names_subject(said) and first not in ARTICLELESS and said[:1].islower():
        return f'a {said}'
    return said


def _who(step):
    """Who does a step, as said: "the store manager", but "finance", "IT", "Sam"."""
    who = step.get('who') or ''
    if not who:
        return 'someone'
    if who.lower().startswith(('the ', 'a ', 'an ')) or who[:1].isupper() or who.casefold() in DEPARTMENTS:
        return who
    return f'the {who}'


def _phrase(step):
    """What a step does, said after who does it: "Scan product on point of sale" -> "scans the product on the point of
    sale". Anyone else taking part, and the system, follow unless the step's name says them already."""
    words = _third_person(step['label']).split()
    out, object_next = [], False
    for n, word in enumerate(words):
        lower = word.casefold()
        if n == 0:
            out.append(word)
            object_next = True
            continue
        if n == 1 and lower in PARTICLES and len(words) > 2:  # "carries out", "puts back"
            out.append(word)
            continue
        infinitive = out[-1].casefold() == 'to' and lower in VERBS  # "to send", but "the order"
        if (object_next and word[:1].isalpha() and not word[:1].isupper() and lower not in ARTICLELESS
                and lower not in PLACES and not infinitive and not lower.endswith('ing')):
            out.append('the')
        out.append(word)
        object_next = lower in PLACES
    phrase = ' '.join(out)
    named = set(_norm(step['label']).split())
    also = step.get('with') or ''
    if also and not set(_norm(also).split()) & named:
        phrase += f' with {also}' if also[:1].isupper() else f' with the {also}'
    system = step.get('system') or ''
    if system and _norm(system) not in _norm(step['label']) and _norm(system) != _norm(step.get('who') or ''):
        # "in SAP", "by email", "on the point of sale"; never the system again when it is the one doing the step.
        if system.casefold() in ('email', 'e-mail', 'phone', 'telephone', 'post', 'letter', 'hand'):
            phrase += f' by {system}'
        elif system[:1].isupper() or system.casefold().startswith(('the ', 'a ', 'an ')):
            phrase += f' in {system}'
        else:
            phrase += f' on the {system}'
    return phrase


def _place_once(phrases):
    """"scans the product on the point of sale and confirms it on the point of sale": a place said by two steps in a row
    is said once, by the second."""
    def endings(phrase):
        words = phrase.split()
        return {' '.join(words[i:]) for i in range(1, len(words)) if words[i].casefold() in PLACES}
    out = list(phrases)
    for n in range(len(out) - 1):
        shared = endings(out[n]) & endings(out[n + 1])
        if shared:
            place = max(shared, key=len)
            out[n] = out[n][:-len(place) - 1]
    return out


def _it(phrases):
    """"locates the product ..., scans the product ...": the second time, "it"."""
    out, last = [], None
    for phrase in phrases:
        words = phrase.split()
        start = 2 if len(words) > 2 and words[1].casefold() in PARTICLES else 1
        end = next((i for i in range(start, len(words)) if words[i].casefold() in PLACES), len(words))
        thing = ' '.join(words[start:end])
        if thing and thing == last and thing.startswith('the ') and len(thing.split()) <= 3:
            phrase = ' '.join(words[:start] + ['it'] + words[end:])
        last = thing or last
        out.append(phrase)
    return out


def _gerund(step):
    """"adds the product to the basket" -> "adding the product to the basket"."""
    words = _phrase(step).split()
    base = _base(words[0].casefold()) or words[0].casefold()
    if base.endswith('ie'):
        doing = base[:-2] + 'ying'
    elif base.endswith('e') and not base.endswith(('ee', 'ye', 'oe')):
        doing = base[:-1] + 'ing'
    elif len(base) <= 4 and re.fullmatch(r'[^aeiou]*[aeiou][^aeiouwxy]', base):
        doing = base + base[-1] + 'ing'
    else:
        doing = base + 'ing'
    return ' '.join([doing, *words[1:]])


def _tell(steps, first='', notes=None):
    """Steps in a row as sentences: what the same person does runs on, three things at most to a sentence; a trigger or
    the end is a sentence of its own. Returns [(sentence, step ids)]. ``first``: how the first sentence opens; ``notes``:
    the checks and watch points by step, said after the sentence that tells their step."""
    out, group = [], []

    def opener():
        return CONNECTORS[(len(out) - 1) % len(CONNECTORS)] + ' ' if out else first

    def flush():
        if group:
            phrases = _it(_place_once([_phrase(s) for s in group]))
            body = phrases[0] if len(phrases) == 1 else ', '.join(phrases[:-1]) + ' and ' + phrases[-1]
            out.append((_sentence(f'{opener()}{_who(group[0])} {body}'), [s['id'] for s in group]))
            group.clear()
    for step in steps:
        if step['kind'] == 'task' and not names_subject(step['label']):
            if group and (len(group) >= 3 or _norm(_who(group[0])) != _norm(_who(step))):
                flush()
            group.append(step)
            continue
        flush()
        if step['kind'] == 'task':
            out.append((_sentence(f'{opener()}{_say(step)}'), [step['id']]))
        elif step['kind'] == 'event':
            out.append((_sentence(f'{opener() or "First "}comes a trigger: {_lower_first(step["label"])}'), [step['id']]))
        elif step['kind'] == 'end':
            out.append(('And that is where it ends.', [step['id']]))
        elif step['kind'] == 'open' and not step.get('join'):
            out.append(('It is not described yet.', [step['id']]))
    flush()
    # The last of three or more says so, as the Digital SME's spoken answers do ("Finally, ...").
    last = out[-1][0] if len(out) >= 3 else ''
    lead = next((c for c in CONNECTORS if last.startswith(c + ' ')), None)
    if lead:
        out[-1] = ('Finally, ' + last[len(lead) + 1:], out[-1][1])
    if notes:
        out = [said for sentence in out for said in [sentence, *((note, [i]) for i in sentence[1] for note in notes.get(i, []))]]
    return out


def _watch_points(p):
    """The checks and what goes wrong, by the step they belong to ("" for the process as a whole), said the way the
    Classic Digital SME's walkthrough says them ("This step is governed by ...", "Watch point: ...")."""
    notes = {}
    for control in p.get('controls') or []:
        notes.setdefault(control.get('at') or '', []).append(f'There is a check there: {_lower_first(control["text"].rstrip("."))}.')
    for exception in p.get('exceptions') or []:
        handling = (f', and then {_lower_first(exception["handling"].rstrip("."))}' if exception.get('handling') else '')
        notes.setdefault(exception.get('at') or '', []).append(
            f'Watch point: {_lower_first(exception["text"].rstrip("."))}{handling}.')
    return notes


def _story(sentences):
    """The sentences as spoken parts, one a sentence so the map follows the story: a way's title is said with the
    sentence after it (and lights its whole way), "Is that right?" with the one before. Returns the text and the parts,
    each with the steps it tells."""
    parts, carry = [], None
    for text, ids, glue in sentences:
        if carry is not None:  # "Otherwise," runs on into its sentence: "Otherwise, finance approves the order."
            joined = _lower_first(text) if carry[0].endswith(',') else text
            text, ids, carry = f'{carry[0]} {joined}', list(dict.fromkeys([*carry[1], *ids])), None
        if glue == 'next':
            carry = (text, ids)
        elif glue == 'prev' and parts:
            parts[-1]['text'] += ' ' + text
        else:
            parts.append({'text': text, 'steps': ids})
    if carry is not None:
        parts.append({'text': carry[0], 'steps': carry[1]})
    return {'text': ' '.join(part['text'] for part in parts), 'parts': parts}


def _question(decision, count, columns=False):
    """A decision as said: "What happens next depends on what kind of product is requested, and there are three ways it
    can go." Columns: where the ways are on the map, for the first split."""
    q = decision['label'].strip().rstrip('?').strip()
    ways = 'one way so far' if count == 1 else f'{COUNTS.get(count, count)} ways it can go'
    if q.split(' ', 1)[0].casefold() in WH:
        said = f'What happens next depends on {_lower_first(q)}, and there {"is" if count == 1 else "are"} {ways}.'
    else:
        said = f'Then the question is: {_lower_first(q)}? There {"is" if count == 1 else "are"} {ways}.'
    if decision.get('gateway') in GATEWAYS:
        said += ' ' + GATEWAYS[decision['gateway']]
    if columns and count in COLUMNS:
        said += f' On the map, they are the {COUNTS[count]} columns under that question.'
    return said


def _inner_way(link, said):
    """A way of a question further down, said by its condition: "Has quantity limit: the cashier checks it." """
    condition = link['label'].strip().rstrip('.') or 'Otherwise'
    text = ' '.join(said)
    text = 'not described yet.' if text == 'It is not described yet.' else _lower_first(text)
    return f'{condition[:1].upper() + condition[1:]}: {text}'


def _way(link, n, count):
    """How a way is introduced: "First: e-cigarette or tobacco product." """
    condition = link['label'].strip().rstrip('.')
    if not condition or _norm(condition) in ('otherwise', 'else', 'anything else'):
        return 'Otherwise,' if n == count else f'{ORDINALS[n - 1].capitalize() if n <= len(ORDINALS) else n}: otherwise.'
    return f'{ORDINALS[n - 1].capitalize() if n <= len(ORDINALS) else f"Way {n}"}: {_lower_first(condition)}.'


def _tell_way(by_id, link, joins, notes=None, depth=0):
    """One way from its first step: its sentences (each with its steps), then any question on it with each of its ways,
    briefly. Returns the sentences, all the way's steps, where it meets the others (if it does), and its last step."""
    if link['to'] in joins:
        return [('It goes straight on to where the routes meet.', [])], [], link['to'], None
    steps = _chain(by_id, link['to'], None, joins)
    told = _tell([s for s in steps if s['kind'] != 'decision'], notes=notes)
    ids = [i for _, x in told for i in x]
    last = steps[-1] if steps else None
    met = None
    if last is not None and last['kind'] == 'decision':
        ids.append(last['id'])
        told.append((_question(last, len(last['next'])), [last['id']]))
        if depth < 1:
            for inner in last['next']:
                said, inner_ids, _, _ = _tell_way(by_id, inner, joins, notes, depth + 1)
                told.append((_inner_way(inner, [t for t, _ in said]), inner_ids))
                ids += inner_ids
    elif last is not None and last['next'] and last['next'][0]['to'] in joins:
        met = last['next'][0]['to']
    return told, ids, met, last


def narrate(model: dict, which: int | None = None) -> dict:
    """The process in focus, told as the story of the work (PI F26): what starts it, what happens up to the first
    question, each way it can go, and what happens once the ways meet again, with signposts to the map and the checks
    and watch points where they belong. ``which``: only that way (counting from 1). Returns the text and its parts,
    one a sentence, each with the steps it tells, so the map can follow the story."""
    p = process(model, model['focus']) if model['focus'] else None
    if p is None or not p['steps']:
        text = "I haven't captured any steps yet. Shall we start from the beginning?"
        return {'text': text, 'parts': [{'text': text, 'steps': []}]}
    by_id = {s['id']: s for s in p['steps']}
    name = p['name'] or 'this process'
    trigger = (p['details'].get('trigger') or {}).get('value', '').strip().rstrip('.')
    head = _chain(by_id, p.get('start'), None)
    decision = head[-1] if head and head[-1]['kind'] == 'decision' else None
    lead = [s for s in head if s['kind'] != 'decision']
    notes = _watch_points(p)
    told_ids = set()
    sentences = []

    def say(told, glue=None):
        for text, ids in told:
            sentences.append((text, ids, glue))
            told_ids.update(ids)
    if which is None:
        say([(f'Let me walk you through {name} as I have it, and stop me at any point.', [])])
        if trigger:
            say([(f'It starts when {_scene(trigger)}.', ['start'])])
        say(_tell(lead, first='First ' if trigger else '', notes=notes))
        if decision is not None:
            say([(_question(decision, len(decision['next']), columns=True), [decision['id']])])
    if decision is None:
        last = head[-1] if head else None
        if last is None or last['kind'] != 'end':
            say([('What happens after that is still to be described.', ['end'])])
        say([(note, []) for note in notes.get('', [])])
        say([('Is that right?', [])], 'prev')
        return _story(sentences)
    paths = decision['next']
    if which is not None and not (1 <= which <= len(paths)):
        text = (f'I have {len(paths)} path{"s" if len(paths) != 1 else ""} so far, so there is no option {which} yet. '
                'Which one did you mean?')
        return {'text': text, 'parts': [{'text': text, 'steps': []}]}
    joins = meets(p)
    chosen = list(enumerate(paths, start=1)) if which is None else [(which, paths[which - 1])]
    met, lasts = set(), []
    for n, link in chosen:
        told, ids, meeting, last = _tell_way(by_id, link, joins, notes)
        say([(_way(link, n, len(paths)), ids)], 'next')  # the way lights up as it is named
        say(told)
        if which is None and len(paths) in COLUMNS:
            say([(f'That is the {COLUMNS[len(paths)][n - 1]} column.', ids)])
        if meeting:
            met.add(meeting)
        lasts.append(last)
    if which is None and len(met) == 1:
        meeting = by_id[next(iter(met))]
        if meeting.get('join'):
            say([('The routes then come back together further down the map, and what happens after that is still to be '
                  'described.', [meeting['id']])])
        else:
            after = _chain(by_id, meeting['id'], None, joins - {meeting['id']})
            told = _tell([s for s in after if s['kind'] != 'decision'], first='after that ', notes=notes)
            if told:
                told[0] = ('The routes then come back together further down the map, and ' + _lower_first(told[0][0]),
                           told[0][1])
            say(told or [('The routes then come back together further down the map.', [meeting['id']])])
            if after and after[-1]['kind'] == 'decision':
                question = after[-1]
                say([(_question(question, len(question['next'])), [question['id']])])
                for inner in question['next']:
                    said, inner_ids, _, _ = _tell_way(by_id, inner, joins - {meeting['id']}, notes, depth=1)
                    say([(_inner_way(inner, [t for t, _ in said]), inner_ids)])
    elif which is None:
        ends = [s for s in lasts if s is not None and s['kind'] in STEP_KINDS and not s['next']]
        if len(ends) == len(lasts) >= 2 and len({_norm(s['label']) for s in ends}) == 1:
            say([(f'So whichever way it goes, it ends with {_who(ends[0])} {_gerund(ends[0])}.', [s['id'] for s in ends])])
        if ends:
            say([('What happens after that is still to be described.', ['end'])])
    if which is None:
        # Checks and watch points not tied to a step told above: said once, at the end.
        say([(note, []) for at, said in notes.items() if at not in told_ids for note in said])
    say([('Is that right?', [])], 'prev')
    return _story(sentences)


def readback_sentences(model, ids, limit=6):
    """The latest steps as sentences, told the same way as a whole read-back: exactly what was captured."""
    steps = [item for item in (find(model, i)[1] for i in ids) if item and item.get('kind') not in ('end', 'open')]
    by_id = {s['id']: s for p in model['processes'] for s in p['steps']}
    # A step on a decision's branch is said with the decision, not again after it.
    on_branch = {link['to'] for s in steps if s['kind'] == 'decision' for link in s['next'] if link['label']}
    steps = [s for s in steps if s['id'] not in on_branch or s['kind'] == 'decision'][:limit]
    sentences, run = [], []
    for step in steps:
        if step['kind'] != 'decision':
            run.append(step)
            continue
        sentences += [t for t, _ in _tell(run, first='First ' if not sentences else 'Then ')]
        run = []
        ways = []
        for link in sorted(step['next'], key=lambda n: (not n['label'] or n['label'].casefold().startswith('otherwise'))):
            target = by_id.get(link['to'])
            if target is None:
                continue
            what = ('it ends' if target['kind'] == 'end' else _lower_first(_tell([target])[0][0].rstrip('.'))
                    if target['kind'] in ('task', 'event') else 'not described yet' if target['kind'] == 'open'
                    else target['label'])
            ways.append(f'{link["label"] or "otherwise"}, {what}')
        question = step['label'].rstrip('?')
        sentences.append(f'{"Then" if sentences else "First"} there is a decision, {_lower_first(question)}' +
                         (f': {"; ".join(ways)}.' if ways else '.'))
    sentences += [t for t, _ in _tell(run, first='First ' if not sentences else 'Then ')]
    return ' '.join(sentences).removesuffix('.')


def _steps_text(steps, limit=4):
    parts = []
    for s in steps[:limit]:
        if s['kind'] == 'decision':
            parts.append(f'then a decision: {s["label"].rstrip("?")}?')
        elif s['kind'] == 'task':
            who = f'{s["who"]} ' if s['who'] else ''
            system = f' in {s["system"]}' if s['system'] else ''
            parts.append(f'{who}{s["label"][0].lower() + s["label"][1:]}{system}'.strip())
        elif s['kind'] == 'event':
            parts.append(f'the trigger "{s["label"]}"')
    return '; '.join(parts)


def goals(model: dict, limit: int = 3) -> list[dict]:
    """What to ask next, in order: the first few goals the model's gaps call for. Tibi's reply takes the first one
    the latest answer has not already covered. Each goal has a key (never asked more than twice) and an instruction."""
    out: list[dict] = []

    def add(key, ask, once=False, readback=None):
        if _asked(model, key) >= (1 if once else 2) or any(g['key'] == key for g in out):
            return
        out.append({'key': key, 'ask': ask, **({'readback': readback} if readback else {})})

    proposal = model.get('proposed_change')
    if proposal:
        # Said back exactly, from the model; made only on a yes (PI F9).
        what = ' and '.join(describe(change, model) for change in proposal['ops'])
        add(f'change:{proposal["id"]}', f'So you would like me to {what}. Shall I?', readback=[])
    conflict = next((o for o in model['open'] if o['kind'] == 'conflict' and o['status'] != 'resolved'), None)
    if conflict is not None:
        _, item, kind = find(model, conflict['item'])
        what = (item.get('label') if kind == 'step' else item.get('name', '')) if item else conflict['item']
        add(f'conflict:{conflict["id"]}',
            f'Check a difference, without saying either is wrong: for "{what}", {conflict["field"]} was earlier '
            f'"{conflict.get("earlier", "")}" and now "{conflict.get("now", "")}". '
            'Ask which is right, or whether both happen in different cases.')
    unclear = next((o for o in model['open'] if o['kind'] == 'unclear' and o['status'] == 'open'), None)
    if unclear is not None:
        add(f'unclear:{unclear["id"]}', f'Ask gently: {unclear["text"]}')
    people = model['participant']
    if 'name' not in people:
        add('name', 'Ask their name.')
    if 'role' not in people:
        add('role', 'Ask what their role is.')
    if 'team' not in people and 'name' in people and 'role' in people:
        add('team', 'Ask which team or part of the organisation they work in.', once=True)
    if not model['processes']:
        add('agenda', 'Ask which processes they would like to talk about today.')
        return out[:limit]
    p = process(model, model['focus']) or model['processes'][0]
    name = p['name'] or 'this process'
    if not p['name']:
        add(f'pname:{p["id"]}', 'Ask what they call this process.')
    planned = [q for q in model['processes'] if q['status'] == 'planned' and q is not p and q['id'] != model.get('proposed')]
    if len(model['processes']) == 1 and not p['steps']:
        add('more_processes', f'Ask whether there are other processes to cover, or whether to start with {name}.', once=True)
    steps = ordered_steps(p)
    tasks = [s for s in steps if s['kind'] == 'task']
    unread = [s for s in steps if s['kind'] != 'end' and s['status'] == 'heard' and not s.get('read')]
    if len(unread) >= READBACK_AFTER:
        unread = unread[:READBACK_AFTER]
        add(f'readback:{"-".join(s["id"] for s in unread)}',
            f'Read these steps back in one short sentence and ask if that is right: {_steps_text(unread)}.',
            readback=[s['id'] for s in unread])
    if 'purpose' not in p['details'] and 'purpose' not in p['unknown']:
        add(f'purpose:{p["id"]}', f'Ask what {name} is for: what it achieves.', once=True)
    if 'trigger' not in p['details'] and 'trigger' not in p['unknown']:
        add(f'trigger:{p["id"]}', f'Ask what starts {name}: what sets it off.')
    if not steps:
        add(f'walk:{p["id"]}', f'Ask them to walk you through {name} from the very start, step by step.')
    nobody = [s for s in tasks if not s['who'] and 'who' not in s['unknown']]
    if nobody and not _asked(model, f'owners:{p["id"]}'):
        named = ', '.join(f'"{s["label"]}"' for s in nobody[:3])
        add(f'owners:{p["id"]}', f'Ask who does {named}: the same person throughout, or different people?', once=True)
    for s in steps:
        if s['kind'] == 'decision' and len(s['next']) < 2:
            add(f'branch:{s["id"]}', f'Ask what happens otherwise, at the decision "{s["label"]}".')
        elif s['kind'] == 'decision':
            by_id = {t['id']: t for t in steps}
            unnamed = next((n for n in s['next'] if not n['label'] and n['to'] in by_id), None)
            if unnamed is not None:
                add(f'when:{s["id"]}:{unnamed["to"]}',
                    f'Ask when, at "{s["label"]}", it goes on to "{by_id[unnamed["to"]]["label"]}".', once=True)
    for s in steps:
        paths = [n for n in s['next'] if n['label']]
        if s['kind'] == 'decision' and len(paths) >= 2 and not s.get('gateway'):
            options = ', '.join(f'"{n["label"]}"' for n in paths[:4])
            add(f'kind:{s["id"]}', f'Ask whether more than one of these can apply at the same time ({options}), or only ever '
                                   'one. (Only one, any number, or all of them.)', once=True)
    tails = [s for s in steps if not s['next'] and s['kind'] in STEP_KINDS]
    meeting = _meeting_point(p)
    # Described to the end: every open path has an end, or Tibi has asked what follows it. An end on one branch
    # ("if not, it stops there") does not end the others; paths that meet carry on from there.
    complete = bool(steps) and meeting is None and (not tails or all(_asked(model, f'next:{t["id"]}') for t in tails))
    branched = any(s['kind'] == 'decision' for s in steps)
    if steps and tails:
        if branched and len(tails) > 1:
            # One question for all of them first (PI F23: "it joins with the rest of the process and then there is
            # another step"); each path is asked about on its own only if that does not settle it.
            add(f'meet:{p["id"]}', 'Ask whether the paths end where they are, or meet again and carry on; and if they carry '
                                   'on, what happens next.', once=True)
        for tail in tails:
            if branched and len(tails) > 1:
                add(f'next:{tail["id"]}', f'Ask what happens after "{tail["label"]}": does that path end there, or join back '
                                          'into the rest of the process, and where?')
            else:
                add(f'next:{tail["id"]}', f'Ask what happens after "{tail["label"]}", or whether that is the end.')
    # A path only named so far: walked through once the one being described has ended (PI F19).
    if not tails or all(_asked(model, f'next:{t["id"]}') for t in tails):
        waiting = next((s for s in steps if s['kind'] == 'open' and not s.get('join')), None)
        if waiting is not None:
            add(f'path:{waiting["id"]}', f'Ask them to walk through the path "{waiting["label"]}": what happens first?')
        elif meeting is not None:
            add(f'after:{meeting["id"]}', 'Ask what happens next, once the paths have met.')
    # Systems: asked once for the process (which steps use one), not step by step (PI F12).
    unsure = [s for s in tasks if not s['system'] and 'system' not in s['unknown']]
    if len(tasks) >= 2 and unsure:
        named = ', '.join(f'"{s["label"]}"' for s in unsure[:4])
        add(f'systems:{p["id"]}', f'Ask which of these are done in a system or tool, and which: {named}.', once=True)
    if len(tasks) >= 3:
        if not p['exceptions']:
            add(f'exceptions:{p["id"]}', f'Ask what usually goes wrong in {name}, and what happens then.', once=True)
        if not p['controls']:
            add(f'controls:{p["id"]}', f'Ask whether there are checks or approvals along the way in {name}.', once=True)
        if 'outcome' not in p['details'] and 'outcome' not in p['unknown']:
            add(f'outcome:{p["id"]}', f'Ask how {name} ends: what the end result is.', once=True)
    if complete and len(tasks) >= 3:
        add(f'summary:{p["id"]}', f'Read {name} back briefly, point to the map, and ask if anything is missing.',
            once=True, readback=[s['id'] for s in steps if s['kind'] != 'end'][:6])
        if planned:
            add(f'move:{planned[0]["id"]}',
                f'Say you have a good picture of {name}; ask whether to move on to {planned[0]["name"]}.', once=True)
        else:
            add('another', 'Ask whether there is another process they would like to describe.', once=True)
            add('wrap', 'Thank them, say everything is saved for them to review with the map, and ask if there is anything else.',
                once=True)
    if not out and not model.get('wrapped'):
        add('wrap', 'Thank them, say everything is saved for them to review with the map, and ask if there is anything else.',
            once=True)
    return out[:limit]


def closing(model: dict) -> str:
    name = (model['participant'].get('name') or {}).get('value', '').split(' ')[0]
    return (f'Thank you{", " + name if name else ""}, that is everything I need for now. It is all saved for you to review, '
            'with the map, and we can pick up again whenever you like.')


def asked(model: dict, goal: dict | None, turn: int) -> dict:
    """Record the goal Tibi's reply took: counted, a conflict marked raised, read-back steps marked read, and a move
    to the next process made."""
    if not goal:
        return model
    model = copy.deepcopy(model)
    key = goal['key']
    model['asked'][key] = model['asked'].get(key, 0) + 1
    if key.startswith(('conflict:', 'unclear:')):
        o = next((o for o in model['open'] if o['id'] == key.split(':', 1)[1]), None)
        if o is not None and o['status'] == 'open':
            o['status'] = 'raised'
    if goal.get('readback'):
        for item_id in goal['readback']:
            _, item, _ = find(model, item_id)
            if item is not None:
                item['read'] = True
        model['readback'] = {'items': goal['readback'], 'turn': turn}
    if key.startswith('move:'):
        model['proposed'] = key.split(':', 1)[1]  # moved when they agree (``settle_move``)
    if key == 'wrap':
        model['wrapped'] = True
    return model


def settle_move(model: dict, agreed: bool) -> dict:
    """After Tibi proposed moving to the next process: move when they agree; otherwise that process waits for another
    time and Tibi wraps up."""
    target = process(model, model.get('proposed') or '')
    if target is None:
        return model
    model = copy.deepcopy(model)
    target = process(model, model.pop('proposed'))
    if agreed:
        current = process(model, model['focus'])
        if current is not None:
            current['status'] = 'done'
        target['status'] = 'active'
        model['focus'] = target['id']
    else:
        target['status'] = 'later'
    return model


ORDINALS = ('first', 'second', 'third', 'fourth', 'fifth', 'sixth')


def _chain(steps_by_id, start, stop, joins=frozenset()):
    """Steps from ``start`` along first links until ``stop``, a decision, a step reached twice, the end, or a point
    where paths meet (``joins``: said once, after the paths)."""
    out, seen, current = [], set(), start
    while current and current not in seen and current != stop and current in steps_by_id:
        if out and current in joins:
            break
        seen.add(current)
        step = steps_by_id[current]
        out.append(step)
        if step['kind'] == 'decision':
            break
        current = step['next'][0]['to'] if step['next'] else None
    return out


def _told(steps, limit=6):
    """Steps as short sentences; the rest counted, not said."""
    said = []
    for s in steps[:limit]:
        if s['kind'] == 'task':
            said.append(_say(s))
        elif s['kind'] == 'event':
            said.append(_trigger(s))
        elif s['kind'] == 'end':
            said.append('it ends there')
    rest = len([s for s in steps[limit:] if s['kind'] == 'task'])
    return '; then '.join(said) + (f', and {rest} more step{"s" if rest != 1 else ""}' if rest else '')


def path_readback(model: dict, which: int | None = None) -> str:
    """The process in focus as it is captured, told as the story of the work (``narrate``). Asked for by name ("play it
    back", "what have you got for option one") and never replaced by the next question (PI F19)."""
    return narrate(model, which)['text']


def readback_text(model: dict, ids: list[str]) -> str:
    """A read-back without the conversation model: the steps as captured, and the question."""
    return f'Let me check I have this right. {readback_sentences(model, ids)}. Is that right?'


def recap(model: dict) -> str:
    """A spoken recap of the process in focus, from the model (no model call)."""
    p = process(model, model['focus']) if model['focus'] else None
    if p is None or not p['steps']:
        return "We haven't captured any steps yet. Shall we start with the process you'd like to describe?"
    open_items = len([o for o in model['open'] if o['status'] != 'resolved'])
    tail = f' There {"is" if open_items == 1 else "are"} {open_items} point{"s" if open_items != 1 else ""} to check.' if open_items else ''
    return path_readback(model).removesuffix(' Is that right?') + tail


def resume_line(model: dict) -> str:
    """How Tibi picks up a paused interview (PI F4)."""
    name = (model['participant'].get('name') or {}).get('value', '').split(' ')[0]
    hello = f'Welcome back{", " + name if name else ""}.'
    p = process(model, model['focus']) if model['focus'] else None
    if p is None:
        return f'{hello} Shall we carry on with which processes you would like to cover?'
    steps = [s for s in ordered_steps(p) if s['kind'] == 'task']
    where = f', just after "{steps[-1]["label"]}"' if steps else ''
    return f'{hello} We were on {p["name"] or "your process"}{where}. Shall we carry on from there?'
