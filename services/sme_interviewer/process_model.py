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
import re

SCHEMA_ID = 'opsatlas.process-model.v1'
PARTICIPANT_FIELDS = ('name', 'role', 'team', 'tenure')
PROCESS_FIELDS = ('purpose', 'trigger', 'outcome', 'frequency')
STEP_FIELDS = ('label', 'who', 'system')
LIMITS = {'processes': 8, 'steps': 60, 'open': 60, 'notes': 40}
CORRECTION = re.compile(r"\b(?:no|not|nope|actually|sorry|correction|i meant|i mean|wrong|rather|instead|about the step|"
                        r"isn'?t|wasn'?t|doesn'?t|don'?t|mistake|scratch that|let me correct)\b", re.I)
READBACK_AFTER = 3  # heard steps not yet read back before Tibi reads them back
DEPARTMENTS = {'finance', 'purchasing', 'procurement', 'accounts', 'accounting', 'marketing', 'sales', 'operations', 'it',
               'hr', 'legal', 'payroll', 'logistics', 'security', 'management', 'compliance', 'engineering', 'support',
               'customer service', 'someone'}
ABOUT_THEMSELVES = re.compile(r"\b(?:i'?m|i am|my (?:name|role|job|title|team)|i work|i look after|i run|i manage|i've been|i have been|"
                              r"call me)\b", re.I)


def new_model(space_id: str, space_name: str = '') -> dict:
    return {'schema': SCHEMA_ID, 'space': {'id': space_id, 'name': space_name}, 'participant': {}, 'processes': [],
            'open': [], 'focus': None, 'asked': {}, 'readback': None, 'wrapped': False, 'turns': 0,
            'next': {'p': 1, 's': 1, 'o': 1, 'x': 1, 'c': 1}}


def _norm(text: str) -> str:
    return ' '.join(re.sub(r"[^\w£$€%'&/-]+", ' ', str(text).casefold().replace('’', "'")).split())


def quoted(quote: str, answer: str) -> bool:
    """The quote is an exact excerpt of the answer, ignoring case, spacing and punctuation."""
    q = _norm(quote)
    return bool(q) and q in _norm(answer)


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
    if different and not refined and not settling and not corrects(answer):
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
    else:
        owner[field] = value
        owner['status'] = 'heard'
        owner['read'] = False
        _quote(owner, quote, turn)
    if old:
        log['corrected'].append({'item': item_id, 'field': field, 'was': old, 'now': value})
    if settling:
        settling.update(status='resolved', resolution=value, resolved_turn=turn)
        log['resolved'].append(settling['id'])
    log['applied'].append(f'{item_id}.{field}')


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


