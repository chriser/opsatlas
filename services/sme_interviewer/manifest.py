"""What the running Tibi service is, beyond its engine version: a reproducibility manifest (audit F10).

The engine version (engine.py) names the engine's code and its models by name. Answers and speech also depend on
things it does not cover: the knowledge, governance and retrieval code the service calls, the browser client that
plays the audio, the exact model builds, the recogniser and voice files, the settings that switch them, and the
platform. The manifest records all of them, once, when the service starts: it describes the running process, not
the files that happen to be on disk later (health says when those differ). Scorecards and replays carry it.

Large model files are identified by their pinned revision where they have one (Ollama digests, the Higgs voice's
pinned revision) and otherwise by a content hash, computed once and reused while the file's size and time are
unchanged.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[2]
SETTINGS = ('SME_TIBI_MODEL', 'SME_TIBI_REVIEW_MODEL', 'SME_VOICE_BACKEND', 'SME_SALES_VOICE', 'SME_HIGGS_BITS',
            'SME_SMART_ENDPOINT', 'SME_SOCIAL_CHAT', 'SME_DEFER_REVIEWS', 'SME_ASR_VOCABULARY', 'SME_BOUNDED_PREFILL',
            'SME_QUESTION_PAUSE_MS', 'SME_SENTENCE_PAUSE_MS', 'SME_SPEECH_TEMPO')
COMPONENTS = {
    'knowledge': ['services/opsatlas_sales/knowledge.py', 'services/opsatlas_sales/ontology.py', 'services/opsatlas_sales/content.py',
                  'services/opsatlas_sales/corpus/product_ontology.json', 'services/opsatlas_sales/corpus/product_schema.json'],
    'governance': ['services/opsatlas_sales/governance.py', 'services/opsatlas_sales/statement_governance.py',
                   'src/assistant/governance/statement_review.py'],
    'retrieval': 'src/assistant/retrieval/*.py',
    'client': ['frontend/src/tibi/voice.ts', 'frontend/src/tibi/timing.ts', 'frontend/public/tibi-voice-worklet.js'],
}
PACKAGES = ('fastapi', 'uvicorn', 'httpx', 'websockets', 'numpy', 'mlx', 'torch', 'transformers', 'onnxruntime')
OLLAMA = 'http://127.0.0.1:11434'


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def files_hash(paths) -> str | None:
    """One hash over the listed files' paths and contents; None when none of them exists."""
    digest, found = hashlib.sha256(), False
    for relative in paths:
        path = REPO / relative
        if path.is_file():
            found = True
            digest.update(relative.encode() + b'\0' + _sha(path.read_bytes()).encode())
    return digest.hexdigest()[:16] if found else None


def component(spec) -> str | None:
    paths = sorted(str(p.relative_to(REPO)) for p in REPO.glob(spec)) if isinstance(spec, str) else spec
    return files_hash(paths)


def file_identity(path: Path, cache: dict) -> dict | None:
    """A large file's content hash, reused while its size and modification time are unchanged."""
    if not path.is_file():
        return None
    stat = path.stat()
    key = f'{path}:{stat.st_size}:{int(stat.st_mtime)}'
    if key not in cache:
        digest = hashlib.sha256()
        with path.open('rb') as handle:
            for block in iter(lambda: handle.read(1 << 22), b''):
                digest.update(block)
        cache[key] = digest.hexdigest()[:16]
    return {'file': path.name, 'bytes': stat.st_size, 'sha256': cache[key]}


def ollama_models(names) -> dict:
    """The exact builds behind the model names: Ollama's digests (immutable), or why they could not be read."""
    try:
        tags = httpx.get(OLLAMA + '/api/tags', timeout=2, trust_env=False).json().get('models', [])
    except (httpx.HTTPError, ValueError):
        return {name: {'digest': None, 'note': 'model server not reachable when captured'} for name in names}
    by_name = {m.get('name'): m for m in tags}
    return {name: {'digest': (by_name.get(name) or {}).get('digest'), 'bytes': (by_name.get(name) or {}).get('size')}
            for name in names}


def git_commit() -> dict:
    def run(*args):
        return subprocess.run(['git', *args], cwd=REPO, capture_output=True, text=True, timeout=5).stdout.strip()
    try:
        return {'commit': run('rev-parse', 'HEAD') or None, 'branch': run('rev-parse', '--abbrev-ref', 'HEAD') or None,
                'uncommitted': bool(run('status', '--porcelain', '--untracked-files=no'))}
    except (OSError, subprocess.SubprocessError):
        return {'commit': None, 'branch': None, 'uncommitted': None}


def packages() -> dict:
    found = {}
    for name in PACKAGES:
        try:
            found[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return found


def build(runtime: Path | None = None) -> dict:
    """The manifest of this process, as it starts."""
    from . import engine
    from .tibi import MODEL, REVIEW_MODEL
    runtime = Path(runtime) if runtime else REPO / 'services/sme_interviewer/.runtime'
    cache_path = runtime / 'manifest-cache.json'
    try:
        cache = json.loads(cache_path.read_text())
    except (OSError, ValueError):
        cache = {}
    higgs = runtime / 'experience/audition2-higgs'
    pinned = higgs / 'pinned-revision.json'
    speaker = 'p228' if os.environ.get('SME_SALES_VOICE') == 'higgs_female' else 'p254'
    speech = {
        'recogniser': file_identity(runtime / 'models/ggml-small.en.bin', cache),
        'speech_detection': file_identity(runtime / 'models/ggml-silero-v6.2.0.bin', cache),
        'vocabulary_sha256': _sha((os.environ.get('SME_ASR_VOCABULARY') or '').encode())[:16],
        'voice': {
            'backend': os.environ.get('SME_SALES_VOICE') or os.environ.get('SME_VOICE_BACKEND'),
            'higgs_revision': json.loads(pinned.read_text()) if pinned.is_file() else None,
            'higgs_config_sha256': _sha((higgs / 'config.json').read_bytes())[:16] if (higgs / 'config.json').is_file() else None,
            'precision': '8-bit backbone' if os.environ.get('SME_HIGGS_BITS') == '8' else 'bf16',
            'reference': file_identity(runtime / f'experience/references/vctk/{speaker}_023_enhanced.wav', cache),
        },
        'playback_prebuffer_ms': 120,  # frontend/src/tibi/voice.ts; the client component hash covers changes
    }
    try:
        cache_path.write_text(json.dumps(cache, indent=1))
    except OSError:
        pass
    current = engine.current()
    manifest = {
        'schema': 1,
        'engine': {k: current[k] for k in ('version', 'released', 'fingerprint', 'matches_release')},
        'code': {**git_commit(), 'components': {name: component(spec) for name, spec in COMPONENTS.items()}},
        'models': ollama_models([MODEL, REVIEW_MODEL]),
        'speech': speech,
        'settings': {name: os.environ.get(name) for name in SETTINGS if os.environ.get(name) is not None},
        'platform': {'python': sys.version.split()[0], 'system': platform.platform(), 'machine': platform.machine()},
        'packages': packages(),
    }
    manifest['id'] = identity(manifest)
    manifest['captured_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
    manifest['process'] = os.getpid()
    return manifest


def identity(manifest: dict) -> str:
    """Twelve hex characters naming what the manifest describes (not when or in which process it was captured)."""
    stable = {k: v for k, v in manifest.items() if k not in ('id', 'captured_at', 'process')}
    return _sha(json.dumps(stable, sort_keys=True, default=str).encode())[:12]


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
