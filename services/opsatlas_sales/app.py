"""Separate loopback Atlas instance plus a read-only product-evidence contract."""
import hashlib
import json
import os
import secrets
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from assistant import settings

from . import foundation
from .workspace import REPO, workspace


class Decision(BaseModel):
    expected_hash: str
    approve: bool


class Search(BaseModel):
    q: str


class SpokenDraft(BaseModel):
    record_id: str
    text: str


class Restart(BaseModel):
    which: str = 'tibi'


class Transfer(BaseModel):
    source_id: str
    to: str


class NewSpace(BaseModel):
    name: str
    about: str = ''


class SpaceChange(BaseModel):
    name: str | None = None
    about: str | None = None
    status: str | None = None


class BrowserEvents(BaseModel):
    events: list[dict]


class TurnReview(BaseModel):
    verdict: str | None = None
    note: str = ''


PROFILE = Path(__file__).parent / 'profile.json'


def apply_profile(path=PROFILE):
    """The Sales profile over the environment: 'set' wins, 'default' fills a gap, 'remove' clears. Only registered
    settings may appear, so a typo cannot pass silently."""
    profile = json.loads(Path(path).read_text())
    for name in [*profile['set'], *profile['default'], *profile['remove']]:
        settings.SETTINGS[name]
    for name in profile['remove']:
        os.environ.pop(name, None)
    os.environ.update(profile['set'])
    for name, value in profile['default'].items():
        os.environ.setdefault(name, value)


