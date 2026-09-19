# Speech runtime provenance

Pinned versions and model checksums are in `requirements.lock` and `model-lock.json`. Model files, compiled binaries and installed packages remain local in the ignored runtime/virtual environment; this repository does not redistribute them.

| Component | Revision / form | Upstream licence and source |
|---|---|---|
| Kokoro ONNX wrapper | 0.6.1 | MIT · https://github.com/thewh1teagle/kokoro-onnx |
| Kokoro model and voices | model-files-v1.0, fp32 | Apache-2.0 model · https://huggingface.co/hexgrad/Kokoro-82M ; converted artifacts: https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0 |
| MLX Audio | 0.5.4 | MIT · https://github.com/Blaizzy/mlx-audio |
| Qwen3-TTS VoiceDesign | 1.7B, MLX 4-bit, revision 5c390979e4b93af5f2932f90742ca99c7dd04687 | Apache-2.0 · https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-4bit |
| whisper.cpp | v1.9.4, commit 927cfce34f31707e17f2bff35c349632fb9e2c3a | MIT · https://github.com/ggml-org/whisper.cpp |
| Whisper base.en weights | ggml-base.en.bin, revision 5359861c739e955e79d9a303bcbc70fb988958b1 | MIT · https://huggingface.co/ggerganov/whisper.cpp |

The dependency lock includes transitive packages with their own licences; retain installed distribution metadata. In particular the Kokoro path uses **espeakng-loader 0.2.4**, which bundles [eSpeak NG (GPL-3.0)](https://github.com/espeak-ng/espeak-ng/blob/master/COPYING); inspect its distribution notices before bundling or distributing a packaged application. The package/version licence audit here covers the audition's named speech stack, not approval for future redistribution. No cloning reference or third-party recorded voice sample is supplied to Qwen VoiceDesign.
