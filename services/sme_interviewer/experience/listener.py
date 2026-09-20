"""Small CPU endpoint experiment, separate from semantic interviewing.

Completion is a model estimate, not a command to seize the floor. The policy
requires both speech and silence, and gives an incomplete answer more time.
"""

import time

from .catalog import RUNTIME


class Endpoint:
    def __init__(self):
        import onnxruntime as ort
        from transformers import WhisperFeatureExtractor

        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.session = ort.InferenceSession(str(RUNTIME / 'listener/smart-turn-v3.2-cpu.onnx'),
                                           sess_options=options, providers=['CPUExecutionProvider'])
        self.features = WhisperFeatureExtractor(chunk_length=8)

    def predict(self, audio):
        import numpy as np

        audio = np.asarray(audio, dtype=np.float32)
        if (audio.ndim != 1 or not 8000 <= len(audio) <= 128000
                or not np.isfinite(audio).all() or np.max(np.abs(audio)) > 1.001):
            raise ValueError('Expected 0.5–8 seconds of finite mono 16 kHz samples')
        start = time.perf_counter()
        audio = np.pad(audio, (128000 - len(audio), 0))
        features = self.features(audio, sampling_rate=16000, return_tensors='np', padding='max_length',
                                 max_length=128000, truncation=True, do_normalize=True).input_features
        probability = float(self.session.run(None, {'input_features': features.astype(np.float32)})[0][0].item())
        if not np.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError('Invalid completion probability')
        return {'probability': probability, 'complete': probability >= 0.5,
                'inference_ms': (time.perf_counter() - start) * 1000}
