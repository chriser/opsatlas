import json

import numpy as np
import pytest
import torch

from experiments.local_avatar.natural_preview import motion_frame, render, retarget
from experiments.local_avatar.natural_speech import centered_mouth, chunks, fit, measures, scales, shape_loss


def mouth(opening=1., width=36.):
    angle = torch.arange(14) * (2 * torch.pi / 14)
    outer = torch.stack((128 + width * angle.cos(), 182 + 7 * angle.sin()), 1)
    angle = torch.arange(6) * (2 * torch.pi / 6)
    inner = torch.stack((128 + width * .75 * angle.cos(), 182 + opening * angle.sin()), 1)
    return torch.cat((outer, inner)).flatten() / 256


def test_shape_target_removes_head_translation_without_erasing_opening_or_width():
    closed, opened = mouth(), mouth(18., 40.)
    translation = torch.tensor([.13, -.04]).repeat(20)
    torch.testing.assert_close(centered_mouth(closed + translation), centered_mouth(closed), atol=1e-7, rtol=0)
    ca, cw = measures(centered_mouth(closed))
    oa, ow = measures(centered_mouth(opened))
    assert oa > ca and ow > cw


def test_loss_penalizes_static_closed_mouth_and_has_finite_shape_gradients():
    training = centered_mouth(torch.stack((mouth(), mouth(18.), mouth(6., 40.), mouth(2., 32.))))
    normalizers = scales(training)
    predicted = training[0:1].clone().requires_grad_()
    target = training[1:2]
    loss = shape_loss(predicted, target, normalizers)
    assert loss > 1 and shape_loss(target, target, normalizers) == 0
    loss.backward()
    assert torch.isfinite(predicted.grad).all() and predicted.grad.abs().sum() > 0


def test_invalid_padded_targets_do_not_influence_training_loss():
    training = centered_mouth(torch.stack((mouth(), mouth(18.), mouth(6., 40.), mouth(2., 32.))))
    normalizers = scales(training)
    predicted = training.clone()
    predicted[3] += 100
    assert shape_loss(predicted, training, normalizers, torch.tensor([True, True, True, False])) == 0


def test_temporal_batches_pad_past_only_and_never_bridge_missing_labels():
    inputs = torch.arange(10).float()[:, None]
    targets = inputs.repeat(1, 40)
    valid = np.array([False, True, True, True, False, False, True, True, True, True])
    xs, ys, masks = chunks(inputs, targets, valid, frames=3, context=2)
    assert xs.shape == (3, 5, 1) and ys.shape == (3, 3, 40)
    torch.testing.assert_close(xs[0, :, 0], torch.tensor([0., 0., 1., 2., 3.]))
    torch.testing.assert_close(xs[1, :, 0], torch.tensor([0., 0., 6., 7., 8.]))
    assert masks[-1].tolist() == [True, False, False]
    with pytest.raises(ValueError, match="No continuous"):
        chunks(inputs, targets, np.zeros(10, dtype=bool))


def test_frozen_candidate_cannot_be_silently_refitted(tmp_path):
    (tmp_path / "fit-report.json").write_text("{}")
    with pytest.raises(ValueError, match="already fitted"):
        fit(tmp_path / "absent-corpus", tmp_path)


def test_natural_neutral_retargets_exactly_to_existing_renderer_without_changing_eyes():
    source = torch.cat((mouth(), torch.tensor([.3, .3]).repeat(12)))
    neutral = centered_mouth(mouth())
    shapes = torch.stack((neutral, centered_mouth(mouth(18.))))
    mapped = retarget(shapes, neutral, source, np.array([0., .1]))
    torch.testing.assert_close(mapped[0], source)
    torch.testing.assert_close(mapped[:, 40:], source[40:].expand(2, -1))
    aperture, _ = measures(mapped[:, :40])
    assert aperture[1] > aperture[0]


def test_completed_validation_preview_cannot_be_overwritten(tmp_path):
    (tmp_path / "preview-manifest.json").write_text("{}")
    with pytest.raises(ValueError, match="already published"):
        render(tmp_path / "absent", tmp_path / "absent", tmp_path)


def test_preview_rejects_changed_original_artifact_before_rendering(tmp_path):
    source = tmp_path / "original.pt"
    source.write_bytes(b"changed")
    (tmp_path / "protected-artifacts.json").write_text(json.dumps({str(source): "stale"}))
    with pytest.raises(ValueError, match="Prior frozen"):
        render(tmp_path / "absent", tmp_path / "absent", tmp_path)


def test_contour_diagnostic_separates_prediction_from_target_without_face_pixels():
    closed, opened = centered_mouth(mouth()), centered_mouth(mouth(18.))
    frame = motion_frame(closed.numpy(), opened.numpy())
    assert frame.shape == (3, 256, 512) and torch.isfinite(frame).all()
    assert not torch.equal(frame[:, :, :256], frame[:, :, 256:])
    with pytest.raises(ValueError, match="Nonfinite"):
        motion_frame(np.full(40, np.nan), opened.numpy())
