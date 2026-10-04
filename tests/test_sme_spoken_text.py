"""Money fidelity and sentence boundaries at the text-to-speech boundary."""

import pytest

from services.sme_interviewer.spoken_text import for_speech, speech_sentences


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


def test_sentence_boundaries_preserve_amounts_titles_and_wording():
    text = 'Dr. Smith approved £15,000. Finance confirmed 1.5 days. "Ready?" Yes!'
    sentences = list(speech_sentences(text))
    assert sentences == ['Dr. Smith approved £15,000.', 'Finance confirmed 1.5 days.', '"Ready?"', 'Yes!']
    assert ' '.join(sentences) == text
    assert list(speech_sentences('   ')) == []


def test_a_long_reply_is_cut_into_parts_the_voice_can_take():
    """PI F21: a read-back of 1,347 characters was refused whole by the voice (600 a request) and shown only as text."""
    from services.sme_interviewer.spoken_text import SPEECH_PART, speech_parts

    short = 'Here is what I have. Is that right?'
    assert speech_parts(short) == [short]  # within one request: exactly as before
    path = ('The first path, Tobacco: the cashier requests ID from the customer; then the cashier asks which product they '
            'want; then the cashier locates the product in the dedicated drawer; then the cashier scans it on the point '
            'of sale; then the cashier confirms the age check; then the cashier adds the product to the basket. ')
    long = 'Here is what I have for Carrying out cashiering. ' + path * 3 + 'Is that right?'
    parts = speech_parts(long)
    assert len(long) > 1000 and len(parts) >= 3 and all(len(p) <= SPEECH_PART for p in parts)
    assert ' '.join(parts).split() == long.split()  # every word, in order
    one_sentence = '; '.join(f'then the cashier does step {n}' for n in range(60)) + '.'
    assert all(len(p) <= SPEECH_PART for p in speech_parts(one_sentence))
    assert ' '.join(speech_parts(one_sentence)).split() == one_sentence.split()
