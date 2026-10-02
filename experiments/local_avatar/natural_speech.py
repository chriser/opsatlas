"""A/B-only natural speech experiment. No final-test access or appearance fitting."""

import argparse
import copy
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

from experiments.local_avatar.appearance import digest
from experiments.local_avatar.benchmark import memory
from experiments.local_avatar.camera_corpus import contiguous_runs, training_sessions, write_json
from experiments.local_avatar.speech_motion import SpeechMouthNet, history_features

CONFIG = {"seed": 47, "components": 8, "epochs": 120, "batch_size": 16, "chunk_frames": 160,
          "learning_rate": .0005, "weight_decay": .01, "validation_every": 5,
          "ridge_alphas": [1., 10., 100., 1000.], "velocity_weight": .1,
          "loss": "train-scaled centered coordinates + aperture + width; closure weights for aperture",
          "preview_session": "B", "preview_start_seconds": 60., "preview_duration_seconds": 12.,
          "test_access": False}


def centered_mouth(geometry):
    """Remove outer-lip translation; retain relative jaw/lip opening and shape."""
    mouth = geometry[..., :40].reshape(*geometry.shape[:-1], 20, 2)
    return (mouth - mouth[..., :14, :].mean(-2, keepdim=True)).flatten(-2)


def measures(mouth):
    points = mouth.reshape(*mouth.shape[:-1], 20, 2)
    width = points[..., :14, 0].amax(-1) - points[..., :14, 0].amin(-1)
    aperture = (points[..., 14:, 1].amax(-1) - points[..., 14:, 1].amin(-1)) / width.clamp_min(1e-4)
    return aperture, width


def scales(training):
    aperture, width = measures(training)
    return {"coordinates": training.var(0).mean().clamp_min(1e-6),
            "aperture": aperture.var().clamp_min(.0001), "width": width.var().clamp_min(1e-5),
            "closure": torch.quantile(aperture, .2)}


def shape_loss(prediction, target, normalizers, valid=None):
    pa, pw = measures(prediction)
    ta, tw = measures(target)
    mask = torch.ones_like(pa) if valid is None else valid.float()
    divisor = mask.sum().clamp_min(1)
    closure_weight = 1 + 2 * (ta < normalizers["closure"]).float()
    position = ((prediction - target).square().mean(-1) * mask).sum() / divisor / normalizers["coordinates"]
    aperture = ((pa - ta).square() * closure_weight * mask).sum() / (closure_weight * mask).sum().clamp_min(1)
    aperture = aperture / normalizers["aperture"]
    width = ((pw - tw).square() * mask).sum() / divisor / normalizers["width"]
    return position + aperture + width


def decode(coefficients, artifact, bound=True):
    if bound:
        coefficients = coefficients.clamp(artifact["low"], artifact["high"])
    return ((coefficients * artifact["coefficient_std"] + artifact["coefficient_mean"])
            @ artifact["basis"].T + artifact["mouth_mean"])


def chunks(inputs, targets, valid, frames=160, context=28):
    xs, ys, masks = [], [], []
    for left, right in contiguous_runs(valid):
        for start in range(left, right, frames):
            stop = min(start + frames, right)
            before = max(left, start - context)
            xs.append(F.pad(inputs[before:stop], (0, 0, context - (start - before), frames - (stop - start))))
            ys.append(F.pad(targets[start:stop], (0, 0, 0, frames - (stop - start))))
            masks.append(torch.arange(frames) < stop - start)
    if not xs:
        raise ValueError("No continuous training targets")
    return torch.stack(xs), torch.stack(ys), torch.stack(masks)


def predictors(model, artifact, features, rms):
    inputs = (features - artifact["input_mean"]) / artifact["input_std"]
    activity = ((rms - artifact["rms_low"]) / (artifact["rms_high"] - artifact["rms_low"]).clamp_min(1e-5)).clamp(0, 1)
    coefficients = {"neural": model(inputs[None])[0], "ridge": history_features(inputs) @ artifact["ridge"],
                    "amplitude_rule": torch.stack((activity, torch.ones_like(activity)), 1) @ artifact["rule"],
                    "mean": torch.zeros(len(inputs), CONFIG["components"]),
                    "closed": artifact["closed"].expand(len(inputs), -1)}
    return {name: decode(value, artifact) for name, value in coefficients.items()}


