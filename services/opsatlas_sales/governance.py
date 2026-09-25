"""Governance interviews: open Quick Scan issues as an agenda, the Human's answers as pending resolutions.

Tibi works through the platform's own governance issues in priority order. For each one this module
supplies what Tibi needs to explain it (the exact passages involved, and what the rest of the corpus
already says) and verifies the Human's answer against the sources before it is read back. Nothing is
resolved here: an answer is stored as pending, and only the Human's approval in Knowledge review
closes the issue, through the platform's ``accept_issue`` action, with the answer as its record.
Sources are never edited: curated records are hash-bound to the paper sections they cite.
"""
import hashlib
import json
import re
import threading
from datetime import datetime, timezone
from difflib import SequenceMatcher

from assistant.governance.accepted import AcceptedStore, issue_key
from assistant.governance.intelligence import (
    _LINK,
    KnowledgeIntelligence,
    _expansion_matches_acronym,
    _readability_sentences,
    _readability_word_count,
)

from . import claims

# Fix what corrupts answers first, then what confuses readers, then tidiness.
CATEGORY_ORDER = {'correctness': 0, 'consistency': 1, 'compliance': 2}
CHECK_ORDER = {'conflict': 0, 'not_ingested': 1, 'broken_link': 2, 'outdated': 3, 'duplicate': 4, 'localisation': 5,
               'undefined_acronym': 6, 'content_style': 7, 'readability': 8, 'metadata_title': 9}
DECISIONS = ('accept', 'define', 'reword', 'fix_link', 'fix_later')
ACRONYM_STOP = {'a', 'an', 'and', 'for', 'in', 'of', 'or', 'the', 'to'}
# Abbreviations in general use. Tibi offers their usual meanings in one question; the Human decides.
STANDARD = {'AI': 'artificial intelligence', 'CPU': 'central processing unit', 'GPU': 'graphics processing unit',
            'GB': 'gigabytes', 'SDK': 'software development kit', 'CI': 'continuous integration',
            'UAT': 'user acceptance testing', 'README': 'a read-me file'}


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def spoken_title(title):
    """Source titles read aloud: 'DT603 Part A · 3.1 Implemented …' becomes 'DT603 Part A, section 3.1 …'."""
    return re.sub(r'\s*·\s*(?=\d|[A-D]\.|Appendix)', ', section ', title).replace(' · ', ', ')


def initials(words):
    return ''.join(part[0].upper() for word in words for part in re.split(r'-', word)
                   if part and part.lower() not in ACRONYM_STOP)


def definitions_in(text):
    """(acronym, expansion) pairs a text defines: 'Retrieval-Augmented Generation (RAG)' or 'RAG (…)'."""
    found = []
    for match in re.finditer(r'\(([A-Z]{2,6})\)', text):
        acronym = match.group(1)
        words = re.findall(r"[A-Za-z][A-Za-z'-]*", text[max(0, match.start() - 160):match.start()])
        chosen = []
        for word in reversed(words[-12:]):
            chosen.insert(0, word)
            letters = initials(chosen)
            if letters == acronym:
                found.append((acronym, ' '.join(chosen)))
                break
            if len(letters) > len(acronym):
                break
    for match in re.finditer(r'\b([A-Z]{2,6})\s*\(([^)]{3,80})\)', text):
        acronym, expansion = match.groups()
        if _expansion_matches_acronym(acronym, expansion.replace('-', ' ')):
            found.append((acronym, expansion.strip()))
    return found


def mentions_in(text, acronym):
    """Phrases whose initials spell ``acronym`` without being marked as its definition, most frequent first:
    the paper writes "Ontology-Augmented Generation" but never "(OAG)"."""
    if len(acronym) < 3:
        return []
    tokens = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
    counts = {}
    for start, first in enumerate(tokens):
        if first.lower() in ACRONYM_STOP or first[0].upper() != acronym[0]:
            continue
        for end in range(start + 1, min(start + len(acronym) + 3, len(tokens)) + 1):
            letters = initials(tokens[start:end])
            if letters == acronym:
                phrase = ' '.join(tokens[start:end])
                if tokens[end - 1].lower() not in ACRONYM_STOP:
                    key = phrase.lower().rstrip('s')
                    counts[key] = (counts.get(key, (0, phrase))[0] + 1, counts.get(key, (0, phrase))[1])
                break
            if not acronym.startswith(letters):
                break
    return [(phrase, count) for _, (count, phrase) in sorted(counts.items(), key=lambda kv: -kv[1][0])]


