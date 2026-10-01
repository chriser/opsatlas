"""Separate loopback Atlas instance plus a read-only product-evidence contract."""
import json
import os
import time
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from assistant import settings

from . import foundation
from .routes_conversations import build_conversations_router
from .routes_sales_api import build_sales_api_router
from .routes_spaces import build_spaces_router
from .routes_workspace import build_activity_router, build_services_router
from .workspace import REPO, workspace

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
    from assistant.api.access import public
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

    app.include_router(build_services_router(activity))

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

    app.include_router(build_conversations_router(root, activity))

    app.include_router(build_spaces_router(spaces=spaces, cores=cores, build_core=build_core, auth=auth, knowledge=knowledge,
                                           register=register, activity=activity))

    app.include_router(build_activity_router(browser_log))

    app.include_router(build_sales_api_router(app, credential=credential, knowledge=knowledge, ontology=ontology, desk=desk,
                                              register=register, sections=sections, spaces=spaces))

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
