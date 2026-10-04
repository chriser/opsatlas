"""Pre-rendered audio for human-approved spoken answers, keyed by voice and wording hash.

Only wording a human approved is stored here, so replaying it cannot speak anything new.
A changed record withdraws its spoken wording upstream; stale entries are simply never
requested again. The store is bounded and lives in the voice service's runtime.
"""
import json
import re
from pathlib import Path

LIMIT_BYTES = 64_000_000


class SpokenAudio:
    def __init__(self, runtime: Path):
        self.root = Path(runtime) / 'spoken-audio'

    def _path(self, engine, key):
        if not re.fullmatch(r'[a-z_]{2,20}', engine) or not re.fullmatch(r'[0-9a-f]{64}', key or ''):
            raise ValueError('Invalid spoken-audio key')
        return self.root / engine / (key + '.json')

    def get(self, engine, key):
        try:
            path = self._path(engine, key)
        except ValueError:
            return None
        if not path.exists():
            return None
        try:
            chunks = json.loads(path.read_text())
        except ValueError:
            return None
        return chunks if isinstance(chunks, list) and chunks else None

    def put(self, engine, key, chunks):
        path = self._path(engine, key)
        data = json.dumps(chunks)
        existing = sum(p.stat().st_size for p in self.root.rglob('*.json')) if self.root.exists() else 0
        if existing + len(data) > LIMIT_BYTES:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.tmp')
        temporary.write_text(data)
        temporary.replace(path)
        return True
