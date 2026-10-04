"""Reproduce the isolated Swift feasibility harness from pinned upstream source."""

import argparse
import shutil
import subprocess
from pathlib import Path

from .catalog import ROOT, RUNTIME

REVISION = 'c4c2fabbe825a9290c19e2f45d54ca3eae96b003'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    repo = RUNTIME / 'speech-swift'
    if not repo.exists():
        subprocess.run(['git', 'clone', 'https://github.com/soniqo/speech-swift.git', str(repo)], check=True)
        subprocess.run(['git', '-C', str(repo), 'checkout', REVISION], check=True)
    actual = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != REVISION:
        raise ValueError('Unexpected Swift source revision; do not benchmark an unpinned checkout')
    here = Path(__file__).parent
    shutil.copy(here / 'Probe.Package.swift', repo / 'Package.swift')
    shutil.copy(here / 'Probe.Package.resolved', repo / 'Package.resolved')
    (repo / 'Sources/ExperienceProbe').mkdir(exist_ok=True)
    shutil.copy(here / 'Probe.swift', repo / 'Sources/ExperienceProbe/Probe.swift')
    source = repo / 'Sources/PersonaPlex/PersonaPlex.swift'
    text = source.read_text()
    if 'explicitCacheDirectory' not in text:
        before = ('internal func modelCacheDirectory() throws -> URL {\n'
                  '        try HuggingFaceDownloader.getCacheDirectory(for: modelId)\n    }')
        after = ('private var explicitCacheDirectory: URL?\n    internal func modelCacheDirectory() throws -> URL {\n'
                 '        if let directory = explicitCacheDirectory { return directory }\n'
                 '        return try HuggingFaceDownloader.getCacheDirectory(for: modelId)\n    }')
        if before not in text or text.count('model.modelId = modelId') != 1:
            raise ValueError('Upstream voice-cache patch no longer matches')
        text = text.replace(before, after).replace('model.modelId = modelId',
                                                  'model.modelId = modelId\n        model.explicitCacheDirectory = modelDir')
    # The port otherwise inserts zeros when its generator outruns live input.
    # Pace this probe to actual input frames; never reinterpret an underrun as silence.
    if 'EXPERIENCE_INPUT_PACING' not in text:
        before = 'let micSamples = userAudioBuffer.read(mimiFrameSize)'
        if text.count(before) != 1:
            raise ValueError('Upstream input-pacing patch no longer matches')
        text = text.replace(before, '// EXPERIENCE_INPUT_PACING\n'
                            '                        while userAudioBuffer.available < mimiFrameSize {\n'
                            '                            try Task.checkCancellation()\n'
                            '                            try await Task.sleep(nanoseconds: 2_000_000)\n'
                            '                        }\n                        ' + before)
    source.write_text(text)
    if args.build:
        subprocess.run(['swift', 'build', '-c', 'release', '--product', 'experience-probe', '-j', '6'], cwd=repo, check=True)
    if args.run:
        binary_directory = subprocess.check_output(['swift', 'build', '-c', 'release', '--show-bin-path'],
                                                   cwd=repo, text=True).strip()
        subprocess.run(['/usr/bin/sandbox-exec', '-f', str(ROOT / 'offline.sb'),
                        str(Path(binary_directory) / 'experience-probe'), str(RUNTIME / 'personaplex-mlx'),
                        str(RUNTIME / 'clips/pocket-f-numbers.wav'), str(RUNTIME / 'personaplex-probe')], check=True, timeout=600)


if __name__ == '__main__':
    main()
