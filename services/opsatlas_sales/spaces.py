"""Knowledge spaces (KS E1): governed boundaries that every document, fact and conversation belongs to.

A space is a partition: its own data directory holding today's stores (source register, sections, content
management, ontology, process registry, governance, analytics). Each space's API is served by its own core, built by
``assistant.api.app.create_app`` on that partition, so a request for one space can only ever reach that space's data.

* The OpsAtlas family: the **Product Guide** (what OpsAtlas is and how to use it; readable by every user), the internal
  **Sales Playbook** (commercial position, path to production, owner notes, contributed claims and the DT603 paper
  sections used as evidence) and **System** settings (Tibi's conversation style). They are one owner's knowledge about
  one product, so Tibi's curated records, the product ontology and the statement review span the family through the
  facades below, while each space's own pages (sources, written answers, documents) see only that space.
* **Organisations** (phase 2): one space each, never compared or mixed with another.

The Product Guide keeps the workspace's original ``core`` directory as its partition, so nothing is moved on disk for
it; every other space lives under ``spaces/<id>/core``. Each space's path is in ``spaces.json``.
"""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from assistant.ingestion.store import SectionStore
from assistant.sources.register import SourceRegister

PRODUCT, PLAYBOOK, SYSTEM = 'product-guide', 'sales-playbook', 'system'
FAMILY = (PRODUCT, PLAYBOOK, SYSTEM)
ORGANISATION = 'organisation'

# What the Product Guide says when a question is not in it (ARCH H2, the Human's direction of 30 September 2026): the
# graceful redirect a customer should hear, not the plain refusal an organisation's space keeps. Written to the
# guide's partition as space-config.json once, if absent; from then on the file is the owner's to edit.
PRODUCT_GUIDE_CONFIG = {
    'refusal': ('That is not covered by the OpsAtlas product guide. For pricing, certifications, customer references, '
                'release plans and possible enhancements, please contact the sales team, who can give you further information.'),
    'guardrails': {'scope_message': ('I can answer questions about OpsAtlas from its product guide; for anything else, '
                                     'please contact the sales team.')},
}
HEADER = 'x-opsatlas-space'
DEFAULT_SPACES = [
    {'id': PRODUCT, 'kind': 'product', 'name': 'OpsAtlas Product Guide', 'path': 'core',
     'about': 'What OpsAtlas is, how it is built, what it does and how to use it. Every user may read it.'},
    {'id': PLAYBOOK, 'kind': 'playbook', 'name': 'OpsAtlas Sales Playbook', 'path': 'spaces/sales-playbook/core',
     'about': 'Internal: commercial position, path to production, owner notes, contributed claims and the evidence behind '
              'the guide.'},
    {'id': SYSTEM, 'kind': 'system', 'name': 'System settings', 'path': 'spaces/system/core',
     'about': "How Tibi converses: its personality, small talk and boundaries. Administrators only."},
]
# Where the family's own documents belong (the Human's decision 2, 28 September 2026): the commercial records, contributed
# claims and the evidence the records cite are internal (the playbook); Tibi's conversation style is a system setting.
PLAYBOOK_RECORDS = {'commercial', 'next-steps'}
# The content-management tables that hold a document's history, by source.
CONTENT_TABLES = ('documents', 'versions', 'comments', 'activity', 'suggestions_seen', 'suggestions_settled')
ASSET = re.compile(r'/api/content/assets/([A-Za-z0-9._-]+)')


def now():
    return datetime.now(timezone.utc).isoformat()