def metrics(prediction, target, valid, normalizers):
    pa, pw = measures(prediction)
    ta, tw = measures(target)
    differences = prediction - target
    consecutive = valid[1:] & valid[:-1]
    pv, tv = torch.diff(prediction, dim=0)[consecutive] * 256 / .02, torch.diff(target, dim=0)[consecutive] * 256 / .02
    return {"selection_score": float(shape_loss(prediction, target, normalizers, valid)),
            "centered_landmark_rmse_pixels": float(differences[valid].square().mean().sqrt() * 256),
            "aperture_mae_ratio": float((pa[valid] - ta[valid]).abs().mean()),
            "width_mae_pixels": float((pw[valid] - tw[valid]).abs().mean() * 256),
            "predicted_velocity_rms": float(pv.square().mean().sqrt()),
            "target_velocity_rms": float(tv.square().mean().sqrt())}


def freeze_plan(corpus, root):
    root.mkdir(parents=True, exist_ok=True)
    if (root / "plan.json").exists():
        raise ValueError("Experiment plan already frozen")
    training_sessions(corpus)  # Verifies A/B; never opens C.
    write_json(root / "plan.json", {"schema_version": 1, "config": CONFIG,
               "corpus_sha256": digest(corpus / "corpus.json"),
               "datasets": {name: digest(corpus / name / "dataset.npz") for name in ("A", "B")},
               "selection": "Minimum B train-scaled position/aperture/width loss; report static/amplitude/linear controls",
               "scope": "Eight centered mouth components; audio only; no learned head or blink behavior"})


