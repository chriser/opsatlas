"""Deterministic speech delivery, separate from the factual question text.

No unsupported SSML or emotion tags are sent to TTS. Pace preserves pitch;
explicit sentence gaps preserve the model's longer existing pauses.
"""
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Phrase:
    text: str
    pause_after_ms: int


@dataclass(frozen=True)
class Delivery:
    tempo: float = 1.0
    sentence_pause_ms: int = 450
    question_pause_ms: int = 650

    def __post_init__(self):
        if not 0.85 <= self.tempo <= 1.05 or not 200 <= self.sentence_pause_ms <= 1000 or not 200 <= self.question_pause_ms <= 1200:
            raise ValueError('Delivery outside supported bounds')

    def phrases(self, text):
        parts, start = [], 0
        for match in re.finditer(r'[.!?]["”]?\s+(?=[A-Z“"])', text):
            prefix = text[start:match.start() + 1]
            if re.search(r'\b(?:Mr|Mrs|Ms|Dr|Prof|St|e\.g|i\.e)\.$|\b[A-Z]\.$', prefix):
                continue
            parts.append(text[start:match.start() + len(match.group().rstrip())].strip())
            start = match.end()
        parts.append(text[start:].strip())
        parts = [p for p in parts if p]
        return [Phrase(p, 0 if i == len(parts) - 1 else
                       self.question_pause_ms if parts[i + 1].endswith('?') else self.sentence_pause_ms)
                for i, p in enumerate(parts)]


def paced_audio(chunks, rate, tempo):
    """Stream through FFmpeg's pitch-preserving atempo, never resample the pitch."""
    import shutil
    import subprocess
    import threading

    import numpy as np

    if tempo == 1.0:
        for audio, _ in chunks:
            yield np.asarray(audio, dtype=np.float32)
        return

    executable = shutil.which('ffmpeg')
    if not executable:
        raise RuntimeError('Pitch-preserving delivery requires local FFmpeg')
    process = subprocess.Popen(
        [executable, '-hide_banner', '-loglevel', 'error', '-f', 'f32le', '-ar', str(rate), '-ac', '1',
         '-probesize', '32', '-analyzeduration', '0', '-i', 'pipe:0', '-af', f'atempo={tempo}',
         '-f', 'f32le', '-flush_packets', '1', 'pipe:1'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0,
    )
    errors = []

    def produce():
        try:
            for audio, _ in chunks:
                data = memoryview(np.asarray(audio, dtype='<f4').tobytes())
                while data:
                    written = process.stdin.write(data)
                    if not written:
                        raise RuntimeError('Tempo input closed')
                    data = data[written:]
        except BaseException as exc:
            errors.append(exc)
        finally:
            process.stdin.close()

    thread = threading.Thread(target=produce, daemon=True)
    thread.start()
    pending = b''
    try:
        while block := process.stdout.read(3840):
            pending += block
            size = len(pending) // 4 * 4
            if size:
                yield np.frombuffer(pending[:size], dtype='<f4').copy()
                pending = pending[size:]
        thread.join(timeout=5)
        if thread.is_alive() or process.wait(timeout=5) or pending or errors:
            raise RuntimeError('Pitch-preserving speech delivery failed')
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()
        thread.join(timeout=5)
