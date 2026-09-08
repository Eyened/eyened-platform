"""The authoritative AuditLog row writer.

One writer, because the same administration code is driven from two callers on
opposite sides of a package boundary: the ``eorm`` CLI (ORM) and, from step 2,
an authenticated admin API (server). ``server/services/audit_service.py`` held
the only complete writer, and ``orm`` cannot import from ``server`` -- so the
row write lives here and ``AuditService`` delegates to it, keeping the
server-side half: the ``enabled`` kill switch, the buffered stdout mirror and
its commit/rollback listeners.

This replaces ``authz/administration.py``'s ``audit_trusted``, a narrower
duplicate that had already diverged: it hardcoded an ``"eorm "`` prefix, never
set ``ActorID``, and dropped ``ProjectID`` -- including in ``grant``, which had
resolved the project two lines earlier and buried the id in ``Changes``.
"""
from __future__ import annotations

import enum
import json
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from .audit_log import AuditLog
from .authz.actor import ActingAdmin, Actor, TrustedPath

__all__ = ["AuditWriter"]


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


class AuditWriter:
    """Writes the authoritative AuditLog row (Sink 1), flushed for its PK.

    No ``enabled`` flag. ``audit_trusted`` wrote unconditionally because CLI
    attribution is mandatory; the kill switch is server-side policy and stays in
    ``AuditService``. Both existing behaviors are preserved exactly rather than
    replaced by a uniform one.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def write(
        self,
        *,
        actor: Actor,
        action: str,
        entity: str,
        entity_id: int | str | None = None,
        project_id: int | None = None,
        changes: dict | None = None,
    ) -> AuditLog:
        """Write one AuditLog row and return it.

        Returning the row is load-bearing: ``AuditService`` derives its stdout
        mirror from it rather than from a parallel set of locals, so the two
        sinks cannot drift.
        """
        match actor:
            case ActingAdmin(creator_id=creator_id):
                actor_id, trusted_path = creator_id, None
            case TrustedPath(path=path):
                actor_id, trusted_path = None, path
            case _:
                # No default branch: a variant added without a case here must
                # fail loudly rather than write a row with both columns NULL,
                # which reads as an unattributed change.
                raise TypeError(f"unrecognised Actor variant: {actor!r}")
        # Normalize once: both the AuditLog row and any mirror derived from it
        # must see the same JSON-safe data. Round-tripping through
        # json.dumps/loads (rather than a shallow per-value map) also covers
        # enums/datetimes nested inside dicts or lists, which diff()'s
        # {"old": ..., "new": ...} shape can produce.
        safe_changes = (
            json.loads(json.dumps(changes, default=_json_safe))
            if changes is not None
            else None
        )
        row = AuditLog(
            Timestamp=datetime.now(timezone.utc),
            ActorID=actor_id,
            TrustedPath=trusted_path,
            Action=action,
            Entity=entity,
            EntityID=None if entity_id is None else str(entity_id),
            ProjectID=project_id,
            Changes=safe_changes,
        )
        self._session.add(row)
        self._session.flush()  # assign the AuditLog PK before the caller reads it
        return row
