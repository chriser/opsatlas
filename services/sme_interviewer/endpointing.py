"""Audio completion policy shared by the integrated conversation.

Estimates never override resumed speech. No model call runs on the frame receiver.
"""

class TurnBoundary:
    def __init__(self):
        self.reset()

    def reset(self):
        self.voice_sample = 0
        self.hits = 0
        self.checked_at = 0
        self.failed = False

    def voiced(self, sample):
        self.voice_sample = sample
        self.hits = 0

    def result(self, probability, voice_sample):
        if voice_sample != self.voice_sample:
            return
        self.hits = self.hits + 1 if probability >= 0.7 else 0

    def due(self, sample):
        return sample - self.voice_sample >= 5600 and sample - self.checked_at >= 11200

    def complete(self, sample):
        return self.hits >= 2 and sample - self.voice_sample >= 16000
