"""Freeze independent camera sessions; prepare train/validation, seal final test.

No personal material leaves ignored runtime storage. RGB is discarded by the
native extractor except sparse training/validation QC stills. No model is fitted.
"""

import argparse
import json
import math
import subprocess
import wave
from pathlib import Path

import numpy as np
import torch

from experiments.local_avatar.appearance import digest, pixels
from experiments.local_avatar.speech_motion import audio_features, interpolate_labels, mouth_measures

ROLES = {"A": "train", "B": "validation", "C": "test"}
AUDIO = {"sample_rate": 16000, "window_samples": 400, "hop_samples": 320, "fft_size": 512, "mel_bins": 80}
SETTINGS = {"fps": 30, "maximum_size": [640, 1138], "tracker_revision": 3,
            "minimum_confidence": .8, "maximum_label_gap_seconds": .1,
            "conversion": "AVAssetImageGenerator forceSDR and preferred track transform"}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def probe(source):
    return json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration,size:stream=index,codec_type,codec_name,width,height,avg_frame_rate,"
        "pix_fmt,color_space,color_transfer,color_primaries,sample_rate,channels,start_time,duration:stream_side_data=rotation",
        "-of", "json", str(source)]))


def useful_audio_origin(packet, sample_rate):
    """AAC skip samples belong to the packet clock, not a negative waveform start."""
    origin = float(packet["pts_time"])
    skip = sum(int(item.get("skip_samples", 0)) for item in packet.get("side_data_list", []))
    result = origin + skip / sample_rate
    if not math.isfinite(result):
        raise ValueError("Invalid audio origin")
    return result


def freeze(source_dir, root):
    root.mkdir(parents=True, exist_ok=True)
    path = root / "corpus.json"
    if path.exists():
        raise ValueError("Corpus roles already frozen; use the existing corpus or a fresh directory")
    sessions = {}
    for name, role in ROLES.items():
        source = (source_dir / f"{name}.MOV").resolve(strict=True)
        info = probe(source)
        video = next(s for s in info["streams"] if s["codec_type"] == "video")
        audio = next(s for s in info["streams"] if s.get("codec_name") == "aac")
        packets = json.loads(subprocess.check_output([
            "ffprobe", "-v", "error", "-select_streams", str(audio["index"]),
            "-read_intervals", "%+#1", "-show_packets", "-show_entries",
            "packet=pts_time,duration_time:packet_side_data=skip_samples,discard_padding", "-of", "json", str(source)]))
        origin = useful_audio_origin(packets["packets"][0], int(audio["sample_rate"]))
        sessions[name] = {"role": role, "source": str(source), "sha256": digest(source),
                          "duration_seconds": float(video["duration"]), "video_index": video["index"],
                          "audio_index": audio["index"], "audio_origin_seconds": origin,
                          "streams": info, "first_audio_packet": packets["packets"][0]}
    if len({s["sha256"] for s in sessions.values()}) != 3:
        raise ValueError("Require three distinct recording files")
    write_json(path, {"schema_version": 1, "sessions": sessions, "settings": SETTINGS, "audio": AUDIO,
                      "provenance": "User supplied recordings for the agreed natural camera protocol",
                      "authorized_use": "Private local identity avatar research requested by the user",
                      "test_policy": "C excluded from calibration, fitting and model selection; final evaluation not run"})
    print("Three distinct sources frozen: A=train, B=validation, C=test.", flush=True)


def frozen_corpus(root):
    corpus = json.loads((root / "corpus.json").read_text())
    if corpus["settings"] != SETTINGS or corpus["audio"] != AUDIO:
        raise ValueError("Extraction settings changed")
    if {name: s["role"] for name, s in corpus["sessions"].items()} != ROLES:
        raise ValueError("Frozen session roles changed")
    return corpus


def verify_source(session):
    if digest(Path(session["source"])) != session["sha256"]:
        raise ValueError("Original recording changed")


def training_sessions(root):
    """Only A/B are loadable here; verify frozen inputs before downstream fitting."""
    corpus = frozen_corpus(root)
    result = {}
    for name in ("A", "B"):
        folder = root / name
        manifest = json.loads((folder / "dataset-manifest.json").read_text())
        if manifest["role"] != ROLES[name] or manifest["source_sha256"] != corpus["sessions"][name]["sha256"]:
            raise ValueError("Prepared session role/source differs from frozen corpus")
        if manifest["corpus_sha256"] != digest(root / "corpus.json"):
            raise ValueError("Frozen corpus changed")
        for key, filename in (("dataset", "dataset.npz"), ("landmarks", "landmarks.jsonl"), ("waveform", "speech-16k.wav")):
            if manifest[key + "_sha256"] != digest(folder / filename):
                raise ValueError("Frozen preparation changed")
        with np.load(folder / "dataset.npz") as data:
            result[ROLES[name]] = {key: data[key] for key in data.files}
    return result


