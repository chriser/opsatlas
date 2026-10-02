"""Validation-only preview using natural speech motion and the frozen renderer."""

import argparse
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import torch

from experiments.local_avatar.appearance import AppearanceMLP, digest, partition
from experiments.local_avatar.appearance_evaluate import authored_motion, encode, predictions
from experiments.local_avatar.camera_corpus import frozen_corpus, training_sessions, write_json
from experiments.local_avatar.natural_speech import CONFIG, centered_mouth, predictors
from experiments.local_avatar.portrait_revision import reference_renderer
from experiments.local_avatar.speech_evaluate import latest_indices, mux_audio
from experiments.local_avatar.speech_motion import SpeechMouthNet


def verify_trace(trace, validation, artifact):
    model = SpeechMouthNet(outputs=CONFIG["components"]).eval()
    model.load_state_dict(artifact["model"])
    with torch.inference_mode():
        values = predictors(model, artifact, torch.from_numpy(validation["features"]), torch.from_numpy(validation["rms"]))
    expected = {"times": validation["times"], "valid": validation["valid"],
                "target": centered_mouth(torch.from_numpy(validation["geometry"])).numpy(),
                **{name: value.numpy() for name, value in values.items()}}
    if any(not np.allclose(trace[name], value, atol=1e-6, rtol=1e-6) for name, value in expected.items()):
        raise ValueError("Validation predictions differ from the frozen model/inputs")


def motion_frame(prediction, target):
    """Scientific contour view: predicted left, measured right; no face texture."""
    canvas = np.full((256, 512, 3), [16, 21, 27], dtype=np.uint8)
    for column, (mouth, color) in enumerate(((prediction, [117, 199, 180]), (target, [231, 236, 239]))):
        points = np.asarray(mouth).reshape(20, 2) * 512 + [128 + column * 256, 128]
        if not np.isfinite(points).all():
            raise ValueError("Nonfinite motion contour")
        for group in (points[:14], points[14:]):
            for a, b in zip(group, np.roll(group, -1, axis=0)):
                count = max(2, int(np.linalg.norm(b - a)) + 1)
                segment = np.linspace(a, b, count).round().astype(int)
                for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                    x, y = segment[:, 0] + dx, segment[:, 1] + dy
                    valid = (x >= column * 256) & (x < (column + 1) * 256) & (y >= 0) & (y < 256)
                    canvas[y[valid], x[valid]] = color
    return torch.from_numpy(canvas).permute(2, 0, 1).float() / 255


def render_motion_diagnostic(corpus, root):
    if (root / "motion.mp4").exists():
        raise ValueError("Motion diagnostic already exists")
    data = training_sessions(corpus)["validation"]
    trace = np.load(root / "validation-predictions.npz")
    artifact = torch.load(root / "speech.pt", weights_only=True, map_location="cpu")
    verify_trace(trace, data, artifact)
    clock = CONFIG["preview_start_seconds"] + np.arange(360) / 30
    indices = latest_indices(trace["times"], clock)
    if not trace["valid"][indices].all():
        raise ValueError("Invalid diagnostic targets")
    encode((motion_frame(trace["neural"][index], trace["target"][index]) for index in indices), root / "motion-silent.mp4")
    source = frozen_corpus(corpus)["sessions"]["B"]
    mux_audio(root / "motion-silent.mp4", corpus / "B/speech-16k.wav", root / "motion.mp4",
              clock[0], source["audio_origin_seconds"], 12.)
    write_json(root / "motion-manifest.json", {"session": "B", "test_evaluated": False,
               "contours": "neural predicted left; tracked validation target right", "video_sha256": digest(root / "motion.mp4")})


def retarget(mouth, natural_neutral, source_neutral, clock):
    """Training-template mapping into the frozen RGB decoder's landmark domain."""
    natural = natural_neutral.reshape(20, 2)
    source = source_neutral[:40].reshape(20, 2)
    scale = (source[:14, 0].max() - source[:14, 0].min()) / (natural[:14, 0].max() - natural[:14, 0].min()).clamp_min(.05)
    mapped = source_neutral[None].repeat(len(mouth), 1)
    mapped[:, :40] = source.flatten() + (mouth - natural.flatten()) * scale
    blink = torch.from_numpy(np.maximum(0, 1 - np.abs(((clock - clock[0]) % 4) - 2) / .15)).float()
    for start in (20, 26):
        eyes = mapped[:, start * 2:(start + 6) * 2].reshape(-1, 6, 2)
        center = eyes[:, :, 1].mean(1, keepdim=True)
        eyes[:, :, 1] = center + (eyes[:, :, 1] - center) * (1 - .9 * blink[:, None])
    return mapped


