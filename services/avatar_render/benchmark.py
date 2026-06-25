"""Offline benchmark harness for local avatar TTS and render candidates."""

from __future__ import annotations

import json
import os
import platform
import shlex
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from .models import (
    BenchmarkArtifact,
    BenchmarkDependency,
    BenchmarkMetric,
    DependencyState,
    OfflineBenchmarkRequest,
    OfflineBenchmarkResponse,
)

DEFAULT_TTS_OUTPUT_NAME = "speech.wav"
DEFAULT_RENDER_OUTPUT_NAME = "avatar.mp4"
DEFAULT_COMMAND_TIMEOUT_SECONDS = 900


def _safe_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in value.strip())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned[:80] or "avatar-benchmark"


def _artifact(kind: str, path: Path) -> BenchmarkArtifact:
    exists = path.exists()
    size = path.stat().st_size if exists and path.is_file() else 0
    return BenchmarkArtifact(kind=kind, path=str(path), exists=exists, size_bytes=size)


def _command_dependency(name: str, env_var: str, detail: str) -> BenchmarkDependency:
    command = os.environ.get(env_var, "").strip()
    if not command:
        return BenchmarkDependency(name=name, status="missing", detail=f"{env_var} is not configured. {detail}")
    first_token = shlex.split(command)[0] if command else ""
    if first_token and shutil.which(first_token):
        return BenchmarkDependency(name=name, status="ready", detail=f"{env_var} is configured.")
    return BenchmarkDependency(name=name, status="error", detail=f"{env_var} starts with unavailable command: {first_token}.")


