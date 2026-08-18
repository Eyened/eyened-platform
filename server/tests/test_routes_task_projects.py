"""The task list computes project spans only when asked."""
from __future__ import annotations


def test_list_omits_projects_by_default(client, spanning):
    """None means "not requested"; [] would claim a two-project task spans nothing."""
    assert all(t["projects"] is None for t in client.get("/task").json())
