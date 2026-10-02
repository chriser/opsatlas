import argparse
import wave

import numpy as np
import pytest
import torch

from experiments.local_avatar.speech_evaluate import latest_indices, mux_audio
from experiments.local_avatar.speech_motion import (
    SpeechMouthNet,
    audio_features,
    fit,
    history_features,
    interpolate_labels,
    mouth_measures,
    read_wave,
)


def spec():
    return {"sample_rate": 16000, "window_samples": 400, "hop_samples": 320, "fft_size": 512,
            "mel_bins": 80, "audio_offset_seconds": .176062}


def test_audio_features_preserve_source_offset_and_cannot_see_future_samples():
    rng = np.random.default_rng(7)
    original = rng.normal(size=1600).astype(np.float32)
    changed = original.copy()
    changed[600:] += 10
    times, first, _ = audio_features(original, spec())
    _, second, _ = audio_features(changed, spec())
    assert times[0] == .176062
    np.testing.assert_allclose(np.diff(times), .02)
    np.testing.assert_array_equal(first[:2], second[:2])
    assert not np.array_equal(first[2:], second[2:])
    assert first.shape == (5, 80) and np.isfinite(first).all()


def test_wave_reader_rejects_wrong_channel_or_rate(tmp_path):
    path = tmp_path / "synthetic.wav"
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(b"\0" * 400)
    with pytest.raises(ValueError, match="Expected mono"):
        read_wave(path, 16000)


def test_interpolation_rejects_large_missing_label_gaps_and_extrapolation():
    times = np.array([1., 1.06, 1.5, 1.56])
    positions = np.array([[1.], [2.], [3.], [4.]])
    values, valid = interpolate_labels(times, positions, np.array([.9, 1.03, 1.3, 1.56, 1.7]))
    assert valid.tolist() == [False, True, False, True, False]
    assert values[1, 0] == pytest.approx(1.5)


def test_temporal_model_is_causal_and_context_matches_whole_sequence():
    torch.manual_seed(43)
    model = SpeechMouthNet().eval()
    original = torch.randn(1, 80, 80)
    changed = original.clone()
    changed[:, 40:] += 100
    with torch.inference_mode():
        first, second = model(original), model(changed)
        chunk = model(original[:, 40 - model.context_frames:])[:, model.context_frames:]
    torch.testing.assert_close(first[:, :40], second[:, :40])
    torch.testing.assert_close(first[:, 40:], chunk, atol=1e-6, rtol=1e-5)


def test_speech_training_updates_weights_with_finite_gradients():
    torch.manual_seed(43)
    model = SpeechMouthNet()
    optimizer = torch.optim.AdamW(model.parameters(), lr=.01)
    initial = model.layers[0].weight.detach().clone()
    predicted = model(torch.randn(1, 40, 80))
    loss = (predicted - torch.randn_like(predicted)).square().mean()
    loss.backward()
    assert all(torch.isfinite(parameter.grad).all() for parameter in model.parameters())
    optimizer.step()
    assert not torch.equal(initial, model.layers[0].weight)
    assert sum(p.numel() for p in model.parameters()) == 67142


def test_linear_history_uses_only_current_and_past_features():
    features = torch.arange(25).float()[:, None]
    history = history_features(features)
    torch.testing.assert_close(history[20], torch.tensor([20., 15., 10., 0., 1.]))
    torch.testing.assert_close(history[2], torch.tensor([2., 0., 0., 0., 1.]))


def test_measurements_are_geometric_ratios_not_jaw_angles():
    points = np.full((1, 20, 2), .5)
    points[:, 0, 0], points[:, 1, 0] = .2, .6
    points[:, 14, 1], points[:, 15, 1] = .4, .6
    aperture, width = mouth_measures(points.reshape(1, -1))
    assert aperture[0] == pytest.approx(.5)
    assert width[0] == pytest.approx(102.4)


def test_video_motion_uses_latest_available_prediction_never_future_interpolation():
    indices = latest_indices(np.array([118.016062, 118.036062, 118.056062]),
                             np.array([118.016062, 118.03, 118.05]))
    assert indices.tolist() == [0, 0, 1]
    with pytest.raises(ValueError):
        latest_indices(np.array([118.016062]), np.array([118.]))


def test_audio_mux_seeks_in_waveform_clock_and_keeps_output_bounded(monkeypatch, tmp_path):
    commands = []
    monkeypatch.setattr("experiments.local_avatar.speech_evaluate.subprocess.run", lambda cmd, **kwargs: commands.append(cmd))
    mux_audio(tmp_path / "video.mp4", tmp_path / "wave.wav", tmp_path / "out.mp4", 118.016062, .176062, 12.)
    command = commands[0]
    assert command[command.index("-ss") + 1] == "117.840000"
    assert command[command.index("-t") + 1] == "12.000000"
    assert "-shortest" in command
    with pytest.raises(ValueError):
        mux_audio(tmp_path / "v", tmp_path / "a", tmp_path / "o", 0, .176062, 12)


def test_final_test_lock_rejects_speech_refitting(tmp_path):
    (tmp_path / "evaluation.json").write_text("{}")
    with pytest.raises(ValueError, match="Final test already evaluated"):
        fit(tmp_path, argparse.Namespace(epochs=10))
