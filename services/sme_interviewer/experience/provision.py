"""Explicit network provisioning only; inference and the web lab never download models."""

import argparse
import hashlib
import json

from .catalog import RUNTIME

SOURCES = [
    ('references', 'kyutai/tts-voices', '323332d33f997de8394f24a193e1a76df720e01a',
     ['vctk/p254_023_enhanced.wav', 'vctk/p228_023_enhanced.wav', 'README.md']),
    ('listener', 'pipecat-ai/smart-turn-v3', 'f766f81d3cfdf7737ac64aad813d91bbfd56bf93', ['smart-turn-v3.2-cpu.onnx']),
]
PERSONAPLEX = [
    ('personaplex-official', 'nvidia/personaplex-7b-v1', 'fdaf4090a61cb315c138a1faee287ffd6c716309',
     ['*.safetensors', '*.json', '*.md', '*.txt', '*.model', '*.tgz']),
    ('personaplex-mlx', 'aufklarer/PersonaPlex-7B-MLX-8bit', '170375ccea23be9950ca0a611cf2a47b2a452540',
     ['*.safetensors', '*.json', '*.md', '*.model']),
]


def manifest(sources):
    files = {}
    for directory in sorted({source[0] for source in sources}):
        for path in sorted((RUNTIME / directory).rglob('*')):
            if not path.is_file() or '.cache' in path.parts or path.name in {'local.yaml', 'revision.txt'}:
                continue
            digest = hashlib.sha256()
            with path.open('rb') as file:
                for block in iter(lambda: file.read(1024 * 1024), b''):
                    digest.update(block)
            files[str(path.relative_to(RUNTIME))] = {'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}
    return {'sources': sources, 'files': files}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--personaplex', action='store_true')
    parser.add_argument('--manifest-only', action='store_true')
    args = parser.parse_args()
    sources = SOURCES + (PERSONAPLEX if args.personaplex else [])
    if not args.manifest_only:
        from huggingface_hub import get_hf_file_metadata, hf_hub_url, snapshot_download

        if args.personaplex:
            # Enforce official access before using any community adaptation.
            get_hf_file_metadata(hf_hub_url(PERSONAPLEX[0][1], 'model.safetensors', revision=PERSONAPLEX[0][2]))
        for directory, repo, revision, patterns in sources:
            snapshot_download(repo, revision=revision, allow_patterns=patterns, local_dir=RUNTIME / directory)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    (RUNTIME / 'artifacts.json').write_text(json.dumps(manifest(sources), indent=2) + '\n')


if __name__ == '__main__':
    main()