def named(phrase):
    return all(w[0].isupper() for w in re.split(r'[\s-]+', phrase) if w and w.lower() not in ACRONYM_STOP)


def prose_sentences(text):
    """Sentences of a passage, without Markdown headings, bullets markers or table rows."""
    lines = [line.strip().lstrip('-*• ').strip() for line in text.splitlines()
             if line.strip() and not line.lstrip().startswith(('#', '|'))]
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', ' '.join(lines)) if len(s.split()) >= 5]


def overlap(a_text, b_text, limit=3, floor=0.4):
    """The sentence pairs where two passages say the same thing, closest first."""
    words = lambda sentence: re.findall(r"[a-z0-9]+", sentence.lower())  # noqa: E731
    pairs = []
    for a in prose_sentences(a_text)[:60]:
        for b in prose_sentences(b_text)[:60]:
            pairs.append((SequenceMatcher(None, words(a), words(b), autojunk=False).ratio(), a, b))
    chosen, used = [], set()
    for ratio, a, b in sorted(pairs, key=lambda p: -p[0]):
        if ratio < floor or len(chosen) == limit:
            break
        if a in used or b in used:
            continue
        used.update((a, b))
        chosen.append({'a': a, 'b': b, 'similarity': round(ratio, 2)})
    return chosen


def same_expansion(a, b):
    squash = lambda value: re.sub(r'[^a-z]', '', value.lower())  # noqa: E731
    return squash(a) == squash(b)


def quote_around(text, needle, width=220):
    """The sentence containing ``needle``, trimmed to a speakable length."""
    for sentence in re.split(r'(?<=[.!?])\s+', ' '.join(text.split())):
        if re.search(r'\b' + re.escape(needle) + r'\b', sentence):
            return sentence if len(sentence) <= width else sentence[:width].rsplit(' ', 1)[0] + '…'
    return ''


