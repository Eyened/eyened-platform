"""ProjectMember's composite PK is the 'exactly one role per project' rule."""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from eyened_orm import Creator, ProjectMember
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.utils.factories import make_creator, make_project


def test_a_creator_cannot_hold_two_roles_in_one_project(session):
    """The composite PK enforces v0.3's 'exactly one role per project'."""
    creator = make_creator(session, "alice")
    project = make_project(session, "P")
    session.add(
        ProjectMember(
            CreatorID=creator.CreatorID, ProjectID=project.ProjectID, Role=ProjectRole.grader
        )
    )
    session.flush()
    session.add(
        ProjectMember(
            CreatorID=creator.CreatorID,
            ProjectID=project.ProjectID,
            Role=ProjectRole.read_only,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_new_creators_are_neither_admin_nor_inactive(session):
    """Both flags default to false, so /auth/register and OIDC land safe."""
    creator = Creator(CreatorName="bob", IsHuman=True)
    session.add(creator)
    session.commit()
    creator_id = creator.CreatorID  # capture before expunge; session.commit() above
    # expires attributes (expire_on_commit=True), and expunge_all() then detaches
    # the instance, so a post-expunge access would raise DetachedInstanceError.
    session.expunge_all()

    row = session.get(Creator, creator_id)
    assert row.IsAdmin is False
    assert row.Inactive is False
