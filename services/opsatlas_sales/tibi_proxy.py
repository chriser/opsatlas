"""The OpsAtlas gateway to the Tibi service: /services/tibi/api/* on the control panel's origin.

Tibi runs as its own service (its API: health, sessions, the live voice socket, contributions and
drafts). The control panel's Talk with Tibi page reaches it only through this gateway, which:

* requires the OpsAtlas sign-in: the person's session on every HTTP call, and on the live voice socket a 30-second,
  one-use ticket bound to that session and conversation in the first message (IAM F6; a browser socket cannot send
  an Authorization header);
* forwards only the Tibi paths the panel uses, each with its permission (REF S2): anything else answers 404 without
  reaching Tibi. A process interview belongs to one organisation's space, so a request that names a space, or an
  interview held in one, is checked against the caller's access to that space as well;
* passes the Tibi service's own session token untouched, so Tibi's own checks still apply; and presents the service's
  own origin to it, having checked the browser's;
* keeps everything on one origin, so the browser lets the page use the microphone and choose a speaker.

It stores nothing and imports nothing from Tibi. It records the voice socket's life in the activity log: opened,
refused, the state and error messages Tibi sends (never audio or conversation wording), and when and why it closed.
"""
import asyncio
import json
import re
import time

import httpx
from fastapi import Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

PREFIX = '/services/tibi'
FORWARDED = ('content-type', 'x-sme-token', 'accept')
RETURNED = ('content-type', 'content-disposition', 'cache-control')


# The Tibi paths the panel uses, each with what it needs (REF S2). Every one also needs tibi.use (the route's own
# marker). ``space`` says where a named space comes from: the query, the request body, or the interview the path names.
ROUTES = (
    ('GET', r'health|manifest|bootstrap', None, None),
    ('GET', r'contributions', None, None),
    ('POST', r'contributions/propose', None, None),
    ('POST', r'spoken/draft', 'tibi.spoken.edit', None),
    ('POST', r'text/sessions(/[^/]+/(turns|close))?', None, None),
    ('POST', r'interviews', None, 'body'),
    ('GET', r'interviews/[^/]+', 'processes.read', 'interview'),
    ('POST', r'interviews/[^/]+/(pause|resume|timings)', 'processes.capture.create', 'interview'),
    ('GET', r'process-interviews', 'processes.read', 'query'),
    ('DELETE', r'process-interviews/[^/]+', 'processes.capture.create', 'interview'),
)


def route_for(method, path):
    """The listed route a request matches, or None."""
    return next(((need_, where) for m, pattern, need_, where in ROUTES if m == method and re.fullmatch(pattern, path)), None)


# Tibi's messages worth a line in the activity log; the fields kept from each (never the conversation's words).
LOGGED = {'state': ('state', 'message'), 'error': ('message',), 'quality_notice': ('message',), 'ready': (),
          'paused': ('message',), 'social_boundary': ('phase', 'message'), 'reply_preparing': ('reasoning_ms', 'speculative'),
          'social_reply': ('route', 'route_reasons', 'grounding', 'reasoning_ms', 'phase', 'conversation_issue', 'blocked'),
          'endpoint': ('endpoint_kind',), 'speech_done': ('chunks',)}
# The browser's controls; their text (a typed message) is never kept.
CONTROLS = ('social_text', 'finish_answer', 'pause', 'resume', 'recap', 'read_recap', 'confirm_recap')
# The start of the hello worth keeping: how the conversation was set up.
HELLO = ('listener_practice', 'social_voice', 'text_only')


