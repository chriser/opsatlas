import numpy as np
import pytest
import torch

from experiments.local_avatar.appearance import pack
from experiments.local_avatar.portrait_revision import ReferenceCompositor, render_revision


def geometry():
    angle = torch.arange(14) * (2 * torch.pi / 14)
    outer = torch.stack((128 + 36 * angle.cos(), 182 + 7 * angle.sin()), 1)
    angle = torch.arange(6) * (2 * torch.pi / 6)
    inner = torch.stack((128 + 27 * angle.cos(), 182 + angle.sin()), 1)
    eyes = [torch.stack((center + 16 * angle.cos(), 80 + 5 * angle.sin()), 1) for center in (80, 176)]
    return torch.cat((outer, inner, *eyes)).flatten() / 256


def test_neutral_prediction_preserves_reference_detail_and_cheeks_are_never_transferred():
    shape = geometry()
    torch.manual_seed(13)
    photo = torch.rand(3, 256, 256) * .3 + .3
    neutral = pack(torch.full((3, 256, 256), .4))
    compositor = ReferenceCompositor(photo, neutral, shape, shape)
    torch.testing.assert_close(compositor.delta(neutral, shape), torch.zeros_like(photo), atol=1e-7, rtol=0)
    changed = pack(torch.full((3, 256, 256), .8))
    delta = compositor.delta(changed, shape)
    # Nasolabial folds beside/above the mouth, crow's feet and background remain unchanged.
    assert delta[:, 150:175, 50:85].abs().max() == 0
    assert delta[:, 150:175, 172:205].abs().max() == 0
    assert delta[:, 70:95, 205:230].abs().max() == 0
    assert delta[:, :40].abs().max() == 0
    assert delta[:, 182, 128].abs().min() > .1
    assert torch.isfinite(delta).all()


def test_open_mouth_replaces_photo_lip_line_without_transferring_a_second_dark_line():
    closed = geometry()
    photo = torch.full((3, 256, 256), .5)
    photo[:, 181:184, 105:151] = .1
    neutral = pack(torch.full_like(photo, .5))
    compositor = ReferenceCompositor(photo, neutral, closed, closed)
    opened = closed.reshape(32, 2).clone() * 256
    opened[14:20, 1] = (opened[14:20, 1] - 182) * 15 + 182
    opened[:14, 1] = (opened[:14, 1] - 182) * 2 + 182
    generated = torch.full_like(photo, .5)
    generated[:, 170:195, 100:156] = .75
    result = photo + compositor.delta(pack(generated), opened.flatten() / 256)
    assert result[:, 182, 128].min() > .6
    assert torch.isfinite(result).all()
    np.testing.assert_allclose(result[:, :40], photo[:, :40])


def test_published_presentation_cannot_be_silently_overwritten(tmp_path):
    (tmp_path / "manifest.json").write_text("{}")
    with pytest.raises(ValueError, match="already published"):
        render_revision(tmp_path, tmp_path, tmp_path / "missing.wav")


def test_blink_uses_reference_eye_texture_and_leaves_mouth_and_eye_corners_intact():
    shape = geometry()
    photo = torch.full((3, 256, 256), .6)
    photo[:, 76:85, 72:89] = .1
    neutral = pack(torch.full_like(photo, .4))
    compositor = ReferenceCompositor(photo, neutral, shape, shape)
    blink = shape.reshape(32, 2).clone() * 256
    blink[20:26, 1] = (blink[20:26, 1] - 80) * .1 + 80
    delta = compositor.delta(neutral, blink.flatten() / 256)
    assert delta[:, 76, 80].min() > .3  # Iris is compressed rather than left open under a blended eyelid.
    assert delta[:, 150:].abs().max() == 0
    assert delta[:, 70:95, 40:55].abs().max() == 0
    assert delta[:, 70:95, 150:205].abs().max() == 0  # Other eye was not asked to blink.


def test_mouth_proportion_adjustment_enlarges_motion_without_changing_neutral_face():
    shape = geometry()
    photo = torch.full((3, 256, 256), .5)
    anchor = pack(photo)
    original = ReferenceCompositor(photo, anchor, shape, shape)
    enlarged = ReferenceCompositor(photo, anchor, shape, shape, mouth_width_scale=1.12, mouth_height_scale=1.08)
    torch.testing.assert_close(enlarged.delta(anchor, shape), torch.zeros_like(photo), atol=1e-7, rtol=0)
    moving = photo.clone()
    moving[:, 176:189, 114:142] = .1
    old_delta, new_delta = (compositor.delta(pack(moving), shape) for compositor in (original, enlarged))
    old_width = (old_delta.abs().sum(0) > .1).any(0).sum()
    new_width = (new_delta.abs().sum(0) > .1).any(0).sum()
    assert new_width > old_width
    assert new_delta[:, :120].abs().max() == 0
    assert new_delta[:, 145:175, 50:75].abs().max() == 0
    assert new_delta[:, 145:175, 181:205].abs().max() == 0


@pytest.mark.parametrize("width,height", [(float("nan"), 1), (float("inf"), 1), (.5, 1), (1, -1), (1, 2)])
def test_invalid_mouth_presentation_scales_are_rejected(width, height):
    shape = geometry()
    photo = torch.full((3, 256, 256), .5)
    with pytest.raises(ValueError, match="Mouth presentation scales"):
        ReferenceCompositor(photo, pack(photo), shape, shape, mouth_width_scale=width, mouth_height_scale=height)