def apply(model: dict, changes: list, answer: str, turn: int) -> tuple[dict, dict]:
    """Apply the note-taker's changes for one answer. Returns the new model and a log of what was applied, dropped
    (with why), corrected, resolved and found in conflict."""
    model = copy.deepcopy(model)
    log = {'applied': [], 'dropped': [], 'corrected': [], 'conflicts': [], 'resolved': [], 'confirmed': []}
    refs: dict[str, str] = {}
    placed_after_decision: list[tuple[str, str]] = []

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
    listed = [c for c in changes if isinstance(c, dict)] if isinstance(changes, list) else []
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
            if not label:
                drop(change, 'no label')
                continue
            kind = 'decision' if op == 'decision' else ('end' if change.get('kind') == 'end' else 'task')
            after = ref(change.get('after'))
            same = next((s for s in p['steps'] if s['kind'] == kind and _norm(s['label']) == _norm(label)), None)
            anchor = next((s for s in p['steps'] if s['id'] == after), None)
            before_same = [s['id'] for s in p['steps'] if same is not None and any(n['to'] == same['id'] for n in s['next'])]
            if same is not None and anchor is not None and (anchor['kind'] == 'decision' or after not in before_same):
                # The same step reached from somewhere else. The same person (or no one said): the paths join there.
                # Someone else: a step of its own (the same action on another branch, by another role).
                new_who = _clean(change.get('who'))
                if not (not new_who or not same['who'] or _norm(new_who) == _norm(same['who'])):
                    same = None
                elif anchor['kind'] == 'decision':
                    if change.get('ref'):
                        refs[str(change['ref'])] = same['id']
                    placed_after_decision.append((anchor['id'], same['id']))
                    log['applied'].append(f"{anchor['id']}->{same['id']}")
                    continue
                elif not anchor['next'] and anchor['id'] != same['id']:
                    anchor['next'] = [{'to': same['id'], 'label': ''}]
                    if change.get('ref'):
                        refs[str(change['ref'])] = same['id']
                    log['applied'].append(f"{anchor['id']}->{same['id']}")
                    continue
                else:
                    same = None
            if same is not None:  # the step they already described: new details, or a conflict
                if change.get('ref'):
                    refs[str(change['ref'])] = same['id']
                for field in ('who', 'system'):
                    if str(change.get(field, '')).strip() and change[field] != '-':
                        _set(model, same, 'step', same['id'], field, change[field], quote, answer, turn, log)
                continue
            if len(p['steps']) >= LIMITS['steps']:
                drop(change, 'too many steps')
                continue
            step = {'id': _new_id(model, 's'), 'kind': kind, 'label': label, 'next': [], 'status': 'heard', 'read': False,
                    'who': '' if kind != 'task' else _clean(change.get('who')),
                    'system': '' if kind != 'task' else _clean(change.get('system')), 'quotes': [], 'unknown': []}
            _quote(step, quote, turn)
            by_id = {s['id']: s for s in p['steps']}
            p['steps'].append(step)
            if change.get('ref'):
                refs[str(change['ref'])] = step['id']
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
            if target == 'end':
                target = _end_step(model, p, turn, quote)['id']
            elif not any(s['id'] == target for s in p['steps']):
                drop(change, 'no such step')
                continue
            condition = ' '.join(str(change.get('condition', '')).split())[:80]
            link = next((n for n in decision['next'] if n['to'] == target), None)
            if link is None:
                decision['next'].append({'to': target, 'label': condition})
            else:
                link['label'] = condition or link['label']
            _quote(decision, quote, turn)
            log['applied'].append(f"{decision['id']}->{target}")
        elif op == 'change':
            p, item, kind = find(model, ref(change.get('item')))
            field = change.get('field')
            if item is not None and kind == 'step' and field in STEP_FIELDS:
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
    for decision_id, step_id in placed_after_decision:
        p, decision, _ = find(model, decision_id)
        if decision is not None and not any(n['to'] == step_id for n in decision['next']):
            decision['next'].append({'to': step_id, 'label': ''})
    model['turns'] = max(model['turns'], turn)
    return model, log


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
        for s in ordered_steps(p):
            after = ', '.join(f'{n["label"] + ": " if n["label"] else ""}{n["to"]}' for n in s['next'])
            quote = s['quotes'][0]['text'] if s['quotes'] else ''
            who = f' who: {s["who"] or "-"} system: {s["system"] or "-"}' if s['kind'] == 'task' else ''
            lines.append(f'  {s["id"]} {s["kind"]} "{s["label"]}"{who} [{s["status"]}] next: {after or "-"} quote: "{quote[:120]}"')
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
    if word.endswith(('s', 'sh', 'ch', 'x', 'z', 'o')):
        verb = word + 'es'
    elif word.endswith('y') and len(word) > 1 and word[-2] not in 'aeiou':
        verb = word[:-1] + 'ies'
    else:
        verb = word + 's'
    return f'{verb} {rest}'.strip()


def _say(step):
    label_words = step['label'].casefold().split()
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
    system = f' {"by" if by else "in"} {step["system"]}' if step['system'] else ''
    return f'{who} {_third_person(step["label"])}{system}'


def readback_sentences(model, ids, limit=6):
    """The steps as plain sentences: exactly what was captured, never rephrased by a model."""
    steps = [item for item in (find(model, i)[1] for i in ids) if item and item.get('kind') != 'end']
    by_id = {s['id']: s for p in model['processes'] for s in p['steps']}
    # A step on a decision's branch is said with the decision, not again after it.
    on_branch = {link['to'] for s in steps if s['kind'] == 'decision' for link in s['next'] if link['label']}
    steps = [s for s in steps if s['id'] not in on_branch or s['kind'] == 'decision'][:limit]
    parts = []
    for n, step in enumerate(steps):
        opener = 'First' if n == 0 else 'Then'
        if step['kind'] == 'decision':
            branches = []
            # The named case first, then "otherwise".
            for link in sorted(step['next'], key=lambda n: (not n['label'] or n['label'].casefold().startswith('otherwise'))):
                target = by_id.get(link['to'])
                if target is None:
                    continue
                what = 'it ends' if target['kind'] == 'end' else _say(target) if target['kind'] == 'task' else target['label']
                branches.append(f'{link["label"] or "otherwise"}, {what}')
            question = step['label'].rstrip('?')
            said = f'{opener} there is a decision, {question[0].lower() + question[1:]}'
            parts.append(said + (f': {"; ".join(branches)}' if branches else ''))
        else:
            parts.append(f'{opener} {_say(step)}')
    return '. '.join(parts)