class Spaces:
    """The spaces registry of one workspace: ``spaces.json`` at its root."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.path = self.root / 'spaces.json'
        self.lock = threading.Lock()
        if not self.path.exists():
            self._save([{**space, 'status': 'active', 'created_at': now()} for space in DEFAULT_SPACES])

    def _save(self, spaces):
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps({'schema': 1, 'spaces': spaces}, indent=1) + '\n')
        temporary.replace(self.path)

    def all(self) -> list[dict]:
        return json.loads(self.path.read_text())['spaces']

    def active(self) -> list[dict]:
        return [s for s in self.all() if s.get('status', 'active') == 'active']

    def _update(self, change):
        """Read, change and write ``spaces.json`` under the lock, keeping everything else in it (``placed``)."""
        with self.lock:
            data = json.loads(self.path.read_text())
            result = change(data)
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(data, indent=1) + '\n')
            temporary.replace(self.path)
            return result

    def create(self, name: str, about: str = '') -> dict:
        """A new organisation space (KS S7): its id from its name, its partition under ``spaces/<id>/core``."""
        name, about = ' '.join(str(name or '').split()), ' '.join(str(about or '').split())
        if not 1 <= len(name) <= 60:
            raise ValueError('Name the organisation in 1 to 60 characters')
        if len(about) > 300:
            raise ValueError('Keep the description to 300 characters')
        base = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:40] or 'organisation'

        def change(data):
            if any(s['name'].lower() == name.lower() and s.get('status', 'active') == 'active' for s in data['spaces']):
                raise FileExistsError('A space with that name already exists')
            taken, space_id, n = {s['id'] for s in data['spaces']} | set(FAMILY), base, 2
            while space_id in taken:
                space_id, n = f'{base}-{n}', n + 1
            space = {'id': space_id, 'kind': ORGANISATION, 'name': name, 'path': f'spaces/{space_id}/core', 'about': about,
                     'status': 'active', 'created_at': now()}
            data['spaces'].append(space)
            return space
        return self._update(change)

    def change(self, space_id: str, **fields) -> dict:
        """Rename, describe, archive or restore an organisation space; the OpsAtlas family's spaces are fixed. Archiving
        keeps the data: the space is only hidden and no longer served."""
        def edit(data):
            space = next((s for s in data['spaces'] if s['id'] == space_id), None)
            if space is None:
                raise KeyError(space_id)
            if space['kind'] != ORGANISATION:
                raise PermissionError('The OpsAtlas spaces cannot be renamed or archived')
            if 'name' in fields:
                name = ' '.join(str(fields['name'] or '').split())
                if not 1 <= len(name) <= 60:
                    raise ValueError('Name the organisation in 1 to 60 characters')
                if any(s is not space and s['name'].lower() == name.lower() and s.get('status', 'active') == 'active'
                       for s in data['spaces']):
                    raise FileExistsError('A space with that name already exists')
                space['name'] = name
            if 'about' in fields:
                about = ' '.join(str(fields['about'] or '').split())
                if len(about) > 300:
                    raise ValueError('Keep the description to 300 characters')
                space['about'] = about
            if 'status' in fields:
                if fields['status'] not in ('active', 'archived'):
                    raise ValueError('A space is active or archived')
                space['status'] = fields['status']
            return dict(space)
        return self._update(edit)

    def placed(self) -> set[str]:
        """Documents the family layout has already decided: it never moves them again, so a Transfer stands."""
        return set(json.loads(self.path.read_text()).get('placed', []))

    def mark_placed(self, source_ids):
        with self.lock:
            data = json.loads(self.path.read_text())
            data['placed'] = sorted(set(data.get('placed', [])) | set(source_ids))
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(data, indent=1) + '\n')
            temporary.replace(self.path)

    def get(self, space_id: str) -> dict | None:
        return next((s for s in self.all() if s['id'] == space_id), None)

    def partition(self, space_id: str) -> Path:
        space = self.get(space_id)
        if space is None:
            raise KeyError(space_id)
        path = (self.root / space['path']).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError('A space must stay inside its workspace')
        return path


class FamilyRegister:
    """The OpsAtlas family's documents as one register: each call goes to the partition that holds the document.
    New documents go to the Product Guide; the family layout then moves them where they belong."""

    def __init__(self, registers: dict[str, SourceRegister], home: str = PRODUCT):
        self.registers = registers
        self.home = home
        self.base_dir = registers[home].base_dir
        self.files_dir = registers[home].files_dir

    def space_of(self, source_id: str) -> str | None:
        return next((space for space, register in self.registers.items() if register.get(source_id) is not None), None)

    def _for(self, source_id: str) -> SourceRegister:
        space = self.space_of(source_id)
        return self.registers[space] if space else self.registers[self.home]

    def list(self):
        return [record for register in self.registers.values() for record in register.list()]

    def get(self, source_id):
        return self._for(source_id).get(source_id)

    def file_path(self, source_id):
        return self._for(source_id).file_path(source_id)

    def read_content(self, source_id):
        return self._for(source_id).read_content(source_id)

    def write_content(self, source_id, content):
        return self._for(source_id).write_content(source_id, content)

    def update(self, source_id, **fields):
        return self._for(source_id).update(source_id, **fields)

    def add(self, record, content):
        return self.registers[self.home].add(record, content)

    def remove(self, source_id):
        return self._for(source_id).remove(source_id)


class FamilySections:
    """The family's sections, each document's in its own partition."""

    def __init__(self, register: FamilyRegister, stores: dict[str, SectionStore]):
        self.register = register
        self.stores = stores
        self.dir = stores[register.home].dir

    def _for(self, source_id):
        return self.stores[self.register.space_of(source_id) or self.register.home]

    def replace_for_source(self, source_id, sections):
        return self._for(source_id).replace_for_source(source_id, sections)

    def list_for_source(self, source_id):
        return self._for(source_id).list_for_source(source_id)

    def count_for_source(self, source_id):
        return self._for(source_id).count_for_source(source_id)

    def remove_for_source(self, source_id):
        return self._for(source_id).remove_for_source(source_id)


class FamilyActions:
    """Platform actions on the family's documents, each executed by the core of the space that holds the document."""

    def __init__(self, register: FamilyRegister, engines: dict):
        self.register = register
        self.engines = engines

    def execute(self, name, payload, actor):
        space = self.register.space_of((payload or {}).get('source_id', '')) or self.register.home
        return self.engines[space].execute(name, payload, actor)

    def __getattr__(self, name):  # anything else (for example side effects) is the Product Guide's
        return getattr(self.engines[self.register.home], name)


