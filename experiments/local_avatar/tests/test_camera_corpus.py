import json

import numpy as np
import pytest

from experiments.local_avatar.appearance import digest
from experiments.local_avatar.camera_corpus import (
    AUDIO,
    SETTINGS,
    contiguous_runs,
    extract,
    freeze,
    frozen_corpus,
    label_rows,
    prepare,
    training_sessions,
    useful_audio_origin,
    verify_source,
)


def test_aac_priming_uses_first_packet_clock_instead_of_stream_offset():
    packet = {"pts_time": "-0.044", "side_data_list": [{"skip_samples": 2112}]}
    assert useful_audio_origin(packet, 48000) == pytest.approx(0)
    assert useful_audio_origin({"pts_time": ".176062"}, 48000) == pytest.approx(.176062)
    with pytest.raises(ValueError, match="Invalid audio origin"):
        useful_audio_origin({"pts_time": "nan"}, 48000)


@pytest.mark.parametrize("operation", [extract, prepare])
def test_test_session_is_sealed_before_any_io(operation, tmp_path):
    with pytest.raises(ValueError, match="test"):
        operation(tmp_path / "absent", "C")
    assert not (tmp_path / "absent").exists()


def test_role_or_extractor_change_rejects_frozen_corpus(tmp_path):
    corpus = {"settings": SETTINGS, "audio": AUDIO,
              "sessions": {"A": {"role": "train"}, "B": {"role": "validation"}, "C": {"role": "test"}}}
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps(corpus))
    assert frozen_corpus(tmp_path)["sessions"]["C"]["role"] == "test"
    corpus["sessions"]["C"]["role"] = "train"
    path.write_text(json.dumps(corpus))
    with pytest.raises(ValueError, match="session roles changed"):
        frozen_corpus(tmp_path)
    corpus["settings"] = {**SETTINGS, "fps": 2}
    path.write_text(json.dumps(corpus))
    with pytest.raises(ValueError, match="settings changed"):
        frozen_corpus(tmp_path)


def test_corpus_cannot_be_refrozen_and_original_integrity_is_enforced(tmp_path):
    (tmp_path / "corpus.json").write_text("{}")
    with pytest.raises(ValueError, match="already frozen"):
        freeze(tmp_path / "nonexistent", tmp_path)
    source = tmp_path / "private.mov"
    source.write_bytes(b"changed")
    with pytest.raises(ValueError, match="Original recording changed"):
        verify_source({"source": str(source), "sha256": "stale"})


def records():
    face = {"confidence": .99, "bbox": [.1, .2, .5, .6], "outer_lips": [[.5, .2]] * 14,
            "inner_lips": [[.5, .21]] * 6, "left_eye": [[.25, .7]] * 6, "right_eye": [[.75, .7]] * 6}
    return [{"index": i, "source_seconds": i / 30, "width": 640, "height": 1137, "faces": [face]}
            for i in range(150)]


def test_labels_preserve_actual_timestamps_and_reject_missing_or_duplicate_requests():
    rows = records()
    rows[50]["source_seconds"] += .001
    times, geometry, rejected = label_rows(list(reversed(rows)), 5)
    assert times[50] == pytest.approx(50 / 30 + .001)
    assert geometry.shape == (150, 64) and not rejected
    with pytest.raises(ValueError, match="extraction requests"):
        label_rows(rows[:-1], 5)
    with pytest.raises(ValueError, match="extraction requests"):
        label_rows(rows + [rows[0]], 5)


def test_tracker_failures_and_duplicate_source_frames_do_not_become_targets():
    rows = records()
    rows[20] = {"index": 20, "error": "decode failure"}
    rows[21]["source_seconds"] = rows[19]["source_seconds"]
    rows[30]["faces"] = []
    times, geometry, rejected = label_rows(rows, 5)
    assert len(times) == 147 and geometry.shape == (147, 64)
    assert {r["index"] for r in rejected} == {20, 21, 30}
    assert np.all(np.diff(times) > 0)


def test_temporal_batch_bounds_do_not_bridge_missing_labels_or_session_ends():
    valid = np.array([False, True, True, False, True, True, True, False])
    assert contiguous_runs(valid) == [[1, 3], [4, 7]]
    assert contiguous_runs(np.array([True, True])) == [[0, 2]]
    assert contiguous_runs(np.array([False, False])) == []


def test_fitting_loader_rejects_corpus_mutation_before_loading_arrays(tmp_path):
    corpus = {"settings": SETTINGS, "audio": AUDIO,
              "sessions": {"A": {"role": "train", "sha256": "a"},
                           "B": {"role": "validation", "sha256": "b"}, "C": {"role": "test", "sha256": "c"}}}
    (tmp_path / "corpus.json").write_text(json.dumps(corpus))
    (tmp_path / "A").mkdir()
    (tmp_path / "A" / "dataset-manifest.json").write_text(json.dumps(
        {"role": "train", "source_sha256": "a", "corpus_sha256": "stale"}))
    with pytest.raises(ValueError, match="Frozen corpus changed"):
        training_sessions(tmp_path)


def test_fitting_loader_reads_only_train_validation_and_rejects_data_tampering(tmp_path):
    corpus = {"settings": SETTINGS, "audio": AUDIO,
              "sessions": {"A": {"role": "train", "sha256": "a"},
                           "B": {"role": "validation", "sha256": "b"}, "C": {"role": "test", "sha256": "c"}}}
    (tmp_path / "corpus.json").write_text(json.dumps(corpus))
    for name, role in [("A", "train"), ("B", "validation")]:
        folder = tmp_path / name
        folder.mkdir()
        np.savez(folder / "dataset.npz", features=np.ones((3, 80)), valid=np.array([True, False, True]))
        (folder / "landmarks.jsonl").write_text("synthetic")
        (folder / "speech-16k.wav").write_bytes(b"synthetic")
        manifest = {"role": role, "source_sha256": name.lower(), "corpus_sha256": digest(tmp_path / "corpus.json")}
        for key, filename in [("dataset", "dataset.npz"), ("landmarks", "landmarks.jsonl"), ("waveform", "speech-16k.wav")]:
            manifest[key + "_sha256"] = digest(folder / filename)
        (folder / "dataset-manifest.json").write_text(json.dumps(manifest))
    loaded = training_sessions(tmp_path)
    assert set(loaded) == {"train", "validation"}
    assert loaded["train"]["valid"].tolist() == [True, False, True]
    assert not (tmp_path / "C").exists()
    (tmp_path / "B" / "dataset.npz").write_bytes(b"changed")
    with pytest.raises(ValueError, match="Frozen preparation changed"):
        training_sessions(tmp_path)
