"""Creator reads for the administration path."""
from __future__ import annotations

from eyened_orm.repositories import CreatorRepository
from eyened_orm.utils.factories import admin_scope, make_creator


def test_list_humans_returns_people_name_ordered(session):
    make_creator(session, "bob")
    make_creator(session, "alice")
    make_creator(session, "unet-v3", is_human=False)
    session.commit()

    repo = CreatorRepository(session, scope=admin_scope())
    assert [c.CreatorName for c in repo.list_humans()] == ["alice", "bob"]


def test_list_humans_keeps_the_rows_list_authenticatable_drops(session):
    """The two predicates differ on purpose: who is a person, not who can log in.

    A deactivated account and a legacy password-only account are exactly what an
    administrator opens the console to find.
    """
    live = make_creator(session, "alice")
    live.PasswordHash = "$argon2id$v=19$m=65536,t=3,p=4$placeholder"
    deactivated = make_creator(session, "bob")
    deactivated.PasswordHash = "$argon2id$v=19$m=65536,t=3,p=4$placeholder"
    deactivated.Inactive = True
    legacy = make_creator(session, "carol")
    legacy.Password = b"0" * 32
    session.commit()

    repo = CreatorRepository(session, scope=admin_scope())
    assert {c.CreatorName for c in repo.list_humans()} == {"alice", "bob", "carol"}
    assert {c.CreatorName for c in repo.list_authenticatable()} == {"alice"}
