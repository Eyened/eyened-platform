from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from eyened_orm import ProjectMember
from eyened_orm.authz.roles import ProjectRole


class ProjectMemberRepository:
    """Data access for ProjectMember rows.

    Deliberately takes no ``AccessScope``: this repository *builds* the scope,
    so requiring one would be circular. Its only constructor today is
    ``get_access_scope``; the membership CLI will be the second. It is the
    single exemption in the guard that requires every repository to take a
    scope as constructor state.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def roles_for(self, creator_id: int) -> dict[int, ProjectRole]:
        """The creator's project -> role map, in one indexed query."""
        rows = self._session.execute(
            select(ProjectMember.ProjectID, ProjectMember.Role).where(
                ProjectMember.CreatorID == creator_id
            )
        ).all()
        return {int(project_id): role for project_id, role in rows}

    def get(self, creator_id: int, project_id: int) -> ProjectMember | None:
        return self._session.get(
            ProjectMember, {"CreatorID": creator_id, "ProjectID": project_id}
        )

    def list_for_creator(self, creator_id: int) -> list[ProjectMember]:
        return list(
            self._session.scalars(
                select(ProjectMember)
                .where(ProjectMember.CreatorID == creator_id)
                .order_by(ProjectMember.ProjectID)
            ).all()
        )

    def upsert(
        self, creator_id: int, project_id: int, role: ProjectRole
    ) -> tuple[ProjectMember, ProjectRole | None]:
        """Grant or change a role; return the row and the role it replaced.

        The previous role is returned rather than looked up again by the caller
        so an idempotent grant can skip its audit row without a second query.
        """
        existing = self.get(creator_id, project_id)
        if existing is None:
            member = ProjectMember(
                CreatorID=creator_id, ProjectID=project_id, Role=role
            )
            self._session.add(member)
            self._session.flush()
            return member, None
        previous = existing.Role
        existing.Role = role
        self._session.flush()
        return existing, previous

    def delete(self, member: ProjectMember) -> None:
        self._session.delete(member)
        self._session.flush()
