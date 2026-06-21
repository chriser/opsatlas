"""Constrained, grounding-only prompt (mirrors the benchmark answer contract)."""

from __future__ import annotations

REFUSAL = "I do not have that information in the approved knowledge base."

SYSTEM = (
    "You are a process-knowledge assistant. Answer the QUESTION using ONLY the EVIDENCE "
    "below, which is drawn from an approved, anonymised knowledge base.\n"
    "Rules:\n"
    "- Use only the evidence. Do not invent, do not use general knowledge, do not guess.\n"
    "- Do not fuzzy-match to a closest-sounding answer.\n"
    "- Give EITHER a grounded answer OR, only when the evidence does not contain the "
    f'answer, the single sentence: "{REFUSAL}". Never give both, and never repeat it.\n'
    "- Do not disclose real names, system names or commercial data.\n"
    "- Cite the evidence you used with its [n] marker.\n"
    "- Be clear and concise."
)


def build_prompt(question: str, evidence: list[dict]) -> str:
    lines = [SYSTEM, "", "EVIDENCE:"]
    for i, item in enumerate(evidence, start=1):
        lines.append(f"[{i}] ({item['heading']}) {item['text']}")
    lines += ["", f"QUESTION: {question}", "", "ANSWER:"]
    return "\n".join(lines)