def dependency_readiness() -> list[BenchmarkDependency]:
    dependencies = [
        _command_dependency(
            "openvoice_command",
            "AVATAR_TTS_COMMAND",
            "Expected to create a WAV from {text_path} into {audio_path}.",
        ),
        _command_dependency(
            "musetalk_command",
            "AVATAR_RENDER_COMMAND",
            "Expected to create an MP4 from {audio_path} and {avatar_profile_id} into {video_path}.",
        ),
    ]

    ffmpeg = shutil.which("ffmpeg")
    dependencies.append(
        BenchmarkDependency(
            name="ffmpeg",
            status="ready" if ffmpeg else "missing",
            detail=ffmpeg or "ffmpeg is not on PATH; MuseTalk media assembly may fail.",
        )
    )

    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        probe = subprocess.run(
            [nvidia_smi, "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        status: DependencyState = "ready" if probe.returncode == 0 else "error"
        detail = probe.stdout.strip() if probe.returncode == 0 else (probe.stderr.strip() or "nvidia-smi returned an error.")
    else:
        status = "missing"
        detail = "nvidia-smi is not on PATH; realtime MuseTalk performance on NVIDIA CUDA cannot be measured here."
    dependencies.append(BenchmarkDependency(name="nvidia_cuda", status=status, detail=detail))

    dependencies.append(
        BenchmarkDependency(
            name="host",
            status="ready",
            detail=f"{platform.system()} {platform.release()} {platform.machine()}",
        )
    )
    return dependencies


def _render_template(command: str, *, text_path: Path, audio_path: Path, video_path: Path, request: OfflineBenchmarkRequest) -> list[str]:
    formatted = command.format(
        text_path=str(text_path),
        audio_path=str(audio_path),
        video_path=str(video_path),
        data_root=str(text_path.parents[2]),
        run_dir=str(text_path.parent),
        speech_id=request.speech_id,
        style=request.style,
        voice_profile_id=request.voice_profile_id,
        avatar_profile_id=request.avatar_profile_id,
    )
    return shlex.split(formatted)


def _run_command(command: list[str], log_path: Path) -> tuple[int, float]:
    started = time.perf_counter()
    timeout_seconds = float(os.environ.get("AVATAR_BENCHMARK_COMMAND_TIMEOUT_SECONDS", DEFAULT_COMMAND_TIMEOUT_SECONDS))
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("$ " + " ".join(shlex.quote(part) for part in command) + "\n")
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            elapsed = time.perf_counter() - started
            handle.write(f"timed out after {timeout_seconds:g}s\n")
            if exc.stdout:
                handle.write(str(exc.stdout))
                if not str(exc.stdout).endswith("\n"):
                    handle.write("\n")
            if exc.stderr:
                handle.write(str(exc.stderr))
                if not str(exc.stderr).endswith("\n"):
                    handle.write("\n")
            handle.write("exit_code=124\n")
            return 124, elapsed
        elapsed = time.perf_counter() - started
        if completed.stdout:
            handle.write(completed.stdout)
            if not completed.stdout.endswith("\n"):
                handle.write("\n")
        if completed.stderr:
            handle.write(completed.stderr)
            if not completed.stderr.endswith("\n"):
                handle.write("\n")
        handle.write(f"exit_code={completed.returncode}\n")
    return completed.returncode, elapsed


def _parse_rate(value: str) -> float | None:
    if not value or value == "0/0":
        return None
    if "/" not in value:
        try:
            return float(value)
        except ValueError:
            return None
    numerator, denominator = value.split("/", 1)
    try:
        denominator_value = float(denominator)
        if denominator_value == 0:
            return None
        return float(numerator) / denominator_value
    except ValueError:
        return None


def _ffprobe_json(path: Path, selector: str, entries: str) -> dict:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe or not path.exists():
        return {}
    command = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        selector,
        "-show_entries",
        entries,
        "-of",
        "json",
        str(path),
    ]
    probe = subprocess.run(command, capture_output=True, text=True, timeout=30)
    if probe.returncode != 0:
        return {}
    try:
        return json.loads(probe.stdout)
    except json.JSONDecodeError:
        return {}


def _audio_metrics(path: Path) -> list[BenchmarkMetric]:
    data = _ffprobe_json(path, "a:0", "stream=duration")
    streams = data.get("streams") or []
    if not streams:
        return []
    duration = streams[0].get("duration")
    if duration is None:
        return []
    try:
        return [BenchmarkMetric(name="audio_duration_seconds", value=round(float(duration), 3), unit="s")]
    except ValueError:
        return []


def _video_metrics(path: Path) -> list[BenchmarkMetric]:
    data = _ffprobe_json(path, "v:0", "stream=avg_frame_rate,duration,nb_frames,width,height")
    streams = data.get("streams") or []
    if not streams:
        return []
    stream = streams[0]
    metrics: list[BenchmarkMetric] = []
    fps = _parse_rate(str(stream.get("avg_frame_rate", "")))
    if fps is not None:
        metrics.append(BenchmarkMetric(name="video_fps", value=round(fps, 3), unit="fps"))
    for key, metric_name, unit in [
        ("duration", "video_duration_seconds", "s"),
        ("nb_frames", "video_frames", "frames"),
        ("width", "video_width", "px"),
        ("height", "video_height", "px"),
    ]:
        value = stream.get(key)
        if value is None:
            continue
        try:
            number = float(value)
        except ValueError:
            continue
        if number.is_integer():
            number = int(number)
        metrics.append(BenchmarkMetric(name=metric_name, value=number, unit=unit))
    return metrics


def run_offline_benchmark(request: OfflineBenchmarkRequest, data_root: Path) -> OfflineBenchmarkResponse:
    now = datetime.now(UTC)
    run_id = f"{now.strftime('%Y%m%dT%H%M%SZ')}-{_safe_id(request.speech_id)}"
    run_dir = data_root / "benchmarks" / run_id
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        dependencies = dependency_readiness()
        return OfflineBenchmarkResponse(
            status="failed",
            speech_id=request.speech_id,
            run_id=run_id,
            data_root=str(data_root),
            run_dir=str(run_dir),
            dependencies=dependencies,
            artifacts=[],
            metrics=[BenchmarkMetric(name="text_characters", value=len(request.text), unit="chars")],
            warnings=["Benchmark could not write artifacts. Set AVATAR_RENDER_DATA_DIR to a writable local path."],
            errors=[f"Could not create benchmark run directory: {exc}"],
        )

    text_path = run_dir / "approved_text.txt"
    audio_path = run_dir / DEFAULT_TTS_OUTPUT_NAME
    video_path = run_dir / DEFAULT_RENDER_OUTPUT_NAME
    log_path = run_dir / "benchmark.log"
    manifest_path = run_dir / "manifest.json"

    text_path.write_text(request.text, encoding="utf-8")
    dependencies = dependency_readiness()
    metrics: list[BenchmarkMetric] = [
        BenchmarkMetric(name="text_characters", value=len(request.text), unit="chars"),
    ]
    warnings = [
        "Benchmark input is approved speech text only; raw questions and source documents are rejected by schema validation.",
        "Artifacts are written under the local ignored avatar data directory.",
        "Subjective lip-sync, identity drift, jitter and expression quality still require manual review of generated media.",
    ]
    errors: list[str] = []
    status = "blocked"

    allow_execute = os.environ.get("AVATAR_BENCHMARK_ALLOW_EXECUTE", "").strip() == "1"
    if request.run_commands and not allow_execute:
        warnings.append("run_commands was requested, but AVATAR_BENCHMARK_ALLOW_EXECUTE is not set to 1.")

    tts_command = os.environ.get("AVATAR_TTS_COMMAND", "").strip()
    render_command = os.environ.get("AVATAR_RENDER_COMMAND", "").strip()
    can_execute = request.run_commands and allow_execute and tts_command and render_command

    if can_execute:
        status = "completed"
        tts_parts = _render_template(tts_command, text_path=text_path, audio_path=audio_path, video_path=video_path, request=request)
        tts_code, tts_seconds = _run_command(tts_parts, log_path)
        metrics.append(BenchmarkMetric(name="tts_seconds", value=round(tts_seconds, 3), unit="s"))
        if tts_code != 0 or not audio_path.exists():
            status = "failed"
            errors.append("TTS command failed or did not create the expected audio artifact.")
        else:
            metrics.extend(_audio_metrics(audio_path))
            render_parts = _render_template(
                render_command,
                text_path=text_path,
                audio_path=audio_path,
                video_path=video_path,
                request=request,
            )
            render_code, render_seconds = _run_command(render_parts, log_path)
            metrics.append(BenchmarkMetric(name="render_seconds", value=round(render_seconds, 3), unit="s"))
            if render_code != 0 or not video_path.exists():
                status = "failed"
                errors.append("Render command failed or did not create the expected video artifact.")
            else:
                metrics.extend(_video_metrics(video_path))
    else:
        missing = [item.name for item in dependencies if item.name in {"openvoice_command", "musetalk_command"} and item.status != "ready"]
        if missing:
            errors.append("Benchmark commands are not fully configured: " + ", ".join(missing) + ".")
        if not request.run_commands:
            warnings.append("run_commands is false; readiness and manifest were generated without running model commands.")

    artifacts = [
        _artifact("approved_text", text_path),
        _artifact("audio", audio_path),
        _artifact("video", video_path),
        _artifact("log", log_path),
    ]
    response = OfflineBenchmarkResponse(
        status=status,
        speech_id=request.speech_id,
        run_id=run_id,
        data_root=str(data_root),
        run_dir=str(run_dir),
        dependencies=dependencies,
        artifacts=[_artifact("manifest", manifest_path), *artifacts],
        metrics=metrics,
        warnings=warnings,
        errors=errors,
    )
    manifest_path.write_text(json.dumps(response.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8")
    return response.model_copy(update={"artifacts": [_artifact("manifest", manifest_path), *artifacts]})
