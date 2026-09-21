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
