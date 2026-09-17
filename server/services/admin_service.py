from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from eyened_orm import Creator, Project
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.authz.scope import AccessScope
from eyened_orm.repositories.creator_repository import CreatorRepository
from eyened_orm.repositories.project_member_repository import ProjectMemberRepository
from eyened_orm.repositories.project_repository import ProjectRepository

from ..db import get_db
from .access_scope import get_access_scope
from .exceptions import NotFoundError


class AdminService:
    """Read-only administration: users, one user's memberships, projects.

    The gate is the first line of ``__init__`` and it is load-bearing, not
    defensive: ``ProjectRepository`` routes every read through ``apply_scope``
    and ``Project`` is in no scoping registry, so a non-admin scope reaching it
    raises ``KeyError`` -- in no status map, so a 500. This call is what makes
    the refusal a 403. It sits in the constructor because a per-method check is
    per-method forgettable; every other service here has an assignment-only
    ``__init__``, and ``test_admin_service_gate.py`` pins the departure.
    """

    def __init__(
        self,
        creators: CreatorRepository,
        projects: ProjectRepository,
        members: ProjectMemberRepository,
        *,
        scope: AccessScope,
    ) -> None:
        scope.require_admin(entity="Admin")
        self.creators = creators
        self.projects = projects
        self.members = members
        self.scope = scope

    def list_users(self) -> list[Creator]:
        """Every human creator; the route reads per-row state off each one."""
        return self.creators.list_humans()

    def memberships_of_user(
        self, user_id: int
    ) -> list[tuple[int, str, ProjectRole]]:
        """One user's memberships as ``(project_id, project_name, role)``.

        Ordered by project name, matching ``MembershipAdministration.memberships_of``
        -- ``list_for_creator`` orders by ProjectID, so the CLI and the API would
        otherwise answer the same question differently.

        The ``None`` check is not defensive: ``Creator`` is in
        ``SAFE_UNFILTERED_ENTITIES`` and ``get_by_id`` is a bare ``session.get``,
        so without it a missing user returns ``[]`` and the endpoint answers 200
        -- indistinguishable from a real user holding nothing.

        Raises:
            NotFoundError: if no Creator carries ``user_id``.
        """
        if self.creators.get_by_id(user_id) is None:
            raise NotFoundError(f"User {user_id} not found")
        members = self.members.list_for_creator(user_id)
        names = self.projects.names_for(m.ProjectID for m in members)
        return sorted(
            ((m.ProjectID, names[m.ProjectID], m.Role) for m in members),
            key=lambda row: row[1],
        )

    def list_projects(self) -> list[tuple[Project, int]]:
        """Every project paired with its member count."""
        counts = self.projects.member_counts()
        return [
            (project, counts.get(project.ProjectID, 0))
            for project in self.projects.list_all()
        ]


def get_admin_service(
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
) -> AdminService:
    """Default AdminService wiring for FastAPI ``Depends()``."""
    return AdminService(
        CreatorRepository(db, scope=scope),
        ProjectRepository(db, scope=scope),
        ProjectMemberRepository(db),
        scope=scope,
    )