def audit(root):
    """Predefined integrity/clock checks on all files; no viewing test images."""
    corpus = frozen_corpus(root)
    for name, session in corpus["sessions"].items():
        folder = root / name
        folder.mkdir(exist_ok=True)
        if (folder / "audit.json").exists():
            continue
        verify_source(session)
        packets = json.loads(subprocess.check_output([
            "ffprobe", "-v", "error", "-select_streams", str(session["video_index"]), "-show_packets",
            "-show_entries", "packet=pts_time,duration_time", "-of", "json", session["source"]]))["packets"]
        pts = np.sort(np.array([float(p["pts_time"]) for p in packets]))
        gaps = np.diff(pts)
        if len(pts) < 2 or np.any(gaps <= 0):
            raise ValueError("Missing/duplicate video timestamps")
        with (folder / "decode-progress.txt").open("w") as progress, (folder / "decode-errors.txt").open("w") as errors:
            subprocess.run(["ffmpeg", "-v", "error", "-nostats", "-progress", "pipe:1",
                            "-hwaccel", "videotoolbox", "-i", session["source"],
                            "-map", f"0:{session['video_index']}", "-map", f"0:{session['audio_index']}",
                            "-fps_mode", "passthrough", "-enc_time_base:v", "demux",
                            "-f", "null", "-"], stdout=progress, stderr=errors, check=True)
        if (folder / "decode-errors.txt").read_text().strip():
            raise ValueError("Decoder reported errors; inspect private log")
        frames = [line.split("=", 1)[1] for line in (folder / "decode-progress.txt").read_text().splitlines()
                  if line.startswith("frame=")]
        if not frames or int(frames[-1]) != len(pts):
            raise ValueError("Decoded frame count differs from source packets")
        write_json(folder / "audit.json", {"full_primary_decode": "pass", "video_frames": len(pts),
                   "interval_p50_ms": float(np.median(gaps) * 1000), "maximum_interval_ms": float(gaps.max() * 1000),
                   "audio_origin_seconds": session["audio_origin_seconds"], "source_integrity_verified": True,
                   "test_content_inspected": False if name == "C" else None})
        print(f"{name}: full primary decode and timestamps verified ({len(pts)} video frames).", flush=True)


def extract(root, name):
    if name not in ("A", "B"):
        raise ValueError("Final test extraction is reserved for a frozen model evaluation")
    corpus = frozen_corpus(root)
    session = corpus["sessions"][name]
    folder = root / name
    verify_source(session)
    if not (folder / "audit.json").exists():
        raise ValueError("Audit the source before extracting labels")
    tracker = Path(__file__).with_name("track_camera.swift")
    tracker_digest = digest(tracker)
    subprocess.run(["swift", "-module-cache-path", str(root.parent / "swift-module-cache"),
                    str(tracker), session["source"], str(folder),
                    str(session["duration_seconds"]), str(SETTINGS["fps"])], check=True)
    if digest(tracker) != tracker_digest:
        raise ValueError("Extractor changed while running")
    print(f"{name}: dense local labels extracted.", flush=True)


def label_rows(records, duration):
    indices = [r["index"] for r in records]
    if sorted(indices) != list(range(math.ceil(duration * SETTINGS["fps"]))):
        raise ValueError("Missing/duplicate extraction requests")
    accepted, rejected, seen = [], [], set()
    for record in sorted(records, key=lambda r: r.get("source_seconds", float("inf"))):
        try:
            t = float(record["source_seconds"])
            if not math.isfinite(t) or t < 0 or t > duration or t in seen:
                raise ValueError("Invalid/duplicate source timestamp")
            seen.add(t)
            if len(record.get("faces", [])) != 1 or record["faces"][0]["confidence"] < SETTINGS["minimum_confidence"]:
                raise ValueError("Face count/confidence")
            vector, _, _ = pixels(record["faces"][0], record["width"], record["height"])
            if not np.isfinite(vector).all():
                raise ValueError("Nonfinite landmarks")
            accepted.append((t, vector))
        except (ValueError, KeyError) as exc:
            rejected.append({"index": record["index"], "reason": str(exc)})
    if len(accepted) < 100:
        raise ValueError("Insufficient usable geometry")
    return np.array([r[0] for r in accepted]), np.stack([r[1] for r in accepted]), rejected


