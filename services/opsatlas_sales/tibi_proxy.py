"""The OpsAtlas gateway to the Tibi service: /services/tibi/api/* on the control panel's origin.

Tibi runs as its own service (its API: health, sessions, the live voice socket, contributions and
drafts). The control panel's Talk with Tibi page reaches it only through this gateway, which:

* requires the OpsAtlas operator sign-in: a bearer token on every HTTP call, and on the live voice
  socket the same token in the first message (a browser socket cannot send an Authorization header);
* forwards only the Tibi API (/api/*), passing the Tibi service's own session token untouched, so Tibi's
  own checks still apply; and presents the service's own origin to it, having checked the browser's;
* keeps everything on one origin, so the browser lets the page use the microphone and choose a speaker.

It stores nothing and imports nothing from Tibi.
"""
import asyncio
import json

import httpx
from fastapi import Depends, Request, WebSocket
from fastapi.responses import Response

PREFIX = '/services/tibi'
FORWARDED = ('content-type', 'x-sme-token', 'accept')
RETURNED = ('content-type', 'content-disposition', 'cache-control')


def attach(app, voice):
    from assistant.api.routes_auth import make_require_auth

    upstream = voice.rstrip('/')
    socket_upstream = 'ws://' + upstream.split('://', 1)[1]
    signed_in = Depends(make_require_auth(app.state.auth))

    @app.api_route(PREFIX + '/api/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE'], include_in_schema=False,
                   dependencies=[signed_in])
    async def forward(path: str, request: Request):
        headers = {k: v for k, v in request.headers.items() if k.lower() in FORWARDED}
        if request.headers.get('origin'):
            headers['origin'] = upstream  # the OpsAtlas boundary has already checked the browser's origin
        async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=3), trust_env=False) as client:
            try:
                response = await client.request(request.method, f'{upstream}/api/{path}', params=request.query_params,
                                                content=await request.body(), headers=headers)
            except httpx.HTTPError:
                return Response('{"detail": "Tibi is not running. Start the Tibi service and try again."}',
                                status_code=502, media_type='application/json')
        out = {k: v for k, v in response.headers.items() if k.lower() in RETURNED}
        return Response(response.content, status_code=response.status_code, headers=out)

    @app.websocket(PREFIX + '/api/conversation/{identifier}')
    async def forward_socket(socket: WebSocket, identifier: str):
        import websockets

        host = socket.headers.get('host', '')
        if host.split(':')[0] not in ('127.0.0.1', 'localhost') or socket.headers.get('origin') != 'http://' + host:
            await socket.close(code=1008)
            return
        await socket.accept()
        code, reason = 1000, ''
        try:
            # The first message carries the OpsAtlas sign-in; the rest of it is Tibi's own hello.
            hello = json.loads(await asyncio.wait_for(socket.receive_text(), 10))
            if not isinstance(hello, dict) or not app.state.auth.validate(str(hello.pop('opsatlas_token', ''))):
                await socket.close(code=1008, reason='Sign in to OpsAtlas')
                return
            async with websockets.connect(f'{socket_upstream}/api/conversation/{identifier}', origin=upstream,
                                          max_size=8_000_000, open_timeout=5) as voice_socket:
                await voice_socket.send(json.dumps(hello))

                async def browser_to_voice():
                    while True:
                        message = await socket.receive()
                        if message['type'] == 'websocket.disconnect':
                            return
                        if message.get('text') is not None:
                            await voice_socket.send(message['text'])
                        elif message.get('bytes') is not None:
                            await voice_socket.send(message['bytes'])

                async def voice_to_browser():
                    try:
                        async for data in voice_socket:
                            if isinstance(data, bytes):
                                await socket.send_bytes(data)
                            else:
                                await socket.send_text(data)
                    except websockets.exceptions.ConnectionClosed:
                        pass

                tasks = [asyncio.create_task(browser_to_voice()), asyncio.create_task(voice_to_browser())]
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                # The Tibi service's own close ("1008: refused") reaches the page unchanged.
                code, reason = voice_socket.close_code or 1000, voice_socket.close_reason or ''
        except (asyncio.TimeoutError, ValueError):
            code, reason = 1008, 'Expected the conversation hello'
        except (OSError, websockets.exceptions.WebSocketException):
            code, reason = 1011, 'Tibi is not running'
        finally:
            try:
                await socket.close(code=code, reason=reason)
            except RuntimeError:
                pass
