"""Authenticated duplex control/events. Reuses HTTP commands and their revision guards."""

import asyncio
import json
import re
import secrets
from contextlib import suppress

import anyio
import httpx
from fastapi import WebSocket, WebSocketDisconnect


class Events:
    def __init__(self):
        self.listeners = set()

    def publish(self, kind, value):
        for queue in tuple(self.listeners):
            if queue.full():
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait(('overflow', {}))
            else:
                queue.put_nowait((kind, value))


def attach(app, token, interviews, audio, events):
    connected = set()

    @app.websocket('/api/live/{identifier}')
    async def live(socket: WebSocket, identifier: str):
        host = socket.headers.get('host', '')
        if host.split(':')[0] not in ('127.0.0.1', 'localhost') or socket.headers.get('origin') != 'http://' + host:
            await socket.close(code=1008)
            return
        await socket.accept()
        queue = asyncio.Queue(maxsize=64)
        jobs, context = set(), {'turn_id': 'control', 'generation_id': secrets.token_hex(8), 'revision': 0}
        requests = set()
        contexts = {}
        sender = None
        client = None
        registered = False
        lock = asyncio.Lock()

        async def send(data):
            async with lock:
                await socket.send_json(data)

        def envelope(kind, value):
            identity = contexts.get((kind, value.get('id')), context)
            return {'type': kind, 'session_id': identifier, **identity,
                    'revision': value.get('revision', identity['revision']), 'data': value}

        async def pushed():
            while True:
                kind, value = await queue.get()
                if kind == 'overflow':
                    await socket.close(code=1013)
                    return
                if (kind == 'session' and value.get('id') == identifier) or (kind == 'audio' and value.get('id') in jobs):
                    await send(envelope(kind, value))

        try:
            hello = await asyncio.wait_for(socket.receive_json(), 5)
            if not isinstance(hello, dict) or not isinstance(hello.get('token'), str) or not secrets.compare_digest(hello['token'], token):
                await socket.close(code=1008)
                return
            if identifier in connected:
                await socket.close(code=1008)
                return
            session = interviews.store.get(identifier)
            connected.add(identifier)
            registered = True
            events.listeners.add(queue)
            await send(envelope('hello', interviews.view(session)))
            sender = asyncio.create_task(pushed())
            # Internal ASGI dispatch preserves the one existing mutation/validation boundary.
            client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://' + host,
                                       headers={'x-sme-token': token}, timeout=60)
            async def dispatch(data, rid, path, method):
                try:
                    request_context = {key: data[key] for key in ('turn_id', 'generation_id', 'revision')}
                    if path.endswith('/plan'):
                        contexts[('session', identifier)] = request_context
                    response = await client.request(method, path, json=data.get('body') if method == 'POST' else None)
                    result = response.json()
                    if response.is_success and path in ('/api/turns', '/api/transcribe'):
                        jobs.add(result['id'])
                        contexts[('audio', result['id'])] = request_context
                    await send({'type': 'reply', 'id': rid, 'session_id': identifier, **request_context,
                                'revision': result.get('revision', request_context['revision']),
                                'status': response.status_code, 'data': result})
                    # A very fast job may finish before ownership was registered.
                    if path in ('/api/turns', '/api/transcribe') and response.is_success:
                        job = audio.jobs.get(result['id'])
                        if job and job['state'] != 'running':
                            events.publish('audio', {k: v for k, v in job.items() if k not in {'task', 'path', 'created'}})
                except Exception:
                    with suppress(RuntimeError, WebSocketDisconnect):
                        await send({'type': 'reply', 'id': rid, 'status': 500,
                                    'data': {'detail': 'Local command failed. Reopen the saved session before retrying.'}})
            while True:
                raw = await socket.receive_text()
                if len(raw) > 8_000_000:
                    await socket.close(code=1009)
                    break
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError('Invalid request')
                rid, path, method = data.get('id'), data.get('path', ''), data.get('method')
                if (not isinstance(rid, str) or len(rid) > 80 or data.get('session_id') != identifier
                        or type(data.get('revision')) is not int
                        or not isinstance(path, str) or method not in ('GET', 'POST')):
                    raise ValueError('Invalid live command')
                if not all(isinstance(data.get(key), str) and 1 <= len(data[key]) <= 80 for key in ('turn_id', 'generation_id')):
                    raise ValueError('Missing turn identity')
                allowed = re.fullmatch(r'/api/interviews/' + re.escape(identifier) +
                                      r'(?:/(?:segments|discard|scope|plan|pause|resume|finish|assess))?', path)
                audio_path = re.fullmatch(r'/api/turns/([a-f0-9]{32})(?:/cancel)?', path)
                allowed = allowed or path in ('/api/turns', '/api/transcribe') or (audio_path and audio_path[1] in jobs)
                if not allowed:
                    await send({'type': 'reply', 'id': rid, 'status': 400, 'data': {'detail': 'Unsupported live command'}})
                    continue
                requests = {task for task in requests if not task.done()}
                if len(requests) >= 4:
                    await send({'type': 'reply', 'id': rid, 'status': 429, 'data': {'detail': 'Wait for the current requests'}})
                    continue
                requests.add(asyncio.create_task(dispatch(data, rid, path, method)))
        except (WebSocketDisconnect, asyncio.TimeoutError, ValueError, KeyError, RuntimeError):
            pass
        finally:
            with anyio.CancelScope(shield=True):
                events.listeners.discard(queue)
                for task in requests:
                    task.cancel()
                await asyncio.gather(*requests, return_exceptions=True)
                if client:
                    await client.aclose()
                if registered:
                    connected.discard(identifier)
                if sender:
                    sender.cancel()
                    await asyncio.gather(sender, return_exceptions=True)
                for job in jobs:
                    if job in audio.jobs:
                        await audio.cancel(job)
                if registered:
                    with suppress(KeyError):
                        interviews.store.pause(identifier, 'disconnect')
                        await interviews.cancel(identifier)
                with suppress(RuntimeError):
                    await socket.close()
