"""Hash-bound curated records stored through Atlas registration and ingestion."""
import hashlib
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

from assistant.ingestion.service import ingest_source
from assistant.ingestion.store import SectionStore
from assistant.sources.service import register_upload

from . import claims
from .workspace import REPO

SPOKEN_LIMIT = 420
STOPWORDS = frozenset('''a about an and are as at be but by can could do does for from had has have how i if in is it its
me my of on or our per so than that the their them then there these they this to us was we were what when where which
who why will with would you your'''.split())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def document(title, text, input_hash=None):
    body = '# ' + title + '\n\n' + text + '\n'
    if input_hash:
        body += '\nInterview input SHA-256: ' + input_hash + '\n'
    return body.encode()


class Knowledge:
    def __init__(self, register, actions=None):
        self.register = register
        self.actions = actions
        self.sections = SectionStore(register.base_dir)
        self.path = register.base_dir / 'sales-records.json'
        self.spoken_path = register.base_dir / 'sales-spoken.json'
        self.lock = threading.Lock()

    def records(self):
        return json.loads(self.path.read_text()) if self.path.exists() else []

    def _save(self, rows):
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(rows, indent=2) + '\n')
        temporary.replace(self.path)

    def seed(self, corpus=None, papers=None):
        """Create the starting records once, then add any new corpus records as pending.

        ``papers`` holds the local product edition that ``paper:`` references point to; other
        references are repository files. Existing records are never changed here: a curated record
        that is already reviewed keeps its wording and approval until the Human decides otherwise.
        """
        corpus = corpus or Path(__file__).parent / 'corpus/product.json'
        marker = self.register.base_dir / 'sales-corpus.json'
        with self.lock:
            cards = json.loads(corpus.read_text())
            rows = self.records()
            curated = {r['id'] for r in rows if not r.get('provenance') and r.get('kind') != 'conversation'}
            seeded = json.loads(marker.read_text())['corpus'] if marker.exists() else (
                corpus.name if curated <= {c['id'] for c in cards} else None)
            if rows and seeded != corpus.name:
                return self.catalog()  # another corpus seeded this workspace: never merge the two
            known = {r['id'] for r in rows}
            added = [self._card(card, papers) for card in cards if card['id'] not in known]
            if added or not self.path.exists():
                self._save([*rows, *added])
            marker.write_text(json.dumps({'corpus': corpus.name}) + '\n')
            return self.catalog()

    def seed_conversation(self, corpus):
        """Add conversation-style records (how Tibi chats, not what OpsAtlas does) as pending.

        They are ordinary governed records of kind ``conversation``: enabled by the Human like any other,
        never used as product evidence and never an interview topic.
        """
        with self.lock:
            rows = self.records()
            cards = json.loads(Path(corpus).read_text())
            by_id = {card['id']: card for card in cards}
            # Topics are index terms, not part of the approved wording: refreshing them keeps the approval.
            refreshed = False
            for row in rows:
                card = by_id.get(row['id'])
                if card and row.get('kind') == 'conversation' and row.get('topics') != card['topics']:
                    row['topics'] = card['topics']
                    refreshed = True
            known = {r['id'] for r in rows}
            added = [self._card({**card, 'kind': 'conversation'}, None) for card in cards if card['id'] not in known]
            if added or refreshed:
                self._save([*rows, *added])
            return added

    def conversation_guidance(self, text, rows=None):
        """Enabled conversation records relevant to a message (at most two), else the personality record."""
        rows = [r for r in (self.catalog() if rows is None else rows) if r.get('kind') == 'conversation' and r['eligible']]
        value = ' ' + re.sub(r"[^a-z0-9' -]+", ' ', text.lower()) + ' '
        scored = sorted(((sum(1 for t in r.get('topics', []) if f' {t} ' in value), n, r) for n, r in enumerate(rows)),
                        key=lambda item: (-item[0], item[1]))
        chosen = [r for score, _, r in scored if score][:2] or [r for r in rows if r['id'] == 'conv-persona']
        return [{'id': r['id'], 'title': r['title'], 'text': r['text']} for r in chosen]

    def _card(self, card, papers):
        refs = []
        for relative in card['references']:
            if relative.startswith('paper:'):
                if papers is None:
                    raise ValueError('Extract the foundation paper before seeding its records')
                data = (papers / relative.removeprefix('paper:')).read_bytes()
            else:
                data = (REPO / relative).read_bytes()
            # Retain exact originals in the isolated source register as pending evidence.
            existing = next((s for s in self.register.list() if s.content_sha256 == sha(data)), None)
            filename = Path(relative.removeprefix('paper:')).name + ('.txt' if relative.endswith('.py') else '')
            title = data.decode('utf-8', 'replace').splitlines()[0].lstrip('# ') if relative.startswith('paper:') else relative
            source = existing or register_upload(self.register, filename, data, title)
            if not existing:
                ingest_source(self.register, self.sections, source.id)
            refs.append({'path': relative, 'source_id': source.id, 'sha256': sha(data)})
        body = ('# ' + card['title'] + '\n\n' + card['text'] + '\n').encode()
        source = register_upload(self.register, card['id'] + '.md', body, card['title'])
        ingest_source(self.register, self.sections, source.id)
        return {**card, 'references': refs, 'source_id': source.id, 'sha256': sha(body),
                'audience': 'internal_rehearsal', 'approval': 'pending', 'review': None}

    def topics(self):
        """Interview topics are the curated starting records, whichever corpus seeded them."""
        return tuple(r['id'] for r in self.records() if not r.get('provenance') and r.get('kind') != 'conversation')

    def eligible(self, row):
        try:
            return self._eligible(row)
        except OSError:
            return False

    def _eligible(self, row):
        if row.get('disputed') or (row.get('provenance') and row['status'] == 'uncertain'):
            return False
        if self.review_block(row):
            return False
        expected = document(row['title'], row['text'], row.get('input_hash'))
        if sha(expected) != row['sha256']:
            return False
        source = self.register.get(row['source_id'])
        if not source or source.approval_status != 'approved':
            return False
        if source.content_sha256 != row['sha256'] or sha(self.register.read_content(source.id)) != row['sha256']:
            return False
        for ref in row['references']:
            parent = self.register.get(ref['source_id'])
            if not parent or parent.approval_status == 'rejected' or parent.content_sha256 != ref['sha256']:
                return False
            if sha(self.register.read_content(parent.id)) != ref['sha256']:
                return False
        return True

    def catalog(self):
        rows = self.records()
        return [{**row, 'approval': self.native_approval(row), 'approval_origin': 'Atlas Governance',
                 'review_block': self.review_block(row, rows), 'eligible': self.eligible(row), 'overlaps': [
            {'id': r['id'], 'title': r['title'], 'text': r['text'], 'sha256': r['sha256']}
            for r in self.overlaps(row, rows)]} for row in rows]

    def decide(self, identifier, expected_hash, approve):
        with self.lock:
            rows = self.records()
            row = next((r for r in rows if r['id'] == identifier), None)
            if not row:
                raise ValueError('Unknown record')
            if approve and (block := self.review_block(row, rows)):
                raise ValueError(block)
            source = self.register.get(row['source_id'])
            if not source or expected_hash != row['sha256'] or sha(self.register.read_content(source.id)) != expected_hash:
                raise ValueError('Source changed; review the current version')
            for ref in row['references']:
                parent = self.register.get(ref['source_id'])
                if not parent or sha(self.register.read_content(parent.id)) != ref['sha256']:
                    raise ValueError('Supporting evidence changed; refresh the review')
            state = 'approved' if approve else 'rejected'
            if self.actions and source.approval_status != state:
                from assistant.ontology.actions import ActionActor
                result = self.actions.execute('approve_source' if approve else 'reject_source',
                                              {'source_id': source.id}, ActionActor(type='operator', id='local-sales-operator'))
                if result.outcome != 'ok':
                    raise ValueError('Atlas approval action failed; review remains pending')
            else:
                self.register.update(source.id, approval_status=state)
            row['approval'] = state
            row['review'] = {'actor': 'local operator', 'scope': 'internal rehearsal only',
                             'at': datetime.now(timezone.utc).isoformat(), 'hash': expected_hash}
            self._save(rows)
            with (self.register.base_dir / 'sales-review-history.jsonl').open('a') as log:
                log.write(json.dumps({'id': identifier, 'decision': state, **row['review']}) + '\n')
            return {**row, 'approval': self.native_approval(row), 'eligible': self.eligible(row)}

    def propose(self, data):
        """Idempotent, versioned contributor wording. Old approved revisions are withdrawn first."""
        required = {'session_id', 'turn_id', 'contributor', 'topic', 'question', 'raw_text', 'text', 'status',
                    'expected_hash', 'wording_confirmed', 'issue'}
        if set(data) != required or data['wording_confirmed'] is not True:
            raise ValueError('Confirm the corrected wording before proposing a claim')
        if (data['contributor'] not in ('Chris', 'Dan') or data['status'] not in ('available', 'planned', 'uncertain')
                or data['topic'] not in self.topics()
                or any(not isinstance(data[k], str) or not 1 <= len(data[k]) <= limit for k, limit in
                       [('session_id', 80), ('turn_id', 80), ('question', 600), ('raw_text', 1200), ('text', 600)])):
            raise ValueError('Invalid contributor claim')
        if not data['text'].strip() or len(data['text']) > 560:
            raise ValueError('Use 1–560 characters for a claim')
        identifier = sha((data['session_id'] + ':' + data['turn_id']).encode())[:32]
        fingerprint = sha(json.dumps({k: v for k, v in data.items() if k != 'expected_hash'}, sort_keys=True).encode())
        with self.lock:
            rows = self.records()
            old = next((r for r in rows if r['id'] == identifier), None)
            if old and old.get('input_hash') == fingerprint:
                return {**old, 'approval': self.native_approval(old), 'eligible': self.eligible(old)}
            if data['expected_hash'] != (old['sha256'] if old else None):
                raise ValueError('The claim changed; refresh before correcting it')
            if old:
                # Fail closed before any new source registration; interruption leaves old version unavailable.
                self.register.update(old['source_id'], approval_status='rejected')
            provenance = {k: data[k] for k in ('session_id', 'turn_id', 'contributor', 'topic', 'question',
                                             'raw_text', 'text', 'status', 'issue')}
            provenance['wording_confirmed_at'] = datetime.now(timezone.utc).isoformat()
            raw = json.dumps(provenance, indent=2).encode()
            evidence = register_upload(self.register, identifier + '-account.txt', raw, f"{data['contributor']} interview account")
            ingest_source(self.register, self.sections, evidence.id)
            # Keep availability explicit when excerpts are spoken verbatim.
            prefix = {'available': 'Currently: ', 'planned': 'Planned, not confirmed available: ',
                      'uncertain': 'Not yet verified: '}[data['status']]
            text = prefix + data['text']
            if len(text) > 600:
                raise ValueError('Shorten the claim to leave room for its availability label')
            title = f"{data['topic'].capitalize()} · {data['contributor']}"
            body = document(title, text, fingerprint)
            source = register_upload(self.register, identifier + '.md', body, title)
            ingest_source(self.register, self.sections, source.id)
            row = {'id': identifier, 'title': title, 'text': text, 'status': data['status'], 'topics': [data['topic']],
                   'source_id': source.id, 'sha256': sha(body), 'audience': 'internal_rehearsal', 'approval': 'pending',
                   'review': None, 'input_hash': fingerprint, 'provenance': provenance,
                   'references': [{'path': f"{data['contributor']} · confirmed interview wording",
                                   'source_id': evidence.id, 'sha256': sha(raw)}],
                   'versions': [*(old or {}).get('versions', []), *([old['source_id']] if old else [])],
                   'resolution': None, 'disputed': False}
            rows = [r for r in rows if r['id'] != identifier] + [row]
            self._save(rows)
            return {**row, 'eligible': False}

    def adjudicate(self, identifier, expected_hash, decision, related, reason):
        """Explicit operator resolution; never let a model silently decide whose account wins."""
        if (decision not in ('distinct_scope', 'supersede', 'dispute')
                or not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 1000):
            raise ValueError('Choose a disposition and explain scope/evidence in at least 10 characters')
        if not isinstance(related, dict):
            raise ValueError('Supply the reviewed related record hashes')
        with self.lock:
            rows = self.records()
            row = next((r for r in rows if r['id'] == identifier), None)
            if not row or not row.get('provenance') or row['sha256'] != expected_hash:
                raise ValueError('Claim changed; refresh review')
            overlaps = self.overlaps(row, rows)
            if related != {r['id']: r['sha256'] for r in overlaps}:
                raise ValueError('Related evidence changed; review all current topic records')
            # Disputes/supersessions withdraw native approval as well as answer eligibility.
            for item in ([row, *overlaps] if decision == 'dispute' else overlaps if decision == 'supersede' else []):
                self.register.update(item['source_id'], approval_status='rejected')
                item['approval'] = 'rejected'
                item['disputed'] = decision == 'dispute'
            row['disputed'] = decision == 'dispute'
            row['resolution'] = {'decision': decision, 'reason': reason.strip(), 'related': related,
                                 'at': datetime.now(timezone.utc).isoformat(), 'actor': 'local operator'}
            self._save(rows)
            with (self.register.base_dir / 'sales-review-history.jsonl').open('a') as log:
                log.write(json.dumps({'id': identifier, **row['resolution']}) + '\n')
            return {**row, 'approval': self.native_approval(row), 'eligible': self.eligible(row)}

    def native_approval(self, row):
        source = self.register.get(row['source_id'])
        return source.approval_status if source else 'unavailable'

    def review_block(self, row, rows=None):
        if row.get('disputed'):
            return 'Resolve the dispute before enabling this record'
        if row.get('provenance'):
            if row['status'] == 'uncertain':
                return 'Resolve the uncertainty before enabling this claim'
            overlaps = self.overlaps(row, self.records() if rows is None else rows)
            resolution = row.get('resolution') or {}
            if overlaps and (resolution.get('decision') != 'distinct_scope' or resolution.get('related') != {
                    r['id']: r['sha256'] for r in overlaps}):
                return 'Review related topic records and record a scope or supersession decision first'
        return None

    def overlaps(self, row, rows):
        topic = row.get('provenance', {}).get('topic')
        return [r for r in rows if r['id'] != row['id']
                and (self.native_approval(r) not in ('rejected', 'unavailable') or r.get('disputed'))
                and (r['id'] == topic or topic in r.get('topics', []))] if topic else []

    # ---- Retrieval over enabled records (the platform hybrid retriever, restricted) ----

    def rank(self, query, retrieval, rows=None):
        """Rank enabled records with the platform's BM25 + embedding fusion and relevance threshold.

        Unlike ``RetrievalService.search`` every enabled record is returned with its scores, so the
        voice service can route on similarity even below the answer threshold. Nothing is truncated.
        """
        from rank_bm25 import BM25Plus

        from assistant.retrieval.service import RetrievalService, _cosine, _tokenize

        rows = [r for r in (self.catalog() if rows is None else rows) if r['eligible'] and r.get('kind') != 'conversation']
        if not rows or not query.strip():
            return {'mode': 'empty', 'results': []}
        # Curated topic keywords are index terms, not claims: they let "cost" find the commercial record.
        passages = [r['title'] + '. ' + r['text'] + (' Topics: ' + ', '.join(r['topics']) + '.' if r.get('topics') else '')
                    for r in rows]

        def words(text):
            # The core tokenizer splits on whitespace only: strip punctuation ("pricing?" = "pricing,")
            # and conversational filler, which otherwise dominates BM25 on a tiny corpus.
            return [w for w in _tokenize(re.sub(r"[^\w\s-]", ' ', text)) if w not in STOPWORDS]
        lexical = list(BM25Plus([words(t) for t in passages]).get_scores(words(query)))
        semantic, mode = None, 'lexical'
        if retrieval is not None and retrieval.embedder is not None and retrieval.cache is not None:
            try:
                vectors = retrieval.cache.get_or_embed(retrieval.embedder, passages)
                query_vector = retrieval.embedder.embed([query])[0]
                semantic, mode = [_cosine(query_vector, v) for v in vectors], 'hybrid'
            except Exception:
                semantic = None
        threshold = retrieval._relevant if retrieval is not None else (lambda lex, sem: lex > 0)
        results = [
            {'id': rows[i]['id'], 'score': round(float(score), 4), 'lexical': round(float(lexical[i]), 4),
             'similarity': None if semantic is None else round(float(semantic[i]), 4),
             'relevant': bool(threshold(lexical[i], None if semantic is None else semantic[i]))}
            for i, score in RetrievalService._fuse(lexical, semantic)]
        # The platform search drops irrelevant passages; here they are kept for routing but ranked last.
        results.sort(key=lambda r: not r['relevant'])
        return {'mode': mode, 'results': results}

    def digest(self, rows=None):
        """Content hash of what Tiberius may say: enabled records and usable spoken answers."""
        rows = self.catalog() if rows is None else rows
        enabled = sorted((r['id'], r['sha256']) for r in rows if r['eligible'])
        spoken = sorted((v['id'], v['text_sha256']) for v in self.spoken_catalog(rows) if v['usable'])
        return sha(json.dumps([enabled, spoken]).encode())

    # ---- Spoken answers: approved wording that can be pre-rendered in the live voice ----

    def spoken(self):
        return json.loads(self.spoken_path.read_text()) if self.spoken_path.exists() else []

    def _save_spoken(self, rows):
        temporary = self.spoken_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(rows, indent=2) + '\n')
        temporary.replace(self.spoken_path)

    def spoken_catalog(self, rows=None):
        """Every spoken variant with ``usable``: approved, wording intact and bound to the current enabled record."""
        records = {r['id']: r for r in (self.catalog() if rows is None else rows)}
        result = []
        for variant in self.spoken():
            record = records.get(variant['record_id'])
            current = bool(record and record['eligible'] and record['sha256'] == variant['record_sha256'])
            intact = sha(variant['text'].encode()) == variant['text_sha256']
            result.append({**variant, 'current': current,
                           'usable': variant['status'] == 'approved' and current and intact})
        return result

    def add_spoken(self, record_id, text, origin):
        """Store a pending spoken variant. Checked against its record; never approved here."""
        text = ' '.join(str(text).split())
        if not 1 <= len(text) <= SPOKEN_LIMIT:
            raise ValueError(f'Use 1–{SPOKEN_LIMIT} characters for a spoken answer')
        with self.lock:
            record = next((r for r in self.catalog() if r['id'] == record_id), None)
            if not record or not record['eligible']:
                raise ValueError('Enable the record before drafting spoken wording for it')
            if problems := claims.unsupported(text, record['title'] + '. ' + record['text']):
                raise ValueError('The wording goes beyond its record: ' + '; '.join(problems[:3]))
            qualifier = claims.qualifier_for([record])
            if qualifier and not claims.has_qualifier(text):
                text = qualifier + ' ' + text
            rows = self.spoken()
            existing = next((v for v in rows if v['record_id'] == record_id and v['text'] == text
                             and v['record_sha256'] == record['sha256'] and v['status'] != 'rejected'), None)
            if existing:
                return existing
            variant = {'id': sha(f"{record_id}:{record['sha256']}:{text}".encode())[:24], 'record_id': record_id,
                       'record_sha256': record['sha256'], 'text': text, 'text_sha256': sha(text.encode()),
                       'status': 'pending', 'origin': origin, 'created_at': datetime.now(timezone.utc).isoformat(),
                       'review': None}
            self._save_spoken([*rows, variant])
            return variant

    def review_spoken(self, variant_id, expected_hash, approve):
        with self.lock:
            rows = self.spoken()
            variant = next((v for v in rows if v['id'] == variant_id), None)
            if not variant or variant['text_sha256'] != expected_hash or sha(variant['text'].encode()) != expected_hash:
                raise ValueError('Spoken wording changed; refresh the review')
            record = next((r for r in self.catalog() if r['id'] == variant['record_id']), None)
            if approve and (not record or not record['eligible'] or record['sha256'] != variant['record_sha256']):
                raise ValueError('The record changed or is not enabled; review the record first')
            variant['status'] = 'approved' if approve else 'rejected'
            variant['review'] = {'actor': 'local operator', 'scope': 'internal rehearsal only',
                                 'at': datetime.now(timezone.utc).isoformat(), 'hash': expected_hash}
            self._save_spoken(rows)
            with (self.register.base_dir / 'sales-review-history.jsonl').open('a') as log:
                log.write(json.dumps({'spoken': variant_id, 'decision': variant['status'], **variant['review']}) + '\n')
            return variant
