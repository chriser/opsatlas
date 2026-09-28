"""Audio completion policy shared by the integrated conversation.

Estimates never override resumed speech. No model call runs on the frame receiver.

The turn-completion model (Smart Turn, ~24 ms per check on CPU) is consulted every 150 ms
once 200 ms of silence has passed. A confident prediction closes the turn after 300 ms of
silence; two positive predictions close it after 500 ms. Until 24 September 2026 every turn
waited at least 1.0 s of silence regardless of confidence, which was the largest fixed cost
in the measured turn gap (median 1.12 s of the 4.6 s end of speech to first audio).
"""

FIRST_CHECK = 3200        # 0.20 s of silence at 16 kHz
RECHECK = 2400            # 0.15 s between checks
CONFIDENT = 0.85
QUICK_SILENCE = 4800      # 0.30 s
POSITIVE = 0.7
STANDARD_SILENCE = 8000   # 0.50 s
# A process interview (TIBI E5): describing a process is a string of complete sentences with thinking pauses, so a
# sentence that sounds finished is not the end of the answer. The turn ends only after this much silence (PI F8).
PROCESS_PATIENCE = 20800  # 1.30 s


class TurnBoundary:
    def __init__(self, fallback=None, patience=0):
        # ``fallback``: samples of silence that end a turn even when the model is unsure
        # (conversation practice); None keeps waiting for the participant (process interview).
        # ``patience``: the least silence that ends a turn however sure the model is (process interview).
        self.fallback = fallback
        self.patience = patience
        self.reset()

    def reset(self):
        self.voice_sample = 0
        self.hits = 0
        self.last = 0.0
        self.checked_at = 0
        self.failed = False

    def voiced(self, sample):
        self.voice_sample = sample
        self.hits = 0
        self.last = 0.0

    def result(self, probability, voice_sample):
        if voice_sample != self.voice_sample:
            return
        self.last = probability
        self.hits = self.hits + 1 if probability >= POSITIVE else 0

    def due(self, sample):
        return sample - self.voice_sample >= FIRST_CHECK and sample - self.checked_at >= RECHECK

    def complete(self, sample):
        silence = sample - self.voice_sample
        return ((self.last >= CONFIDENT and silence >= max(QUICK_SILENCE, self.patience))
                or (self.hits >= 2 and silence >= max(STANDARD_SILENCE, self.patience))
                or (self.fallback is not None and silence >= self.fallback))
