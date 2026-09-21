"""Offline Charles adapter: stream promptly, retain a short onset pre-roll.

Only leading quiet is removed. Interior pauses and prosody belong to the model.
"""

import importlib.resources

import numpy as np


class OnsetTrim:
    def __init__(self, rate=24000):
        self.window = rate // 100
        self.preroll = rate // 25
        self.pending = np.empty(0, dtype=np.float32)
        self.started = False

    def feed(self, audio, final=False):
        audio = np.asarray(audio, dtype=np.float32).reshape(-1)
        if not np.isfinite(audio).all():
            raise ValueError('Non-finite speech')
        if self.started:
            return audio
        self.pending = np.concatenate((self.pending, audio))
        for i in range(0, len(self.pending) - self.window + 1, self.window):
            if np.sqrt(np.mean(self.pending[i:i + self.window] ** 2)) >= 0.003:
                self.started = True
                result = self.pending[max(0, i - self.preroll):]
                self.pending = np.empty(0, dtype=np.float32)
                return result
        # Keep enough history for an onset crossing a chunk boundary; bounded even
        # if a faulty model emits nothing but silence.
        self.pending = self.pending[-(self.preroll + self.window):]
        if final:
            raise ValueError('No audible speech generated')
        return np.empty(0, dtype=np.float32)


class PocketCharles:
    def __init__(self, runtime):
        import torch
        import yaml
        from pocket_tts import TTSModel

        torch.set_num_threads(4)
        root = runtime / 'experience/pocket'
        config = yaml.safe_load((importlib.resources.files('pocket_tts') / 'config/english.yaml').read_text())
        model_path = str(root / 'languages/english/model.safetensors')
        config['weights_path'] = config['weights_path_without_voice_cloning'] = model_path
        config['flow_lm']['lookup_table']['tokenizer_path'] = str(root / 'languages/english/tokenizer.model')
        config_path = root / 'local.yaml'
        config_path.write_text(yaml.safe_dump(config))
        self.model = TTSModel.load_model(config=config_path)
        self.model.has_voice_cloning = False
        self.state = self.model.get_state_for_audio_prompt(str(root / 'languages/english/embeddings/charles.safetensors'))
        self.rate = self.model.sample_rate
        # Warm inference, not merely model loading, before accepting microphone input.
        list(self.chunks('Ready when you are.'))

    def chunks(self, text):
        trim = OnsetTrim(self.rate)
        for chunk in self.model.generate_audio_stream(self.state, text):
            audio = trim.feed(chunk.detach().cpu().numpy())
            if len(audio):
                yield audio, self.rate
        trim.feed([], final=True)

    async def create_stream(self, text, **kwargs):
        for audio, rate in self.chunks(text):
            yield audio, rate
