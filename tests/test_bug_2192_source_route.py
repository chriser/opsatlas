"""Bug #2192: the unused Sales route that served a family document's text without checking its approval is gone.

GET /api/sales/source/{identifier} answered a withdrawn document's text (the design red team on REF S19b found it, 4
October 2026). No client called it (the panel and Tibi use other routes), so it is removed rather than guarded.
"""
from __future__ import annotations


def test_a_family_documents_text_is_not_served_by_the_removed_route(sales_workspace):
    app, client = sales_workspace.app, sales_workspace.client
    family = app.state.family_register.list()
    assert family, "the workspace seeds family documents"
    answered = client.get(f"/api/sales/source/{family[0].id}")
    assert answered.status_code == 404
    assert "text" not in answered.text

