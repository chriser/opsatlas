"""Local diagnostic: causal log-mel audio -> six learned mouth-shape components.

This does not label jaw angle, recover all rig controls or learn blink behavior.
Use original media timestamps. Training/validation statistics never use test rows.
"""

import argparse
import copy
import json
import re
import subprocess
import time
import wave
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from experiments.local_avatar.appearance import digest, partition, pixels
from experiments.local_avatar.benchmark import memory


def extract(root, source):
    if (root / "dataset-manifest.json").exists():
        raise ValueError("Dataset frozen; use a fresh experiment directory")
    spec = json.loads((root / "split.json").read_text())
    frames = root / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    if list(frames.iterdir()):
        raise ValueError("Use an empty frames directory")
    with (root / "frame-extraction.log").open("w") as stream:
        subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(source), "-an", "-vf",
                        "select='isnan(prev_selected_t)+gte(t-prev_selected_t,0.04)',scale=528:396,showinfo",
                        "-fps_mode", "vfr", "-q:v", "3", "-y", str(frames / "frame-%04d.jpg")],
                       stdout=stream, stderr=subprocess.STDOUT, check=True)
    with (root / "landmarks.json").open("w") as stream:
        subprocess.run(["swift", "-module-cache-path", str(root.parent / "swift-module-cache"),
                        str(Path(__file__).with_name("track_faces.swift")), str(frames)], stdout=stream, check=True)
    metadata = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=start_time", "-of", "json", str(source)]))
    offset = float(metadata["streams"][0]["start_time"])
    if abs(offset - spec["audio_offset_seconds"]) > 1e-5:
        raise ValueError("Frozen audio offset differs from source; correct metadata in a fresh experiment")
    manifest = {"source_sha256": digest(source), "log_sha256": digest(root / "frame-extraction.log"),
                "landmarks_sha256": digest(root / "landmarks.json"), "audio_offset_seconds": offset,
                "tracker": "Apple Vision revision 3", "source_integrity_rechecked": True}
    (root / "extraction-manifest.json").write_text(json.dumps(manifest, indent=2))
    print("Private timestamped landmark extraction complete.", flush=True)


def read_wave(path, sample_rate):
    with wave.open(str(path), "rb") as stream:
        if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) != (1, 2, sample_rate):
            raise ValueError("Expected mono signed PCM16 at the frozen sample rate")
        return np.frombuffer(stream.readframes(stream.getnframes()), dtype="<i2").astype(np.float32) / 32768


