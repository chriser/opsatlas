"""REF S6: SVG inserted into the panel cannot run anything; the picture it draws is kept."""
from assistant.process.svg_safety import REFUSED, safe_svg

PLANTED = (
    '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="100" height="40">'
    '<style>.box { fill: #eef; }</style>'
    '<script>alert("svg script")</script>'
    '<g data-node="step-1" class="box" onclick="alert(1)"><rect width="10" height="10" onload="alert(2)"/>'
    '<text x="2" y="20">Approve the supplier &amp; record it</text></g>'
    '<a xlink:href="javascript:alert(3)"><text>link</text></a><a href=" JaVaScRiPt:alert(4)"><text>two</text></a>'
    '<a href="#step-1"><text>fine</text></a>'
    '<foreignObject><div xmlns="http://www.w3.org/1999/xhtml"><img src="x" onerror="alert(5)"/></div></foreignObject>'
    '<set attributeName="href" to="javascript:alert(6)"/><use href="https://example.test/x.svg#a"/>'
    '<rect style="background: url(javascript:alert(7))" width="1" height="1"/>'
    '</svg>'
)


def test_a_script_planted_in_a_diagram_does_not_survive():
    out = safe_svg(PLANTED)
    low = out.lower()
    for bad in ("<script", "onclick", "onload", "onerror", "javascript:", "foreignobject", "<set", "<use", "alert("):
        assert bad not in low, bad
    # The picture stays: shapes, text, data attributes the canvas clicks on, styles and in-page links.
    assert 'data-node="step-1"' in out and "Approve the supplier &amp; record it" in out
    assert "<rect" in out and ".box { fill: #eef; }" in out and 'href="#step-1"' in out
    assert out.startswith("<svg") and 'xmlns="http://www.w3.org/2000/svg"' in out


def test_declarations_and_unreadable_markup_are_refused():
    assert safe_svg('<!DOCTYPE svg [<!ENTITY a "aaaa">]><svg xmlns="http://www.w3.org/2000/svg">&a;</svg>') == REFUSED
    assert safe_svg("<svg><g></svg>") == REFUSED
    assert safe_svg("<html><script>alert(1)</script></html>") == REFUSED
    assert safe_svg("") == "" and safe_svg(None) is None


def test_a_real_activity_canvas_draws_the_same_after_cleaning(tmp_path):
    from assistant.eam.model import build_eam_model
    from assistant.eam.render_activity import render_activity_svg
    from assistant.eam.taxonomy import TaxonomyConfig
    from assistant.ontology import OntologyStore

    svg = render_activity_svg(build_eam_model(OntologyStore(tmp_path / "o.db"), TaxonomyConfig.load()))
    cleaned = safe_svg(svg)
    assert cleaned != REFUSED and cleaned.count("<rect") == svg.count("<rect") and cleaned.count("<text") == svg.count("<text")
