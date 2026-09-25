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
    assert len(CORPUS) == 21 and len({r['id'] for r in CORPUS}) == 21
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
    assert len(rows) == 21 and not any(r['eligible'] for r in rows)
    titles = {s.title for s in k.register.list()}
    assert 'DT603 Part A · 1 Business problem and delivered scope' in titles
    assert set(k.topics()) == {r['id'] for r in CORPUS}
    with pytest.raises(ValueError, match='Extract the foundation'):
        Knowledge(SourceRegister(workspace(tmp_path / 'other') / 'core')).seed(corpus, None)


def test_without_an_extracted_paper_the_starter_corpus_is_used(tmp_path):
    corpus, papers = foundation.active(tmp_path / 'missing')
    assert corpus.name == 'product.json' and papers is None


def test_the_demo_and_a_real_deployment_are_separate_records():
    records = {r['id']: r for r in CORPUS}
    real = records['real-deployment']
    assert real['status'] == 'planned' and real['text'].startswith('Planned, not delivered:')
    assert "organisation's own data" in real['text'] and 'proof of concept' in real['text']
    assert any(ref.startswith('services/opsatlas_sales/corpus/owner-direction/') for ref in real['references'])
    assert records['security']['status'] == 'available' and 'audit traces' in records['security']['text']
    assert 'proof of concept' in records['data']['title']


def test_new_corpus_records_join_as_pending_and_reviewed_ones_are_untouched(tmp_path):
    cards = json.loads((foundation.CORPUS / 'product.json').read_text())
    corpus = tmp_path / 'corpus.json'
    corpus.write_text(json.dumps(cards[:3]))
    k = Knowledge(SourceRegister(workspace(tmp_path / 'sales') / 'core'))
    first = k.seed(corpus)[0]
    k.decide(first['id'], first['sha256'], True)
    corpus.write_text(json.dumps(cards[:4]))
    rows = {r['id']: r for r in k.seed(corpus)}
    assert len(rows) == 4 and rows[first['id']]['eligible'] and rows[first['id']]['sha256'] == first['sha256']
    assert rows[cards[3]['id']]['approval'] == 'pending' and not rows[cards[3]['id']]['eligible']
    # Another corpus is never merged into a seeded workspace.
    other = tmp_path / 'other.json'
    other.write_text(json.dumps([{**cards[4], 'id': 'unrelated'}]))
    assert 'unrelated' not in {r['id'] for r in k.seed(other)}
