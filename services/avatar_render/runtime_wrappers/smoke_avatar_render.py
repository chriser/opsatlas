"""CPU smoke renderer for visible local avatar benchmark artifacts.

This wrapper is intentionally not a MuseTalk replacement. It can animate either
a supplied local portrait image or a simple drawn face from a WAV amplitude
envelope so the benchmark API can prove end-to-end orchestration on machines
without CUDA.
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
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from .common import RuntimeWrapperError, load_profile, require_file


def _profile_value(profile: dict[str, Any], key: str, fallback: str) -> str:
    value = profile.get(key, fallback)
    return str(value).strip() or fallback


def _profile_float(
    profile: dict[str, Any],
    key: str,
    fallback: float,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    try:
        value = float(profile.get(key, fallback))
    except (TypeError, ValueError):
        value = fallback
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _profile_bool(profile: dict[str, Any], key: str, fallback: bool) -> bool:
    value = profile.get(key, fallback)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_color(value: str, fallback: str) -> str:
    text = value.strip()
    if len(text) == 7 and text.startswith("#"):
        return text
    return fallback


def _load_source_image(profile: dict[str, Any]) -> Image.Image | None:
    configured = _profile_value(profile, "source_image_path", "")
    if not configured:
        return None
    source_path = require_file(Path(configured), "Source avatar image")
    try:
        return Image.open(source_path).convert("RGB")
    except OSError as exc:
        raise RuntimeWrapperError(f"Source avatar image could not be opened: {source_path}") from exc


def _cover_image(
    source: Image.Image,
    *,
    width: int,
    height: int,
    center_x: float,
    center_y: float,
    zoom: float,
) -> Image.Image:
    source_width, source_height = source.size
    target_ratio = width / height
    source_ratio = source_width / source_height
    if source_ratio > target_ratio:
        crop_height = source_height
        crop_width = crop_height * target_ratio
    else:
        crop_width = source_width
        crop_height = crop_width / target_ratio

    crop_width = min(source_width, crop_width / zoom)
    crop_height = min(source_height, crop_height / zoom)
    left = (source_width - crop_width) * center_x
    top = (source_height - crop_height) * center_y
    left = min(max(0, left), source_width - crop_width)
    top = min(max(0, top), source_height - crop_height)
    crop = source.crop((round(left), round(top), round(left + crop_width), round(top + crop_height)))
    return crop.resize((width, height), Image.Resampling.LANCZOS)


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
    source_image: Image.Image | None = None,
) -> None:
    if source_image is not None:
        _draw_source_image_frame(
            path,
            width=width,
            height=height,
            amplitude=amplitude,
            frame_index=frame_index,
            fps=fps,
            profile=profile,
            source_image=source_image,
        )
        return

    _draw_cartoon_frame(
        path,
        width=width,
        height=height,
        amplitude=amplitude,
        frame_index=frame_index,
        fps=fps,
        profile=profile,
    )


def _draw_source_image_frame(
    path: Path,
    *,
    width: int,
    height: int,
    amplitude: float,
    frame_index: int,
    fps: int,
    profile: dict[str, Any],
    source_image: Image.Image,
) -> None:
    t = frame_index / fps
    intensity = _profile_float(profile, "motion_intensity", 1.0, minimum=0.0, maximum=3.0)
    center_x = _profile_float(profile, "source_center_x", 0.5, minimum=0.0, maximum=1.0)
    center_y = _profile_float(profile, "source_center_y", 0.32, minimum=0.0, maximum=1.0)
    base_zoom = _profile_float(profile, "source_zoom", 1.03, minimum=1.0, maximum=2.0)
    zoom = base_zoom + (math.sin(t * 0.8) * 0.005 * intensity) + (amplitude * 0.018 * intensity)
    animated_center_x = center_x + (math.sin(t * 0.6) * 0.006 * intensity)
    animated_center_y = center_y + (math.sin(t * 0.9) * 0.004 * intensity) - (amplitude * 0.004 * intensity)

    background = _cover_image(
        source_image,
        width=width,
        height=height,
        center_x=center_x,
        center_y=center_y,
        zoom=max(1.0, base_zoom - 0.02),
    )
    background = background.filter(ImageFilter.GaussianBlur(radius=10))
    background = ImageEnhance.Brightness(background).enhance(0.58)
    foreground = _cover_image(
        source_image,
        width=width,
        height=height,
        center_x=animated_center_x,
        center_y=animated_center_y,
        zoom=zoom,
    )
    image = Image.blend(background, foreground, 0.88)

    draw = ImageDraw.Draw(image, "RGBA")
    if _profile_bool(profile, "show_label", True):
        label_font = _font(20)
        display_name = _profile_value(profile, "display_name", "Local Avatar Photo Preview")
        draw.rounded_rectangle((24, 24, 420, 88), radius=18, fill=(12, 18, 24, 150))
        draw.text((42, 36), display_name, fill=(232, 238, 242, 255), font=label_font)
        draw.text((42, 62), "photo smoke preview - not MuseTalk", fill=(190, 204, 214, 255), font=label_font)
        draw.rounded_rectangle((width - 220, height - 55, width - 32, height - 28), radius=12, fill=(12, 18, 24, 180))
        draw.rectangle((width - 210, height - 47, width - 210 + int(160 * amplitude), height - 36), fill=(42, 161, 152, 255))

    image.save(path)


def _draw_cartoon_frame(
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
    source_image = _load_source_image(profile)
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
                source_image=source_image,
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
