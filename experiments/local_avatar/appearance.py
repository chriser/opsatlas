"""Restricted, landmark-conditioned appearance learning. No speech model or source replay.

PCA learns a compact RGB decoder from training patches only. A randomly initialized
MLP learns landmark -> decoder coefficients. Ridge and mean predictors are controls.
Personal frames, coordinates, split manifests and checkpoints stay in ignored storage.
"""

import argparse
import copy
import hashlib
import json
import re
import resource
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

REGIONS = ((56, 120, 200, 216, 96, 64), (40, 48, 216, 112, 128, 48))
PATCH_SIZE = sum(w * h * 3 for _, _, _, _, w, h in REGIONS)
GROUPS = ("outer_lips", "inner_lips", "left_eye", "right_eye")
COUNTS = (14, 6, 6, 6)


def partition(times, spec):
    """Half-open, separated intervals; excluded samples can never enter a split."""
    masks = {}
    allowed = np.ones(len(times), dtype=bool)
    for start, stop in spec["excluded"]:
        allowed &= ~((times >= start) & (times < stop))
    spans = [spec[name] for name in ("train", "validation", "test")]
    if any(a >= b for a, b in spans) or not (spans[0][1] < spans[1][0] and spans[1][1] < spans[2][0]):
        raise ValueError("Require ordered, separated contiguous splits")
    for name, (start, stop) in zip(("train", "validation", "test"), spans):
        masks[name] = allowed & (times >= start) & (times < stop)
    return masks


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pixels(face, width, height):
    x, y, w, h = face["bbox"]
    groups = {}
    for name, count in zip(GROUPS, COUNTS):
        points = np.asarray(face[name], dtype=np.float32)
        if points.shape != (count, 2):
            raise ValueError("Incomplete landmarks")
        groups[name] = np.column_stack(((x + points[:, 0] * w) * width, (1 - y - points[:, 1] * h) * height))
    eyes = sorted((groups["left_eye"].mean(0), groups["right_eye"].mean(0)), key=lambda p: p[0])
    origin = (eyes[0] + eyes[1]) / 2
    axis = (eyes[1] - eyes[0]) / 96
    matrix = np.stack((axis, [-axis[1], axis[0]]), axis=1)
    if np.linalg.norm(axis) < .2:
        raise ValueError("Face too small")
    inverse = np.linalg.inv(matrix)
    features = np.concatenate([(points - origin) @ inverse.T + [128, 80] for points in groups.values()]).reshape(-1) / 256
    return features.astype(np.float32), origin.astype(np.float32), matrix.astype(np.float32)


def canonical(image, origin, matrix):
    """Similarity alignment to fixed eye centers, with correct Vision y inversion."""
    height, width = image.shape[:2]
    y, x = torch.meshgrid(torch.arange(256), torch.arange(256), indexing="ij")
    coordinates = torch.stack((x - 128, y - 80), -1).float() @ torch.from_numpy(matrix).T + torch.from_numpy(origin)
    grid = coordinates * torch.tensor([2 / (width - 1), 2 / (height - 1)]) - 1
    source = torch.from_numpy(image.copy()).permute(2, 0, 1).float()[None] / 255
    return F.grid_sample(source, grid[None], align_corners=True, padding_mode="border")[0]


def pack(face):
    return torch.cat([F.interpolate(face[None, :, top:bottom, left:right], size=(h, w), mode="bilinear", align_corners=False).flatten()
                      for left, top, right, bottom, w, h in REGIONS])


def unpack(vector):
    result = torch.zeros(3, 256, 256)
    offset = 0
    for left, top, right, bottom, w, h in REGIONS:
        count = 3 * w * h
        patch = vector[offset:offset + count].reshape(1, 3, h, w)
        result[:, top:bottom, left:right] = F.interpolate(patch, size=(bottom - top, right - left), mode="bilinear", align_corners=False)[0]
        offset += count
    return result


