"""One final held-out appearance evaluation and private portrait previews.

Conditioning uses measured test landmarks, not test pixels. This is rendering
evaluation, not autonomous speech animation. Authored motion uses training-only
landmark templates interpolated into new trajectories, never source RGB replay.
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

from experiments.local_avatar.appearance import (
    REGIONS,
    AppearanceMLP,
    alpha_mask,
    digest,
    partition,
    pixels,
    raw_image,
    unpack,
)


def predictions(model, artifact, features):
    normalized = (features - artifact["input_mean"]) / artifact["input_std"]
    coefficients = model(normalized) * artifact["coefficient_std"] + artifact["coefficient_mean"]
    neural = coefficients @ artifact["basis"].T + artifact["pixel_mean"]
    augmented = torch.cat((normalized, torch.ones(len(normalized), 1)), 1)
    linear = (augmented @ artifact["ridge"] * artifact["coefficient_std"] + artifact["coefficient_mean"])
    linear = linear @ artifact["basis"].T + artifact["pixel_mean"]
    return neural.clamp(0, 1), linear.clamp(0, 1)


def metrics(predicted, expected):
    mse = float(F.mse_loss(predicted, expected))
    offset, regions = 0, {}
    for name, (_, _, _, _, width, height) in zip(("mouth", "eyes"), REGIONS):
        count = 3 * width * height
        regions[name] = float(F.mse_loss(predicted[:, offset:offset + count], expected[:, offset:offset + count]))
        offset += count
    return {"mse": mse, "psnr_db": float(-10 * np.log10(max(mse, 1e-12))), "region_mse": regions}


def resample(times, features, fps=30):
    clock = np.arange(times[0], times[-1] + 1e-6, 1 / fps)
    values = np.stack([np.interp(clock, times, features[:, column]) for column in range(features.shape[1])], axis=1)
    return clock, torch.from_numpy(values).float()


def authored_motion(training, fps=30):
    shape = training.reshape(-1, 32, 2)
    aperture = np.ptp(shape[:, 14:20, 1], axis=1)
    blink = np.ptp(shape[:, 20:26, 1], axis=1) + np.ptp(shape[:, 26:32, 1], axis=1)
    closed, opened, blinking = (training[index].copy() for index in (aperture.argmin(), aperture.argmax(), blink.argmin()))
    controls = []
    for frame in range(fps * 6):
        t = frame / fps
        mouth = (1 - np.cos(2 * np.pi * t / 2)) / 2
        vector = closed * (1 - mouth) + opened * mouth
        eye_weight = max(0, 1 - abs((t % 2) - 1) / .17)
        vector[40:] = vector[40:] * (1 - eye_weight) + blinking[40:] * eye_weight
        controls.append(vector)
    return torch.from_numpy(np.stack(controls)).float()


def portrait_renderer(root):
    original = raw_image(root / "portrait/reference.png", 1122, 1402)
    face = json.loads((root / "portrait-landmarks.json").read_text())["records"][0]["faces"]
    if len(face) != 1:
        raise ValueError("Need exactly one portrait face")
    _, origin, matrix = pixels(face[0], 1122, 1402)
    width, height = 560, 700
    scale = np.array([width / 1122, height / 1402], dtype=np.float32)
    origin, matrix = origin * scale, matrix * scale[:, None]
    y, x = torch.meshgrid(torch.arange(height), torch.arange(width), indexing="ij")
    coordinates = (torch.stack((x, y), -1).float() - torch.from_numpy(origin)) @ torch.from_numpy(np.linalg.inv(matrix)).T
    grid = ((coordinates + torch.tensor([128, 80])) / 127.5 - 1)[None]
    base = F.interpolate(torch.from_numpy(original.copy()).permute(2, 0, 1)[None].float() / 255,
                         size=(height, width), mode="area")[0]
    alpha = alpha_mask()[None]

    def render(vector):
        warped = F.grid_sample(torch.cat((unpack(vector) * alpha, alpha), 0)[None], grid, align_corners=True)[0]
        return (base * (1 - warped[3:]) + warped[:3]).clamp(0, 1)

    return render


def encode(frames, path, fps=30):
    import subprocess

    first = next(frames)
    height, width = first.shape[1:]
    command = ["ffmpeg", "-v", "error", "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", f"{width}x{height}",
               "-framerate", str(fps), "-i", "-", "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-y", str(path)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    try:
        for frame in (first,):
            process.stdin.write((frame.permute(1, 2, 0) * 255).round().byte().numpy().tobytes())
        for frame in frames:
            process.stdin.write((frame.permute(1, 2, 0) * 255).round().byte().numpy().tobytes())
    finally:
        process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError("Video encoding failed")


def evaluate(root):
    if (root / "evaluation.json").exists():
        raise ValueError("Final test already evaluated; preserve result and use a new experiment directory for further work")
    torch.set_num_threads(4)
    artifact = torch.load(root / "appearance.pt", weights_only=True, map_location="cpu")
    for name, filename in (("dataset", "dataset.npz"), ("split", "split.json")):
        if digest(root / filename) != artifact[name + "_sha256"]:
            raise ValueError("Frozen artifact mismatch")
    data = np.load(root / "dataset.npz")
    masks = partition(data["times"], json.loads((root / "split.json").read_text()))
    features = torch.from_numpy(data["features"][masks["test"]])
    targets = torch.from_numpy(data["patches"][masks["test"]])
    model = AppearanceMLP().eval()
    model.load_state_dict(artifact["model"])
    with torch.inference_mode():
        neural, linear = predictions(model, artifact, features)
        mean = artifact["pixel_mean"].expand_as(targets)
        report = {"schema_version": 1, "test_frames": len(features), "test": {
            "neural": metrics(neural, targets), "ridge": metrics(linear, targets), "mean": metrics(mean, targets)},
            "conditioning": "held-out measured lip and eye landmarks; no test pixels enter predictions",
            "generalization_limit": "one synthetic recording, separated time sections; not an independent camera/session test"}
        # Lock the quantitative result before visual inspection; no test-guided retraining.
        (root / "evaluation.json").write_text(json.dumps(report, indent=2))
        _, test_motion = resample(data["times"][masks["test"]], features.numpy())
        test_neural, test_linear = predictions(model, artifact, test_motion)
        authored = authored_motion(data["features"][masks["train"]])
        authored_neural, _ = predictions(model, artifact, authored)
        render = portrait_renderer(root)
        encode((render(vector) for vector in test_neural), root / "heldout.mp4")
        encode((render(vector) for vector in authored_neural), root / "authored.mp4")
        # Mean | linear | neural | held-out source patches, all on the same supplied portrait.
        encode((torch.cat([render(v) for v in (mean[i], linear[i], neural[i], targets[i])], dim=2)
                for i in range(len(targets))), root / "comparison.mp4", fps=5)
        for _ in range(25):
            predictions(model, artifact, features[:1])
        elapsed = []
        for _ in range(200):
            started = time.perf_counter()
            predictions(model, artifact, features[:1])
            elapsed.append((time.perf_counter() - started) * 1000)
        report["cpu_inference"] = {"samples": 200, "batch": 1, "p50_ms": float(np.percentile(elapsed, 50)),
                                   "p95_ms": float(np.percentile(elapsed, 95)),
                                   "scope": "neural plus ridge RGB patch prediction, excludes tracking, compositing and video encoding"}
        composite_elapsed = []
        for vector in authored_neural[:100]:
            started = time.perf_counter()
            render(vector)
            composite_elapsed.append((time.perf_counter() - started) * 1000)
        report["cpu_composite"] = {"p50_ms": float(np.percentile(composite_elapsed, 50)),
                                   "p95_ms": float(np.percentile(composite_elapsed, 95)), "resolution": [560, 700]}
    (root / "evaluation.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".runtime/local-avatar/appearance"))
    evaluate(parser.parse_args().output)


if __name__ == "__main__":
    main()
