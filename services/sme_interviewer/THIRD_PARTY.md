# Speech runtime provenance

Pinned versions and model checksums are in `requirements.lock` and `model-lock.json`. Model files, compiled binaries and installed packages remain local in the ignored runtime/virtual environment; this repository does not redistribute them.

| Component | Revision / form | Upstream licence and source |
|---|---|---|
| MLX Audio | 0.5.4 | MIT · https://github.com/Blaizzy/mlx-audio |
| whisper.cpp | v1.9.4, commit 927cfce34f31707e17f2bff35c349632fb9e2c3a | MIT · https://github.com/ggml-org/whisper.cpp |
| Whisper base.en weights | ggml-base.en.bin, revision 5359861c739e955e79d9a303bcbc70fb988958b1 | MIT · https://huggingface.co/ggerganov/whisper.cpp |

The dependency lock includes transitive packages with their own licences; retain installed distribution metadata. The Kokoro and Qwen3-TTS VoiceDesign voices were removed (AUDIT F11), but until the environment is rebuilt `requirements.lock` still installs the Kokoro ONNX wrapper (0.6.1, MIT) and its **espeakng-loader 0.2.4**, which bundles [eSpeak NG (GPL-3.0)](https://github.com/espeak-ng/espeak-ng/blob/master/COPYING); inspect its distribution notices before bundling or distributing a packaged application. The package/version licence audit here covers the named speech stack, not approval for future redistribution.