def alpha_mask():
    y, x = torch.meshgrid(torch.arange(256), torch.arange(256), indexing="ij")
    mask = torch.zeros(256, 256)
    for cx, cy, rx, ry in ((128, 165, 68, 43), (80, 80, 35, 23), (176, 80, 35, 23)):
        radius = torch.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2)
        mask = torch.maximum(mask, ((1 - radius) / .25).clamp(0, 1))
    return mask


def composite(portrait, patch, origin, matrix):
    height, width = portrait.shape[:2]
    y, x = torch.meshgrid(torch.arange(height), torch.arange(width), indexing="ij")
    coordinates = (torch.stack((x, y), -1).float() - torch.from_numpy(origin)) @ torch.from_numpy(np.linalg.inv(matrix)).T
    coordinates += torch.tensor([128, 80])
    grid = coordinates / 127.5 - 1
    alpha = alpha_mask()[None]
    # Warp premultiplied color to avoid black edges around feathered regions.
    warped = F.grid_sample(torch.cat((unpack(patch) * alpha, alpha), 0)[None], grid[None], align_corners=True)[0]
    base = torch.from_numpy(portrait.copy()).permute(2, 0, 1).float() / 255
    return (base * (1 - warped[3:]) + warped[:3]).clamp(0, 1)


def raw_image(path, width, height):
    data = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    return np.frombuffer(data, dtype=np.uint8).reshape(height, width, 3)


