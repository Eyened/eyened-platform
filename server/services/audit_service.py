from __future__ import annotations

import enum
import json
import logging
import math
from datetime import date, datetime, timezone

from fastapi import Depends
from sqlalchemy import event
from sqlalchemy.orm import Session

from eyened_orm import AuditLog

from ..db import get_db
from .acting_user import ActingUser

_AUDIT_LOGGER = logging.getLogger("eyened.audit")
_BUFFER_KEY = "_audit_events"
# {id(SessionTransaction): buffer length when that SAVEPOINT opened}
_MARK_KEY = "_audit_savepoint_marks"


def _finite(o: object) -> object:
    """Replace non-finite floats with their names, recursing into the containers
    ``diff()`` can produce.

    ``json.dumps`` serializes floats itself, so ``default=_json_safe`` is never
    consulted for them: ``NaN``/``Infinity``/``-Infinity`` would be emitted as
    those non-standard JSON literals, and ``json.loads`` accepts them straight
    back, so the normalization round-trip does not catch them. MySQL's JSON
    column validates its input and rejects them, which turns an audited write of
    a nullable float (``Segmentation.Threshold``) into a 500. SQLite stores JSON
    as TEXT and accepts anything, so no test on the sqlite fixture can see this.
    """
    if isinstance(o, float) and not math.isfinite(o):
        return str(o)  # 'nan' / 'inf' / '-inf'
    if isinstance(o, dict):
        return {k: _finite(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_finite(v) for v in o]
    return o


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
    for the post-commit stdout mirror (Sink 2)."""

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
        # allow_nan=False is the strictness MySQL's JSON validator applies; with
        # _finite() ahead of it nothing should trip it, so it stands as a loud
        # guard rather than a silent pass-through if a new container shape slips
        # a non-finite float past _finite.
        safe_changes = (
            json.loads(
                json.dumps(_finite(changes), default=_json_safe, allow_nan=False)
            )
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
        self._session.flush()  # assign the AuditLog PK before buffering the event
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


def _drain(session: Session) -> None:
    session.info.pop(_MARK_KEY, None)
    for payload in session.info.pop(_BUFFER_KEY, []):
        _AUDIT_LOGGER.info(json.dumps(payload, default=str))


def _mark_savepoint(session: Session, transaction) -> None:
    """Record how many events were already buffered when a SAVEPOINT opened, so
    its rollback can drop the events staged inside it and only those."""
    if transaction.nested:
        session.info.setdefault(_MARK_KEY, {})[id(transaction)] = len(
            session.info.get(_BUFFER_KEY, [])
        )


def _rollback(session: Session, previous_transaction) -> None:
    """Discard the buffered events the rolled-back scope staged, and only those.

    ``record()`` buffers an event and flushes its AuditLog row together, so
    buffer position and row staging move in lockstep: truncating to the mark
    taken when the SAVEPOINT opened drops exactly the events whose rows the
    savepoint rollback discards, and keeps the earlier ones — whose rows are
    still staged and still commit.

    Clearing the whole buffer here instead (the previous behaviour) silently
    lost events that the AuditLog table went on to keep, so the two sinks
    disagreed. ``prev.nested`` is the discriminator, not
    ``session.in_nested_transaction()`` — that reads False for a single-level
    savepoint rollback and True for the inner one of two, so it cannot tell the
    two cases apart.

    ``after_soft_rollback`` fires for every rollback, real or nested, so it
    subsumes ``after_rollback`` and this is the only listener that clears.
    """
    if not previous_transaction.nested:
        session.info.pop(_BUFFER_KEY, None)
        session.info.pop(_MARK_KEY, None)
        return
    # Marks are cleaned up here and at drain time rather than in
    # after_transaction_end, which fires *before* this for a nested rollback and
    # would take the mark away before it could be read.
    mark = session.info.get(_MARK_KEY, {}).pop(id(previous_transaction), 0)
    buffer = session.info.get(_BUFFER_KEY)
    if buffer is not None:
        del buffer[mark:]


# Register once at import. Listening on the base Session class covers both the
# production EyenedSession subclass and the plain Session used in tests.
event.listen(Session, "after_commit", _drain)
event.listen(Session, "after_transaction_create", _mark_savepoint)
event.listen(Session, "after_soft_rollback", _rollback)


def get_audit_service(db: Session = Depends(get_db)) -> AuditService:
    """Default AuditService wiring for FastAPI ``Depends()``.

    Enabled/level come from settings; kept import-local so ORM-only test
    imports of this module do not require the full server settings stack.
    """
    from ..config import settings

    _AUDIT_LOGGER.setLevel(settings.db_log.level)
    return AuditService(db, enabled=settings.db_log.enabled)
