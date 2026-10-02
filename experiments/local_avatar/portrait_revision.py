"""Render frozen predictions onto a new private portrait; never refit or rescore.

The neutral portrait supplies cheek, beard and skin detail. A narrow lip region
receives changes relative to a training-only neutral prediction. An opening mouth
receives generated interior pixels. Blinks compress the reference eye texture.
"""

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

from experiments.local_avatar.appearance import AppearanceMLP, canonical, digest, partition, pixels, raw_image, unpack
from experiments.local_avatar.appearance_evaluate import authored_motion, encode, predictions, resample
from experiments.local_avatar.speech_evaluate import add_rule_eyes, latest_indices, mux_audio, predict_motion
from experiments.local_avatar.speech_motion import SpeechMouthNet, frozen_data


def ellipse(center, radius):
    y, x = torch.meshgrid(torch.arange(256), torch.arange(256), indexing="ij")
    distance = torch.sqrt(((x - center[0]) / radius[0]) ** 2 + ((y - center[1]) / radius[1]) ** 2)
    return ((1 - distance) / .25).clamp(0, 1)[None]


class ReferenceCompositor:
    def __init__(self, reference, neutral, source_geometry, reference_geometry):
        source = source_geometry.reshape(32, 2) * 256
        target = reference_geometry.reshape(32, 2) * 256
        source_center = (source[:14].amin(0) + source[:14].amax(0)) / 2
        target_center = (target[:14].amin(0) + target[:14].amax(0)) / 2
        source_width = source[:14, 0].max() - source[:14, 0].min()
        self.scale = (target[:14, 0].max() - target[:14, 0].min()) / source_width.clamp_min(1)
        self.source_center, self.target_center = source_center, target_center
        y, x = torch.meshgrid(torch.arange(256), torch.arange(256), indexing="ij")
        coordinates = (torch.stack((x, y), -1) - target_center) / self.scale + source_center
        self.mouth_grid = (coordinates / 127.5 - 1)[None]
        # Lips and nearby beard only: preserve nasolabial folds, nose and cheeks.
        self.mouth_mask = ellipse(target_center, (float(source_width * self.scale / 2 + 6), 27))
        self.eye_centers = [target[start:start + 6].mean(0) for start in (20, 26)]
        self.reference = reference
        self.neutral = self.align(neutral)
        self.neutral_aperture = source[14:20, 1].max() - source[14:20, 1].min()
        self.neutral_eye_height = [source[start:start + 6, 1].max() - source[start:start + 6, 1].min()
                                   for start in (20, 26)]
        # Low-frequency lighting correction applies only to newly visible mouth interior.
        self.color_offset = F.avg_pool2d(F.pad((reference - self.neutral)[None], (8, 8, 8, 8), mode="replicate"), 17, stride=1)[0]

    def align(self, vector):
        image = unpack(vector)
        mouth = F.grid_sample(image[None], self.mouth_grid, align_corners=True)[0]
        # Mouth is below the eye region; no transferred cheek texture is ever used.
        result = image.clone()
        result[:, 120:] = mouth[:, 120:]
        return result

    def delta(self, vector, geometry):
        current = self.align(vector)
        relative = self.reference + current - self.neutral
        points = geometry.reshape(32, 2) * 256
        inner = points[14:20]
        inner = (inner - self.source_center) * self.scale + self.target_center
        span = inner.amax(0) - inner.amin(0)
        opening = ((span[1] / self.scale - self.neutral_aperture) / 6).clamp(0, 1)
        outer = (points[:14] - self.source_center) * self.scale + self.target_center
        lip_center = (outer.amin(0) + outer.amax(0)) / 2
        lip_span = outer.amax(0) - outer.amin(0)
        # Cover the original lip line when the mouth opens, avoiding a second lip.
        interior = ellipse(lip_center, (float(lip_span[0] / 2 + 4), float(lip_span[1] / 2 + 5))) * opening * self.mouth_mask
        corrected = (current + self.color_offset).clamp(0, 1)
        animated = relative * (1 - interior) + corrected * interior
        delta = (animated.clamp(0, 1) - self.reference) * self.mouth_mask
        # A reference-native geometric blink avoids ghosting an open iris against
        # the soft learned eyelid patch. It is a presentation rule, not a new model.
        y, x = torch.meshgrid(torch.arange(256), torch.arange(256), indexing="ij")
        for i, start in enumerate((20, 26)):
            eye = points[start:start + 6]
            eye_height = eye[:, 1].max() - eye[:, 1].min()
            ratio = (eye_height / self.neutral_eye_height[i].clamp_min(1)).clamp(.08, 1)
            if ratio >= 1 - 1e-6:
                continue
            center = self.eye_centers[i]
            grid = torch.stack((x.float(), center[1] + (y - center[1]) / ratio), -1) / 127.5 - 1
            compressed = F.grid_sample(self.reference[None], grid[None], align_corners=True, padding_mode="border")[0]
            delta += (compressed - self.reference) * ellipse(center, (23, 11))
        return delta