def render(runtime, corpus, root):
    if (root / "preview-manifest.json").exists():
        raise ValueError("Validation preview already published")
    guard = root / "protected-artifacts.json"
    if not guard.exists():
        paths = [runtime / directory / name for directory in ("appearance", "speech-v1")
                 for name in ("appearance.pt" if directory == "appearance" else "speech.pt",
                              "evaluation.json", "dataset.npz", "split.json")]
        paths += [runtime / "presentation-v3" / name for name in ("manifest.json", "portrait/reference.png")]
        write_json(guard, {str(path): digest(path) for path in paths})
    protected = json.loads(guard.read_text())
    if any(digest(Path(path)) != value for path, value in protected.items()):
        raise ValueError("Prior frozen research/presentation artifact changed")
    torch.set_num_threads(4)
    fit = json.loads((root / "fit-report.json").read_text())
    plan = json.loads((root / "plan.json").read_text())
    if plan["config"] != CONFIG or fit["plan_sha256"] != digest(root / "plan.json"):
        raise ValueError("Frozen preview plan changed")
    if fit["checkpoint_sha256"] != digest(root / "speech.pt"):
        raise ValueError("Fitted speech model changed")
    if plan["corpus_sha256"] != digest(corpus / "corpus.json") or any(
            plan["datasets"][name] != digest(corpus / name / "dataset.npz") for name in ("A", "B")):
        raise ValueError("Fitted A/B inputs changed")
    prepared = training_sessions(corpus)
    trace = np.load(root / "validation-predictions.npz")
    selected = fit["selected_predictor"]
    clock = CONFIG["preview_start_seconds"] + np.arange(360) / 30
    indices = latest_indices(trace["times"], clock)
    if clock[-1] > trace["times"][-1] or not trace["valid"][indices].all():
        raise ValueError("Validation preview exceeds usable labels")
    appearance = runtime / "appearance"
    image_art = torch.load(appearance / "appearance.pt", weights_only=True, map_location="cpu")
    image_model = AppearanceMLP().eval()
    image_model.load_state_dict(image_art["model"])
    data = np.load(appearance / "dataset.npz")
    masks = partition(data["times"], json.loads((appearance / "split.json").read_text()))
    source_neutral = authored_motion(data["features"][masks["train"]])[0]
    speech_art = torch.load(root / "speech.pt", weights_only=True, map_location="cpu")
    verify_trace(trace, prepared["validation"], speech_art)
    (root / "portrait").mkdir(exist_ok=True)
    shutil.copyfile(runtime / "presentation-v3/portrait/reference.png", root / "portrait/reference.png")
    shutil.copyfile(runtime / "presentation-v3/portrait-landmarks.json", root / "portrait-landmarks.json")
    with torch.inference_mode():
        neutral, _ = predictions(image_model, image_art, source_neutral[None])
        renderer = reference_renderer(root, neutral[0], source_neutral, mouth_width_scale=1.12, mouth_height_scale=1.08)
        shapes, images = {}, {}
        names = ["amplitude_rule", "ridge", "neural", "tracked_reference"]
        for name in names:
            mouth = torch.from_numpy(trace["target" if name == "tracked_reference" else name][indices])
            shapes[name] = retarget(mouth, speech_art["neutral_mouth"], source_neutral, clock)
            images[name], _ = predictions(image_model, image_art, shapes[name])
        encode((renderer(v, g) for v, g in zip(images["neural"], shapes["neural"])), root / "neural-silent.mp4")
        if selected == "neural":
            shutil.copyfile(root / "neural-silent.mp4", root / "selected-silent.mp4")
        else:
            if selected not in images:
                mouth = torch.from_numpy(trace[selected][indices])
                shapes[selected] = retarget(mouth, speech_art["neutral_mouth"], source_neutral, clock)
                images[selected], _ = predictions(image_model, image_art, shapes[selected])
            encode((renderer(v, g) for v, g in zip(images[selected], shapes[selected])), root / "selected-silent.mp4")
        encode((torch.cat([renderer(images[name][index], shapes[name][index]) for name in names], dim=2)
                for index in range(len(clock))), root / "comparison-silent.mp4")
    source = frozen_corpus(corpus)["sessions"]["B"]
    waveform = corpus / "B/speech-16k.wav"
    for name in ("selected", "neural", "comparison"):
        mux_audio(root / f"{name}-silent.mp4", waveform, root / f"{name}.mp4", clock[0], source["audio_origin_seconds"], 12.)
    subprocess.run(["swift", "-module-cache-path", str(runtime / "swift-module-cache"),
                    str(Path(__file__).with_name("camera_excerpt.swift")), source["source"], str(root / "source-silent.mp4"),
                    str(clock[0]), "12"], check=True)
    mux_audio(root / "source-silent.mp4", waveform, root / "source-reference.mp4", clock[0], source["audio_origin_seconds"], 12.)
    render_motion_diagnostic(corpus, root)
    summary = {"schema_version": 1, "session": "B", "kind": "validation preview; final C test remains sealed",
               "selected_predictor": selected, "validation": fit["validation"], "parameters": fit["parameters"],
               "selected_epoch": fit["selected_epoch"], "training_seconds": fit["training_seconds"],
               "training_frames": fit["training_frames"], "validation_frames": fit["validation_frames"],
               "preview_start_seconds": float(clock[0]), "preview_duration_seconds": 12., "test_evaluated": False,
               "rendering": "Frozen appearance decoder; training-template retargeting; closed-lip photo; authored blinks",
               "timing": "Original source clocks; causal audio and 560 ms history; latest available prediction"}
    write_json(root / "public-summary.json", summary)
    if any(digest(Path(path)) != value for path, value in protected.items()):
        raise ValueError("Prior frozen research/presentation artifact changed")
    write_json(root / "preview-manifest.json", {"schema_version": 1, "session": "B", "test_evaluated": False,
               "speech_sha256": digest(root / "speech.pt"), "appearance_sha256": digest(appearance / "appearance.pt"),
               "trace_sha256": digest(root / "validation-predictions.npz"), "source_waveform_sha256": digest(waveform),
               "video_files": [name + ".mp4" for name in ("selected", "neural", "comparison", "source-reference", "motion")],
               "selection": selected, "protected_artifacts_unchanged": True, "uploads": []})
    print("Natural validation preview complete; final C and original experiments unchanged.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, default=Path(".runtime/local-avatar"))
    parser.add_argument("--corpus", type=Path, default=Path(".runtime/local-avatar/camera-corpus-v1"))
    parser.add_argument("--output", type=Path, default=Path(".runtime/local-avatar/speech-camera-v1"))
    args = parser.parse_args()
    render(args.runtime, args.corpus, args.output)


if __name__ == "__main__":
    main()