def _content_db(base_dir: Path) -> Path:
    return Path(base_dir) / 'content' / 'content.db'


def _move_content(source_id: str, source_dir: Path, target_dir: Path, folder: list[str] | None):
    """Move a document's content-management history (drafts, versions, comments and replies, activity, suggestions)
    and place it in the target's library under ``folder`` (group titles, created if missing), or at the top level."""
    from assistant.content.store import ContentStore
    ContentStore(target_dir)  # the target's tables exist
    origin, target = _content_db(source_dir), _content_db(target_dir)
    if not origin.exists():
        return
    with sqlite3.connect(origin) as src, sqlite3.connect(target) as dst:
        src.row_factory = sqlite3.Row
        comment_ids = [r['id'] for r in src.execute('SELECT id FROM comments WHERE source_id=?', (source_id,))]
        for table in CONTENT_TABLES:
            rows = src.execute(f'SELECT * FROM {table} WHERE source_id=?', (source_id,)).fetchall()
            for row in rows:
                columns = list(row.keys())
                if table == 'activity':  # activity ids are the target's own sequence
                    columns = [c for c in columns if c != 'id']
                dst.execute(f"INSERT OR REPLACE INTO {table} ({','.join(columns)}) VALUES ({','.join('?' * len(columns))})",
                            [row[c] for c in columns])
            src.execute(f'DELETE FROM {table} WHERE source_id=?', (source_id,))
        for comment_id in comment_ids:
            for row in src.execute('SELECT * FROM replies WHERE comment_id=?', (comment_id,)).fetchall():
                dst.execute(f"INSERT OR REPLACE INTO replies ({','.join(row.keys())}) VALUES ({','.join('?' * len(row))})",
                            list(row))
            src.execute('DELETE FROM replies WHERE comment_id=?', (comment_id,))
        src.execute('DELETE FROM placements WHERE source_id=?', (source_id,))
        parent = None
        for title in folder or []:
            found = dst.execute('SELECT id FROM groups WHERE title=? AND parent IS ?', (title, parent)).fetchone()
            if found:
                parent = f'group:{found[0]}'
                continue
            import uuid
            group_id = uuid.uuid4().hex[:12]
            position = (dst.execute('SELECT COALESCE(MAX(position), 0) FROM groups WHERE parent IS ?', (parent,)).fetchone()[0]
                        or 0) + 1
            dst.execute('INSERT INTO groups (id, title, parent, position, created_at) VALUES (?, ?, ?, ?, ?)',
                        (group_id, title, parent, position, now()))
            parent = f'group:{group_id}'
        position = (dst.execute('SELECT COALESCE(MAX(position), 0) FROM placements WHERE parent IS ?', (parent,)).fetchone()[0]
                    or 0) + 1
        dst.execute('INSERT OR REPLACE INTO placements (source_id, parent, position) VALUES (?, ?, ?)', (source_id, parent, position))
        # The target library is seeded already: a new group set must not be overwritten by its starting groups.
        dst.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('library_keys', '{}')")


