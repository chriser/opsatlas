"""Foundation knowledge from the Human's DT603 Part A paper (local product edition)."""
import json

import pytest

from assistant.sources.register import SourceRegister
from services.opsatlas_sales import claims, foundation
from services.opsatlas_sales.knowledge import Knowledge
from services.opsatlas_sales.workspace import workspace

CORPUS = json.loads((foundation.CORPUS / 'foundation.json').read_text())


def test_flatten_rejoins_wrapped_lines_keeps_headings_and_drops_captions():
    raw = ('3.2 Working solution walkthrough\nGovern the knowledge\nA knowledge owner can register\nmaterial and decide.\n'
           'Figure 8. Knowledge-source registration, approval and\ngovernance review.\n• first point;\n• second point.')
    text = foundation.flatten(raw)
    assert '## 3.2 Working solution walkthrough' in text and '## Govern the knowledge' in text
    assert 'A knowledge owner can register material and decide.' in text
    assert 'Figure 8' not in text and 'governance review.' not in text
    assert '- first point;' in text and '- second point.' in text


def test_sections_remove_excluded_passages():
    raw = ('6. Stakeholder value\nUseful. The commercial analysis in Section 4 shows £364,000. '
           'The more significant next step is feasibility.\n7. Conclusion')
    body = foundation.section(raw, '6. Stakeholder value', '7. Conclusion',
                              [('The commercial analysis in Section 4', 'The more significant next step')])
    assert '£364,000' not in body and 'The more significant next step' in body


def test_excluded_paper_parts_are_not_in_the_section_map():
    starts = ' '.join(start for _, _, start, _, _ in foundation.SECTIONS)
    assert 'Appendix B' not in starts and 'Appendix E' not in starts and 'Appendix F' not in starts
    assert '4.4 Commercial analysis' not in starts and '2. Project Plan' not in starts


def test_foundation_records_are_self_consistent_and_keep_their_qualifications():
    assert len(CORPUS) == 19 and len({r['id'] for r in CORPUS}) == 19
    for record in CORPUS:
        assert not claims.unsupported(record['text'], record['title'] + '. ' + record['text']), record['id']
        needed = claims.qualifier_for([record])
        assert not needed or claims.has_qualifier(record['text']), record['id']
    text = ' '.join(r['text'] for r in CORPUS)
    assert '£' not in text and 'NPV' not in text  # the Human chose to leave the commercial projections out


def test_seeding_from_the_product_edition_and_topics_follow_the_records(tmp_path):
    papers = tmp_path / 'foundation'
    papers.mkdir()
    for name, title, *_ in foundation.SECTIONS:
        (papers / name).write_text(f'# {title}\n\nSection text.\n')
    (papers / 'manifest.json').write_text('{}')
    corpus, found = foundation.active(papers)
    assert corpus.name == 'foundation.json' and found == papers
    assert foundation.topics(papers)[0] == 'overview' and 'activity-model' in foundation.topics(papers)
    k = Knowledge(SourceRegister(workspace(tmp_path / 'sales') / 'core'))
    rows = k.seed(corpus, papers)
    assert len(rows) == 19 and not any(r['eligible'] for r in rows)
    titles = {s.title for s in k.register.list()}
    assert 'DT603 Part A · 1 Business problem and delivered scope' in titles
    assert set(k.topics()) == {r['id'] for r in CORPUS}
    with pytest.raises(ValueError, match='Extract the foundation'):
        Knowledge(SourceRegister(workspace(tmp_path / 'other') / 'core')).seed(corpus, None)


def test_without_an_extracted_paper_the_starter_corpus_is_used(tmp_path):
    corpus, papers = foundation.active(tmp_path / 'missing')
    assert corpus.name == 'product.json' and papers is None
