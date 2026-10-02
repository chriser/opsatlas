"""Locked final evaluation and audio-driven portrait generation, without test motion inputs."""

import argparse
import json
import subprocess
import time
from pathlib import Path

import numpy as np
import torch

from experiments.local_avatar.appearance import AppearanceMLP, digest
from experiments.local_avatar.appearance_evaluate import encode, portrait_renderer, predictions
from experiments.local_avatar.speech_motion import SpeechMouthNet, frozen_data, history_features, mouth_measures


def predict_motion(model, artifact, audio_features, rms):
    inputs = (audio_features - artifact["input_mean"]) / artifact["input_std"]
    activity = ((rms - artifact["rms_low"]) / (artifact["rms_high"] - artifact["rms_low"]).clamp_min(1e-5)).clamp(0, 1)
    output = {
        "neural": model(inputs[None])[0],
        "ridge": history_features(inputs) @ artifact["ridge"],
        "amplitude_rule": torch.stack((activity, torch.ones_like(activity)), 1) @ artifact["rule"],
        "closed": artifact["closed"].expand(len(inputs), -1),
        "mean": torch.zeros(len(inputs), 6),
    }
    return {name: ((coefficients.clamp(artifact["low"], artifact["high"]) * artifact["coefficient_std"]
                    + artifact["coefficient_mean"]) @ artifact["basis"].T + artifact["mouth_mean"])
            for name, coefficients in output.items()}


def motion_metrics(predicted, target, hop_seconds):
    predicted, target = predicted.numpy(), target.numpy()
    aperture, width = mouth_measures(predicted)
    true_aperture, true_width = mouth_measures(target)
    velocity, true_velocity = np.diff(predicted, axis=0) * 256 / hop_seconds, np.diff(target, axis=0) * 256 / hop_seconds
    return {"landmark_rmse_canonical_pixels": float(np.sqrt(np.mean((predicted - target) ** 2)) * 256),
            "aperture_mae_ratio": float(np.mean(np.abs(aperture - true_aperture))),
            "width_mae_canonical_pixels": float(np.mean(np.abs(width - true_width))),
            "velocity_rmse_canonical_pixels_per_second": float(np.sqrt(np.mean((velocity - true_velocity) ** 2))),
            "predicted_velocity_rms": float(np.sqrt(np.mean(velocity ** 2))),
            "target_velocity_rms": float(np.sqrt(np.mean(true_velocity ** 2)))}


def latest_indices(clock, output_clock):
    """Zero-order hold uses only an already available prediction, never future interpolation."""
    if len(clock) == 0 or output_clock.min() < clock[0]:
        raise ValueError("No available prediction at output start")
    return np.searchsorted(clock, output_clock, side="right") - 1


def add_rule_eyes(mouth, artifact, clock):
    time_since_start = clock - clock[0]
    blink = np.maximum(0, 1 - np.abs((time_since_start % 4) - 2) / .15)
    eyes = artifact["eyes_open"][None] * torch.from_numpy(1 - blink[:, None]).float()
    eyes += artifact["eyes_closed"][None] * torch.from_numpy(blink[:, None]).float()
    return torch.cat((mouth, eyes), 1)


def mux_audio(silent_video, waveform, output, source_start, offset, duration):
    audio_seek = source_start - offset
    if audio_seek < 0:
        raise ValueError("Preview starts before audio")
    command = ["ffmpeg", "-v", "error", "-i", str(silent_video), "-ss", f"{audio_seek:.6f}", "-t", f"{duration:.6f}",
               "-i", str(waveform), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
               "-movflags", "+faststart", "-shortest", "-y", str(output)]
    subprocess.run(command, check=True)


