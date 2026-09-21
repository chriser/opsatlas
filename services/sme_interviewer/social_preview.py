"""Separate local social conversation; never loads the full interview planner."""
import json
import os
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from .expressive_preview import candidate_app
from .speech import ROOT


def social_app():
    os.environ['SME_SOCIAL_CHAT'] = '1'
    app = candidate_app('social-preview')
    os.environ['SME_VOICE_BACKEND'] = 'chatterbox'
    @app.middleware('http')
    async def social_entry(request, call_next):
        if request.url.path in ('/', '/conversation') and request.query_params.get('social') != '1':
            return RedirectResponse('/conversation?social=1')
        return await call_next(request)

    runtime = ROOT / '.runtime/social-preview'
    binary = runtime / 'conversation-recognizer'
    verified = ROOT / '.runtime/recognition-check/conversation-recognizer'
    if verified.exists():
        binary.unlink()
        binary.symlink_to(verified)

    @app.get('/social-voices')
    async def voices():
        return FileResponse(ROOT / 'experience/web/social-voices.html')

    @app.get('/social-voices.js')
    async def script():
        return FileResponse(ROOT / 'experience/web/social-voices.js')

    @app.get('/api/social-voices')
    async def catalog():
        file = ROOT / '.runtime/experience/social-comparison/results.json'
        return json.loads(file.read_text()) if file.exists() else []

    @app.get('/social-audio/{name}')
    async def audio(name: str):
        if Path(name).name != name or not name.endswith('.wav'):
            raise HTTPException(404)
        file = ROOT / '.runtime/experience/social-comparison' / name
        if not file.is_file():
            raise HTTPException(404)
        return FileResponse(file, media_type='audio/wav')

    return app


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(social_app(), host='127.0.0.1', port=8772, ws_max_size=8_000_000)
