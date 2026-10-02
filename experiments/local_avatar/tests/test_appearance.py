import argparse
import json

import numpy as np
import pytest
import torch

from experiments.local_avatar.appearance import (
    PATCH_SIZE,
    AppearanceMLP,
    composite,
    fit,
    normalization,
    partition,
    pixels,
)
from experiments.local_avatar.appearance_evaluate import authored_motion, resample


def test_contiguous_splits_enforce_buffers_exclusions_and_boundaries():
    spec = {"train": [2, 10], "validation": [12, 16], "test": [18, 22], "excluded": [[5, 7]]}
    masks = partition(np.arange(24), spec)
    assert np.flatnonzero(masks["train"]).tolist() == [2, 3, 4, 7, 8, 9]
    assert np.flatnonzero(masks["validation"]).tolist() == [12, 13, 14, 15]
    assert np.flatnonzero(masks["test"]).tolist() == [18, 19, 20, 21]
    assert not (masks["train"] & masks["test"]).any()
    with pytest.raises(ValueError):
        partition(np.arange(24), {**spec, "validation": [9, 16]})


def test_normalization_uses_only_supplied_training_rows():
    train = torch.tensor([[0., 1.], [2., 1.]])
    center, scale = normalization(train)
    torch.testing.assert_close(center, torch.tensor([1., 1.]))
    torch.testing.assert_close(scale, torch.tensor([2 ** .5, .005]))


def test_vision_y_axis_is_inverted_and_similarity_features_ignore_translation_scale():
    face = {"bbox": [.1, .2, .5, .6], "outer_lips": [[.5, .2]] * 14, "inner_lips": [[.5, .21]] * 6,
            "left_eye": [[.25, .7]] * 6, "right_eye": [[.75, .7]] * 6}
    features, origin, matrix = pixels(face, 1000, 800)
    assert origin[1] == pytest.approx((1 - .2 - .7 * .6) * 800)
    assert features[1] > 80 / 256  # Mouth is below eyes after the y-axis conversion.
    changed, _, _ = pixels({**face, "bbox": [.3, .1, .25, .3]}, 1000, 800)
    np.testing.assert_allclose(features, changed, atol=1e-6)
    assert np.linalg.det(matrix) > 0


def test_appearance_training_updates_random_weights_with_finite_gradients():
    torch.manual_seed(41)
    model = AppearanceMLP()
    optimizer = torch.optim.AdamW(model.parameters(), lr=.01)
    before = model.network[0].weight.detach().clone()
    controls = torch.randn(8, 64)
    loss = model(controls).square().mean()
    loss.backward()
    assert all(torch.isfinite(p.grad).all() for p in model.parameters())
    optimizer.step()
    assert not torch.equal(before, model.network[0].weight)
    assert sum(p.numel() for p in model.parameters()) == 31024


def test_compositing_changes_regions_but_preserves_background_exactly():
    image = np.full((256, 256, 3), 200, dtype=np.uint8)
    output = composite(image, torch.zeros(PATCH_SIZE), np.array([128, 80], dtype=np.float32), np.eye(2, dtype=np.float32))
    torch.testing.assert_close(output[:, :30], torch.full((3, 30, 256), 200 / 255))
    assert output[:, 165, 128].max() == 0
    assert torch.isfinite(output).all()


def test_refitting_after_final_test_and_frozen_data_tampering_are_rejected(tmp_path):
    args = argparse.Namespace(output=tmp_path, epochs=10)
    (tmp_path / "evaluation.json").write_text("{}")
    with pytest.raises(ValueError, match="Test already evaluated"):
        fit(args)
    (tmp_path / "evaluation.json").unlink()
    (tmp_path / "dataset.npz").write_bytes(b"changed")
    (tmp_path / "dataset-manifest.json").write_text(json.dumps({"dataset_sha256": "stale"}))
    with pytest.raises(ValueError, match="Frozen data changed"):
        fit(args)


def test_motion_resampling_uses_source_clock_and_authored_blinks_are_independent():
    clock, values = resample(np.array([118.2, 118.6]), np.array([[0., 1.], [1., 0.]]), fps=10)
    assert clock[0] == 118.2
    torch.testing.assert_close(values[2], torch.tensor([.5, .5]))
    training = np.zeros((3, 64), dtype=np.float32)
    training[1, 29] = .2
    training[0, 41] = .1
    training[1, 41] = .1
    motion = authored_motion(training).numpy()
    assert motion.shape == (180, 64)
    assert motion[30, 29] == pytest.approx(.2)
    assert motion[30, 41] == 0
    assert motion[0, 29] == 0
