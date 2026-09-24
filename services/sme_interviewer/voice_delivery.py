"""Whole-phrase delivery controls; never alter pitch or resample packet by packet."""
import shutil
import subprocess
from pathlib import Path

import numpy as np


def settle_phrase(audio, rate, tempo=0.94):
    samples = np.asarray(audio, dtype=np.float32).reshape(-1)
    if not len(samples) or not np.isfinite(samples).all():
        raise ValueError('Invalid voice samples')
    executable = shutil.which('ffmpeg')
    if executable is None and Path('/opt/homebrew/bin/ffmpeg').is_file():
        executable = '/opt/homebrew/bin/ffmpeg'
    if executable is None:
        raise RuntimeError('Chatterbox paced delivery requires local ffmpeg')
    rendered = subprocess.run(
        [executable, '-hide_banner', '-loglevel', 'error', '-f', 'f32le', '-ar', str(rate), '-ac', '1',
         '-i', 'pipe:0', '-af', f'atempo={tempo}', '-f', 'f32le', 'pipe:1'],
        input=samples.astype('<f4').tobytes(), capture_output=True, timeout=10, check=True)
    output = np.frombuffer(rendered.stdout, dtype='<f4').copy()
    if not len(output) or not np.isfinite(output).all():
        raise ValueError('Invalid paced voice samples')
    # Attenuate loud phrases once; never pump gain within speech or boost quiet speech.
    active = output[np.abs(output) > 0.01]
    rms = float(np.sqrt(np.mean(active ** 2))) if len(active) else 0
    gain = min(1.0, 0.085 / max(rms, 1e-6), 0.85 / max(float(np.max(np.abs(output))), 1e-6))
    output *= gain
    ramp = min(int(rate * 0.005), len(output) // 2)
    if ramp:
        window = np.sin(np.linspace(0, np.pi / 2, ramp)) ** 2
        output[:ramp] *= window
        output[-ramp:] *= window[::-1]
    return output