def prepare(args):
    root = args.output
    root.mkdir(parents=True, exist_ok=True)
    spec = json.loads((root / "split.json").read_text())  # Must be frozen before extraction/fitting.
    if (root / "dataset-manifest.json").exists():
        raise ValueError("Prepared data is frozen; use a new experiment directory")
    frame_dir = root / "frames"
    frame_dir.mkdir(exist_ok=True)
    if list(frame_dir.glob("frame-*.jpg")):
        raise ValueError("Use an empty frames directory for verified source extraction")
    interval = spec["sample_interval_seconds"]
    if type(interval) not in (int, float) or not .1 <= interval <= 2:
        raise ValueError("Invalid sampling interval")
    with (root / "frame-extraction.log").open("w") as stream:
        command = ["ffmpeg", "-hide_banner", "-nostats", "-i", str(args.source), "-an", "-vf",
                   f"select='isnan(prev_selected_t)+gte(t-prev_selected_t,{interval})',scale=792:594,showinfo",
                   "-fps_mode", "vfr", "-q:v", "2", "-y", str(frame_dir / "frame-%04d.jpg")]
        subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=True)
    times = np.array([float(t) for t in re.findall(r"\bn:\s*\d+.*?pts_time:([\d.]+)", (root / "frame-extraction.log").read_text())])
    frames = sorted((root / "frames").glob("frame-*.jpg"))
    if len(times) != len(frames) or len(times) < 10 or np.any(np.diff(times) <= 0):
        raise ValueError("Frame timestamps/count mismatch")
    tracker = Path(__file__).with_name("track_faces.swift")
    cache = root.parent / "swift-module-cache"
    with (root / "landmarks.json").open("w") as stream:
        subprocess.run(["swift", "-module-cache-path", str(cache), str(tracker), str(root / "frames")], stdout=stream, check=True)
    reference_dir = root / "portrait"
    reference_dir.mkdir(exist_ok=True)
    shutil.copyfile(args.reference, reference_dir / "reference.png")
    with (root / "portrait-landmarks.json").open("w") as stream:
        subprocess.run(["swift", "-module-cache-path", str(cache), str(tracker), str(reference_dir)], stdout=stream, check=True)
    records = json.loads((root / "landmarks.json").read_text())["records"]
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(root / "frames/frame-%04d.jpg"),
                                   "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    images = np.frombuffer(raw, dtype=np.uint8).reshape(len(frames), 594, 792, 3)
    masks = partition(times, spec)
    if any(mask.sum() < minimum for mask, minimum in zip(masks.values(), (64, 10, 10))):
        raise ValueError("Insufficient frames in one or more frozen sections")
    selected = masks["train"] | masks["validation"] | masks["test"]
    features, patches, accepted_times, rejected = [], [], [], []
    torch.set_num_threads(4)
    for index, (frame, record) in enumerate(zip(frames, records)):
        if frame.name != record["frame"]:
            raise ValueError("Tracker order mismatch")
        if not selected[index]:
            continue
        try:
            if len(record.get("faces", [])) != 1 or record["faces"][0]["confidence"] < .8:
                raise ValueError("Face count/confidence")
            feature, origin, matrix = pixels(record["faces"][0], 792, 594)
            patches.append(pack(canonical(images[index], origin, matrix)).numpy())
            features.append(feature)
            accepted_times.append(times[index])
        except (ValueError, KeyError) as exc:
            rejected.append({"timestamp": times[index], "reason": str(exc)})
    np.savez_compressed(root / "dataset.npz", features=np.stack(features), patches=np.stack(patches), times=accepted_times)
    accepted_masks = partition(np.array(accepted_times), spec)
    if any(mask.sum() < minimum for mask, minimum in zip(accepted_masks.values(), (64, 10, 10))):
        raise ValueError("Insufficient accepted faces in one or more sections")
    manifest = {"schema_version": 1, "source_sha256": digest(args.source), "reference_sha256": digest(args.reference),
                "dataset_sha256": digest(root / "dataset.npz"), "split_sha256": digest(root / "split.json"),
                "source": spec["provenance"], "tracker": "pretrained Apple Vision revision 3", "rejected": rejected,
                "counts": {name: int(mask.sum()) for name, mask in accepted_masks.items()},
                "features": "64 similarity-aligned outer lip, inner lip and eye coordinates; not the twelve authored rig controls",
                "rgb_targets": "96x64 mouth plus 128x48 combined eyes, source decoded to RGB24"}
    (root / "dataset-manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps({"prepared": manifest["counts"], "rejected": len(rejected)}), flush=True)


class AppearanceMLP(nn.Module):
    def __init__(self, inputs=64, coefficients=48):
        super().__init__()
        self.network = nn.Sequential(nn.Linear(inputs, 128), nn.SiLU(), nn.Linear(128, 128), nn.SiLU(), nn.Linear(128, coefficients))

    def forward(self, controls):
        return self.network(controls)


def normalization(training):
    return training.mean(0), training.std(0).clamp_min(.005)


def fit(args):
    root = args.output
    if (root / "evaluation.json").exists():
        raise ValueError("Test already evaluated; start a new experiment instead of refitting this checkpoint")
    manifest = json.loads((root / "dataset-manifest.json").read_text())
    for name, filename in (("dataset", "dataset.npz"), ("split", "split.json")):
        if digest(root / filename) != manifest[name + "_sha256"]:
            raise ValueError("Frozen data changed")
    data = np.load(root / "dataset.npz")
    masks = partition(data["times"], json.loads((root / "split.json").read_text()))
    # Only training/validation arrays enter this function's fitted statistics/model selection.
    x, y = torch.from_numpy(data["features"][masks["train"]]), torch.from_numpy(data["patches"][masks["train"]])
    vx, vy = torch.from_numpy(data["features"][masks["validation"]]), torch.from_numpy(data["patches"][masks["validation"]])
    del data
    torch.manual_seed(41)
    torch.set_num_threads(4)
    started = time.perf_counter()
    xm, xs = normalization(x)
    x, vx = (x - xm) / xs, (vx - xm) / xs
    mean = y.mean(0)
    _, _, basis = torch.pca_lowrank(y - mean, q=48, center=False, niter=4)
    z = (y - mean) @ basis
    zm, zs = z.mean(0), z.std(0).clamp_min(.01)
    target = (z - zm) / zs
    vx1, x1 = torch.cat((vx, torch.ones(len(vx), 1)), 1), torch.cat((x, torch.ones(len(x), 1)), 1)
    ridge_candidates = []
    for regularization in (.1, 1., 10., 100.):
        penalty = torch.eye(x1.shape[1]) * regularization
        penalty[-1, -1] = 0
        weights = torch.linalg.solve(x1.T @ x1 + penalty, x1.T @ target)
        prediction = ((vx1 @ weights) * zs + zm) @ basis.T + mean
        ridge_candidates.append((float(F.mse_loss(prediction, vy)), regularization, weights))
    ridge_loss, ridge_alpha, ridge = min(ridge_candidates, key=lambda item: item[0])
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model = AppearanceMLP(x.shape[1], basis.shape[1]).to(device)
    initial = copy.deepcopy(model.cpu().state_dict())
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=.01)
    dx, dz, dvx = x.to(device), target.to(device), vx.to(device)
    d_vy, d_basis, d_mean, d_zm, d_zs = (t.to(device) for t in (vy, basis, mean, zm, zs))
    best_loss, best_epoch, best_state = float("inf"), 0, None
    history = []
    for epoch in range(1, args.epochs + 1):
        model.train()
        for indices in torch.randperm(len(x)).split(64):
            optimizer.zero_grad(set_to_none=True)
            loss = F.mse_loss(model(dx[indices.to(device)]), dz[indices.to(device)])
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5)
            optimizer.step()
        if epoch % 10 == 0:
            model.eval()
            with torch.inference_mode():
                prediction = (model(dvx) * d_zs + d_zm) @ d_basis.T + d_mean
                validation = float(F.mse_loss(prediction, d_vy).cpu())
            history.append({"epoch": epoch, "validation_mse": validation})
            if validation < best_loss:
                best_loss, best_epoch = validation, epoch
                best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
            if epoch % 100 == 0:
                print(json.dumps({"epoch": epoch, "best_validation_mse": best_loss}), flush=True)
    model.cpu()
    updated = any(not torch.equal(initial[key], value) for key, value in best_state.items())
    artifact = {"model": best_state, "input_mean": xm, "input_std": xs, "pixel_mean": mean,
                "basis": basis, "coefficient_mean": zm, "coefficient_std": zs, "ridge": ridge,
                "dataset_sha256": manifest["dataset_sha256"], "split_sha256": manifest["split_sha256"]}
    torch.save(artifact, root / "appearance.pt")
    report = {"schema_version": 1, "device": device, "training_seconds": time.perf_counter() - started,
              "epochs": args.epochs, "selected_epoch": best_epoch, "parameters": sum(p.numel() for p in model.parameters()),
              "parameters_updated": updated,
              "validation_mse": {"mlp": best_loss, "ridge": ridge_loss, "mean": float(F.mse_loss(mean.expand_as(vy), vy))},
              "ridge_regularization": ridge_alpha, "history": history, "checkpoint_bytes": (root / "appearance.pt").stat().st_size,
              "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "mps_driver_allocated_bytes": torch.mps.driver_allocated_memory() if device == "mps" else None,
              "selection": "validation RGB MSE only; test untouched until separate evaluation",
              "weights": "random-initialized own MLP, training-only PCA decoder and ridge; pretrained OS tracker reused"}
    (root / "fit-report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "history"}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "fit"))
    parser.add_argument("--output", type=Path, default=Path(".runtime/local-avatar/appearance"))
    parser.add_argument("--source", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--epochs", type=int, default=500)
    args = parser.parse_args()
    if args.command == "prepare":
        if args.source is None or args.reference is None:
            parser.error("prepare needs source and reference")
        prepare(args)
    else:
        if args.epochs < 10:
            parser.error("fit needs at least 10 epochs")
        fit(args)


if __name__ == "__main__":
    main()
