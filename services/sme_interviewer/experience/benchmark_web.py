"""Local audition and explicit feedback capture; never trains or promotes a model."""
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse

from .benchmark import CANDIDATES, CASES, DIRECTORY

WEB = Path(__file__).parent / 'web'


def attach_benchmark(app, directory=DIRECTORY):
    token = secrets.token_urlsafe(32)
    directory.mkdir(parents=True, exist_ok=True)
    alias_file = directory / 'aliases.json'
    if not alias_file.exists():
        names = list(CANDIDATES)
        secrets.SystemRandom().shuffle(names)
        alias_file.write_text(json.dumps({chr(65+i): name for i, name in enumerate(names)}))
    aliases = json.loads(alias_file.read_text())

    def records():
        return [r for name in CANDIDATES if (path := directory / f'{name}.json').exists() for r in json.loads(path.read_text())]

    @app.get('/voice-benchmark')
    async def page():
        return FileResponse(WEB / 'benchmark.html')

    @app.get('/voice-benchmark.js')
    async def script():
        return FileResponse(WEB / 'benchmark.js')

    @app.get('/voice-benchmark.css')
    async def stylesheet():
        return FileResponse(WEB / 'benchmark.css')

    @app.get('/api/voice-benchmark')
    async def catalog(reveal: bool = False):
        rows = records()
        return {'token': token, 'cases': CASES, 'voices': [{'alias': a, 'name': CANDIDATES[n] if reveal else 'Voice '+a,
                    'clips': [{k: r[k] for k in ('case', 'first_output_ms', 'total_ms', 'audio_seconds', 'rtf', 'clipped_samples')}
                              for r in rows if r['candidate'] == n]} for a, n in aliases.items()],
                'policy': 'Research audition only. Original transcript wording may be incorrect. Feedback is not training approval.'}

    @app.get('/api/voice-benchmark/audio/{alias}/{case}')
    async def audio(alias: str, case: str):
        if alias not in aliases or case not in {r['id'] for r in CASES}:
            raise HTTPException(404)
        row = next((r for r in records() if r['candidate'] == aliases[alias] and r['case'] == case), None)
        if not row:
            raise HTTPException(404, 'Audio not generated')
        return FileResponse(directory / row['file'], media_type='audio/wav')

    @app.post('/api/voice-benchmark/feedback')
    async def feedback(request: Request):
        origin = request.headers.get('origin')
        if origin not in (None, str(request.base_url).rstrip('/')) or not secrets.compare_digest(
                request.headers.get('x-benchmark-token', ''), token):
            raise HTTPException(403)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 12000:
                raise HTTPException(413)
        try:
            value = json.loads(body)
            if value['alias'] not in aliases or value['case'] not in {r['id'] for r in CASES}:
                raise ValueError()
            if any(type(value.get(k)) is not int or not 1 <= value[k] <= 5 for k in ('naturalness', 'pace', 'pronunciation', 'accent')):
                raise ValueError()
            if any(not isinstance(value.get(k, ''), str) or len(value.get(k, '')) > 2000 for k in ('notes', 'preferred_wording')):
                raise ValueError()
            row = next(r for r in records() if r['candidate'] == aliases[value['alias']] and r['case'] == value['case'])
        except (ValueError, KeyError, TypeError, StopIteration):
            raise HTTPException(422, 'Choose an available clip and all four ratings') from None
        fields = ('alias', 'case', 'naturalness', 'pace', 'pronunciation', 'accent', 'notes', 'preferred_wording')
        saved = {k: value.get(k, '') for k in fields}
        saved.update(candidate=row['candidate'], clip_sha256=row['sha256'], at=datetime.now(timezone.utc).isoformat(),
                     review_status='unreviewed', eligible_for_training=False)
        with (directory / 'feedback.jsonl').open('a') as file:
            file.write(json.dumps(saved)+'\n')
        return {'saved': True, 'eligible_for_training': False}

    @app.get('/api/voice-benchmark/export')
    async def export():
        path = directory / 'feedback.jsonl'
        return {'schema': 1, 'cases': CASES, 'measurements': records(),
                'feedback': [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else [],
                'policy': 'Unreviewed feedback. No automatic learning or deployment.'}