class GovernanceDesk:
    def __init__(self, register, sections, retrieval, actions, knowledge):
        self.register, self.sections, self.actions, self.knowledge = register, sections, actions, knowledge
        self.retrieval = retrieval
        self.accepted = AcceptedStore(register.base_dir)
        self.intelligence = KnowledgeIntelligence(register, sections, None, None, generator=None, accepted=self.accepted)
        self.path = register.base_dir / 'governance-answers.json'
        self.lock = threading.Lock()
        self._texts = {}
        self._scan = (None, None)

    # ---- corpus ------------------------------------------------------------------------

    def text(self, source_id):
        source = self.register.get(source_id)
        if source is None:
            return ''
        key = (source_id, source.content_sha256)
        if key not in self._texts:
            self._texts[key] = self.register.read_content(source_id).decode('utf-8', 'replace')
        return self._texts[key]

    def corpus_definitions(self, acronym):
        """Every definition of ``acronym`` in the workspace's sources: [(expansion, source title, quote)]."""
        found = []
        for source in self.register.list():
            if source.approval_status == 'rejected':
                continue
            text = self.text(source.id)
            for name, expansion in definitions_in(text):
                if name == acronym and not any(same_expansion(expansion, e) for e, _, _ in found):
                    found.append((expansion, source.title, quote_around(text, acronym)))
        return found

    def corpus_mentions(self, acronym):
        """Phrases the sources use that spell out ``acronym``: [(phrase, source title)], best first."""
        totals = {}
        for source in self.register.list():
            if source.approval_status == 'rejected':
                continue
            for phrase, count in mentions_in(self.text(source.id), acronym):
                key = re.sub(r'[^a-z]', '', phrase.lower()).rstrip('s')
                seen = totals.setdefault(key, [0, phrase, source.title])
                seen[0] += count
        # A chance run of words ("source material extracted") is noise: keep phrases used more than once
        # across the sources, or written as a name ("Ontology-Augmented Generation").
        ranked = sorted(totals.values(), key=lambda v: -v[0])
        return [(phrase, title) for count, phrase, title in ranked if count >= 2 or named(phrase)][:2]

    # ---- agenda ------------------------------------------------------------------------

    def fingerprint(self):
        state = [(s.id, s.content_sha256, s.approval_status) for s in self.register.list()]
        return sha(json.dumps([state, sorted(self.accepted.all())]))

    def agenda(self):
        """Open issues in priority order. The scan is cached until sources or accepted issues change;
        answer statuses are laid over it on every call, so saving an answer never re-runs the scan."""
        key = self.fingerprint()
        if self._scan[0] != key:
            self._scan = (key, self._build_agenda())
        value = self._scan[1]
        latest = {}
        for answer in self.answers():
            if answer['status'] not in ('rejected', 'superseded'):
                latest[answer['issue_key']] = answer
        items = [{**item, 'answer': {k: latest[item['key']][k] for k in ('id', 'status', 'answer')}
                  if item['key'] in latest else None} for item in value['items']]
        return {**value, 'items': items}

    def item(self, issue_key):
        return next((i for i in self.agenda()['items'] if i['key'] == issue_key), None)

    def scan(self):
        """The platform Quick Scan. Duplicates need embeddings; without them the other checks still run."""
        self.intelligence.embedder = getattr(self.retrieval, 'embedder', None)
        self.intelligence.cache = getattr(self.retrieval, 'cache', None)
        try:
            return self.intelligence.run()
        except Exception:  # the local embedding model is unavailable
            self.intelligence.embedder = self.intelligence.cache = None
            return self.intelligence.run()

    def _build_agenda(self):
        report = self.scan()
        items, acronyms = [], {}
        for category, issues in report['issues'].items():
            for issue in issues:
                key = issue_key(issue['source_id'], issue['check'], issue['detail'])
                ref = {'key': key, 'source_id': issue['source_id'], 'source_title': issue['source_title'],
                       'check': issue['check'], 'detail': issue['detail']}
                if issue['check'] == 'undefined_acronym':
                    # One question per acronym, not per source: "RAG" is answered once for all six sources.
                    ref['acronyms'] = re.findall(r'\b[A-Z]{2,6}\b', issue['detail'].split(':', 1)[-1])
                    for acronym in ref['acronyms']:
                        acronyms.setdefault(acronym, []).append(ref)
                    continue
                items.append({**self.describe(issue), 'key': key, 'kind': 'issue', 'category': category, 'issues': [ref]})
        standard = sorted(a for a in acronyms if a in STANDARD)
        if standard:
            refs = list({r['key']: r for a in standard for r in acronyms[a]}.values())
            items.append({'key': 'standard:' + '+'.join(standard), 'kind': 'standard', 'check': 'undefined_acronym',
                          'category': 'compliance', 'severity': 'low', 'score': 1, 'acronyms': standard,
                          'meanings': {a: STANDARD[a] for a in standard}, 'issues': refs,
                          'source_title': f'{len({r["source_id"] for r in refs})} sources', 'detail': ', '.join(standard)})
        for acronym, refs in acronyms.items():
            if acronym in STANDARD:
                continue
            first = refs[0]
            items.append({'key': 'acronym:' + acronym, 'kind': 'acronym', 'check': 'undefined_acronym',
                          'category': 'compliance', 'severity': 'low', 'score': 1, 'acronym': acronym, 'issues': refs,
                          'source_id': first['source_id'], 'source_title': first['source_title'],
                          'spoken_title': spoken_title(first['source_title']), 'detail': acronym,
                          'sources': [spoken_title(r['source_title']) for r in refs],
                          'in_source': quote_around(self.text(first['source_id']), acronym),
                          'known': [{'expansion': e, 'source_title': t, 'quote': q}
                                    for e, t, q in self.corpus_definitions(acronym)],
                          'mentions': [{'phrase': m, 'source_title': t} for m, t in self.corpus_mentions(acronym)]})
        # Correctness, then consistency, then acronyms used most widely, the standard ones, and readability last.
        items.sort(key=lambda i: (-i['score'], CATEGORY_ORDER.get(i['category'], 9), CHECK_ORDER.get(i['check'], 99),
                                  {'acronym': 0, 'standard': 1}.get(i['kind'], 0), -len(i['issues']),
                                  i.get('source_title', '')))
        for n, item in enumerate(items, 1):
            item['position'] = n
        return {'health': report['health'], 'categories': report['categories'], 'issues': report['total_issues'],
                'total': len(items), 'items': items}

    def describe(self, issue):
        """Explanation material per check: the passages involved, and what the corpus already says."""
        text = self.text(issue['source_id'])
        base = {k: issue[k] for k in ('check', 'severity', 'score', 'source_id', 'source_title', 'detail',
                                      'recommended_action', 'why_it_matters')}
        base['spoken_title'] = spoken_title(issue['source_title'])
        if issue['check'] == 'undefined_acronym':
            names = re.findall(r'\b[A-Z]{2,6}\b', issue['detail'].split(':', 1)[-1])
            base['acronyms'] = [{'acronym': a, 'in_source': quote_around(text, a),
                                 'known': [{'expansion': e, 'source_title': t, 'quote': q}
                                           for e, t, q in self.corpus_definitions(a)]} for a in names]
        elif issue['check'] == 'readability':
            prose = '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith(('#', '**', '|')))
            base['examples'] = [' '.join(s.split()) for s in _readability_sentences(prose) if _readability_word_count(s) > 40][:3]
        elif issue['check'] == 'broken_link':
            base['links'] = [h for h in _LINK.findall(text) if not h.strip().startswith(('http://', 'https://', '/', '#', 'mailto:'))
                             or not h.strip() or 'example.com' in h][:5]
        elif issue['check'] == 'duplicate':
            base.update(source_b_id=issue.get('source_b_id'), source_b_title=issue.get('source_b_title'),
                        spoken_title_b=spoken_title(issue.get('source_b_title') or ''))
            match = re.match(r"Section '(.*)' closely matches '(.*)' in '", issue['detail'])
            base['headings'] = list(match.groups()) if match else []
            base['passages'] = [self.passage(issue['source_id'], base['headings'][0] if match else None),
                                self.passage(issue.get('source_b_id'), base['headings'][1] if match else None)]
            # Where the duplication sits: the closest sentence pairs across the two passages.
            base['overlap'] = overlap(self.section_text(issue['source_id'], base['headings'][0] if match else None),
                                      self.section_text(issue.get('source_b_id'), base['headings'][1] if match else None))
            base['relation'] = self.relation(issue['source_id'], issue.get('source_b_id'))
        return base

    def section_text(self, source_id, heading):
        if not source_id:
            return ''
        sections = self.sections.list_for_source(source_id)
        chosen = next((s for s in sections if heading and s.heading == heading), sections[0] if sections else None)
        return chosen.text if chosen else ''

    def passage(self, source_id, heading):
        body = ' '.join(self.section_text(source_id, heading).split())
        return body if len(body) <= 360 else body[:360].rsplit(' ', 1)[0] + '…'

    def relation(self, a, b):
        """Why two sources may overlap by design: a curated record citing the other as its evidence."""
        for row in self.knowledge.records():
            cited = {ref['source_id'] for ref in row.get('references', [])}
            if row['source_id'] == a and b in cited or row['source_id'] == b and a in cited:
                other = b if row['source_id'] == a else a
                source = self.register.get(other)
                return {'record_title': row['title'], 'cites': source.title if source else other}
            if a in cited and b in cited:
                return {'record_title': row['title'], 'cites': 'both'}
        return None

    # ---- verification ------------------------------------------------------------------

    def verify(self, item, resolution, answer):
        """Check the Human's answer against the sources before it is read back.

        Returns findings, each {status, message}: matches, conflicts, not_found, changes_meaning, unverified or check.
        """
        findings = []
        if resolution.get('decision') == 'define':
            for pair in resolution.get('definitions', []):
                acronym, expansion = pair.get('acronym', '').strip().upper(), ' '.join(pair.get('expansion', '').split())
                if not acronym or not expansion:
                    continue
                known = self.corpus_definitions(acronym)
                same = [k for k in known if same_expansion(k[0], expansion)]
                if same:
                    findings.append({'status': 'matches', 'acronym': acronym,
                                     'message': f'That matches {spoken_title(same[0][1])}.'})
                elif known:
                    findings.append({'status': 'conflicts', 'acronym': acronym, 'expected': known[0][0],
                                     'message': f'But {spoken_title(known[0][1])} defines {acronym} as {known[0][0]}.'})
                elif mentioned := [m for m in self.corpus_mentions(acronym) if same_expansion(m[0].rstrip('s'), expansion.rstrip('s'))]:
                    findings.append({'status': 'matches', 'acronym': acronym,
                                     'message': f'That fits how {spoken_title(mentioned[0][1])} uses it.'})
                elif mentions := self.corpus_mentions(acronym):
                    findings.append({'status': 'conflicts', 'acronym': acronym, 'expected': mentions[0][0],
                                     'message': f'But the sources talk about {mentions[0][0]}, which also spells {acronym}.'})
                elif acronym in STANDARD and same_expansion(STANDARD[acronym], expansion):
                    findings.append({'status': 'not_found', 'acronym': acronym,
                                     'message': f'{acronym} is a standard abbreviation; the sources do not define it.'})
                else:
                    findings.append({'status': 'not_found', 'acronym': acronym,
                                     'message': f'The sources do not define {acronym}, so it will be recorded as your definition.'})
                if not _expansion_matches_acronym(acronym, expansion.replace('-', ' ')):
                    findings.append({'status': 'check', 'acronym': acronym,
                                     'message': f"{expansion} does not spell out {acronym}."})
        if resolution.get('decision') == 'reword' and resolution.get('replacement'):
            original = ' '.join(item.get('examples', [])) or self.text(item['source_id'])
            reasons = claims.unsupported(resolution['replacement'], original)
            if reasons:
                findings.append({'status': 'changes_meaning', 'message': 'The rewording may change the meaning: '
                                 + '; '.join(reasons[:2]) + '.'})
        if resolution.get('decision') == 'fix_link' and resolution.get('url'):
            if not re.match(r'^(?:https?://[\w.-]+\.[a-z]{2,}\S*|/\S+|mailto:\S+@\S+)$', resolution['url'].strip()):
                findings.append({'status': 'check', 'message': "That doesn't look like a complete web address."})
        if item['check'] == 'duplicate' and resolution.get('decision') == 'accept' and item.get('relation'):
            findings.append({'status': 'matches', 'message': 'That fits: ' + self.relation_sentence(item)})
        # Anything else the Human states as fact is checked against the passages involved.
        involved = {r['source_id'] for r in item.get('issues', [])} | {item.get('source_id'), item.get('source_b_id')}
        sources_text = ' '.join(self.text(s) for s in involved if s)
        for sentence in claims.sentences_of(answer):
            # Meta-talk ("go to question 3") is not a claim: only claim vocabulary, percentages or money are checked.
            if claims.question_form(sentence) or not (claims.claim_terms(sentence) or re.search(
                    r'\d\s*(?:%|per ?cent)|[£$€]\s*\d', sentence, re.I)):
                continue
            reasons = claims.unsupported(sentence, sources_text)
            if reasons:
                denied = next((r for r in reasons if 'negates' in r), None)
                term = (denied or reasons[0]).split('"')[1] if '"' in (denied or reasons[0]) else ''
                message = (f'The sources say the opposite about {term}.' if denied else
                           f'The sources do not state {term}.' if term else "The sources don't support part of that.")
                findings.append({'status': 'conflicts' if denied else 'unverified', 'message': message,
                                 'sentence': sentence, 'reasons': reasons[:3]})
        return findings

    @staticmethod
    def relation_sentence(item):
        relation = item['relation']
        if relation['cites'] == 'both':
            return f"the record {relation['record_title']} cites both passages, so the overlap is by design."
        return (f"the record {relation['record_title']} cites {spoken_title(relation['cites'])} as its evidence, "
                'so the overlap is by design.')

    # ---- answers -----------------------------------------------------------------------

    def answers(self):
        return json.loads(self.path.read_text()) if self.path.exists() else []

    def _save(self, rows):
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(rows, indent=2) + '\n')
        temporary.replace(self.path)

    def propose(self, data):
        """Store the Human's confirmed answer as pending. A newer answer to the same issue replaces a pending one."""
        required = {'issue_key', 'contributor', 'session_id', 'answer', 'resolution'}
        if not required <= set(data) or data['contributor'] not in ('Chris', 'Dan'):
            raise ValueError('Invalid governance answer')
        if not isinstance(data['answer'], str) or not 1 <= len(data['answer'].strip()) <= 1200:
            raise ValueError('Use 1–1200 characters for an answer')
        resolution = data['resolution']
        if not isinstance(resolution, dict) or resolution.get('decision') not in DECISIONS:
            raise ValueError('Choose a governance decision')
        item = self.item(data['issue_key'])
        if item is None:
            raise ValueError('That issue is no longer open; refresh the agenda')
        verification = self.verify(item, resolution, data['answer'])
        body = {'issue_key': item['key'], 'kind': item['kind'], 'check': item['check'], 'category': item['category'],
                'severity': item['severity'], 'source_title': item.get('source_title', ''), 'detail': item['detail'],
                'issues': item['issues'], 'contributor': data['contributor'],
                'session_id': str(data['session_id'])[:80], 'answer': data['answer'].strip(),
                'resolution': {k: resolution.get(k) for k in ('decision', 'definitions', 'replacement', 'url', 'note')
                               if resolution.get(k)}, 'verification': verification}
        body['text_sha256'] = sha(json.dumps(body, sort_keys=True))
        with self.lock:
            rows = self.answers()
            for row in rows:
                if row['issue_key'] == item['key'] and row['status'] == 'pending':
                    row['status'] = 'superseded'
            answer = {'id': body['text_sha256'][:24], **body, 'status': 'pending',
                      'created_at': datetime.now(timezone.utc).isoformat(), 'review': None}
            self._save([*rows, answer])
        return answer

    def _close(self, row, rows):
        """Accept the issues an approved answer settles. An acronym issue listing several acronyms closes
        only when every one of them has an approved answer."""
        from assistant.ontology.actions import ActionActor

        approved = set()
        for other in [*rows, row]:
            if other is row or other['status'] == 'approved':
                if other.get('kind') == 'acronym':
                    approved.add(other['issue_key'].split(':', 1)[1])
                elif other.get('kind') == 'standard':
                    approved.update(other['issue_key'].split(':', 1)[1].split('+'))
        for ref in row['issues']:
            if ref.get('acronyms') and not set(ref['acronyms']) <= approved:
                continue
            if self.accepted.is_accepted(ref['source_id'], ref['check'], ref['detail']):
                continue
            result = self.actions.execute('accept_issue', {'source_id': ref['source_id'], 'check': ref['check'],
                                                           'detail': ref['detail']},
                                          ActionActor(type='operator', id='local-sales-operator'))
            if result.outcome != 'ok':
                raise ValueError('Atlas could not record the resolution; the answer remains pending')

    def review(self, identifier, expected_hash, approve):
        """The Human's decision. Approval closes the issue in Governance through the platform action."""
        with self.lock:
            rows = self.answers()
            row = next((r for r in rows if r['id'] == identifier), None)
            if not row or row['text_sha256'] != expected_hash or row['status'] != 'pending':
                raise ValueError('That answer changed or was already reviewed; refresh the review')
            if approve:
                self._close(row, rows)
            row['status'] = 'approved' if approve else 'rejected'
            row['review'] = {'actor': 'local operator', 'at': datetime.now(timezone.utc).isoformat(), 'hash': expected_hash}
            self._save(rows)
            with (self.register.base_dir / 'sales-review-history.jsonl').open('a') as log:
                log.write(json.dumps({'governance_answer': identifier, 'decision': row['status'], **row['review']}) + '\n')
            return row
