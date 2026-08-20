"""upgrade_to_head's contract with alembic.

Alembic's own upgrade is mocked: what matters here is the wiring we own.
"""

import sqlalchemy as sa

from eyened_orm.utils.alembic_utils import upgrade_to_head


def test_upgrade_to_head_injects_a_borrowed_connection(monkeypatch):
    """The connection goes into cfg.attributes; env.py reads it to skip the prompt."""
    captured = {}

    def fake_upgrade(cfg, revision):
        captured["revision"] = revision
        captured["connection"] = cfg.attributes.get("connection")

    monkeypatch.setattr("alembic.command.upgrade", fake_upgrade)

    head = upgrade_to_head(sa.create_engine("sqlite://"))

    assert captured["revision"] == "head"
    assert isinstance(captured["connection"], sa.engine.Connection)
    assert head == "orm_baseline"
