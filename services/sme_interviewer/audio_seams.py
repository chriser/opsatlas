"""Repair anomalous synthesis joins without resampling, shortening or changing pace."""
import numpy as np


class SeamRepair:
    """Hold 2 ms; smooth only joins anomalous relative to adjacent waveform slopes.

    This treats decoder discontinuities, not clicks already inside a source chunk.
    It never runs at arbitrary transport packet boundaries.
    """
    def __init__(self, rate):
        self.hold = max(2, round(rate * 0.002))
        self.tail = np.empty(0, dtype=np.float32)
        self.repairs = 0

    def push(self, audio):
        incoming = np.asarray(audio, dtype=np.float32).reshape(-1).copy()
        if not np.isfinite(incoming).all():
            raise ValueError('Non-finite voice samples')
        if not len(incoming):
            return incoming
        if len(self.tail) >= 2 and len(incoming) >= 2:
            n = min(self.hold, len(self.tail), len(incoming))
            left, right = self.tail[-n:], incoming[:n]
            slopes = np.r_[np.diff(left), np.diff(right)]
            expected = float((left[-1] - left[-2] + right[1] - right[0]) / 2)
            jump = float(right[0] - left[-1])
            correction = jump - expected
            threshold = max(0.012, 3 * float(np.quantile(np.abs(slopes), 0.9)))
            if abs(correction) > threshold:
                ramp = (0.5 - 0.5 * np.cos(np.linspace(0, np.pi, n))).astype(np.float32)
                patched_left = left + correction * 0.5 * ramp
                patched_right = right - correction * 0.5 * ramp[::-1]
                # Do not introduce clipping while attempting to fix a join.
                if max(np.max(np.abs(patched_left)), np.max(np.abs(patched_right))) < 1:
                    self.tail[-n:] = patched_left
                    incoming[:n] = patched_right
                    self.repairs += 1
        joined = np.concatenate((self.tail, incoming))
        count = min(self.hold, len(joined))
        self.tail = joined[-count:].copy()
        return joined[:-count]

    def finish(self):
        tail, self.tail = self.tail, np.empty(0, dtype=np.float32)
        return tail
