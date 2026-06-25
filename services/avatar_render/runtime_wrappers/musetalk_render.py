"""MuseTalk wrapper used by the local avatar offline benchmark."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .common import RuntimeWrapperError, configured_path, load_profile, require_dir, require_file


def _profile_value(profile: dict[str, Any], key: str, fallback: str | None = None) -> str | None:
    value = profile.get(key, fallback)
    if value is None:
        return None
    return str(value).strip() or None


def _resolve_avatar_source(args: argparse.Namespace, profile: dict[str, Any]) -> Path:
    configured = (
        args.avatar_source
        or _profile_value(profile, "source_video_path")
        or _profile_value(profile, "source_image_path")
        or _profile_value(profile, "video_path")
    )
    if not configured:
        raise RuntimeWrapperError(
            "MuseTalk needs a local user-owned avatar source file. Pass --avatar-source or set "
            "source_video_path in the avatar profile JSON."
        )
    return require_file(Path(configured), "Avatar source file")


def write_inference_config(config_path: Path, *, avatar_source: Path, audio_path: Path, bbox_shift: int | None = None) -> Path:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "task_0:",
        f'  video_path: "{avatar_source}"',
        f'  audio_path: "{audio_path}"',
    ]
    if bbox_shift is not None:
        lines.append(f"  bbox_shift: {bbox_shift}")
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return config_path


def _latest_mp4(result_dir: Path) -> Path | None:
    videos = sorted(result_dir.rglob("*.mp4"), key=lambda path: path.stat().st_mtime, reverse=True)
    return videos[0] if videos else None


def render(args: argparse.Namespace) -> Path:
    data_root = args.data_root.expanduser().resolve()
    profile = load_profile(data_root, "avatar", args.avatar_profile_id)
    audio_path = require_file(args.audio, "Input audio file")
    output_path = args.output.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    repo_dir = require_dir(configured_path(os.environ.get("MUSETALK_REPO_DIR"), args.repo_dir, "MUSETALK_REPO_DIR"), "MUSETALK_REPO_DIR")
    avatar_source = _resolve_avatar_source(args, profile)
    version = args.version or _profile_value(profile, "version", "v1.5")
    mode = args.mode or _profile_value(profile, "mode", "normal")
    if mode != "normal":
        raise RuntimeWrapperError("Offline benchmark wrapper currently supports MuseTalk normal mode only.")
    if version not in {"v1.5", "v1.0"}:
        raise RuntimeWrapperError("MuseTalk version must be v1.5 or v1.0.")

    model_dir = repo_dir / "models" / ("musetalkV15" if version == "v1.5" else "musetalk")
    unet_model_path = require_file(
        model_dir / ("unet.pth" if version == "v1.5" else "pytorch_model.bin"),
        "MuseTalk UNet/model checkpoint",
    )
    unet_config = require_file(model_dir / "musetalk.json", "MuseTalk UNet config")
    ffmpeg_path = args.ffmpeg_path or os.environ.get("MUSETALK_FFMPEG_PATH", "")
    if ffmpeg_path:
        require_dir(Path(ffmpeg_path), "MUSETALK_FFMPEG_PATH")

    result_dir = output_path.parent / "musetalk_results"
    inference_config = output_path.parent / "musetalk_inference.yaml"
    bbox_shift = args.bbox_shift
    if bbox_shift is None and "bbox_shift" in profile:
        bbox_shift = int(profile["bbox_shift"])
    write_inference_config(inference_config, avatar_source=avatar_source, audio_path=audio_path, bbox_shift=bbox_shift)

    python_bin = args.python or os.environ.get("MUSETALK_PYTHON", sys.executable)
    command = [
        python_bin,
        "-m",
        "scripts.inference",
        "--inference_config",
        str(inference_config),
        "--result_dir",
        str(result_dir),
        "--unet_model_path",
        str(unet_model_path),
        "--unet_config",
        str(unet_config),
        "--version",
        "v15" if version == "v1.5" else "v1",
    ]
    if ffmpeg_path:
        command.extend(["--ffmpeg_path", ffmpeg_path])

    completed = subprocess.run(command, cwd=str(repo_dir), capture_output=True, text=True, timeout=args.timeout_seconds)
    if completed.returncode != 0:
        raise RuntimeWrapperError(
            "MuseTalk inference failed with exit code "
            f"{completed.returncode}. stderr: {completed.stderr.strip() or '<empty>'}"
        )
    produced = _latest_mp4(result_dir)
    if produced is None:
        raise RuntimeWrapperError(f"MuseTalk completed but no MP4 was found under {result_dir}.")
    shutil.copy2(produced, output_path)
    if not output_path.exists():
        raise RuntimeWrapperError(f"MuseTalk did not create output MP4: {output_path}")
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render an avatar MP4 with a local MuseTalk checkout.")
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--avatar-profile-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--repo-dir", default="")
    parser.add_argument("--avatar-source", default="")
    parser.add_argument("--version", default="")
    parser.add_argument("--mode", default="")
    parser.add_argument("--bbox-shift", type=int)
    parser.add_argument("--ffmpeg-path", default="")
    parser.add_argument("--python", default="")
    parser.add_argument("--timeout-seconds", type=float, default=900)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output = render(args)
    except RuntimeWrapperError as exc:
        print(f"musetalk_render failed: {exc}", file=sys.stderr)
        return 2
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