def evaluate(root, appearance, waveform, source):
    if (root / "evaluation.json").exists():
        raise ValueError("Final test already evaluated; preserve it")
    torch.set_num_threads(4)
    spec = json.loads((root / "split.json").read_text())
    data, manifest, masks = frozen_data(root)
    if digest(waveform) != manifest["audio_sha256"] or digest(source) != manifest["source_sha256"]:
        raise ValueError("Media changed after preparation")
    artifact = torch.load(root / "speech.pt", weights_only=True, map_location="cpu")
    for name in ("dataset_sha256", "split_sha256"):
        if artifact[name] != manifest[name]:
            raise ValueError("Checkpoint data mismatch")
    model = SpeechMouthNet().eval()
    model.load_state_dict(artifact["model"])
    selected = json.loads((root / "fit-report.json").read_text())["selected_predictor"]
    audio_features = torch.from_numpy(data["features"][masks["test"]])
    rms = torch.from_numpy(data["rms"][masks["test"]])
    targets = torch.from_numpy(data["geometry"][masks["test"], :40])
    clock = data["times"][masks["test"]]
    hop = spec["hop_samples"] / spec["sample_rate"]
    with torch.inference_mode():
        motion = predict_motion(model, artifact, audio_features, rms)
        metrics = {name: motion_metrics(value, targets, hop) for name, value in motion.items()}
        report = {"schema_version": 1, "test_frames": len(clock), "test_duration_seconds": len(clock) * hop,
                  "source_start_seconds": float(clock[0]), "selected_on_validation": selected, "test": metrics,
                  "condition": "audio only; no held-out mouth coordinates or RGB enter generated predictions",
                  "eye_behavior": "authored 4-second blink schedule using training-only eye templates, not learned from audio",
                  "evaluation_limit": spec["evaluation_limit"], "speech_checkpoint_sha256": digest(root / "speech.pt"),
                  "appearance_checkpoint_sha256": digest(appearance / "appearance.pt")}
        # Freeze test results before visual inspection, so subsequent work cannot tune this checkpoint to the test.
        (root / "evaluation.json").write_text(json.dumps(report, indent=2))
        image_artifact = torch.load(appearance / "appearance.pt", weights_only=True, map_location="cpu")
        image_model = AppearanceMLP().eval()
        image_model.load_state_dict(image_artifact["model"])
        output_clock = clock[0] + np.arange(360) / 30
        indices = latest_indices(clock, output_clock)
        if indices.max() >= len(clock):
            raise ValueError("Preview exceeds available predictions")
        render = portrait_renderer(appearance)
        shapes, images = {}, {}
        for name in dict.fromkeys(("neural", "ridge", "amplitude_rule", selected)):
            shapes[name] = add_rule_eyes(motion[name][indices], artifact, output_clock)
            images[name], _ = predictions(image_model, image_artifact, shapes[name])
        reference_shape = add_rule_eyes(targets[indices], artifact, output_clock)
        images["tracked_reference"], _ = predictions(image_model, image_artifact, reference_shape)
        encode((render(vector) for vector in images["neural"]), root / "neural-silent.mp4")
        encode((render(vector) for vector in images[selected]), root / "selected-silent.mp4")
        encode((torch.cat([render(images[name][index]) for name in
                          ("amplitude_rule", "ridge", "neural", "tracked_reference")], dim=2)
                for index in range(len(output_clock))), root / "comparison-silent.mp4")
        duration = len(output_clock) / 30
        for name in ("neural", "selected", "comparison"):
            mux_audio(root / f"{name}-silent.mp4", waveform, root / f"{name}.mp4", clock[0], spec["audio_offset_seconds"], duration)
        # Original reference clip with the same source interval and corrected useful audio channel.
        command = ["ffmpeg", "-v", "error", "-i", str(source), "-ss", f"{clock[0]:.6f}", "-t", str(duration),
                   "-map", "0:v:0", "-map", "0:a:0", "-vf", "fps=30,scale=792:594",
                   "-af", "pan=mono|c0=c0,volume=0.25894389847467847", "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                   "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-y", str(root / "source-reference.mp4")]
        subprocess.run(command, check=True)
        # Timings include CPU causal mouth model and geometric decoding, not appearance or transport.
        sample = audio_features[:29]
        sample_rms = rms[:29]
        for _ in range(20):
            predict_motion(model, artifact, sample, sample_rms)
        timing = []
        for _ in range(200):
            started = time.perf_counter()
            predict_motion(model, artifact, sample, sample_rms)
            timing.append((time.perf_counter() - started) * 1000)
        report["cpu_inference"] = {"p50_ms": float(np.percentile(timing, 50)), "p95_ms": float(np.percentile(timing, 95)),
                                   "samples": 200, "context_frames": 29,
                                   "scope": "all five motion predictors and mouth geometry; excludes audio features/appearance/compositing"}
        report["display"] = {"fps": 30, "frames": len(output_clock), "duration_seconds": duration,
                             "source_start_seconds": float(clock[0]),
                             "audio_waveform_seek_seconds": float(clock[0] - spec["audio_offset_seconds"]),
                             "motion_resampling": "latest available 50 Hz prediction; no future interpolation",
                             "startup_history": "zero padding at test-section start; 560 ms receptive history"}
    trace = {"source_seconds": clock.tolist(), "target_aperture": mouth_measures(targets.numpy())[0].tolist(),
             "predicted_aperture": {name: mouth_measures(value.numpy())[0].tolist() for name, value in motion.items()},
             "audio_rms": rms.tolist()}
    (root / "evaluation-trace.json").write_text(json.dumps(trace))
    (root / "evaluation.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if "sha256" not in k}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".runtime/local-avatar/speech-v1"))
    parser.add_argument("--appearance", type=Path, default=Path(".runtime/local-avatar/appearance"))
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    evaluate(args.output, args.appearance, args.audio, args.source)


if __name__ == "__main__":
    main()
