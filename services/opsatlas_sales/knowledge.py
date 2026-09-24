"""Hash-bound curated records stored through Atlas registration and ingestion."""
import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from assistant.ingestion.service import ingest_source
from assistant.ingestion.store import SectionStore
from assistant.sources.service import register_upload

from .workspace import REPO


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
        self.lock = threading.Lock()

    def records(self):
        return json.loads(self.path.read_text()) if self.path.exists() else []

    def _save(self, rows):
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(rows, indent=2) + '\n')
        temporary.replace(self.path)

    def seed(self):
        with self.lock:
            if self.path.exists():
                return self.catalog()
            cards = json.loads((Path(__file__).parent / 'corpus/product.json').read_text())
            rows = []
            for card in cards:
                refs = []
                for relative in card['references']:
                    data = (REPO / relative).read_bytes()
                    # Retain exact originals in the isolated source register as pending evidence.
                    existing = next((s for s in self.register.list() if s.content_sha256 == sha(data)), None)
                    filename = Path(relative).name + ('.txt' if relative.endswith('.py') else '')
                    source = existing or register_upload(self.register, filename, data, relative)
                    if not existing:
                        ingest_source(self.register, self.sections, source.id)
                    refs.append({'path': relative, 'source_id': source.id, 'sha256': sha(data)})
                body = ('# ' + card['title'] + '\n\n' + card['text'] + '\n').encode()
                source = register_upload(self.register, card['id'] + '.md', body, card['title'])
                ingest_source(self.register, self.sections, source.id)
                rows.append({**card, 'references': refs, 'source_id': source.id, 'sha256': sha(body),
                             'audience': 'internal_rehearsal', 'approval': 'pending', 'review': None})
            self._save(rows)
            return self.catalog()

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
                or data['topic'] not in ('overview', 'governance', 'retrieval', 'process',
                                         'deployment', 'limitations', 'tiberius', 'commercial')
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
