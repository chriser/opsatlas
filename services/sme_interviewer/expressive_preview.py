"""Explicit opt-in Charles/Smart Turn candidate with its own session database.

Run: python -m services.sme_interviewer.expressive_preview
Existing production and audition services are not restarted.
"""

import os
from pathlib import Path

from .app import create_app
from .speech import ROOT


def candidate_app(runtime_name="expressive-preview"):
    source = ROOT / '.runtime'
    runtime = source / runtime_name
    runtime.mkdir(parents=True, exist_ok=True)
    for name in ('models', 'conversation-recognizer', 'experience', 'experience-env'):
        target = runtime / name
        if not target.exists():
            target.symlink_to(source / name, target_is_directory=(source / name).is_dir())
    os.environ['SME_VOICE_BACKEND'] = 'pocket'
    os.environ['SME_SMART_ENDPOINT'] = '1'
    os.environ['SME_DEFER_REVIEWS'] = '1'
    os.environ['SME_LISTENER_LAB'] = '1'
    return create_app(Path(runtime))


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(candidate_app(), host='127.0.0.1', port=8770, ws_max_size=8_000_000)
