"""Money fidelity at the text-to-speech boundary."""

import pytest

from services.sme_interviewer.spoken_text import for_speech


@pytest.mark.parametrize(
    ("original", "spoken"),
    [
        (
            "The limit is £15,000, not £50,000. Approval happens before activation.",
            "The limit is fifteen thousand pounds, not fifty thousand pounds. Approval happens before activation.",
        ),
        ("£1", "one pound"),
        ("£0", "zero pounds"),
        ("£1.00", "one pound"),
        ("£0.01", "one penny"),
        ("£0.50", "fifty pence"),
        ("£1.01", "one pound and one penny"),
        ("£21.5", "twenty-one pounds and fifty pence"),
        ("£1,001.09", "one thousand and one pounds and nine pence"),
        ("£1,100", "one thousand one hundred pounds"),
        ("£1,234.56", "one thousand two hundred and thirty-four pounds and fifty-six pence"),
        ("£1,000,001", "one million and one pounds"),
        ("£1000000000", "one billion pounds"),
        ("-£15.20", "minus fifteen pounds and twenty pence"),
        ("−£15", "minus fifteen pounds"),
        ("+£2", "plus two pounds"),
        ("£ 50.", "fifty pounds."),
        ("Between £15 and £50, before approval.", "Between fifteen pounds and fifty pounds, before approval."),
    ],
)
def test_sterling_preserves_value_and_sentence(original, spoken):
    assert for_speech(original) == spoken
    assert for_speech(spoken) == spoken  # Rendered text is stable across repeat calls.


@pytest.mark.parametrize(
    "text",
    [
        "Keep 15,000, £, VAT and 50% as captured.",
        "£15k",
        "£1.234",
        "£1,23",
        "£1,2345",
        "£1000000000000",
        "£15million",
        "ref£123",
        "£-15",
        "£1e3",
        "£15.00.50",
        "GBP 15,000",
        "£15,000.000",
        "££12",
    ],
)
def test_unsupported_or_non_currency_text_is_not_partially_rewritten(text):
    assert for_speech(text) == text


def test_original_transcript_remains_separate():
    transcript = {"text": "£15,000, not £50,000", "revision": 1}
    spoken = for_speech(transcript["text"])
    assert transcript == {"text": "£15,000, not £50,000", "revision": 1}
    assert spoken == "fifteen thousand pounds, not fifty thousand pounds"
