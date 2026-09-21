"""Regression boundaries for the audition winner's live integration."""

import numpy as np
import pytest

from services.sme_interviewer.endpointing import TurnBoundary
from services.sme_interviewer.pocket_voice import OnsetTrim


def test_onset_trim_keeps_preroll_and_interior_pauses():
    trim = OnsetTrim()
    assert not len(trim.feed(np.zeros(24000)))
    result = trim.feed(np.concatenate([np.zeros(2400), np.ones(480) * .02]))
    assert len(result) == 1440  # Forty ms of pre-roll, then speech.
    interior = np.concatenate([np.zeros(24000), np.ones(240) * .02])
    np.testing.assert_array_equal(trim.feed(interior), interior.astype(np.float32))
    trim.feed([], final=True)


def test_silent_invalid_and_split_onsets():
    trim = OnsetTrim()
    for _ in range(30):
        trim.feed(np.zeros(24000))
    assert len(trim.pending) <= 1200
    with pytest.raises(ValueError):
        trim.feed([], final=True)
    with pytest.raises(ValueError):
        OnsetTrim().feed([float('nan')])
    trim = OnsetTrim()
    trim.feed(np.ones(120) * .02)
    assert len(trim.feed(np.ones(120) * .02)) == 240


def test_endpoint_cannot_seize_floor_on_one_estimate_or_stale_audio():
    boundary = TurnBoundary()
    boundary.voiced(16000)
    boundary.result(.9, 16000)
    assert not boundary.complete(32000)
    boundary.voiced(24000)
    boundary.result(.99, 16000)
    assert boundary.hits == 0
    boundary.result(.9, 24000)
    boundary.result(.95, 24000)
    assert not boundary.complete(39999)
    assert boundary.complete(40000)
    boundary.result(.2, 24000)
    assert not boundary.complete(48000)


def test_delivery_preserves_numbers_abbreviations_and_orders_pauses():
    from services.sme_interviewer.delivery import Delivery
    parts = Delivery().phrases('Dr. Jones set £15,000. It was 1.5 times the limit. What happened next?')
    assert [p.text for p in parts] == ['Dr. Jones set £15,000.', 'It was 1.5 times the limit.', 'What happened next?']
    assert [p.pause_after_ms for p in parts] == [450, 650, 0]
    with pytest.raises(ValueError):
        Delivery(tempo=.5)


def test_pitch_preserving_tempo_has_expected_duration_and_frequency():
    import shutil

    from services.sme_interviewer.delivery import paced_audio
    if not shutil.which('ffmpeg'):
        pytest.skip('Optional local voice runtime requires FFmpeg')
    rate = 24000
    tone = (.1 * np.sin(2 * np.pi * 440 * np.arange(rate * 2) / rate)).astype(np.float32)
    output = np.concatenate(list(paced_audio(iter([(tone, rate)]), rate, .9)))
    assert abs(len(output) / len(tone) - 1 / .9) < .03
    spectrum = abs(np.fft.rfft(output))
    peak = np.argmax(spectrum) * rate / len(output)
    assert abs(peak - 440) < 2
