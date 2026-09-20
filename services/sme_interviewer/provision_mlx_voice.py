"""Explicit optional Metal speech provisioning; the serving process stays offline."""

import json

from .provision import ROOT, RUNTIME, download, sha256


def main():
    files = json.loads((ROOT / 'model-lock.json').read_text())['files']
    for name, item in files.items():
        if item.get('optional_backend') != 'kokoro_mlx':
            continue
        path = RUNTIME / name
        download(item['url'], path)
        if sha256(path) != item['sha256']:
            raise RuntimeError('Unexpected pinned speech artifact: ' + name)
        print(name, item['sha256'])


if __name__ == '__main__':
    main()