def contiguous_runs(valid):
    """Exclusive bounds prevent temporal batches from crossing missing-label gaps."""
    edges = np.diff(np.r_[False, valid, False].astype(np.int8))
    return np.column_stack((np.flatnonzero(edges == 1), np.flatnonzero(edges == -1))).tolist()


def prepare(root, name):
    if name not in ("A", "B"):
        raise ValueError("Final test is sealed until model selection finishes")
    corpus = frozen_corpus(root)
    session = corpus["sessions"][name]
    folder = root / name
    if (folder / "dataset-manifest.json").exists():
        raise ValueError("Prepared session already frozen")
    verify_source(session)
    records = [json.loads(line) for line in (folder / "landmarks.jsonl").read_text().splitlines()]
    times, geometry, rejected = label_rows(records, session["duration_seconds"])
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", session["source"],
                                   "-map", f"0:{session['audio_index']}", "-ac", "1", "-ar", "16000",
                                   "-f", "f32le", "-"])
    samples = np.frombuffer(raw, dtype="<f4").copy()
    if not len(samples) or not np.isfinite(samples).all():
        raise ValueError("Empty/nonfinite primary audio")
    peak = float(np.abs(samples).max())
    gain = min(1., .95 / max(peak, 1e-9))
    normalized = samples * gain
    with wave.open(str(folder / "speech-16k.wav"), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes((normalized * 32767).round().astype("<i2").tobytes())
    spec = {**AUDIO, "audio_offset_seconds": session["audio_origin_seconds"]}
    torch.set_num_threads(4)
    audio_times, features, rms = audio_features(normalized, spec)
    labels, valid = interpolate_labels(times, geometry, audio_times, SETTINGS["maximum_label_gap_seconds"])
    valid &= audio_times < session["duration_seconds"]
    np.savez_compressed(folder / "dataset.npz", times=audio_times, features=features, rms=rms,
                        geometry=labels, valid=valid, landmark_times=times, landmark_geometry=geometry)
    report = {"role": session["role"], "requested_frames": len(records), "accepted_frames": len(times),
              "rejected_frames": len(rejected), "audio_frames": len(audio_times), "usable_audio_frames": int(valid.sum()),
              "retried_requests": sum(bool(r.get("retries")) for r in records),
              "usable_fraction": float(valid.mean()), "continuous_runs": contiguous_runs(valid),
              "landmark_interval_p50_ms": float(np.median(np.diff(times)) * 1000),
              "landmark_maximum_gap_ms": float(np.diff(times).max() * 1000),
              "audio_duration_seconds": len(samples) / 16000, "audio_origin_seconds": session["audio_origin_seconds"],
              "raw_mono_peak": peak, "raw_mono_rms": float(np.sqrt(np.mean(samples ** 2))),
              "raw_samples_above_0_999": int((np.abs(samples) >= .999).sum()), "derivative_gain": gain,
              "rejected": rejected, "timing": "Container clock retained; no test-based offset tuning"}
    if name == "A":
        aperture, width = mouth_measures(geometry[:, :40])
        report["training_shape_ranges"] = {"aperture_ratio": [float(aperture.min()), float(aperture.max())],
                                           "canonical_width_pixels": [float(width.min()), float(width.max())]}
    write_json(folder / "preparation-report.json", report)
    write_json(folder / "dataset-manifest.json", {"schema_version": 1, "role": session["role"],
               "source_sha256": session["sha256"], "corpus_sha256": digest(root / "corpus.json"),
               "landmarks_sha256": digest(folder / "landmarks.jsonl"), "dataset_sha256": digest(folder / "dataset.npz"),
               "waveform_sha256": digest(folder / "speech-16k.wav"), "prepared": True,
               "extractor_sha256": digest(Path(__file__).with_name("track_camera.swift")),
               "test_evaluated": False, "fit_statistics": "None; compute normalization/targets on A only"})
    summary_keys = ["role", "accepted_frames", "requested_frames", "usable_audio_frames", "usable_fraction"]
    print(json.dumps({k: report[k] for k in summary_keys}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("freeze", "audit", "extract", "prepare"))
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--session", choices=("A", "B"))
    args = parser.parse_args()
    if args.command == "freeze":
        if args.source_dir is None:
            parser.error("freeze requires --source-dir")
        freeze(args.source_dir, args.output)
    elif args.command == "audit":
        audit(args.output)
    else:
        if args.session is None:
            parser.error("extract/prepare requires --session")
        (extract if args.command == "extract" else prepare)(args.output, args.session)


if __name__ == "__main__":
    main()
