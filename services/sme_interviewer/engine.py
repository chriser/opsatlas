"""Tibi's engine version (OBS S9): which engine produced a reply or a score, and whether the engine changed.

The engine is what decides what Tibi says and how quickly: the voice service's modules (prompts, routing rules,
turn-taking, speech) and the models they use, by name. Each delivered change gets a new version in
``config/tibi/engine-versions.json`` with a line on what changed. The fingerprint is
computed from the engine's files and model names; a test fails when they change and the version does not. A version
names the engine's code, not everything around it: the knowledge and retrieval code, the model builds, the voice and
recogniser files, settings and platform are in the service's manifest (manifest.py, audit F10), which scorecards and
replays carry too. ``current`` is this process's engine, computed once; ``fingerprint`` reads the files on disk now.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REGISTRY = REPO / 'config/tibi/engine-versions.json'
# Tools around the engine, not part of it: evaluations, replays, benchmarks, set-up, previews.
TOOLS = ('evaluate_', 'replay_', 'benchmark', 'concurrent_benchmark', 'recognition_benchmark', 'latency_report',
         'provision', 'verify_runtime', 'atlas_fixture', 'engine', 'manifest', 'expressive_preview', 'social_preview')
SHARED = ('services/opsatlas_sales/claims.py',)  # Tibi's routing rules live with the sales workspace


def engine_files(listing=None) -> list[str]:
    names = listing if listing is not None else [p.name for p in (REPO / 'services/sme_interviewer').glob('*.py')]
    own = sorted(f'services/sme_interviewer/{n}' for n in names if n.endswith('.py') and not n[:-3].startswith(TOOLS))
    return [*own, *SHARED]


def models() -> dict:
    """The models the engine uses, as configured for this process."""
    from .process_interviewer import NOTE_MODEL
    from .tibi import MODEL, REVIEW_MODEL
    return {'conversation': MODEL, 'review': REVIEW_MODEL, 'process_notes': NOTE_MODEL}


def fingerprint(read=None, listing=None, model_names=None) -> str:
    """Twelve hex characters that change when any engine file or model changes."""
    read = read or (lambda path: (REPO / path).read_bytes())
    digest = hashlib.sha256()
    for path in engine_files(listing):
        digest.update(path.encode() + b'\0' + hashlib.sha256(read(path)).digest())
    digest.update(json.dumps(model_names if model_names is not None else models(), sort_keys=True).encode())
    return digest.hexdigest()[:12]


def fingerprint_at(commit: str) -> str:
    """The fingerprint of the engine as committed at ``commit`` (for recording a version after the fact)."""
    listing = subprocess.run(['git', 'ls-tree', '--name-only', f'{commit}:services/sme_interviewer'], cwd=REPO,
                             capture_output=True, text=True, check=True).stdout.split()
    return fingerprint(lambda path: subprocess.run(['git', 'show', f'{commit}:{path}'], cwd=REPO, capture_output=True,
                                                   check=True).stdout, listing)


def registry() -> dict:
    return json.loads(REGISTRY.read_text())


@lru_cache(maxsize=1)
def current() -> dict:
    """This engine: its version, fingerprint, models, and whether it is the version as released or has changed since."""
    record = registry()
    version = record['current']
    released = next((v for v in record['versions'] if v['version'] == version), {})
    mine = fingerprint()
    return {'version': version if mine == released.get('fingerprint') else f'{version}+changed',
            'released': version, 'fingerprint': mine, 'models': models(), 'matches_release': mine == released.get('fingerprint')}


if __name__ == '__main__':
    print(json.dumps(current(), indent=2))
