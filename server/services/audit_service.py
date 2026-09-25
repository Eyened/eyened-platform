from __future__ import annotations

import json
import logging

from fastapi import Depends
from sqlalchemy import event
from sqlalchemy.orm import Session

from eyened_orm.audit_writer import AuditWriter
from eyened_orm.authz.actor import ActingAdmin, Actor, TrustedPath

from ..db import get_db
from .acting_user import ActingUser

_AUDIT_LOGGER = logging.getLogger("eyened.audit")
_BUFFER_KEY = "_audit_events"


def _to_actor(actor: ActingUser | None, trusted_path: str | None) -> Actor:
    """Translate this layer's two optional keywords into the ORM's Actor union.

    ``ActingUser`` and ``ActingAdmin`` are deliberately not unified: ~30 call
    sites pass ``ActingUser``, and ``Actor`` must live in the ORM, which cannot
    import from ``server/``. The translation is one function at the boundary.
    """
    if actor is not None and trusted_path is not None:
        raise ValueError("pass actor= or trusted_path=, not both")
    if actor is not None:
        return ActingAdmin(creator_id=actor.id)
    if trusted_path is not None:
        return TrustedPath(path=trusted_path)
    raise ValueError("record() requires actor= or trusted_path=")


class AuditService:
    """Writes the authoritative AuditLog row (Sink 1, via AuditWriter) and buffers
    a JSON event for the post-commit stdout mirror (Sink 2)."""

    def __init__(self, session: Session, *, enabled: bool = True) -> None:
        self._session = session
        self._enabled = enabled
        self._writer = AuditWriter(session)

    def record(
        self,
        *,
        action: str,
        entity: str,
        actor: ActingUser | None = None,
        trusted_path: str | None = None,
        entity_id: int | str | None = None,
        project_id: int | None = None,
        changes: dict | None = None,
    ) -> None:
        # The kill switch is checked before the actor is resolved, deliberately:
        # a disabled service writes nothing and validates nothing, which is the
        # behavior every existing caller and test already relies on.
        if not self._enabled:
            return
        row = self._writer.write(
            actor=_to_actor(actor, trusted_path),
            action=action,
            entity=entity,
            entity_id=entity_id,
            project_id=project_id,
            changes=changes,
        )
        # Derived from the row, not from parallel locals: the two sinks are then
        # incapable of reporting different data for the same event.
        self._session.info.setdefault(_BUFFER_KEY, []).append(
            {
                "ts": row.Timestamp.isoformat(),
                "actor_id": row.ActorID,
                "trusted_path": row.TrustedPath,
                "action": row.Action,
                "entity": row.Entity,
                "entity_id": row.EntityID,
                "project_id": row.ProjectID,
                "changes": row.Changes,
            }
        )

    @staticmethod
    def snapshot(entity: object, *fields: str) -> dict[str, object]:
        """Capture *fields*' current values before mutating ``entity``.

        Pair with ``diff``. The result holds plain Python values, so no later
        flush can affect it — unlike attribute history, which a flush clears.
        """
        return {field: getattr(entity, field) for field in fields}

    @staticmethod
    def diff(before: dict[str, object], entity: object) -> dict[str, dict[str, object]]:
        """Return ``{field: {"old": …, "new": …}}`` for the snapshotted fields
        whose value changed. Unchanged fields are omitted."""
        changes: dict[str, dict[str, object]] = {}
        for field, old in before.items():
            new = getattr(entity, field)
            if old != new:
                changes[field] = {"old": old, "new": new}
        return changes


def _drain(session: Session) -> None:
    for payload in session.info.pop(_BUFFER_KEY, []):
        _AUDIT_LOGGER.info(json.dumps(payload, default=str))


def _clear(session: Session) -> None:
    session.info.pop(_BUFFER_KEY, None)


# Register once at import. Listening on the base Session class covers both the
# production EyenedSession subclass and the plain Session used in tests.
event.listen(Session, "after_commit", _drain)
event.listen(Session, "after_rollback", _clear)
event.listen(Session, "after_soft_rollback", lambda s, prev: _clear(s))


def get_audit_service(db: Session = Depends(get_db)) -> AuditService:
    """Default AuditService wiring for FastAPI ``Depends()``.

    Enabled/level come from settings; kept import-local so ORM-only test
    imports of this module do not require the full server settings stack.
    """
    from ..config import settings

    _AUDIT_LOGGER.setLevel(settings.db_log.level)
    return AuditService(db, enabled=settings.db_log.enabled)
