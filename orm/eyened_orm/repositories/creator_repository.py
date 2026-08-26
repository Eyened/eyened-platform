from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from eyened_orm import Creator
from eyened_orm.authz.scope import AccessScope


class CreatorRepository:
    """Data access for Creator rows (identity table; escalation-relevant under RBAC)."""

    def __init__(self, session: Session, *, scope: AccessScope) -> None:
        self._session = session
        self._scope = scope

    def get_by_id(self, creator_id: int) -> Creator | None:
        return self._session.get(Creator, creator_id)

    def get_by_name(self, name: str) -> Creator | None:
        return self._session.scalars(
            select(Creator).where(Creator.CreatorName == name)
        ).first()

    def get_by_employee_identifier(self, key: str) -> Creator | None:
        return self._session.scalars(
            select(Creator).where(Creator.EmployeeIdentifier == key)
        ).first()

    def add(self, creator: Creator) -> None:
        self._session.add(creator)
        self._session.flush()