def create_sales_app(root=None):
    root = workspace() if root is None else workspace(root)
    credential = (root / 'local-access.key').read_text().strip()  # the sidecars' service credential (x-sales-token)
    # The Sales profile (AUDIT F12): the model, rewrite and rerank off, no shared password (personal accounts in
    # <root>/iam.db), the diagram service launchd's (PI F1), the one operator's name for edits (CM S26).
    apply_profile()
    # Not inherited: this workspace's own data folder, and the diagram service's log with the other service logs.
    os.environ['KP_DATA_DIR'] = str(root / 'core')
    os.environ['PROCESS_DIAGRAM_LOG_PATH'] = str(REPO / '.runtime/opsatlas-sales-logs/diagrams.log')
    from assistant.api.app import create_app
    from assistant.sources.register import SourceRegister

    from .knowledge import Knowledge
    from .ontology import ProductOntology
    from .spaces import FAMILY, PRODUCT, PRODUCT_GUIDE_CONFIG, FamilyActions, FamilyRegister, FamilySections, Spaces, apply_family_layout
    # Knowledge spaces (KS E1): the Product Guide's core is this app, on the workspace's original ``core`` directory;
    # every other space has its own core on its own partition, sharing only the sign-in.
    spaces = Spaces(root)
    from assistant.space_config import SpaceConfig
    SpaceConfig.ensure(root / 'core', SpaceConfig.model_validate(PRODUCT_GUIDE_CONFIG))  # the guide's wording, set once (ARCH H2)
    from assistant.api.access import current_actor, need, public, service
    from assistant.api.access import signed_in as handler_checks
    from assistant.api.auth import AuthService
    auth = AuthService.from_workspace(root, origin=settings.get('OPSATLAS_ORIGIN'), guide_space=PRODUCT)
    for space in spaces.all():  # the policy knows every space; a platform administrator's bindings follow (IAM F4)
        auth.register_space(space['id'], space['name'], space['kind'], space.get('status', 'active'))
    app = create_app(auth=auth, space_id=PRODUCT)
    cores = {PRODUCT: app}

    def build_core(space_id):
        """A space's own core on its own partition. Built at start, and when an organisation space is created or
        restored (KS S7): the router serves it at once, without a restart."""
        partition = spaces.partition(space_id)
        partition.mkdir(parents=True, exist_ok=True)
        cores[space_id] = create_app(register=SourceRegister(partition), auth=app.state.auth, space_id=space_id)

    for space in spaces.active():  # an archived space keeps its data but is not served
        if space['id'] != PRODUCT:
            build_core(space['id'])
    app.state.spaces, app.state.cores = spaces, cores
    from .spaces import SpaceRouter
    app.add_middleware(SpaceRouter, cores=cores)  # inside the host and activity checks added below
    # The activity log (OBS F1): every request, what the page did and Tibi's socket, for diagnosing what happened.
    from .activity import ActivityLog
    activity = ActivityLog(root, 'core', secrets=(credential,))
    browser_log = ActivityLog(root, 'browser', secrets=(credential,))
    app.state.activity = activity
    activity.write('service', event='OpsAtlas started', pid=os.getpid(), workspace=str(root))
    # The OpsAtlas family (KS S3): Tibi's records, the product ontology and the statement review span the guide, the
    # playbook and system settings; each space's own pages see only that space.
    register = FamilyRegister({s: cores[s].state.register for s in FAMILY})
    sections = FamilySections(register, {s: cores[s].state.section_store for s in FAMILY})
    actions = FamilyActions(register, {s: cores[s].state.actions for s in FAMILY})
    app.state.family_register = register
    knowledge = Knowledge(register, actions, sections)
    corpus, papers = foundation.active()
    knowledge.seed(corpus, papers)
    knowledge.seed_conversation(foundation.CORPUS / 'conversation.json')
    # Each family document in the space it belongs in (KS S4): the migration of an existing workspace, once; a new
    # workspace's documents as they are seeded. Approvals, history and folders move with them.
    placed = apply_family_layout(knowledge, register, sections, spaces)
    if placed:
        activity.write('service', event='documents placed in their spaces', moved=len(placed),
                       spaces=sorted({m['to'] for m in placed}))
    app.state.sales = knowledge
    # The product ontology has its own schema and database: rebuilding it never touches the core ontology.
    ontology = ProductOntology(register.base_dir / 'product-ontology.db')
    ontology.ensure(knowledge.catalog())
    app.state.product_ontology = ontology
    from .governance import GovernanceDesk
    desk = GovernanceDesk(register, sections, app.state.retrieval, actions, knowledge)
    app.state.governance_desk = desk
    # Content management keeps records consistent when their documents are edited (CM S12), in every family space.
    from .content import attach as attach_content
    for space in FAMILY:
        attach_content(cores[space].state.content, knowledge, desk, library=space == PRODUCT)
    # Tibi inside the control panel: the same workflows behind the OpsAtlas operator sign-in.
    from .tibi_api import build_router, voice_url
    from .tibi_proxy import attach as attach_tibi
    voice = voice_url()
    app.include_router(build_router(app, knowledge, ontology, desk, voice))
    attach_tibi(app, voice, activity)  # the gateway to the Tibi service, behind the OpsAtlas sign-in

    @app.post('/api/services/restart', dependencies=[need('platform.services.restart', scope='platform')])
    def restart_services(data: Restart):
        """Restart services from the control panel: Tibi alone (the operator stays signed in), the process diagram
        service alone, or everything, this core last (sign-ins are held in memory, so the operator signs in again)."""
        from . import manage
        if data.which not in ('tibi', 'diagrams', 'all'):
            raise HTTPException(400, 'Restart "tibi", "diagrams" or "all"')
        activity.write('service', event='restart requested', which=data.which)
        restarting = []
        try:
            if data.which in ('tibi', 'all'):
                manage.restart('voice')
                restarting.append('tibi')
            if data.which == 'diagrams' or (data.which == 'all' and manage.loaded('diagrams')):
                manage.restart('diagrams')
                restarting.append('diagrams')
            if data.which == 'all':
                manage.restart_later('core')
                restarting.append('core')
        except (RuntimeError, subprocess.CalledProcessError) as exc:
            activity.write('service', event='restart refused', which=data.which, error=str(exc))
            raise HTTPException(409, str(exc) if isinstance(exc, RuntimeError) else 'launchd could not restart the service') from exc
        return {'restarting': restarting, 'sign_in_again': data.which == 'all'}

    @app.post('/api/services/start', dependencies=[need('platform.services.restart', scope='platform')])
    def start_service(data: Restart):
        """Start the process diagram service under launchd (PI F1), for a workspace set up before it joined the Sales
        services. A running service is left alone."""
        from . import manage
        if data.which != 'diagrams':
            raise HTTPException(400, 'Only the process diagram service is started from here')
        activity.write('service', event='start requested', which=data.which)
        try:
            manage.start(only='diagrams')
        except (RuntimeError, subprocess.CalledProcessError) as exc:
            activity.write('service', event='start refused', which=data.which, error=str(exc))
            raise HTTPException(409, str(exc) if isinstance(exc, RuntimeError) else 'launchd could not start the service') from exc
        return {'started': 'diagrams'}

    @app.middleware('http')
    async def boundary(request: Request, call_next):
        host = request.headers.get('host', '')
        if host.split(':')[0] not in ('127.0.0.1', 'localhost', 'testserver'):
            return HTMLResponse('Local workspace only', status_code=403)
        origin = request.headers.get('origin')
        if origin and origin != f'{request.url.scheme}://{host}':
            return HTMLResponse('Use the sales workspace', status_code=403)
        response = await call_next(request)
        response.headers['X-OpsAtlas-Workspace'] = 'opsatlas-sales'
        response.headers['Cache-Control'] = 'no-store'
        return response

    from .activity import POLLS

    @app.middleware('http')
    async def record(request: Request, call_next):
        """Every request in the activity log, with the page it came from; sign-ins as their own events."""
        started = time.perf_counter()
        path = request.url.path
        fields = {'method': request.method, 'path': path, 'view': request.headers.get('x-opsatlas-view') or None,
                  'poll': path in POLLS or None}
        if request.url.query:
            fields['query'] = dict(request.query_params)
        try:
            response = await call_next(request)
        except Exception as exc:
            activity.write('http', **fields, status=500, ms=round((time.perf_counter() - started) * 1000, 1),
                           error=type(exc).__name__)
            raise
        ms = round((time.perf_counter() - started) * 1000, 1)
        if path.startswith(('/api/', '/services/')):
            activity.write('http', **fields, status=response.status_code, ms=ms)
        elif not path.startswith('/assets/'):
            activity.write('http', method=request.method, path=path, status=response.status_code, ms=ms, page=True)
        if path == '/api/auth/login' and request.method == 'POST':
            activity.write('auth', event='signed in' if response.status_code == 200 else 'sign-in refused',
                           status=response.status_code)
        elif path == '/api/auth/logout':
            activity.write('auth', event='signed out')
        return response

    # The conversation log (OBS F2): Tibi writes each turn; the Human reviews sessions and marks turns here.
    from . import conversations

    @app.get('/api/conversations', dependencies=[need('conversations.read_all')])
    def conversation_sessions(days: int = 30):
        return {'sessions': conversations.sessions(root, min(max(days, 1), 365))}

    @app.get('/api/conversations/flagged', dependencies=[need('conversations.read_all')])
    def conversation_flags():
        return {'turns': conversations.flagged(root)}

    @app.get('/api/conversations/{identifier}', dependencies=[need('conversations.read_all')])
    def conversation(identifier: str):
        try:
            return conversations.session(root, identifier)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.put('/api/conversations/{identifier}/turns/{turn}/review', dependencies=[need('conversations.review')])
    def review_turn(identifier: str, turn: int, data: TurnReview, request: Request):
        try:
            row = conversations.review(root, identifier, turn, data.verdict, data.note, current_actor(request).display_name)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        activity.write('review', event='marked a turn', session=identifier, turn=turn, verdict=data.verdict)
        return row

    # Knowledge spaces (KS S1, S5): what spaces there are, and an administrator's Transfer between them.
    from .spaces import move_document

    @app.get('/api/spaces', dependencies=[handler_checks('the spaces the caller may read; archived ones for whoever may create spaces')])
    def list_spaces(request: Request):
        actor = current_actor(request)
        visible = []
        for space in spaces.all():
            if space.get('status') == 'archived':
                if not actor.can('spaces.create'):
                    continue
            elif not actor.can('spaces.read', space['id']):
                continue
            visible.append({**{k: space.get(k) for k in ('id', 'kind', 'name', 'about', 'status')},
                            'documents': len(cores[space['id']].state.register.list()) if space['id'] in cores else 0})
        return {'spaces': visible}

    @app.post('/api/spaces', dependencies=[need('spaces.create', scope='platform')])
    def create_space(data: NewSpace):
        """A new organisation space (KS S7), empty and served at once. Organisations are outside the OpsAtlas family:
        nothing in them reaches Tibi's product knowledge."""
        try:
            space = spaces.create(data.name, data.about)
        except FileExistsError as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        auth.register_space(space['id'], space['name'], space['kind'])
        build_core(space['id'])
        activity.write('spaces', event='space created', space=space['id'], space_kind=space['kind'])
        return {**space, 'documents': 0}

    @app.patch('/api/spaces/{space_id}', dependencies=[handler_checks('spaces.update, spaces.archive or spaces.restore in that space')])
    def change_space(space_id: str, data: SpaceChange, request: Request):
        """Rename, describe, archive or restore an organisation space. Archiving keeps its data and stops serving it."""
        fields = data.model_dump(exclude_none=True)
        actor = current_actor(request)
        wanted = {'archived': 'spaces.archive', 'active': 'spaces.restore'}.get(fields.get('status', ''), 'spaces.update')
        actor.require(wanted, space_id)
        if wanted != 'spaces.update' and (set(fields) - {'status'}):
            actor.require('spaces.update', space_id)
        try:
            space = spaces.change(space_id, **fields)
        except KeyError as exc:
            raise HTTPException(404, 'No such space') from exc
        except PermissionError as exc:
            raise HTTPException(409, str(exc)) from exc
        except FileExistsError as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        auth.register_space(space_id, space['name'], space['kind'], space['status'])
        if space['status'] == 'archived':
            cores.pop(space_id, None)
        elif space_id not in cores:
            build_core(space_id)
        activity.write('spaces', event='space changed', space=space_id, changed=sorted(fields))
        return {**space, 'documents': len(cores[space_id].state.register.list()) if space_id in cores else 0}

    @app.post('/api/spaces/transfer', dependencies=[handler_checks('documents.transfer in the origin and sources.upload in the target')])
    def transfer(data: Transfer, request: Request):
        """Move a document to another space. It arrives unapproved, to be reviewed there. The family's records keep
        their documents and evidence inside the family, so a record's document or cited evidence cannot leave it."""
        actor = current_actor(request)
        origin = next((s for s, core in cores.items() if core.state.register.get(data.source_id)), None)
        if origin is None or not actor.can('spaces.read', origin):
            raise HTTPException(404, 'No such document')
        if data.to not in cores or not actor.can('spaces.read', data.to):
            raise HTTPException(404, 'No such space')
        actor.require('documents.transfer', origin)
        actor.require('sources.upload', data.to)
        if data.to == origin:
            raise HTTPException(409, 'The document is already in that space')
        rows = knowledge.records()
        cited = any(data.source_id == r['source_id'] or any(ref['source_id'] == data.source_id for ref in r.get('references', []))
                    for r in rows)
        if cited and data.to not in FAMILY:
            raise HTTPException(409, 'A document behind the OpsAtlas records stays in the OpsAtlas spaces')
        source = cores[origin].state
        target = cores[data.to].state
        moved = move_document(data.source_id, (source.register, source.section_store), (target.register, target.section_store),
                              keep_approval=False, actor=actor.display_name)
        for core in (cores[origin], cores[data.to]):
            core.state.rebuild_ontology()  # the document's facts leave one map and, once approved, join the other (ARCH F2)
        target.content.store.log(data.source_id, moved['actor'], 'transferred',
                                 f"From {spaces.get(origin)['name']}: it arrives unapproved, to be reviewed here")
        activity.write('spaces', event='document transferred', source=data.source_id, origin=origin, to=data.to)
        with (register.base_dir / 'sales-review-history.jsonl').open('a') as log:
            log.write(json.dumps({'transferred': data.source_id, 'from': origin, 'to': data.to, 'approval': 'pending',
                                  'at': datetime.now(timezone.utc).isoformat()}) + '\n')
        return {**moved, 'from': origin, 'to': data.to}

    @app.post('/api/activity', dependencies=[handler_checks('the caller records the events of their own page')])
    def browser_activity(data: BrowserEvents):
        """What the control panel page did, in small batches: pages, buttons, Tibi's microphone and socket, errors."""
        for event in data.events[:100]:
            if isinstance(event, dict):
                kind = str(event.pop('kind', 'action'))[:40]
                browser_log.write(kind, **{str(k)[:40]: v for k, v in list(event.items())[:20]})
        return {'recorded': min(len(data.events), 100)}

    def check(request):
        if not secrets.compare_digest(request.headers.get('x-sales-token', ''), credential):
            raise HTTPException(403, 'Sales workspace access required')
    sales_service = service(check, "the workspace credential: Tibi's governance interviewer and the read-only product contract")

    def answer_digest(rows=None):
        """What Tibi may say, in one hash: enabled records with the evidence versions they were enabled against, usable
        spoken answers, and which product facts hold (audit F01, F04). Tibi checks it again before it speaks."""
        rows = knowledge.catalog() if rows is None else rows
        ontology.ensure(rows)
        return hashlib.sha256(f'{knowledge.digest(rows)}:{ontology.digest()}'.encode()).hexdigest()
    app.state.answer_digest = answer_digest

    @app.get('/api/sales/knowledge', dependencies=[sales_service])
    def catalog(request: Request):
        check(request)
        rows = knowledge.catalog()
        return {'workspace': 'opsatlas-sales', 'records': rows, 'customer_approved': False,
                'digest': answer_digest(rows)}

    @app.get('/api/sales/digest', dependencies=[sales_service])
    def digest(request: Request):
        # Cheap revalidation before speech: changes whenever enabled records or usable spoken answers change.
        check(request)
        return {'workspace': 'opsatlas-sales', 'digest': answer_digest()}

    @app.post('/api/sales/search', dependencies=[sales_service])
    def search(data: Search, request: Request):
        check(request)
        if not 1 <= len(data.q.strip()) <= 1200:
            raise HTTPException(400, 'Use a shorter question')
        rows = knowledge.catalog()
        return {'workspace': 'opsatlas-sales', 'digest': answer_digest(rows),
                **knowledge.rank(data.q, app.state.retrieval, rows), 'ontology': ontology.match(data.q),
                'conversation': knowledge.conversation_guidance(data.q, rows)}

    @app.get('/api/sales/governance/agenda', dependencies=[sales_service])
    def governance_agenda(request: Request):
        check(request)
        return {'workspace': 'opsatlas-sales', **desk.agenda()}

    @app.post('/api/sales/governance/verify', dependencies=[sales_service])
    async def governance_verify(request: Request):
        check(request)
        data = await request.json()
        item = desk.item(str(data.get('issue_key', '')))
        if item is None or not isinstance(data.get('resolution'), dict) or not isinstance(data.get('answer'), str):
            raise HTTPException(409, 'That issue is no longer open; refresh the agenda')
        return {'workspace': 'opsatlas-sales', 'verification': desk.verify(item, data['resolution'], data['answer'][:1200])}

    @app.get('/api/sales/governance/answers', dependencies=[sales_service])
    def governance_answers(request: Request):
        check(request)
        return {'workspace': 'opsatlas-sales', 'answers': desk.answers()}

    @app.post('/api/sales/governance/answers', dependencies=[sales_service])
    async def governance_propose(request: Request):
        check(request)
        try:
            return desk.propose(await request.json())
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post('/api/sales/governance/answers/{identifier}/review', dependencies=[sales_service])
    def governance_review(identifier: str, data: Decision, request: Request):
        check(request)
        try:
            return desk.review(identifier, data.expected_hash, data.approve)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get('/api/sales/ontology', dependencies=[sales_service])
    def product_ontology(request: Request):
        check(request)
        rows = knowledge.catalog()
        return {'workspace': 'opsatlas-sales', 'digest': answer_digest(rows), **ontology.export()}

    @app.get('/api/sales/spoken', dependencies=[sales_service])
    def spoken(request: Request):
        check(request)
        rows = knowledge.catalog()
        return {'workspace': 'opsatlas-sales', 'variants': knowledge.spoken_catalog(rows), 'digest': answer_digest(rows)}

    @app.post('/api/sales/spoken', dependencies=[sales_service])
    def spoken_draft(data: SpokenDraft, request: Request):
        check(request)
        try:
            return knowledge.add_spoken(data.record_id, data.text, 'local model draft')
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post('/api/sales/spoken/{identifier}/review', dependencies=[sales_service])
    def spoken_review(identifier: str, data: Decision, request: Request):
        check(request)
        try:
            return knowledge.review_spoken(identifier, data.expected_hash, data.approve)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post('/api/sales/knowledge/{identifier}/review', dependencies=[sales_service])
    def review(identifier: str, data: Decision, request: Request):
        check(request)
        try:
            result = knowledge.decide(identifier, data.expected_hash, data.approve)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return result

    @app.get('/api/sales/source/{identifier}', dependencies=[sales_service])
    def source(identifier: str, request: Request):
        check(request)
        record = app.state.family_register.get(identifier)
        if not record:
            raise HTTPException(404)
        return {'title': record.title, 'text': app.state.family_register.read_content(identifier).decode('utf-8')}

    @app.post('/api/sales/proposals', dependencies=[sales_service])
    async def propose(request: Request):
        check(request)
        try:
            row = knowledge.propose(await request.json())
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(409, str(exc)) from exc
        apply_family_layout(knowledge, register, sections, spaces)  # a contributed claim belongs in the playbook
        if settings.get('SALES_GOVERNANCE_AUTO_REVIEW') != '0':
            # A new claim is checked against the records before the Human enables it: only its own pairs are judged.
            desk.statements.start()
        return row

    @app.post('/api/sales/knowledge/{identifier}/resolve', dependencies=[sales_service])
    async def resolve(identifier: str, request: Request):
        check(request)
        try:
            data = await request.json()
            return knowledge.adjudicate(identifier, data['expected_hash'], data['decision'], data['related'], data['reason'])
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(409, str(exc)) from exc

    # Existing built Control Panel uses same-origin /api, never the old 8010 backend.
    dist = REPO / 'frontend/dist'

    @app.get('/{path:path}', dependencies=[public('the control panel: its static files and page')])
    def frontend(path: str):
        if path.startswith('api/'):
            raise HTTPException(404)
        file = (dist / path).resolve()
        if not file.is_relative_to(dist.resolve()):
            raise HTTPException(404)
        if file.is_file() and file.name != 'index.html':
            return FileResponse(file)
        html = (dist / 'index.html').read_text()
        return HTMLResponse(html.replace('<title>', '<title>OpsAtlas Sales · '))
    return app


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(create_sales_app(), host='127.0.0.1', port=8780)
