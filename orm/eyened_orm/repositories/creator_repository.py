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

    def list_authenticatable(self) -> list[Creator]:
        """Every human, active creator that can authenticate -- the cutover set.

        ``PasswordHash.is_not(None)`` rather than a password-validity check on
        purpose. ``disable_password`` writes ``'!'``, a valid hash that verifies
        nothing, and OIDC-provisioned accounts get exactly that (auth.py's
        create_user call passes password=None). They can authenticate -- just
        not by password -- so they belong in the cutover grant. Only rows with
        no PasswordHash at all (AI models, attribution-only creators) are
        skipped.
        """
        return list(
            self._session.scalars(
                select(Creator).where(
                    Creator.IsHuman.is_(True),
                    Creator.Inactive.is_(False),
                    Creator.PasswordHash.is_not(None),
                )
            ).all()
        )

    def save(self, creator: Creator) -> None:
        """Persist in-place mutations to ``creator`` within the caller's transaction.

        ``creator`` names what is being saved; the flush covers the whole unit
        of work, deliberately not just this row.
        """
        self._session.flush()
