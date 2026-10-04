"""Private voice-rating pages, separated from the live Tiberius service (review 2, S146).

Run with: services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.experience.voice_ratings
It serves on 127.0.0.1:8774 and writes ratings only to the experiment runtime, never to the
sales workspace. Ratings are unreviewed feedback, not training or promotion approval.
"""
from fastapi import FastAPI
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import higgs_comparison
from .benchmark_web import attach_benchmark
from .evaluation import CANDIDATES as EVALUATION_CANDIDATES
from .evaluation import CASES as EVALUATION_CASES
from .evaluation import DIRECTORY as EVALUATION_DIRECTORY


def ratings_app():
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost'])
    attach_benchmark(app)
    attach_benchmark(app, EVALUATION_DIRECTORY, candidates=EVALUATION_CANDIDATES, cases=EVALUATION_CASES,
                     prefix='/voice-evaluation')
    attach_benchmark(app, higgs_comparison.DIRECTORY, candidates=higgs_comparison.CANDIDATES,
                     cases=higgs_comparison.CASES, prefix='/higgs-voices')
    return app


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(ratings_app(), host='127.0.0.1', port=8774)
