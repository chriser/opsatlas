import numpy as np
import pytest

from services.sme_interviewer.audio_seams import SeamRepair


def render(chunks, rate=24000):
    repair = SeamRepair(rate)
    audio = np.concatenate([*[repair.push(c) for c in chunks], repair.finish()])
    return audio, repair.repairs


def test_decoder_step_is_removed_without_losing_samples_or_modifying_other_audio():
    left = np.full(9600, 0.2, dtype=np.float32)
    right = np.full(9600, -0.1, dtype=np.float32)
    audio, repaired = render([left, right])
    assert repaired == 1 and len(audio) == len(left) + len(right)
    assert abs(audio[9600] - audio[9599]) < 1e-6
    np.testing.assert_array_equal(audio[:9552], left[:9552])
    np.testing.assert_array_equal(audio[9648:], right[48:])
    assert np.max(np.abs(audio)) <= 0.2


def test_continuous_voiced_waveform_and_silence_are_bit_exact():
    audio = (0.3 * np.sin(np.arange(28800) * 2 * np.pi * 180 / 24000)).astype(np.float32)
    output, repaired = render(np.array_split(audio, 9))
    np.testing.assert_array_equal(output, audio)
    assert repaired == 0
    output, repaired = render([np.zeros(10), np.zeros(800)])
    assert not np.any(output) and repaired == 0


def test_interior_transient_is_not_treated_as_chunk_seam():
    audio = np.zeros(1000, dtype=np.float32)
    audio[400] = 0.9
    output, repaired = render([audio])
    np.testing.assert_array_equal(output, audio)
    assert repaired == 0


def test_short_empty_and_non_finite_chunks():
    output, _ = render([np.array([0.1]), np.array([]), np.array([0.1])])
    np.testing.assert_array_equal(output, np.array([0.1, 0.1], dtype=np.float32))
    with pytest.raises(ValueError):
        render([np.array([float('nan')])])