def move_document(source_id: str, source: tuple, target: tuple, *, keep_approval: bool, folder: list[str] | None = None,
                  actor: str = 'local operator', note: str = '') -> dict:
    """Move one document from one partition to another, whole: its register entry and file, sections, content history,
    library place and the images it uses. ``source`` and ``target`` are (register, sections) pairs.

    ``keep_approval`` is for restructuring the family's own content (the migration). A Transfer by an administrator
    arrives unapproved in the target, to be reviewed there."""
    (src_register, src_sections), (dst_register, dst_sections) = source, target
    record = src_register.get(source_id)
    if record is None:
        raise KeyError(source_id)
    if dst_register.get(source_id) is not None:
        raise ValueError('The target space already holds this document')
    content = src_register.read_content(source_id)
    fields = record.model_dump()
    dst_register.add(record, content)
    if not keep_approval:
        fields['approval_status'] = 'pending'
    dst_register.update(source_id, **{k: v for k, v in fields.items() if k not in ('id',)})
    dst_sections.replace_for_source(source_id, src_sections.list_for_source(source_id))
    _move_content(source_id, src_register.base_dir, dst_register.base_dir, folder)
    for name in set(ASSET.findall(content.decode('utf-8', 'replace'))):
        asset = Path(src_register.base_dir) / 'content' / 'assets' / name
        if asset.is_file():
            destination = Path(dst_register.base_dir) / 'content' / 'assets' / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(asset, destination)
    src_sections.remove_for_source(source_id)
    src_register.remove(source_id)
    return {'source_id': source_id, 'title': record.title, 'approval': fields['approval_status'], 'note': note, 'actor': actor}


def family_space(record: dict | None, cited: bool) -> str | None:
    """The family space a document belongs in (decision 2), or None to leave it where it is: a record's document by
    its kind; evidence a record cites in the playbook; any other document stays where it was put."""
    if record is not None:
        if record.get('kind') == 'conversation':
            return SYSTEM
        if record['id'] in PLAYBOOK_RECORDS or record.get('provenance'):
            return PLAYBOOK
        return PRODUCT
    return PLAYBOOK if cited else None


def default_folder(record: dict | None, source, space: str) -> list[str]:
    """Where a placed document sits in its new space's library when its old place is not known (a new workspace)."""
    if record is None:
        return ['Evidence', 'DT603 paper' if (source.title or '').startswith('DT603') else 'Owner notes']
    if space == SYSTEM:
        return ['Conversation style']
    return ['Contributed claims'] if record.get('provenance') else ['Commercial and roadmap']


def apply_family_layout(knowledge, register: FamilyRegister, sections: FamilySections, spaces: Spaces) -> list[dict]:
    """Put each family document in the space it belongs in, keeping its approval, history and folder: the migration of
    an existing workspace, and the placing of a new one's or a new claim's documents. Each document is decided once, so
    an administrator's later Transfer stands. Folders the moves leave empty are removed, and no others."""
    rows = knowledge.records()
    records = {r['source_id']: r for r in rows}
    cited = {ref['source_id'] for r in rows for ref in r.get('references', [])}
    placed = spaces.placed()
    moved, emptied, decided = [], {}, []
    for source in register.list():
        if source.id in placed:
            continue
        decided.append(source.id)
        want = family_space(records.get(source.id), source.id in cited)
        have = register.space_of(source.id)
        if want is None or have == want or have is None:
            continue
        chain = library_chain(register.registers[have].base_dir, source.id)
        folder = [title for _, title in chain] or default_folder(records.get(source.id), source, want)
        emptied.setdefault(have, set()).update(group for group, _ in chain)
        moved.append({**move_document(source.id, (register.registers[have], sections.stores[have]),
                                      (register.registers[want], sections.stores[want]), keep_approval=True, folder=folder,
                                      note='placed by the family layout'), 'from': have, 'to': want})
    if moved:
        # The guide's starting folders for what now lives in other spaces go too, when empty; the Human's own stay.
        emptied.setdefault(register.home, set()).update(_starting_groups(register.base_dir, MOVED_STARTING_FOLDERS))
    for space, groups in emptied.items():
        prune_emptied(register.registers[space].base_dir, groups)
    spaces.mark_placed(decided)
    return moved


