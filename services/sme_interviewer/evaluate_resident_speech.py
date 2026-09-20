"""Synthetic development comparison; not a held-out or headset acceptance test."""

import asyncio
import json
import time

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from services.sme_interviewer.resident import Resident
from services.sme_interviewer.speech import ROOT, SpeechWorker

CASES = [
    ("numbers", "The limit is £15,000, not £50,000. Approval happens before activation."),
    ("negation", "Finance did not approve it. The supplier remained on hold."),
    ("acronyms", "The SME checks the ERP record and the VAT number."),
    ("hesitation", "The request, um, arrived on Monday, and after checking the details, we asked for approval."),
]


async def main():
    root = ROOT / ".runtime" / "continuous-evaluation"
    root.mkdir(parents=True, exist_ok=True)
    worker = SpeechWorker("kokoro", ROOT / ".runtime")
    cases = []
    try:
        for name, text in CASES:
            path = root / (name + ".wav")
            if not path.exists():
                await worker.synthesize("A", text, path)
            audio, sr = sf.read(path)
            audio = resample_poly(audio, 16000, sr).astype("<f4")
            cases.append((name, text, audio))
        noisy = cases[0][2] + np.random.default_rng(71).normal(0, 0.015, len(cases[0][2])).astype("<f4")
        cases.append(("numbers-with-noise", CASES[0][1], np.clip(noisy, -1, 1)))
    finally:
        await worker.close()
    report = []
    for model in ("ggml-base.en.bin", "ggml-small.en.bin"):
        worker = Resident(ROOT / ".runtime", "asr", model)
        try:
            start = time.perf_counter()
            await worker.start()
            print("startup", model, round(time.perf_counter() - start, 3), flush=True)
            for name, expected, audio in cases:
                start = time.perf_counter()
                result = await worker.infer(audio.astype("<f4").tobytes())
                row = dict(model=model, case=name, expected=expected, result=result, seconds=round(time.perf_counter() - start, 3))
                report.append(row)
                print(json.dumps(row), flush=True)
        finally:
            await worker.close()
    (root / "asr-comparison.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
