"""Explicit pinned downloads for the September native-delivery audition."""
import json

from .catalog import RUNTIME
from .provision import SOCIAL, SOURCES, manifest

ADDITIONS = [
    ('chatterbox-v3', 'mlx-community/chatterbox-multilingual-v3', '03565773edd72e949572557597af8063bb49a18a',
     ['*.json', '*.safetensors', '*.txt', '*.model', '*.md', '*.tiktoken', '*.pt']),
    ('qwen-custom-8bit', 'mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit', '41d3337e8b7f2843a75841595fc14e4b9a7a4b96',
     ['*.json', '*.safetensors', '*.txt', '*.model', '*.md']),
    ('vibevoice', 'mlx-community/VibeVoice-Realtime-0.5B-fp16', '59ba546c294935410544f037a2de20b9da7ed219',
     ['*.json', '*.safetensors', '*.txt', '*.model', '*.md', '*.npz']),
    ('vibe-tokenizer', 'Qwen/Qwen2.5-0.5B', '060db6499f32faf8b98477b0a26969ef7d8b9987',
     ['tokenizer*', 'vocab.json', 'merges.txt', 'config.json']),
]


def main():
    from huggingface_hub import snapshot_download

    sources = [s for s in SOURCES if s[0] in ('chatterbox', 'references', 's3tokenizer')] + SOCIAL + ADDITIONS
    for directory, repo, revision, patterns in sources:
        snapshot_download(repo, revision=revision, allow_patterns=patterns, local_dir=RUNTIME / directory)
    (RUNTIME / 'benchmark-artifacts.json').write_text(json.dumps(manifest(sources), indent=2)+'\n')


if __name__ == '__main__':
    main()