def reference_renderer(root, neutral, source_geometry):
    portrait = root / "portrait/reference.png"
    info = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                              "-show_entries", "stream=width,height", "-of", "json", str(portrait)]))
    width, height = (info["streams"][0][name] for name in ("width", "height"))
    original = raw_image(portrait, width, height)
    records = json.loads((root / "portrait-landmarks.json").read_text())["records"]
    if len(records) != 1 or len(records[0]["faces"]) != 1:
        raise ValueError("Need exactly one reference image with one face")
    features, origin, matrix = pixels(records[0]["faces"][0], width, height)
    compositor = ReferenceCompositor(canonical(original, origin, matrix), neutral, source_geometry, torch.from_numpy(features))
    output_width, output_height = 560, 700
    scale = np.array([output_width / width, output_height / height], dtype=np.float32)
    origin, matrix = origin * scale, matrix * scale[:, None]
    y, x = torch.meshgrid(torch.arange(output_height), torch.arange(output_width), indexing="ij")
    coordinates = (torch.stack((x, y), -1).float() - torch.from_numpy(origin)) @ torch.from_numpy(np.linalg.inv(matrix)).T
    grid = ((coordinates + torch.tensor([128, 80])) / 127.5 - 1)[None]
    base = F.interpolate(torch.from_numpy(original.copy()).permute(2, 0, 1)[None].float() / 255,
                         size=(output_height, output_width), mode="area")[0]

    def render(vector, geometry):
        delta = F.grid_sample(compositor.delta(vector, geometry)[None], grid, align_corners=True)[0]
        return (base + delta).clamp(0, 1)

    return render


