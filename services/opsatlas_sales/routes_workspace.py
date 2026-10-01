"""The workspace's own operations (AUDIT F13, from create_sales_app): restarting its services, and the control panel's
activity events."""
import subprocess

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from assistant.api.access import need
from assistant.api.access import signed_in as handler_checks


class Restart(BaseModel):
    which: str = 'tibi'


class BrowserEvents(BaseModel):
    events: list[dict]


def build_services_router(activity) -> APIRouter:
    router = APIRouter()

    @router.post('/api/services/restart', dependencies=[need('platform.services.restart', scope='platform')])
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

    @router.post('/api/services/start', dependencies=[need('platform.services.restart', scope='platform')])
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
    return router


def build_activity_router(browser_log) -> APIRouter:
    router = APIRouter()

    @router.post('/api/activity', dependencies=[handler_checks('the caller records the events of their own page')])
    def browser_activity(data: BrowserEvents):
        """What the control panel page did, in small batches: pages, buttons, Tibi's microphone and socket, errors."""
        for event in data.events[:100]:
            if isinstance(event, dict):
                kind = str(event.pop('kind', 'action'))[:40]
                browser_log.write(kind, **{str(k)[:40]: v for k, v in list(event.items())[:20]})
        return {'recorded': min(len(data.events), 100)}
    return router
