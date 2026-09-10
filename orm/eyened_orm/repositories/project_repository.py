from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from eyened_orm import Project
from eyened_orm.authz.scope import AccessScope
from eyened_orm.authz.scoping import apply_scope

__all__ = ["ProjectRepository"]


class ProjectRepository:
    """Data access for Project rows.

    Every read goes through ``apply_scope``, which short-circuits an admin scope
    before consulting any registry and raises ``KeyError`` for anything else --
    ``Project`` is in none of ``scoping.py``'s three registries. That is
    deliberate and it is why the reads are written this way rather than as bare
    selects: a repository that accepted a ``scope`` and never used it would read
    as filtered while returning every row, which is the exact "silent no-op
    wearing a scoped name" ``apply_scope`` fails closed to prevent.

    P0's only caller is the ``eorm`` CLI's unbounded scope, and the admin
    endpoints that follow sit behind ``require_admin``. Deciding what a
    non-admin may read from this table is a change to the read policy; adding
    ``Project`` to a registry is what would make that call.

    ``scoped_one`` is not used for the single-row read: it has no
    ``SAFE_UNFILTERED_ENTITIES`` fallback and raises unconditionally, so it
    would reject an admin scope too.

    No ``get_by_id``: P0 resolves projects by name, and an id lookup lands with
    its first caller when step 2's URLs need one. Shipping it now would be an
    untested public method, which the repo's 80% patch-coverage gate would
    also flag.
    """

    def __init__(self, session: Session, *, scope: AccessScope) -> None:
        self._session = session
        self._scope = scope

    def get_by_name(self, name: str) -> Project | None:
        return self._session.scalars(
            apply_scope(
                select(Project).where(Project.ProjectName == name),
                Project,
                self._scope,
            )
        ).first()

    def all_ids(self) -> list[int]:
        """Every project id, ordered, for the cutover grant."""
        return [
            int(project_id)
            for project_id in self._session.scalars(
                apply_scope(select(Project.ProjectID), Project, self._scope).order_by(
                    Project.ProjectID
                )
            ).all()
        ]

    def names_for(self, project_ids: Iterable[int]) -> dict[int, str]:
        """``{project_id: name}`` for the given ids, in one query.

        Callers pass ids that came out of the database in the same transaction,
        so an id with no row is not an expected input and is simply absent from
        the result.
        """
        ids = list(project_ids)
        if not ids:
            return {}
        rows = self._session.execute(
            apply_scope(
                select(Project.ProjectID, Project.ProjectName).where(
                    Project.ProjectID.in_(ids)
                ),
                Project,
                self._scope,
            )
        ).all()
        return {int(project_id): name for project_id, name in rows}
