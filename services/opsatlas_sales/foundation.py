"""Foundation knowledge for Tiberius from the Human's DT603 Part A paper.

The paper is the canonical account of what OpsAtlas is. Its text stays on this Mac: this module
extracts a local "product edition" (the sections that describe the product) into the git-ignored
runtime folder, and the curated records in ``corpus/foundation.json`` cite those sections.

Excluded by the Human's decisions of 25 September 2026: Section 2 and Appendix B (how the product
was built), the commercial scenarios and their validation (Sections 4.4, 4.5, D.4 and the P50
paragraph in Section 6), references, Appendix E (links and an assessor's contact), Appendix F
(the generative AI log) and an editing note left in Appendix A.

    .venv/bin/python -m services.opsatlas_sales.foundation --paper "/path/to/DT603 Part A.pdf"
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from .workspace import REPO

FOUNDATION = REPO / '.runtime/opsatlas-sales-foundation'
CORPUS = Path(__file__).parent / 'corpus'

# (file, title, start heading, end heading, passages removed from the section)
SECTIONS = [
    ('01-business-problem.md', 'DT603 Part A · 1 Business problem and delivered scope',
     '1. Business problem and delivered scope', '2. Project Plan, Risk and Delivery Management', []),
    ('03-1-architecture.md', 'DT603 Part A · 3.1 Implemented solution architecture',
     '3.1 Implemented solution architecture', '3.2 Working solution walkthrough', []),
    ('03-2-walkthrough.md', 'DT603 Part A · 3.2 Working solution walkthrough',
     '3.2 Working solution walkthrough', '3.3 Delivered scope and boundaries', []),
    ('03-3-scope.md', 'DT603 Part A · 3.3 Delivered scope and boundaries',
     '3.3 Delivered scope and boundaries', '4. Data preparation and analytical techniques', []),
    ('04-analytics-evaluation.md', 'DT603 Part A · 4.1–4.3 Analytics and RAG–OAG evaluation',
     '4. Data preparation and analytical techniques', '4.4 Commercial analysis', []),
    ('05-assurance-governance.md', 'DT603 Part A · 5 Assurance, governance and maintainability',
     '5. Assurance, governance and maintainability', '6. Stakeholder value and business impact', []),
    ('06-stakeholder-value.md', 'DT603 Part A · 6 Stakeholder value and business impact',
     '6. Stakeholder value and business impact', '7. Conclusion',
     [('The commercial analysis in Section 4', 'The more significant next step')]),
    ('07-conclusion.md', 'DT603 Part A · 7 Conclusion', '7. Conclusion', 'References', []),
    ('a-ontology.md', 'DT603 Part A · Appendix A Evolution from RAG to OAG',
     'Appendix A: Evolution from Retrieval-Augmented', 'Appendix B: Human-Led Multi-Agent',
     [('One subtle correction there', 'A.6 Enterprise Activity Model')]),
    ('c-technical-reference.md', 'DT603 Part A · Appendix C Technical architecture reference',
     'Appendix C: Technical Architecture and Implementation', 'Appendix D: Analytics Methods', []),
    ('d-analytics-methods.md', 'DT603 Part A · Appendix D.1–D.3 Analytics methods and evaluation',
     'Appendix D: Analytics Methods', 'D.4 Commercial model and sensitivity analysis', []),
    ('d-6-limitations.md', 'DT603 Part A · Appendix D.6 Limitations and interpretation',
     'D.6 Limitations and interpretation', 'Appendix E: Demonstration and Project Evidence', []),
]


def paper_text(pdf):
    from pypdf import PdfReader

    # Page breaks fall mid-paragraph: strip each page's edges so a break is not read as a new paragraph.
    pages = [(page.extract_text() or '').strip() for page in PdfReader(str(pdf)).pages]
    return '\n'.join(pages)


HEADING = re.compile(r'^(?:\d+(?:\.\d+)*\.?|[A-D]\.\d+(?:\.\d+)?|Appendix [A-F]:)\s+[A-Z][^.:;]{2,80}$|'
                     r'^(?:Govern the knowledge|Ask and verify|Explore process and operating intelligence|Measure and improve)$')


def flatten(text):
    """PDF lines to paragraphs: join wrapped lines, keep headings and bullets, drop figure captions."""
    text = re.sub(r'(\w)-\n(\w)', r'\1-\2', text)
    lines = [line.strip() for line in text.splitlines()]
    paragraphs, current, caption = [], [], False
    for line in lines:
        if caption:  # a figure caption wrapped over several lines
            caption = not line.endswith('.')
            continue
        if HEADING.match(line):
            if current:
                paragraphs.append(' '.join(current))
                current = []
            paragraphs.append('## ' + line)
            continue
        if re.match(r'^Figure [A-Z]?\d+\.', line):
            if current:
                paragraphs.append(' '.join(current))
                current = []
            caption = not line.endswith('.')
            continue
        if not line:
            if current:
                paragraphs.append(' '.join(current))
                current = []
            continue
        if line.startswith('•'):
            if current:
                paragraphs.append(' '.join(current))
            current = ['- ' + line.lstrip('• ').strip()]
            continue
        current.append(line)
        if re.search(r'[.:;]$', line):
            paragraphs.append(' '.join(current))
            current = []
    if current:
        paragraphs.append(' '.join(current))
    return '\n\n'.join(re.sub(r'\s{2,}', ' ', p).strip() for p in paragraphs if p.strip())


def section(text, start, end, removals):
    begin = text.index(start)
    finish = text.index(end, begin + len(start))
    body = text[begin:finish]
    for cut_from, cut_to in removals:
        a = body.index(cut_from)
        b = body.index(cut_to, a)
        body = body[:a] + body[b:]
    return body


def extract(pdf, out=FOUNDATION):
    """Write the product edition as one Markdown file per section, plus a manifest."""
    pdf = Path(pdf)
    raw = paper_text(pdf)
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for name, title, start, end, removals in SECTIONS:
        body = flatten(section(raw, start, end, removals))
        (out / name).write_text(f'# {title}\n\n{body}\n')
        files.append({'file': name, 'title': title, 'chars': len(body)})
    manifest = {'schema': 1, 'source': pdf.name, 'sha256': hashlib.sha256(pdf.read_bytes()).hexdigest(),
                'sections': files, 'note': 'Local product edition of the DT603 Part A paper; not committed.'}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def active(root=FOUNDATION):
    """(corpus path, reference folder) for seeding: the paper foundation when it has been extracted."""
    if (root / 'manifest.json').exists():
        return CORPUS / 'foundation.json', root
    return CORPUS / 'product.json', None


def topics(root=FOUNDATION):
    corpus, _ = active(root)
    return tuple(card['id'] for card in json.loads(corpus.read_text()))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--paper', required=True, type=Path)
    manifest = extract(parser.parse_args().paper)
    for item in manifest['sections']:
        print(f"{item['chars']:6} chars  {item['file']}")
    print('Product edition written to', FOUNDATION)


if __name__ == '__main__':
    main()
