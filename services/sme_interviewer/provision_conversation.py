"""Explicit provisioning for the resident ASR / VAD adapter; serving is offline."""

import json
import subprocess

from .provision import ROOT, RUNTIME, WHISPER_REVISION, download, sha256

VAD_REVISION = "9ffd54a1e1ee413ddf265af9913beaf518d1639b"


def main():
    model = RUNTIME / "models/ggml-silero-v6.2.0.bin"
    url = f"https://huggingface.co/ggml-org/whisper-vad/resolve/{VAD_REVISION}/{model.name}"
    download(url, model)
    if sha256(model) != "2aa269b785eeb53a82983a20501ddf7c1d9c48e33ab63a41391ac6c9f7fb6987":
        raise RuntimeError("Silero model checksum does not match the reviewed revision")
    asr = RUNTIME / "models/ggml-small.en.bin"
    download(f"https://huggingface.co/ggerganov/whisper.cpp/resolve/{WHISPER_REVISION}/{asr.name}", asr)
    if sha256(asr) != "c6138d6d58ecc8322097e0f987c32f1be8bb0a18532a3f88f734d1bbf9c41e5d":
        raise RuntimeError("Recognition model checksum does not match the reviewed revision")
    source = RUNTIME / "whisper.cpp"
    expected = json.loads((ROOT / "model-lock.json").read_text())["whisper_cpp"]["commit"]
    actual = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if actual != expected:
        raise RuntimeError("Unexpected whisper.cpp revision")
    library = source / "build/bin"
    binary = RUNTIME / "conversation-recognizer"
    subprocess.run(
        [
            "c++",
            "-O2",
            "-std=c++17",
            str(ROOT / "native/recognizer.cpp"),
            "-I" + str(source / "include"),
            "-I" + str(source / "ggml/include"),
            "-L" + str(library),
            "-lwhisper",
            "-Wl,-rpath," + str(library),
            "-o",
            str(binary),
        ],
        check=True,
    )
    manifest = {
        "asr_model": "ggml-small.en.bin",
        "asr_revision": WHISPER_REVISION,
        "asr_sha256": sha256(asr),
        "vad_revision": VAD_REVISION,
        "vad_sha256": sha256(model),
        "whisper_commit": actual,
        "adapter_sha256": sha256(ROOT / "native/recognizer.cpp"),
        "binary_sha256": sha256(binary),
    }
    (RUNTIME / "conversation-runtime.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()
