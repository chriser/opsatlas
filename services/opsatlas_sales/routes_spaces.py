"""Knowledge spaces' routes: list, create, change and transfer between them (KS S1, S5, S7; AUDIT F13, from
create_sales_app)."""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from assistant.api.access import current_actor, need
from assistant.api.access import signed_in as handler_checks

from .spaces import FAMILY


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


def build_spaces_router(*, spaces, cores, build_core, auth, knowledge, register, activity) -> APIRouter:
    router = APIRouter()

    # Knowledge spaces (KS S1, S5): what spaces there are, and an administrator's Transfer between them.
    from .spaces import move_document

    @router.get('/api/spaces', dependencies=[handler_checks('the spaces the caller may read; archived ones for whoever may create spaces')])
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

    @router.post('/api/spaces', dependencies=[need('spaces.create', scope='platform')])
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

    @router.patch('/api/spaces/{space_id}', dependencies=[handler_checks('spaces.update, spaces.archive or spaces.restore in that space')])
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

    @router.post('/api/spaces/transfer', dependencies=[handler_checks('documents.transfer in the origin and sources.upload in the target')])
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
    return router