# The sales workspace's starting folders whose documents now live in the playbook or system settings.
MOVED_STARTING_FOLDERS = ('conversation', 'claims', 'evidence', 'paper', 'notes')


def _starting_groups(base_dir: Path, keys) -> set[str]:
    path = _content_db(base_dir)
    if not path.exists():
        return set()
    with sqlite3.connect(path) as db:
        row = db.execute("SELECT value FROM meta WHERE key='library_keys'").fetchone()
    known = json.loads(row[0]) if row and row[0] else {}
    return {known[k] for k in keys if k in known}


def prune_emptied(base_dir: Path, groups: set[str]):
    """Remove the given groups where they now hold nothing (no document or group beneath them), deepest first."""
    path = _content_db(base_dir)
    if not groups or not path.exists():
        return
    with sqlite3.connect(path) as db:
        changed = True
        while changed:
            changed = False
            for group in list(groups):
                key = f'group:{group}'
                used = db.execute('SELECT 1 FROM placements WHERE parent=? UNION SELECT 1 FROM groups WHERE parent=?',
                                  (key, key)).fetchone()
                if not used:
                    deleted = db.execute('DELETE FROM groups WHERE id=?', (group,)).rowcount
                    groups.discard(group)
                    changed = changed or bool(deleted)


def library_chain(base_dir: Path, source_id: str) -> list[tuple[str, str]]:
    """The groups (id, title) a document sits under in its library, top first (documents it sits under are skipped)."""
    path = _content_db(base_dir)
    if not path.exists():
        return []
    with sqlite3.connect(path) as db:
        groups = {r[0]: (r[1], r[2]) for r in db.execute('SELECT id, title, parent FROM groups')}
        placements = {r[0]: r[1] for r in db.execute('SELECT source_id, parent FROM placements')}
    chain, parent, seen = [], placements.get(source_id), set()
    while parent and parent not in seen:
        seen.add(parent)
        kind, _, key = parent.partition(':')
        if kind == 'group' and key in groups:
            chain.insert(0, (key, groups[key][0]))
            parent = groups[key][1]
        elif kind == 'source':
            parent = placements.get(key)
        else:
            break
    return chain


# Routes that belong to the workspace, not to a space: sign-in, services, the activity and conversation logs, Tibi and
# its knowledge (the OpsAtlas family), and the spaces themselves.
WORKSPACE_ROUTES = ('/api/auth', '/api/services', '/api/activity', '/api/conversations', '/api/sales', '/api/tibi',
                    '/api/spaces')


def requested_space(scope) -> str | None:
    """The space a request names: the X-OpsAtlas-Space header, or ``?space=`` where a header cannot be sent (an image
    in a document)."""
    for name, value in scope.get('headers') or []:
        if name.decode('latin-1').lower() == HEADER:
            return value.decode('latin-1').strip() or None
    from urllib.parse import parse_qs
    values = parse_qs(scope.get('query_string', b'').decode('latin-1')).get('space')
    return values[0] if values else None


class SpaceRouter:
    """Serve each space-scoped API request from that space's own core (KS S2). A request that names no space is the
    Product Guide's, which every signed-in user may read; a request naming an unknown space is refused. A space's core
    only holds its own partition, so nothing here can mix two spaces' data."""

    def __init__(self, app, cores: dict):
        self.app, self.cores = app, cores

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http' and scope['path'].startswith('/api/') and not scope['path'].startswith(WORKSPACE_ROUTES):
            space = requested_space(scope)
            if space and space != PRODUCT:
                core = self.cores.get(space)
                if core is None:
                    body = json.dumps({'detail': 'No such space'}).encode()
                    await send({'type': 'http.response.start', 'status': 404,
                                'headers': [(b'content-type', b'application/json'), (b'content-length', str(len(body)).encode())]})
                    await send({'type': 'http.response.body', 'body': body})
                    return
                await core(scope, receive, send)
                return
        await self.app(scope, receive, send)
