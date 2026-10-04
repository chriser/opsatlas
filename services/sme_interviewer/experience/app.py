"""Loopback experience lab: blind auditions and transient endpoint measurements."""

import asyncio
import json
import secrets
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .catalog import PROMPTS, ROOT, RUNTIME, VOICES

WEB = Path(__file__).parent / 'web'


def create_app(runtime=RUNTIME):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost'])
    token = secrets.token_urlsafe(32)
    candidates = list(VOICES)
    secrets.SystemRandom().shuffle(candidates)
    aliases = {chr(65 + index): voice for index, voice in enumerate(candidates)}
    endpoint = None
    inference_lock = asyncio.Lock()
    microphone_lock = asyncio.Lock()

    @app.middleware('http')
    async def boundary(request, call_next):
        expected = f"{request.url.scheme}://{request.headers.get('host', '')}"
        if request.headers.get('origin') not in (None, expected):
            return JSONResponse({'detail': 'Use the local lab page'}, status_code=403)
        if request.method != 'GET' and not secrets.compare_digest(request.headers.get('x-lab-token', ''), token):
            return JSONResponse({'detail': 'Refresh the lab page'}, status_code=403)
        response = await call_next(request)
        response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
                                 'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; "
                                 "media-src 'self' blob:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'"})
        return response

    async def body(request, limit=8192):
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > limit:
                raise HTTPException(413, 'Request too large')
        return bytes(data)

    def records():
        return [record for engine in ('kokoro', 'pocket', 'chatterbox', 'qwen')
                if (path := runtime / f'{engine}-results.json').exists() for record in json.loads(path.read_text())]

    @app.get('/')
    async def index():
        return FileResponse(WEB / 'index.html')

    @app.get('/assets/{name}')
    async def assets(name: str):
        if name not in {'lab.js', 'lab.css', 'floor.js', 'voice-worklet.js'}:
            raise HTTPException(404)
        return FileResponse((ROOT / 'web' if name == 'voice-worklet.js' else WEB) / name)

    @app.get('/api/catalog')
    async def catalog():
        available = {(r['candidate'], r['prompt']) for r in records()}
        return {'token': token, 'voices': list(aliases),
                'prompts': [{'id': key, 'label': value[0], 'text': value[1]} for key, value in PROMPTS.items()],
                'available': [f'{alias}/{prompt}' for alias, voice in aliases.items()
                              for prompt in PROMPTS if (voice, prompt) in available]}

    @app.get('/audio/{alias}/{prompt}')
    async def audio(alias: str, prompt: str):
        if alias not in aliases or prompt not in PROMPTS:
            raise HTTPException(404)
        path = runtime / 'clips' / f'{aliases[alias]}-{prompt}.wav'
        if not path.is_file():
            raise HTTPException(404, 'Sample not generated yet')
        return FileResponse(path, media_type='audio/wav')

    @app.post('/api/rating')
    async def rating(request: Request):
        try:
            value = json.loads(await body(request))
            if value['alias'] not in aliases or value['prompt'] not in PROMPTS:
                raise ValueError()
            for key in ('naturalness', 'pronunciation', 'accent', 'pace'):
                if type(value.get(key)) is not int or not 1 <= value[key] <= 5:
                    raise ValueError()
            if not isinstance(value.get('notes', ''), str) or len(value.get('notes', '')) > 2000:
                raise ValueError()
        except (ValueError, TypeError, KeyError):
            raise HTTPException(422, 'Choose a score from 1–5 for each criterion') from None
        record = {key: value[key] for key in ('alias', 'prompt', 'naturalness', 'pronunciation', 'accent', 'pace')}
        record.update(candidate=aliases[value['alias']], notes=value.get('notes', ''), time=time.time())
        runtime.mkdir(parents=True, exist_ok=True)
        with (runtime / 'ratings.jsonl').open('a') as output:
            output.write(json.dumps(record) + '\n')
        return {'saved': True}

    @app.get('/api/reveal')
    async def reveal():
        return {alias: VOICES[voice]['name'] for alias, voice in aliases.items()}

    @app.get('/api/results')
    async def results():
        path = runtime / 'ratings.jsonl'
        return {'ratings': [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else [],
                'measurements': records()}

    @app.post('/api/endpoint')
    async def predict(request: Request):
        nonlocal endpoint
        raw = await body(request, 512000)
        if len(raw) % 4 or not 32000 <= len(raw) <= 512000:
            raise HTTPException(422, 'Use 0.5–8 seconds of float32 mono 16 kHz audio')
        # Bound work; the browser drops obsolete snapshots rather than queuing them.
        if inference_lock.locked():
            raise HTTPException(409, 'Endpoint detector busy')
        async with inference_lock:
            import numpy as np

            from .listener import Endpoint

            if endpoint is None:
                endpoint = await asyncio.to_thread(Endpoint)
            try:
                return await asyncio.to_thread(endpoint.predict, np.frombuffer(raw, dtype='<f4'))
            except ValueError:
                raise HTTPException(422, 'Invalid audio samples') from None

    @app.websocket('/api/vad')
    async def vad(socket: WebSocket):
        nonlocal endpoint
        host = socket.headers.get('host', '')
        if socket.headers.get('origin') != f'http://{host}' or microphone_lock.locked():
            await socket.close(code=1008)
            return
        await socket.accept()
        detector = None
        try:
            message = await asyncio.wait_for(socket.receive_text(), 5)
            if len(message) > 256 or not secrets.compare_digest(message, token):
                await socket.close(code=1008)
                return
            if microphone_lock.locked():
                await socket.close(code=1008)
                return
            async with microphone_lock:
                from ..resident import Resident
                from .listener import Endpoint

                # Prepare before capture, so the first answer does not pay the
                # feature-extractor import/model-load cost at its ending pause.
                async with inference_lock:
                    if endpoint is None:
                        endpoint = await asyncio.to_thread(Endpoint)

                native = runtime / 'listener-runtime'
                native.mkdir(parents=True, exist_ok=True)
                for name in ('models', 'conversation-recognizer'):
                    path = native / name
                    if not path.exists():
                        path.symlink_to(ROOT / '.runtime' / name)
                detector = Resident(native, 'vad')
                await detector.start()
                await socket.send_json({'ready': True})
                while True:
                    raw = await asyncio.wait_for(socket.receive_bytes(), 15)
                    if len(raw) != 2048:
                        await socket.close(code=1009)
                        return
                    import numpy as np

                    samples = np.frombuffer(raw, dtype='<f4')
                    if not np.isfinite(samples).all() or np.max(np.abs(samples)) > 1.001:
                        await socket.close(code=1008)
                        return
                    await socket.send_json(await detector.infer(raw))
        except (WebSocketDisconnect, TimeoutError, RuntimeError, KeyError, ValueError):
            pass
        finally:
            if detector is not None:
                await detector.close()
            try:
                await socket.close()
            except RuntimeError:
                pass

    return app


app = create_app()
