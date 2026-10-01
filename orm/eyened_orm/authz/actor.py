"""Who a state change is attributed to.

Two variants and no third. ``ActingAdmin`` is an authenticated administrator;
``TrustedPath`` is a named write path v0.3 places outside RBAC enforcement --
the ``eorm`` CLI, and ``auth:register``, which creates a Creator before there
is an actor to name. An "unattributed" variant is deliberately absent: no
production call site omits attribution today, and defining the variant is what
would let one start.

Defined here rather than beside ``server/services/acting_user.py``'s
``ActingUser`` because ``AuditWriter`` and the administration classes are ORM
code, and importing from ``server/`` there would invert the dependency arrow.
The two are not unified: ``ActingUser`` reaches ``AuditService.record`` at ~30
call sites and is translated at that boundary.
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = ["ActingAdmin", "Actor", "TrustedPath"]


@dataclass(frozen=True)
class TrustedPath:
    """A named write path with no authenticated actor.

    ``path`` is the whole name -- ``"eorm grant"``, ``"auth:register"`` -- not a
    subcommand the writer prefixes. ``auth:register`` is the proof that no
    single prefix belongs in the writer, so the caller names itself.
    """

    path: str


@dataclass(frozen=True)
class ActingAdmin:
    """An authenticated actor, identified by ``Creator.CreatorID``.

    ``AuditLog.ActorID`` is a plain nullable integer rather than a foreign key,
    so an audit row outlives the ``Creator`` it names.
    """

    creator_id: int


Actor = TrustedPath | ActingAdmin
