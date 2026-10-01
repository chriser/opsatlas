"""Regression boundaries for live turn endpointing."""

from services.sme_interviewer.endpointing import TurnBoundary


def test_endpoint_needs_confidence_ignores_stale_audio_and_closes_quickly():
    boundary = TurnBoundary()
    boundary.voiced(16000)
    boundary.result(.8, 16000)             # positive but not confident: one estimate cannot close
    assert not boundary.complete(16000 + 4800) and not boundary.complete(16000 + 7999)
    boundary.voiced(24000)
    boundary.result(.99, 16000)            # stale audio is ignored
    assert boundary.hits == 0 and not boundary.complete(24000 + 4800)
    boundary.result(.9, 24000)             # confident: 0.3 s of silence is enough
    assert not boundary.complete(24000 + 4799)
    assert boundary.complete(24000 + 4800)
    boundary.result(.2, 24000)             # the latest estimate says unfinished
    assert not boundary.complete(24000 + 40000)


def test_two_positive_estimates_close_after_half_a_second_and_fallback_is_opt_in():
    boundary = TurnBoundary()
    boundary.voiced(0)
    boundary.result(.75, 0)
    boundary.result(.8, 0)
    assert not boundary.complete(7999) and boundary.complete(8000)
    patient, relaxed = TurnBoundary(), TurnBoundary(fallback=40000)
    for b in (patient, relaxed):
        b.voiced(0)
        b.result(.3, 0)
    assert not patient.complete(200000)
    assert not relaxed.complete(39999) and relaxed.complete(40000)
    assert not patient.due(3199) and patient.due(3200)
