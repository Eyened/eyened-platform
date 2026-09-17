"""The admin gate is in AdminService.__init__, and nothing else enforces it.

Deleting that line is not a 403 regression: non-admins get a 500 (apply_scope
raises KeyError, which is in no status map) and admins get an unfiltered
listing. Both look green to a route test that only checks the happy path.
"""
from __future__ import annotations

import pytest

from eyened_orm.authz.errors import PermissionDeniedError
from eyened_orm.repositories.creator_repository import CreatorRepository
from eyened_orm.repositories.project_member_repository import ProjectMemberRepository
from eyened_orm.repositories.project_repository import ProjectRepository
from eyened_orm.utils.factories import admin_scope, scope_for
from server.services.admin_service import AdminService


def _build(session, scope):
    return AdminService(
        CreatorRepository(session, scope=scope),
        ProjectRepository(session, scope=scope),
        ProjectMemberRepository(session),
        scope=scope,
    )


def test_a_non_admin_scope_is_refused_at_construction(session):
    with pytest.raises(PermissionDeniedError) as excinfo:
        _build(session, scope_for())

    # entity="Admin", not an ORM entity name: one constructor call covers all
    # three endpoints, so any ORM name contradicts the path logged beside it.
    assert excinfo.value.entity == "Admin"


def test_an_admin_scope_constructs(session):
    """Positive control: the refusal above also passes against a constructor
    that raises unconditionally."""
    _build(session, admin_scope())
