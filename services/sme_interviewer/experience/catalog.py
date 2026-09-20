"""Identical fictional material across candidates; identities are hidden during rating."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / '.runtime' / 'experience'
VOICES = {
    'kokoro-f': {'engine': 'kokoro', 'voice': 'bf_isabella', 'name': 'Kokoro · Isabella (current B)'},
    'kokoro-m': {'engine': 'kokoro', 'voice': 'bm_george', 'name': 'Kokoro · George'},
    'pocket-f': {'engine': 'pocket', 'voice': 'anna', 'name': 'Pocket TTS · Anna'},
    'pocket-m': {'engine': 'pocket', 'voice': 'charles', 'name': 'Pocket TTS · Charles'},
    'chatterbox-f': {'engine': 'chatterbox', 'voice': 'anna', 'name': 'Chatterbox Turbo · VCTK p228'},
    'chatterbox-m': {'engine': 'chatterbox', 'voice': 'charles', 'name': 'Chatterbox Turbo · VCTK p254'},
    'qwen-f': {'engine': 'qwen', 'voice': 'anna', 'name': 'Qwen3 TTS Base 0.6B · VCTK p228'},
    'qwen-m': {'engine': 'qwen', 'voice': 'charles', 'name': 'Qwen3 TTS Base 0.6B · VCTK p254'},
}
REFERENCES = {'anna': 'p228_023_enhanced.wav', 'charles': 'p254_023_enhanced.wav'}
# Independently recognised by local Whisper for both supplied reference clips.
REFERENCE_TEXT = (
    'If the red of the second bow falls upon the green of the first, the result is to give a bow '
    'with an abnormally wide yellow band, since red and green light when mixed form yellow.'
)
PROMPTS = {
    'pronunciation': ('Pronunciation', 'Before we recap, could you explain what Finance checked? Who gave the final approval?'),
    'numbers': ('Amounts and negation', 'The limit is fifteen thousand pounds, not fifty thousand pounds. '
                'Approval happens before activation.'),
    'curiosity': ('A natural follow-up', 'What made you pause at that point? Was there something unusual about this particular request?'),
    'uncertainty': ('Room for uncertainty', 'That is fine. You do not need to guess. We can leave that point open and come back to it.'),
    'recap': ('A longer recap', 'Let me check the sequence. The manager approved the request, then the supplier was activated. '
              'The company could access the information after that. What is still unclear is who checked the bank details. '
              'Have I understood the order correctly?'),
    'correction': ('Accepting a correction', 'Ah, thank you. I had the order wrong. '
                   'The checks came first. What happened after those checks?'),
    'patience': ('An invitation to take time', 'Take your time. There is no rush.'),
    'acknowledge': ('A brief listening sound', 'Mm-hm.'),
    'words': ('Words in isolation', 'Finance. Recap. Finance. Recap.'),
    'abbreviations': ('Abbreviations in context', 'The SME reviews the ERP record. '
                      'We will keep the VAT check separate from final approval.'),
}
