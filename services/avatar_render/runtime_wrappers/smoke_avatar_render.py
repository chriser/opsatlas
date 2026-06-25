"""CPU smoke renderer for visible local avatar benchmark artifacts.

This wrapper is intentionally not a MuseTalk replacement. It creates a simple
animated face from a WAV amplitude envelope so the benchmark API can prove
end-to-end orchestration on machines without CUDA or user-owned avatar assets.
"""

from __future__ import annotations

import argparse
import math
import shutil
import subprocess
import wave
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .common import RuntimeWrapperError, load_profile, require_file


def _profile_value(profile: dict[str, Any], key: str, fallback: str) -> str:
    value = profile.get(key, fallback)
    return str(value).strip() or fallback


def _parse_color(value: str, fallback: str) -> str:
    text = value.strip()
    if len(text) == 7 and text.startswith("#"):
        return text
    return fallback


def _chunk_rms(chunk: bytes, sample_width: int, channels: int) -> float:
    if sample_width == 1:
        samples = np.frombuffer(chunk, dtype=np.uint8).astype(np.float32) - 128.0
    elif sample_width == 2:
        samples = np.frombuffer(chunk, dtype="<i2").astype(np.float32)
    elif sample_width == 4:
        samples = np.frombuffer(chunk, dtype="<i4").astype(np.float32)
    else:
        raise RuntimeWrapperError(f"Unsupported WAV sample width for smoke renderer: {sample_width} bytes")
    if channels > 1 and samples.size >= channels:
        samples = samples.reshape(-1, channels).mean(axis=1)
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(samples))))


def audio_envelope(audio_path: Path, fps: int) -> tuple[list[float], float]:
    audio = require_file(audio_path, "Input audio file")
    try:
        with wave.open(str(audio), "rb") as handle:
            sample_rate = handle.getframerate()
            sample_width = handle.getsampwidth()
            channels = handle.getnchannels()
            total_frames = handle.getnframes()
            duration = total_frames / sample_rate if sample_rate else 0
            samples_per_video_frame = max(1, int(sample_rate / fps))
            values: list[float] = []
            while True:
                chunk = handle.readframes(samples_per_video_frame)
                if not chunk:
                    break
                values.append(_chunk_rms(chunk, sample_width, channels))
    except wave.Error as exc:
        raise RuntimeWrapperError(f"Smoke renderer expects a PCM WAV input: {audio}") from exc

    if not values:
        return [0.0], 0.0
    peak = max(max(values), 1.0)
    smoothed: list[float] = []
    previous = 0.0
    for raw in values:
        current = min(raw / peak, 1.0)
        previous = (previous * 0.58) + (current * 0.42)
        smoothed.append(round(previous, 4))
    return smoothed, duration