def render_revision(runtime, output, waveform):
    if (output / "manifest.json").exists():
        raise ValueError("Presentation revision already published; use a new directory")
    appearance, speech = runtime / "appearance", runtime / "speech-v1"
    protected = [root / name for root, names in ((appearance, ("appearance.pt", "evaluation.json", "dataset.npz", "split.json")),
                                               (speech, ("speech.pt", "evaluation.json", "dataset.npz", "split.json"))) for name in names]
    before = {str(path): digest(path) for path in protected}
    torch.set_num_threads(4)
    art = torch.load(appearance / "appearance.pt", weights_only=True, map_location="cpu")
    for name in ("dataset", "split"):
        if digest(appearance / (name + (".npz" if name == "dataset" else ".json"))) != art[name + "_sha256"]:
            raise ValueError("Frozen appearance input changed")
    data = np.load(appearance / "dataset.npz")
    masks = partition(data["times"], json.loads((appearance / "split.json").read_text()))
    training = data["features"][masks["train"]]
    authored = authored_motion(training)
    neutral_shape = authored[0]
    image_model = AppearanceMLP().eval()
    image_model.load_state_dict(art["model"])
    for directory in ("appearance", "speech"):
        (output / directory).mkdir(parents=True, exist_ok=True)
    with torch.inference_mode():
        neutral, linear_neutral = predictions(image_model, art, neutral_shape[None])
        render = reference_renderer(output, neutral[0], neutral_shape)
        linear_render = reference_renderer(output, linear_neutral[0], neutral_shape)
        values, _ = predictions(image_model, art, authored)
        encode((render(v, g) for v, g in zip(values, authored)), output / "appearance/authored.mp4")
        _, shapes = resample(data["times"][masks["test"]], data["features"][masks["test"]])
        values, _ = predictions(image_model, art, shapes)
        encode((render(v, g) for v, g in zip(values, shapes)), output / "appearance/heldout.mp4")
        test_shapes = torch.from_numpy(data["features"][masks["test"]])
        neural, linear = predictions(image_model, art, test_shapes)
        mean_render = reference_renderer(output, art["pixel_mean"], neutral_shape)
        closed_index = np.ptp(training.reshape(-1, 32, 2)[:, 14:20, 1], axis=1).argmin()
        source_render = reference_renderer(output, torch.from_numpy(data["patches"][masks["train"]][closed_index]), neutral_shape)
        targets = torch.from_numpy(data["patches"][masks["test"]])
        encode((torch.cat((mean_render(art["pixel_mean"], neutral_shape), linear_render(linear[i], g), render(neural[i], g),
                           source_render(targets[i], g)), dim=2) for i, g in enumerate(test_shapes)),
               output / "appearance/comparison.mp4", fps=5)
        speech_data, manifest, speech_masks = frozen_data(speech)
        if digest(waveform) != manifest["audio_sha256"]:
            raise ValueError("Frozen waveform changed")
        speech_art = torch.load(speech / "speech.pt", weights_only=True, map_location="cpu")
        for name in ("dataset_sha256", "split_sha256"):
            if speech_art[name] != manifest[name]:
                raise ValueError("Frozen speech input changed")
        speech_model = SpeechMouthNet().eval()
        speech_model.load_state_dict(speech_art["model"])
        clock = speech_data["times"][speech_masks["test"]]
        display = json.loads((speech / "evaluation.json").read_text())["display"]
        output_clock = display["source_start_seconds"] + np.arange(display["frames"]) / display["fps"]
        indices = latest_indices(clock, output_clock)
        if indices.max() >= len(clock):
            raise ValueError("Preview exceeds frozen predictions")
        motions = predict_motion(speech_model, speech_art, torch.from_numpy(speech_data["features"][speech_masks["test"]]),
                                torch.from_numpy(speech_data["rms"][speech_masks["test"]]))
        selected = json.loads((speech / "fit-report.json").read_text())["selected_predictor"]
        shapes, images = {}, {}
        for name in dict.fromkeys(("neural", "ridge", "amplitude_rule", selected, "tracked_reference")):
            mouth = (torch.from_numpy(speech_data["geometry"][speech_masks["test"], :40])
                     if name == "tracked_reference" else motions[name])
            shapes[name] = add_rule_eyes(mouth[indices], speech_art, output_clock)
            images[name], _ = predictions(image_model, art, shapes[name])
        for label, name in (("selected", selected), ("neural", "neural")):
            encode((render(v, g) for v, g in zip(images[name], shapes[name])), output / f"speech/{label}-silent.mp4")
        names = ("amplitude_rule", "ridge", "neural", "tracked_reference")
        encode((torch.cat([render(images[name][i], shapes[name][i]) for name in names], dim=2)
                for i in range(len(output_clock))), output / "speech/comparison-silent.mp4")
        spec = json.loads((speech / "split.json").read_text())
        for name in ("selected", "neural", "comparison"):
            mux_audio(output / f"speech/{name}-silent.mp4", waveform, output / f"speech/{name}.mp4",
                      output_clock[0], spec["audio_offset_seconds"], display["duration_seconds"])
    if before != {str(path): digest(path) for path in protected}:
        raise ValueError("Frozen research artifact was modified")
    report = {"schema_version": 2, "purpose": "presentation refinement; no fitting or new quantitative evaluation",
              "reference_sha256": digest(output / "portrait/reference.png"), "protected_artifacts": before,
              "compositing": "neutral-relative lips; generated mouth interior; reference-native geometric blinks; preserved cheeks",
              "motion": "unchanged frozen models and intervals; authored blinks", "uploads": []}
    # Completion marker: the server switches only after all six previews are ready.
    (output / "manifest.json").write_text(json.dumps(report, indent=2))
    print("New private portrait revision rendered; frozen models and test reports unchanged.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, default=Path(".runtime/local-avatar"))
    parser.add_argument("--output", type=Path, default=Path(".runtime/local-avatar/presentation-v2"))
    parser.add_argument("--audio", type=Path, required=True)
    args = parser.parse_args()
    render_revision(args.runtime, args.output, args.audio)


if __name__ == "__main__":
    main()
