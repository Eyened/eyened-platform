from __future__ import annotations

import enum
import json
import logging
from datetime import date, datetime, timezone

from fastapi import Depends
from sqlalchemy import event
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import get_history

from eyened_orm import AuditLog

from ..db import get_db
from .acting_user import ActingUser

_AUDIT_LOGGER = logging.getLogger("eyened.audit")
_BUFFER_KEY = "_audit_events"


def _json_safe(o: object) -> object:
    """``json.dumps(..., default=...)`` fallback for values ``diff()``/callers put
    in ``changes``. ``TagType``, ``TaskState``, ``SubTaskState`` and ``Laterality``
    are plain ``Enum`` subclasses (not ``str, Enum``), and ``AuditLog.Changes`` is a
    stock JSON column (no ``default=``); serializing a raw enum member or a
    datetime otherwise raises ``StatementError`` on flush. Scoped to this one
    normalization site so other JSON columns (``FormData``, ``TaskConfig``, ...)
    keep failing loudly on genuinely unserializable data."""
    if isinstance(o, enum.Enum):
        return o.value
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    return str(o)


class AuditService:
    """Writes the authoritative AuditLog row (Sink 1) and buffers a JSON event
    for the post-commit stdout mirror (Sink 2). See design §3."""

    def __init__(self, session: Session, *, enabled: bool = True) -> None:
        self._session = session
        self._enabled = enabled

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
        if not self._enabled:
            return
        ts = datetime.now(timezone.utc)
        actor_id = actor.id if actor is not None else None
        # Normalize once: both the AuditLog row and the stdout mirror must see the
        # same JSON-safe data. Round-tripping through json.dumps/loads (rather
        # than a shallow per-value map) also covers enums/datetimes nested inside
        # dicts or lists, which diff()'s {"old": ..., "new": ...} shape can produce.
        safe_changes = (
            json.loads(json.dumps(changes, default=_json_safe))
            if changes is not None
            else None
        )
        row = AuditLog(
            Timestamp=ts,
            ActorID=actor_id,
            TrustedPath=trusted_path,
            Action=action,
            Entity=entity,
            EntityID=None if entity_id is None else str(entity_id),
            ProjectID=project_id,
            Changes=safe_changes,
        )
        self._session.add(row)
        self._session.flush()  # surface integrity errors in-request; assign PK
        event_payload = {
            "ts": ts.isoformat(),
            "actor_id": actor_id,
            "trusted_path": trusted_path,
            "action": action,
            "entity": entity,
            "entity_id": row.EntityID,
            "project_id": project_id,
            "changes": safe_changes,
        }
        self._session.info.setdefault(_BUFFER_KEY, []).append(event_payload)

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

    @staticmethod
    def _diff_from_history(entity: object, *fields: str) -> dict:
        """Transitional: the pre-snapshot change map, kept only until every
        caller moves to ``snapshot``/``diff``. Do not add new callers.

        Derive a ``{field: {"old": …, "new": …}}`` change map from an entity's
        still-pending scalar mutations.

        Uses SQLAlchemy's attribute history (``get_history``), so it must be
        called *after* the in-place assignment(s) and *before* any ``flush()`` —
        a flush clears the pending history. Only scalar column attributes are
        supported; link/relationship changes stay explicit at the call site.
        Fields whose value did not actually change are omitted.
        """
        changes: dict[str, dict[str, object]] = {}
        for field in fields:
            history = get_history(entity, field)
            if not history.has_changes():
                continue
            changes[field] = {
                "old": history.deleted[0] if history.deleted else None,
                "new": history.added[0] if history.added else None,
            }
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
