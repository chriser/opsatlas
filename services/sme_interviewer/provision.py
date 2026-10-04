"""Explicit online provisioning. Serving and benchmarking never download models."""

import hashlib
import json
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / ".runtime"
WHISPER_REVISION = "5359861c739e955e79d9a303bcbc70fb988958b1"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url, path):
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    print("Downloading", path.name, flush=True)
    with urllib.request.urlopen(url, timeout=120) as source, temporary.open("wb") as target:
        while chunk := source.read(1024 * 1024):
            target.write(chunk)
    temporary.replace(path)


def main():
    RUNTIME.mkdir(exist_ok=True)
    files = {}
    whisper_url = f"https://huggingface.co/ggerganov/whisper.cpp/resolve/{WHISPER_REVISION}/ggml-base.en.bin"
    path = RUNTIME / "models" / "ggml-base.en.bin"
    download(whisper_url, path)
    files[str(path.relative_to(RUNTIME))] = {"sha256": sha256(path), "url": whisper_url, "licence": "MIT"}
    source = RUNTIME / "whisper.cpp"
    if not source.exists():
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", "v1.9.4", "https://github.com/ggml-org/whisper.cpp", str(source)], check=True
        )
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    expected = json.loads((ROOT / "model-lock.json").read_text())
    if revision != expected["whisper_cpp"]["commit"]:
        raise RuntimeError("whisper.cpp revision differs from the reviewed model lock")
    for name, entry in expected["files"].items():
        if name not in files or files[name]["sha256"] != entry["sha256"]:
            raise RuntimeError("Model checksum differs from the reviewed model lock: " + name)
    subprocess.run(
        [
            "cmake",
            "-S",
            str(source),
            "-B",
            str(source / "build"),
            "-DCMAKE_BUILD_TYPE=Release",
            "-DGGML_METAL=ON",
            "-DWHISPER_BUILD_TESTS=OFF",
            "-DWHISPER_BUILD_SERVER=OFF",
        ],
        check=True,
    )
    subprocess.run(["cmake", "--build", str(source / "build"), "--config", "Release", "-j", "8", "--target", "whisper-cli"], check=True)
    manifest = {
        "schema": 1,
        "files": files,
        "whisper_cpp": {"tag": "v1.9.4", "commit": revision, "licence": "MIT"},
    }
    (RUNTIME / "provision-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Provisioned local models and Metal ASR; manifest recorded", flush=True)


if __name__ == "__main__":
    main()