def mel_filter(sample_rate=16000, fft_size=512, bins=80):
    frequencies = torch.linspace(0, sample_rate / 2, fft_size // 2 + 1)
    maximum = 2595 * np.log10(1 + sample_rate / 2 / 700)
    points = 700 * (10 ** (torch.linspace(0, float(maximum), bins + 2) / 2595) - 1)
    left = (frequencies[:, None] - points[:-2]) / (points[1:-1] - points[:-2])
    right = (points[2:] - frequencies[:, None]) / (points[2:] - points[1:-1])
    return torch.minimum(left, right).clamp_min(0)


def audio_features(samples, spec):
    """Each 25 ms window ends at its output clock; no centered/future samples."""
    waveform = torch.from_numpy(samples)
    window, hop = spec["window_samples"], spec["hop_samples"]
    windows = F.pad(waveform, (window - 1, 0)).unfold(0, window, hop)
    spectrum = torch.fft.rfft(windows * torch.hann_window(window), n=spec["fft_size"]).abs().square()
    filters = mel_filter(spec["sample_rate"], spec["fft_size"], spec["mel_bins"])
    features = torch.log10((spectrum @ filters).clamp_min(1e-8)).numpy()
    rms = windows.square().mean(-1).sqrt().numpy()
    times = spec["audio_offset_seconds"] + np.arange(len(features)) * hop / spec["sample_rate"]
    return times, features, rms


def mouth_measures(vectors):
    shape = np.asarray(vectors).reshape(-1, 20, 2)
    width = np.ptp(shape[:, :14, 0], axis=1)
    aperture = np.ptp(shape[:, 14:, 1], axis=1) / np.maximum(width, 1e-6)
    return aperture, width * 256


def interpolate_labels(times, landmarks, wanted, maximum_gap=.15):
    indices = np.searchsorted(times, wanted, side="right")
    before, after = np.clip(indices - 1, 0, len(times) - 1), np.clip(indices, 0, len(times) - 1)
    valid = (wanted >= times[0]) & (wanted <= times[-1]) & ((times[after] - times[before]) <= maximum_gap)
    values = np.stack([np.interp(wanted, times, landmarks[:, column]) for column in range(landmarks.shape[1])], axis=1)
    return values.astype(np.float32), valid


def prepare(root, source, audio):
    if (root / "dataset-manifest.json").exists():
        raise ValueError("Dataset frozen; use a fresh experiment directory")
    torch.set_num_threads(4)
    spec = json.loads((root / "split.json").read_text())
    extraction = json.loads((root / "extraction-manifest.json").read_text())
    if digest(source) != extraction["source_sha256"]:
        raise ValueError("Source differs from the verified extraction")
    for key, filename in (("log_sha256", "frame-extraction.log"), ("landmarks_sha256", "landmarks.json")):
        if digest(root / filename) != extraction[key]:
            raise ValueError("Extracted landmarks/timestamps changed")
    if abs(spec["audio_offset_seconds"] - extraction["audio_offset_seconds"]) > 1e-5:
        raise ValueError("Audio clock differs from frozen extraction")
    times = np.array([float(t) for t in re.findall(r"\bn:\s*\d+.*?pts_time:([\d.]+)",
                                                 (root / "frame-extraction.log").read_text())])
    records = json.loads((root / "landmarks.json").read_text())["records"]
    if len(times) != len(records) or np.any(np.diff(times) <= 0):
        raise ValueError("Tracker/timestamp mismatch")
    accepted, geometry, rejected = [], [], []
    for index, (t, record) in enumerate(zip(times, records)):
        if record["frame"] != f"frame-{index + 1:04d}.jpg":
            raise ValueError("Frame order mismatch")
        try:
            if len(record.get("faces", [])) != 1 or record["faces"][0]["confidence"] < .8:
                raise ValueError("Face count/confidence")
            vector, _, _ = pixels(record["faces"][0], 528, 396)
            accepted.append(t)
            geometry.append(vector)
        except (ValueError, KeyError):
            rejected.append(float(t))
    accepted, geometry = np.array(accepted), np.array(geometry)
    audio_times, features, rms = audio_features(read_wave(audio, spec["sample_rate"]), spec)
    labels, valid = interpolate_labels(accepted, geometry, audio_times)
    masks = partition(audio_times, spec)
    indices = np.concatenate([np.flatnonzero(mask & valid) for mask in masks.values()])
    # No missing/interpolated target gap is allowed inside a training sequence.
    for name, mask in masks.items():
        selected = np.flatnonzero(mask)
        if len(selected) < 100 or not valid[selected].all():
            raise ValueError(f"Incomplete or insufficient {name} labels")
    np.savez_compressed(root / "dataset.npz", times=audio_times[indices], features=features[indices],
                        rms=rms[indices], geometry=labels[indices])
    train = masks["train"] & valid
    aperture, widths = mouth_measures(labels[train, :40])
    energy = np.log10(rms[train].clip(1e-5))
    alignment = []
    for lag in np.arange(-.3, .301, .02):
        shifted, usable = interpolate_labels(accepted, geometry[:, :40], audio_times[train] + lag)
        shifted_aperture, _ = mouth_measures(shifted)
        correlation = float(np.corrcoef(energy[usable], shifted_aperture[usable])[0, 1])
        alignment.append({"mouth_lag_seconds": float(round(lag, 4)), "energy_aperture_correlation": correlation})
    best = max(alignment, key=lambda item: item["energy_aperture_correlation"])
    calibration = {"schema_version": 1, "accepted_landmark_frames": len(geometry), "rejected_frames": len(rejected),
                   "landmark_interval_p50_ms": float(np.median(np.diff(accepted)) * 1000),
                   "landmark_interval_p95_ms": float(np.percentile(np.diff(accepted), 95) * 1000),
                   "maximum_label_interpolation_gap_ms": 150, "audio_offset_seconds": spec["audio_offset_seconds"],
                   "train_aperture_range": [float(aperture.min()), float(aperture.max())],
                   "train_width_pixels_range": [float(widths.min()), float(widths.max())],
                   "alignment_train_only": alignment, "best_energy_correlation": best,
                   "timing_decision": "Retain container offset. Energy correlation is not phoneme alignment; no offset tuning on test.",
                   "recoverable_targets": "lip geometry, aperture ratio and width; not independent jaw/closure angles",
                   "perceived_phoneme_timing": "not yet Human validated"}
    manifest = {"schema_version": 1, "source_sha256": digest(source), "audio_sha256": digest(audio),
                "dataset_sha256": digest(root / "dataset.npz"), "split_sha256": digest(root / "split.json"),
                "provenance": "User-confirmed Anam synthetic recording, not camera motion ground truth",
                "tracker": "reused built-in pretrained Apple Vision revision 3",
                "counts": {name: int((mask & valid).sum()) for name, mask in masks.items()}}
    (root / "calibration.json").write_text(json.dumps(calibration, indent=2))
    (root / "dataset-manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps({"counts": manifest["counts"], "calibration": calibration}), flush=True)


class SpeechMouthNet(nn.Module):
    context_frames = 28

    def __init__(self, inputs=80, outputs=6):
        super().__init__()
        self.layers = nn.ModuleList([nn.Conv1d(inputs, 64, 5), nn.Conv1d(64, 64, 5, dilation=2),
                                     nn.Conv1d(64, 64, 5, dilation=4)])
        self.output = nn.Conv1d(64, outputs, 1)

    def forward(self, features):
        encoded = features.transpose(1, 2)
        for layer in self.layers:
            encoded = F.silu(layer(F.pad(encoded, (4 * layer.dilation[0], 0))))
        return self.output(encoded).transpose(1, 2)


def history_features(features):
    """Linear spectral baseline with current, 100/200/400 ms past context."""
    contexts = []
    for delay in (0, 5, 10, 20):
        contexts.append(F.pad(features, (0, 0, delay, 0))[:len(features)])
    return torch.cat((*contexts, torch.ones(len(features), 1)), 1)


def frozen_data(root):
    manifest = json.loads((root / "dataset-manifest.json").read_text())
    for name, filename in (("dataset", "dataset.npz"), ("split", "split.json")):
        if digest(root / filename) != manifest[name + "_sha256"]:
            raise ValueError("Frozen data changed")
    data = np.load(root / "dataset.npz")
    return data, manifest, partition(data["times"], json.loads((root / "split.json").read_text()))


def fit(root, epochs):
    if (root / "evaluation.json").exists():
        raise ValueError("Final test already evaluated; no refitting")
    torch.manual_seed(43)
    torch.set_num_threads(4)
    data, manifest, masks = frozen_data(root)
    x, y = (torch.from_numpy(data[name][masks["train"]]) for name in ("features", "geometry"))
    vx, vy = (torch.from_numpy(data[name][masks["validation"]]) for name in ("features", "geometry"))
    rms, vrms = (torch.from_numpy(data["rms"][masks[name]]) for name in ("train", "validation"))
    del data
    started = time.perf_counter()
    xm, xs = x.mean(0), x.std(0).clamp_min(.1)
    x, vx = (x - xm) / xs, (vx - xm) / xs
    mouth_mean = y[:, :40].mean(0)
    _, _, basis = torch.pca_lowrank(y[:, :40] - mouth_mean, q=6, center=False, niter=4)
    coefficients = (y[:, :40] - mouth_mean) @ basis
    cm, cs = coefficients.mean(0), coefficients.std(0).clamp_min(.0001)
    z, vz = (coefficients - cm) / cs, ((vy[:, :40] - mouth_mean) @ basis - cm) / cs
    low, high = z.min(0).values, z.max(0).values
    train_history, validation_history = history_features(x), history_features(vx)
    candidates = []
    for alpha in (1., 10., 100., 1000.):
        penalty = torch.eye(train_history.shape[1]) * alpha
        penalty[-1, -1] = 0
        ridge = torch.linalg.solve(train_history.T @ train_history + penalty, train_history.T @ z)
        error = float(F.mse_loss((validation_history @ ridge).clamp(low, high), vz))
        candidates.append((error, alpha, ridge))
    ridge_error, ridge_alpha, ridge = min(candidates, key=lambda item: item[0])
    # Simple amplitude rule fitted on training only: open more as RMS energy rises.
    rms_low, rms_high = torch.quantile(rms, .1), torch.quantile(rms, .9)
    activity = ((rms - rms_low) / (rms_high - rms_low).clamp_min(1e-5)).clamp(0, 1)
    rule_x = torch.stack((activity, torch.ones_like(activity)), 1)
    rule = torch.linalg.lstsq(rule_x, z).solution
    val_activity = ((vrms - rms_low) / (rms_high - rms_low).clamp_min(1e-5)).clamp(0, 1)
    rule_error = float(F.mse_loss((torch.stack((val_activity, torch.ones_like(val_activity)), 1) @ rule).clamp(low, high), vz))
    aperture, _ = mouth_measures(y[:, :40].numpy())
    closed = z[np.argsort(aperture)[:max(1, len(aperture) // 20)]].mean(0)
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model = SpeechMouthNet().to(device)
    initial = copy.deepcopy(model.cpu().state_dict())
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=.01)
    dx, dz, dvx, dvz = (t[None].to(device) for t in (x, z, vx, vz))
    best_error, best_epoch, best_state = float("inf"), 0, None
    history = []
    for epoch in range(1, epochs + 1):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        predicted = model(dx)
        position = F.mse_loss(predicted, dz)
        velocity = F.mse_loss(predicted[:, 1:] - predicted[:, :-1], dz[:, 1:] - dz[:, :-1])
        loss = position + .1 * velocity
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 5, error_if_nonfinite=True)
        optimizer.step()
        if epoch % 10 == 0:
            model.eval()
            with torch.inference_mode():
                prediction = model(dvx)[0].cpu().clamp(low, high)
                error = float(F.mse_loss(prediction, dvz[0].cpu()))
            history.append({"epoch": epoch, "validation_mse": error, "training_loss": float(loss.detach().cpu())})
            if error < best_error:
                best_error, best_epoch = error, epoch
                best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            if epoch % 100 == 0:
                print(json.dumps({"epoch": epoch, "best_validation_mse": best_error}), flush=True)
    parameters_updated = any(not torch.equal(initial[k], value) for k, value in best_state.items())
    blink_sizes = np.ptp(y[:, 40:].reshape(-1, 12, 2).numpy()[:, :, 1], axis=1)
    artifact = {"model": best_state, "input_mean": xm, "input_std": xs, "mouth_mean": mouth_mean,
                "basis": basis, "coefficient_mean": cm, "coefficient_std": cs, "low": low, "high": high,
                "ridge": ridge, "rule": rule, "rms_low": rms_low, "rms_high": rms_high, "closed": closed,
                "eyes_open": y[:, 40:].median(0).values, "eyes_closed": y[int(blink_sizes.argmin()), 40:],
                "dataset_sha256": manifest["dataset_sha256"], "split_sha256": manifest["split_sha256"]}
    torch.save(artifact, root / "speech.pt")
    validation = {"neural": best_error, "ridge": ridge_error, "amplitude_rule": rule_error,
                  "mean": float(F.mse_loss(torch.zeros_like(vz), vz)), "closed": float(F.mse_loss(closed.expand_as(vz), vz))}
    report = {"schema_version": 1, "device": device, "training_seconds": time.perf_counter() - started,
              "parameters": sum(p.numel() for p in model.parameters()), "parameters_updated": parameters_updated,
              "epochs": epochs, "selected_epoch": best_epoch, "validation": validation, "ridge_alpha": ridge_alpha,
              "selected_predictor": min(validation, key=validation.get), "history": history,
              "checkpoint_bytes": (root / "speech.pt").stat().st_size, "memory": memory(device),
              "scope": "random-initialized causal audio model; six train-only mouth shape components; no learned eye/head controls"}
    (root / "fit-report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "history"}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("extract", "prepare", "fit"))
    parser.add_argument("--output", type=Path, default=Path(".runtime/local-avatar/speech-v1"))
    parser.add_argument("--source", type=Path)
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--epochs", type=int, default=500)
    args = parser.parse_args()
    if args.command == "extract":
        if args.source is None:
            parser.error("extract needs source")
        extract(args.output, args.source)
    elif args.command == "prepare":
        if args.source is None or args.audio is None:
            parser.error("prepare needs source and normalized audio")
        prepare(args.output, args.source, args.audio)
    else:
        if not 10 <= args.epochs <= 2000:
            parser.error("epochs must be 10..2000")
        fit(args.output, args.epochs)


if __name__ == "__main__":
    main()