def fit(corpus, root):
    if (root / "fit-report.json").exists() or (root / "speech.pt").exists():
        raise ValueError("Candidate already fitted; preserve it and use a fresh experiment for further B-only research")
    plan = json.loads((root / "plan.json").read_text())
    if plan["config"] != CONFIG or plan["corpus_sha256"] != digest(corpus / "corpus.json"):
        raise ValueError("Frozen experiment changed")
    if any(plan["datasets"][name] != digest(corpus / name / "dataset.npz") for name in ("A", "B")):
        raise ValueError("Frozen A/B dataset changed")
    data = training_sessions(corpus)
    torch.manual_seed(CONFIG["seed"])
    torch.set_num_threads(4)
    started = time.perf_counter()
    train, validation = data["train"], data["validation"]
    x, vx = (torch.from_numpy(d["features"]) for d in (train, validation))
    y, vy = (centered_mouth(torch.from_numpy(d["geometry"])) for d in (train, validation))
    mask, vmask = (torch.from_numpy(d["valid"]) for d in (train, validation))
    rms, vrms = (torch.from_numpy(d["rms"]) for d in (train, validation))
    xm, xs = x[mask].mean(0), x[mask].std(0).clamp_min(.1)
    x, vx = (x - xm) / xs, (vx - xm) / xs
    mean = y[mask].mean(0)
    _, singular, basis = torch.linalg.svd(y[mask] - mean, full_matrices=False)
    basis = basis[:CONFIG["components"]].T.contiguous()
    raw = (y[mask] - mean) @ basis
    cm, cs = raw.mean(0), raw.std(0).clamp_min(.0001)
    z = (raw - cm) / cs
    normalizers = scales(y[mask])
    artifact = {"input_mean": xm, "input_std": xs, "mouth_mean": mean, "basis": basis,
                "coefficient_mean": cm, "coefficient_std": cs,
                "low": torch.quantile(z, .001, dim=0), "high": torch.quantile(z, .999, dim=0),
                "normalizers": normalizers, "plan_sha256": digest(root / "plan.json")}
    # History is created inside each session, never by concatenating A and B.
    hx, hv = history_features(x), history_features(vx)
    candidates = []
    for alpha in CONFIG["ridge_alphas"]:
        penalty = torch.eye(hx.shape[1]) * alpha
        penalty[-1, -1] = 0
        ridge = torch.linalg.solve(hx[mask].T @ hx[mask] + penalty, hx[mask].T @ z)
        score = float(shape_loss(decode(hv @ ridge, artifact), vy, normalizers, vmask))
        candidates.append((score, alpha, ridge))
    _, ridge_alpha, artifact["ridge"] = min(candidates, key=lambda item: item[0])
    artifact["rms_low"], artifact["rms_high"] = torch.quantile(rms[mask], .1), torch.quantile(rms[mask], .9)
    activity = ((rms[mask] - artifact["rms_low"]) / (artifact["rms_high"] - artifact["rms_low"]).clamp_min(1e-5)).clamp(0, 1)
    artifact["rule"] = torch.linalg.lstsq(torch.stack((activity, torch.ones_like(activity)), 1), z).solution
    aperture, _ = measures(y[mask])
    closed = aperture <= torch.quantile(aperture, .05)
    artifact["closed"] = z[closed].mean(0)
    artifact["neutral_mouth"] = y[mask][closed].mean(0)
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model = SpeechMouthNet(outputs=CONFIG["components"]).to(device)
    initial = copy.deepcopy(model.cpu().state_dict())
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=CONFIG["learning_rate"], weight_decay=CONFIG["weight_decay"])
    batch_x, batch_y, batch_mask = chunks(x, y, train["valid"], CONFIG["chunk_frames"], model.context_frames)
    batch_x, batch_y, batch_mask = (t.to(device) for t in (batch_x, batch_y, batch_mask))
    device_art = {k: v.to(device) for k, v in artifact.items() if isinstance(v, torch.Tensor)}
    device_scales = {k: v.to(device) for k, v in normalizers.items()}
    dvx = vx[None].to(device)
    best, best_epoch, best_state, history = float("inf"), 0, None, []
    for epoch in range(1, CONFIG["epochs"] + 1):
        model.train()
        order = torch.randperm(len(batch_x)).to(device)
        losses = []
        for start in range(0, len(order), CONFIG["batch_size"]):
            indices = order[start:start + CONFIG["batch_size"]]
            bx, by, bm = batch_x[indices], batch_y[indices], batch_mask[indices]
            optimizer.zero_grad(set_to_none=True)
            prediction = decode(model(bx)[:, model.context_frames:], device_art, bound=False)
            loss = shape_loss(prediction, by, device_scales, bm)
            paired = bm[:, 1:] & bm[:, :-1]
            velocity = ((prediction[:, 1:] - prediction[:, :-1]) - (by[:, 1:] - by[:, :-1])).square().mean(-1)
            loss += CONFIG["velocity_weight"] * (velocity * paired).sum() / paired.sum().clamp_min(1) / device_scales["coordinates"]
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5, error_if_nonfinite=True)
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
        if epoch % CONFIG["validation_every"] == 0:
            model.eval()
            with torch.inference_mode():
                predicted = decode(model(dvx)[0].cpu(), artifact)
                score = float(shape_loss(predicted, vy, normalizers, vmask))
            history.append({"epoch": epoch, "training_loss": float(np.mean(losses)), "validation_score": score})
            if score < best:
                best, best_epoch = score, epoch
                best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            print(json.dumps(history[-1]), flush=True)
    model.cpu().load_state_dict(best_state)
    model.eval()
    artifact["model"] = best_state
    with torch.inference_mode():
        outputs = predictors(model, artifact, torch.from_numpy(validation["features"]), vrms)
        results = {name: metrics(value, vy, vmask, normalizers) for name, value in outputs.items()}
    selected = min(results, key=lambda name: results[name]["selection_score"])
    torch.save(artifact, root / "speech.pt")
    static = min(results[name]["selection_score"] for name in ("mean", "closed"))
    report = {"schema_version": 1, "config": CONFIG, "selected_predictor": selected, "validation": results,
              "selected_epoch": best_epoch, "ridge_alpha": ridge_alpha, "history": history,
              "training_seconds": time.perf_counter() - started, "device": device,
              "parameters": sum(p.numel() for p in model.parameters()),
              "parameters_updated": any(not torch.equal(initial[k], v) for k, v in best_state.items()),
              "pca_variance_retained": float(singular[:CONFIG["components"]].square().sum() / singular.square().sum()),
              "training_frames": int(mask.sum()), "validation_frames": int(vmask.sum()),
              "selected_improvement_over_static_percent": 100 * (1 - results[selected]["selection_score"] / static),
              "memory": memory(device), "checkpoint_bytes": (root / "speech.pt").stat().st_size,
              "checkpoint_sha256": digest(root / "speech.pt"), "plan_sha256": digest(root / "plan.json"),
              "test_evaluated": False, "timing": "Original clocks retained; no energy-lag or final-test offset tuning",
              "scope": "A-only training/statistics, B-only selection; centered lip shape, not full head motion"}
    write_json(root / "fit-report.json", report)
    trace = {"times": validation["times"], "valid": validation["valid"], "target": vy.numpy(),
             **{name: values.numpy() for name, values in outputs.items()}}
    np.savez_compressed(root / "validation-predictions.npz", **trace)
    print(json.dumps({k: v for k, v in report.items() if k not in ("history", "checkpoint_sha256", "plan_sha256")}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "fit"))
    parser.add_argument("--corpus", type=Path, default=Path(".runtime/local-avatar/camera-corpus-v1"))
    parser.add_argument("--output", type=Path, default=Path(".runtime/local-avatar/speech-camera-v1"))
    args = parser.parse_args()
    (freeze_plan if args.command == "plan" else fit)(args.corpus, args.output)


if __name__ == "__main__":
    main()
