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
        expected = ('# ' + row['title'] + '\n\n' + row['text'] + '\n').encode()
        if sha(expected) != row['sha256']:
            return False
        source = self.register.get(row['source_id'])
        if not source or source.approval_status != 'approved' or row['approval'] != 'approved':
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
        return [{**row, 'eligible': self.eligible(row)} for row in self.records()]

    def decide(self, identifier, expected_hash, approve):
        with self.lock:
            rows = self.records()
            row = next((r for r in rows if r['id'] == identifier), None)
            if not row:
                raise ValueError('Unknown record')
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
            return {**row, 'eligible': self.eligible(row)}