def _font(size: int) -> ImageFont.ImageFont:
    for candidate in [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ]:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _draw_frame(
    path: Path,
    *,
    width: int,
    height: int,
    amplitude: float,
    frame_index: int,
    fps: int,
    profile: dict[str, Any],
) -> None:
    background = _parse_color(_profile_value(profile, "background_color", "#17212b"), "#17212b")
    skin = _parse_color(_profile_value(profile, "skin_color", "#c98962"), "#c98962")
    accent = _parse_color(_profile_value(profile, "accent_color", "#2aa198"), "#2aa198")
    text_color = "#e8eef2"
    image = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(image)

    t = frame_index / fps
    head_x = width // 2 + int(math.sin(t * 1.4) * 8)
    head_y = height // 2 - 15 + int(math.sin(t * 0.9) * 5)
    head_radius = min(width, height) // 4
    shoulder_y = head_y + head_radius + 70

    draw.rounded_rectangle(
        (width * 0.18, shoulder_y - 45, width * 0.82, height + 80),
        radius=80,
        fill="#263744",
        outline=accent,
        width=4,
    )
    draw.ellipse(
        (head_x - head_radius, head_y - head_radius, head_x + head_radius, head_y + head_radius),
        fill=skin,
        outline="#f0c19b",
        width=4,
    )

    blink = (frame_index % (fps * 4)) in {0, 1, 2}
    eye_y = head_y - 45
    pupil_offset = int(math.sin(t * 1.7) * 5)
    for eye_x in (head_x - 65, head_x + 65):
        if blink:
            draw.line((eye_x - 28, eye_y, eye_x + 28, eye_y), fill="#1b2025", width=5)
        else:
            draw.ellipse((eye_x - 30, eye_y - 15, eye_x + 30, eye_y + 15), fill="#f7fbff")
            draw.ellipse((eye_x - 7 + pupil_offset, eye_y - 8, eye_x + 9 + pupil_offset, eye_y + 8), fill="#17212b")

    brow_shift = int(math.sin(t * 1.1) * 4)
    draw.line((head_x - 95, eye_y - 35 + brow_shift, head_x - 35, eye_y - 48 + brow_shift), fill="#4d342c", width=6)
    draw.line((head_x + 35, eye_y - 48 - brow_shift, head_x + 95, eye_y - 35 - brow_shift), fill="#4d342c", width=6)

    nose_top = head_y - 15
    draw.line((head_x, nose_top, head_x - 14, nose_top + 55, head_x + 18, nose_top + 55), fill="#9d674e", width=4)

    mouth_open = 10 + int(amplitude * 72)
    mouth_width = 132 + int(amplitude * 26)
    mouth_y = head_y + 95
    draw.ellipse(
        (
            head_x - mouth_width // 2,
            mouth_y - mouth_open // 2,
            head_x + mouth_width // 2,
            mouth_y + mouth_open // 2,
        ),
        fill="#241116",
        outline="#8d2f45",
        width=5,
    )
    if mouth_open > 30:
        draw.arc(
            (
                head_x - mouth_width // 2 + 20,
                mouth_y - mouth_open // 2 + 8,
                head_x + mouth_width // 2 - 20,
                mouth_y + mouth_open // 2 + 14,
            ),
            start=0,
            end=180,
            fill="#f7d9cb",
            width=3,
        )

    label_font = _font(22)
    title_font = _font(32)
    display_name = _profile_value(profile, "display_name", "Local Avatar Smoke Preview")
    draw.text((32, 30), display_name, fill=text_color, font=title_font)
    draw.text((32, height - 55), "CPU smoke preview - not MuseTalk", fill="#b9c8d3", font=label_font)
    draw.rounded_rectangle((width - 220, height - 55, width - 32, height - 28), radius=12, fill="#0f171f")
    draw.rectangle((width - 210, height - 47, width - 210 + int(160 * amplitude), height - 36), fill=accent)

    image.save(path)


def render(args: argparse.Namespace) -> Path:
    data_root = args.data_root.expanduser().resolve()
    profile = load_profile(data_root, "avatar", args.avatar_profile_id)
    output_path = args.output.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which(args.ffmpeg)
    if not ffmpeg:
        raise RuntimeWrapperError(f"ffmpeg command is not available: {args.ffmpeg}")

    envelope, duration = audio_envelope(args.audio, args.fps)
    total_frames = max(1, math.ceil(duration * args.fps), len(envelope))
    with TemporaryDirectory(prefix="smoke-avatar-", dir=str(output_path.parent)) as frame_dir_raw:
        frame_dir = Path(frame_dir_raw)
        for index in range(total_frames):
            amplitude = envelope[min(index, len(envelope) - 1)]
            frame_path = frame_dir / f"frame_{index:06d}.png"
            _draw_frame(
                frame_path,
                width=args.width,
                height=args.height,
                amplitude=amplitude,
                frame_index=index,
                fps=args.fps,
                profile=profile,
            )
        command = [
            ffmpeg,
            "-y",
            "-framerate",
            str(args.fps),
            "-i",
            str(frame_dir / "frame_%06d.png"),
            "-i",
            str(args.audio),
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=args.timeout_seconds)
    if completed.returncode != 0:
        raise RuntimeWrapperError(f"ffmpeg failed with exit code {completed.returncode}: {completed.stderr.strip()}")
    if not output_path.exists():
        raise RuntimeWrapperError(f"Smoke renderer did not create output MP4: {output_path}")
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render a visible CPU smoke avatar MP4 from a local WAV file.")
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--avatar-profile-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--timeout-seconds", type=float, default=120)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output = render(args)
    except RuntimeWrapperError as exc:
        print(f"smoke_avatar_render failed: {exc}", flush=True)
        return 2
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