def _steps_text(steps, limit=4):
    parts = []
    for s in steps[:limit]:
        if s['kind'] == 'decision':
            parts.append(f'then a decision: {s["label"].rstrip("?")}?')
        elif s['kind'] == 'task':
            who = f'{s["who"]} ' if s['who'] else ''
            system = f' in {s["system"]}' if s['system'] else ''
            parts.append(f'{who}{s["label"][0].lower() + s["label"][1:]}{system}'.strip())
    return '; '.join(parts)


def goals(model: dict, limit: int = 3) -> list[dict]:
    """What to ask next, in order: the first few goals the model's gaps call for. Tibi's reply takes the first one
    the latest answer has not already covered. Each goal has a key (never asked more than twice) and an instruction."""
    out: list[dict] = []

    def add(key, ask, once=False, readback=None):
        if _asked(model, key) >= (1 if once else 2) or any(g['key'] == key for g in out):
            return
        out.append({'key': key, 'ask': ask, **({'readback': readback} if readback else {})})

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
        add(f'readback:{"-".join(s["id"] for s in unread)}',
            f'Read these steps back in one short sentence and ask if that is right: {_steps_text(unread)}.',
            readback=[s['id'] for s in unread])
    if 'purpose' not in p['details'] and 'purpose' not in p['unknown']:
        add(f'purpose:{p["id"]}', f'Ask what {name} is for: what it achieves.', once=True)
    if 'trigger' not in p['details'] and 'trigger' not in p['unknown']:
        add(f'trigger:{p["id"]}', f'Ask what starts {name}: what sets it off.')
    if not steps:
        add(f'walk:{p["id"]}', f'Ask them to walk you through {name} from the very start, step by step.')
    for s in tasks:
        if not s['who'] and 'who' not in s['unknown']:
            add(f'who:{s["id"]}', f'Ask who does "{s["label"]}".')
    for s in steps:
        if s['kind'] == 'decision' and len(s['next']) < 2:
            add(f'branch:{s["id"]}', f'Ask what happens otherwise, at the decision "{s["label"]}".')
    tails = [s for s in steps if not s['next'] and s['kind'] == 'task']
    # Described to the end: every open path has an end, or Tibi has asked what follows it. An end on one branch
    # ("if not, it stops there") does not end the others.
    complete = bool(steps) and (not tails or all(_asked(model, f'next:{t["id"]}') for t in tails))
    if steps and tails:
        for tail in tails:
            add(f'next:{tail["id"]}', f'Ask what happens after "{tail["label"]}", or whether that is the end.')
    for s in tasks:
        if not s['system'] and 'system' not in s['unknown']:
            add(f'system:{s["id"]}', f'Ask whether "{s["label"]}" is done in a system or tool, and which.', once=True)
    if len(tasks) >= 3:
        if not p['exceptions']:
            add(f'exceptions:{p["id"]}', f'Ask what usually goes wrong in {name}, and what happens then.', once=True)
        if not p['controls']:
            add(f'controls:{p["id"]}', f'Ask whether there are checks or approvals along the way in {name}.', once=True)
        if 'outcome' not in p['details'] and 'outcome' not in p['unknown']:
            add(f'outcome:{p["id"]}', f'Ask how {name} ends: what the end result is.', once=True)
    if complete and len(tasks) >= 3:
        add(f'summary:{p["id"]}', f'Read the whole of {name} back briefly and ask if anything is missing: {_steps_text(steps, 8)}.',
            once=True, readback=[s['id'] for s in steps if s['kind'] != 'end'])
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
    return f'So far for {p["name"] or "this process"}: {_steps_text(ordered_steps(p), 6)}.{tail}'


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
