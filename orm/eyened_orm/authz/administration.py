"""Membership administration, as plain functions over a Session.

The Click commands in ``commands/rbac.py`` are thin shells over these: the
logic is here so it can be unit-tested against the in-memory SQLite suite,
which cannot build the real ``Database()`` the CLI opens.

v0.3 places the CLI outside RBAC enforcement as a trusted path, so nothing here
authorizes its operator. Everything here **attributes**: each state change
writes an AuditLog row with TrustedPath set and ActorID NULL, which is the
combination the AuditLog model documents for exactly this.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit_log import AuditLog
from ..creator import Creator
from ..project import Project
from ..repositories.project_member_repository import ProjectMemberRepository
from .roles import ProjectRole

__all__ = [
    "GrantResult",
    "audit_trusted",
    "grant",
    "parse_role",
    "resolve_creator",
    "resolve_project",
    "revoke",
]


def parse_role(value: str) -> ProjectRole:
    """Convert a CLI string to a ProjectRole, naming the valid roles on failure.

    The conversion happens once, at the boundary; everything past it deals in
    the enum, so no downstream code compares role strings.
    """
    try:
        return ProjectRole[value]
    except KeyError:
        valid = ", ".join(r.name for r in ProjectRole)
        raise ValueError(f"unknown role {value!r}; valid roles are: {valid}") from None


def resolve_creator(session: Session, username: str) -> Creator:
    creator = session.scalars(
        select(Creator).where(Creator.CreatorName == username)
    ).first()
    if creator is None:
        raise LookupError(f"no creator named {username!r}")
    return creator


def resolve_project(session: Session, project_name: str) -> Project:
    project = session.scalars(
        select(Project).where(Project.ProjectName == project_name)
    ).first()
    if project is None:
        raise LookupError(f"no project named {project_name!r}")
    return project


def audit_trusted(
    session: Session,
    *,
    command: str,
    action: str,
    entity: str,
    entity_id: int | None = None,
    changes: dict | None = None,
) -> None:
    session.add(
        AuditLog(
            TrustedPath=f"eorm {command}",
            Action=action,
            Entity=entity,
            EntityID=None if entity_id is None else str(entity_id),
            Changes=changes,
        )
    )
    session.flush()


@dataclass(frozen=True)
class GrantResult:
    """The outcome of a `grant` call.

    ``previous`` is only meaningful when ``changed`` is True (the role that
    was replaced, or None for a brand-new membership). On the unchanged path
    it is set to the current ``role`` rather than None -- callers must guard
    on ``changed`` before reading it, not treat ``previous`` as authoritative
    on its own.
    """

    creator_id: int
    project_id: int
    project_name: str
    previous: ProjectRole | None
    role: ProjectRole
    changed: bool


def grant(
    session: Session, *, username: str, project_name: str, role: ProjectRole
) -> GrantResult:
    """Grant or change a role. Idempotent: an unchanged grant writes no audit row."""
    creator = resolve_creator(session, username)
    project = resolve_project(session, project_name)
    repository = ProjectMemberRepository(session)

    existing = repository.get(creator.CreatorID, project.ProjectID)
    if existing is not None and existing.Role is role:
        return GrantResult(
            creator_id=creator.CreatorID,
            project_id=project.ProjectID,
            project_name=project_name,
            previous=role,
            role=role,
            changed=False,
        )

    _, previous = repository.upsert(creator.CreatorID, project.ProjectID, role)
    audit_trusted(
        session,
        command="grant",
        action="INSERT" if previous is None else "UPDATE",
        entity="ProjectMember",
        changes={
            "creator_id": creator.CreatorID,
            "username": username,
            "project_id": project.ProjectID,
            "project_name": project_name,
            "role": role.name
            if previous is None
            else {"old": previous.name, "new": role.name},
        },
    )
    return GrantResult(
        creator_id=creator.CreatorID,
        project_id=project.ProjectID,
        project_name=project_name,
        previous=previous,
        role=role,
        changed=True,
    )


def revoke(session: Session, *, username: str, project_name: str) -> bool:
    """Remove a membership. Returns False when there was nothing to remove."""
    creator = resolve_creator(session, username)
    project = resolve_project(session, project_name)
    repository = ProjectMemberRepository(session)

    member = repository.get(creator.CreatorID, project.ProjectID)
    if member is None:
        return False
    previous = member.Role
    repository.delete(member)
    audit_trusted(
        session,
        command="revoke",
        action="DELETE",
        entity="ProjectMember",
        changes={
            "creator_id": creator.CreatorID,
            "username": username,
            "project_id": project.ProjectID,
            "project_name": project_name,
            "role": previous.name,
        },
    )
    return True