def attach(app, voice, activity=None):
    def log(event, **fields):
        if activity is not None:
            activity.write('socket', event=event, **fields)

    from assistant.api.access import DEFAULT_SPACE, AccessError, current_actor, mark_websocket, need

    upstream = voice.rstrip('/')
    socket_upstream = 'ws://' + upstream.split('://', 1)[1]
    iam = app.state.auth.iam
    space_id = getattr(app.state, 'space_id', DEFAULT_SPACE)

    def mark_websocket_route(endpoint):
        return mark_websocket(endpoint, 'tibi.voice.use', 'a one-use ticket in the hello; closed within 5 s of the session ending')

    @app.api_route(PREFIX + '/api/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE'], include_in_schema=False,
                   dependencies=[need('tibi.use')])
    async def forward(path: str, request: Request):
        listed = route_for(request.method, path)
        if listed is None:
            raise AccessError(404, 'NOT_FOUND', 'Not found')
        permission, where = listed
        actor = current_actor(request)
        body = await request.body()
        headers = {k: v for k, v in request.headers.items() if k.lower() in FORWARDED}
        if request.headers.get('origin'):
            headers['origin'] = upstream  # the OpsAtlas boundary has already checked the browser's origin
        async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=3), trust_env=False) as client:
            try:
                await check(actor, request, path, body, permission, where, client)
                response = await client.request(request.method, f'{upstream}/api/{path}', params=request.query_params,
                                                content=body, headers=headers)
            except httpx.HTTPError:
                return Response('{"detail": "Tibi is not running. Start the Tibi service and try again."}',
                                status_code=502, media_type='application/json')
        out = {k: v for k, v in response.headers.items() if k.lower() in RETURNED}
        return Response(response.content, status_code=response.status_code, headers=out)

    async def check(actor, request, path, body, permission, where, client):
        """The listed permission at the app's space, and at the space the request names or the interview is held in.
        A space the caller cannot see answers 404, as everywhere else."""
        if where == 'query':
            space = request.query_params.get('space') or ''
            actor.require(permission, space or space_id)
        elif where == 'body':
            try:
                data = json.loads(body or b'{}')
            except ValueError:
                data = {}
            settings = data.get('process_interview') if isinstance(data, dict) else None
            if isinstance(settings, dict) and isinstance(settings.get('space'), str):
                actor.require('processes.capture.create', settings['space'])
            if isinstance(data, dict) and data.get('sales_rehearsal') is not None:
                actor.require('tibi.rehearsal.use', space_id)
        elif where == 'interview':
            held = await interview_space(client, path.split('/')[1])
            if held:
                actor.require(permission, held)
        elif permission:
            actor.require(permission, space_id)

    async def interview_space(client, identifier):
        """The organisation's space an interview is held in, or None (a product, governance or rehearsal session, or
        one Tibi does not know: Tibi then answers for itself)."""
        response = await client.get(f'{upstream}/api/interviews/{identifier}')
        if response.status_code != 200:
            return None
        settings = ((response.json() or {}).get('evidence') or {}).get('process_interview')
        return settings.get('space') if isinstance(settings, dict) else None

    @app.websocket(PREFIX + '/api/conversation/{identifier}')
    @mark_websocket_route
    async def forward_socket(socket: WebSocket, identifier: str):
        import websockets

        host = socket.headers.get('host', '')
        if host.split(':')[0] not in ('127.0.0.1', 'localhost') or socket.headers.get('origin') != 'http://' + host:
            log('refused: not this origin', session=identifier)
            await socket.close(code=1008)
            return
        await socket.accept()
        opened = time.perf_counter()
        counts = {'microphone_frames': 0, 'audio_chunks': 0}
        log('opened', session=identifier)
        code, reason = 1000, ''
        try:
            # The first message carries the OpsAtlas sign-in: a one-use ticket for this conversation (IAM F6); the rest
            # of it is Tibi's own hello. The signed-in person must be allowed the voice here, and the socket closes
            # within five seconds of the session ending.
            hello = json.loads(await asyncio.wait_for(socket.receive_text(), 10))
            resolved = None
            if isinstance(hello, dict):
                ticket = str(hello.pop('opsatlas_ticket', '') or '')
                hello.pop('opsatlas_token', None)
                resolved = iam.consume_ticket(ticket, identifier) if ticket else None
            if resolved is None or not iam.can(resolved[0]['id'], 'tibi.voice.use', space_id):
                log('refused: not signed in', session=identifier)
                await socket.close(code=1008, reason='Sign in to OpsAtlas')
                return
            session_id = resolved[1]['id']

            async def watch_session():
                while True:
                    await asyncio.sleep(5)
                    if iam.session_by_id(session_id) is None:
                        log('closed: signed out', session=identifier)
                        await socket.close(code=1008, reason='Signed out')
                        return
            connecting = time.perf_counter()
            async with websockets.connect(f'{socket_upstream}/api/conversation/{identifier}', origin=upstream,
                                          max_size=8_000_000, open_timeout=5) as voice_socket:
                log('connected to Tibi', session=identifier, ms=round((time.perf_counter() - connecting) * 1000, 1),
                    hello={k: v for k, v in hello.items() if k in HELLO})
                await voice_socket.send(json.dumps(hello))

                async def browser_to_voice():
                    while True:
                        message = await socket.receive()
                        if message['type'] == 'websocket.disconnect':
                            return
                        if message.get('text') is not None:
                            await voice_socket.send(message['text'])
                            note(message['text'], 'browser')
                        elif message.get('bytes') is not None:
                            await voice_socket.send(message['bytes'])

                async def voice_to_browser():
                    try:
                        async for data in voice_socket:
                            if isinstance(data, bytes):
                                await socket.send_bytes(data)
                            else:
                                await socket.send_text(data)
                                note(data, 'tibi')
                    except (websockets.exceptions.ConnectionClosed, RuntimeError, WebSocketDisconnect):
                        pass  # the browser left first: nothing more to forward

                def note(text, side):
                    """Tibi's state and error messages, and the browser's controls, after they have been forwarded.
                    Audio (microphone frames, Tibi's chunks, acknowledgements) is only counted, never parsed."""
                    head = text[:40]
                    if '"frame"' in head or '"audio_ack"' in head:
                        counts['microphone_frames'] += '"frame"' in head
                        return
                    if '"audio_chunk"' in head:
                        counts['audio_chunks'] += 1
                        return
                    try:
                        data = json.loads(text)
                    except ValueError:
                        return
                    if not isinstance(data, dict):
                        return
                    kind = str(data.get('type', ''))
                    if side == 'tibi' and kind in LOGGED:
                        log(f'tibi: {kind}', session=identifier, **{k: data.get(k) for k in LOGGED[kind] if data.get(k) is not None})
                    elif side == 'browser' and kind in CONTROLS:
                        log(f'browser: {kind}', session=identifier)

                tasks = [asyncio.create_task(browser_to_voice()), asyncio.create_task(voice_to_browser()),
                         asyncio.create_task(watch_session())]
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                # The Tibi service's own close ("1008: refused") reaches the page unchanged.
                code, reason = voice_socket.close_code or 1000, voice_socket.close_reason or ''
        except (asyncio.TimeoutError, ValueError):
            code, reason = 1008, 'Expected the conversation hello'
        except (OSError, websockets.exceptions.WebSocketException) as exc:
            code, reason = 1011, 'Tibi is not running'
            log('could not reach Tibi', session=identifier, error=type(exc).__name__)
        finally:
            log('closed', session=identifier, code=code, reason=reason or None,
                seconds=round(time.perf_counter() - opened, 1), **counts)
            try:
                await socket.close(code=code, reason=reason)
            except RuntimeError:
                pass
