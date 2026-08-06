"""RBAC administration commands.

v0.3 places the CLI and ``eorm`` outside RBAC enforcement as trusted paths, so
these commands do not authorize their operator. They **do** attribute: every one
writes an ``AuditLog`` row with ``TrustedPath`` set and ``ActorID`` NULL, which
is what the AuditLog model documents that combination for.
"""
from __future__ import annotations

from typing import Any

import click
from sqlalchemy.orm import Session

from ..audit_log import AuditLog
from ..authz.bootstrap import BootstrapOutcome, ensure_admin
from .shared import get_database


def _audit(
    session: Session,
    *,
    command: str,
    action: str,
    entity: str,
    entity_id: object | None = None,
    changes: dict[str, Any] | None = None,
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


@click.command("init-admin")
@click.option(
    "--username", type=str, prompt=True, help="Must match EYENED_API_ADMIN_USERNAME."
)
@click.option(
    "--password",
    type=str,
    default=None,
    help="Omit to leave password login disabled (or unchanged, for an existing account).",
)
def init_admin(username: str, password: str | None) -> None:
    """Create or promote the platform administrator (idempotent)."""
    database = get_database()
    with database.get_session() as session:
        creator, outcome = ensure_admin(session, username, password)
        # None means "nothing happened, so nothing to audit" -- keeping that in the
        # match keeps the audit condition from being written twice and drifting.
        action: str | None
        match outcome:
            case BootstrapOutcome.unchanged:
                action = None
            case BootstrapOutcome.created:
                action = "INSERT"
            case BootstrapOutcome.promoted | BootstrapOutcome.reactivated:
                action = "UPDATE"
            case _:
                raise ValueError(f"unhandled BootstrapOutcome: {outcome!r}")
        if action is not None:
            _audit(
                session,
                command="init-admin",
                action=action,
                entity="Creator",
                entity_id=creator.CreatorID,
                changes={
                    "username": username,
                    "is_admin": True,
                    "outcome": outcome.value,
                },
            )
        session.commit()
    click.echo(f"{username}: {outcome.value}")


rbac_commands = [init_admin]
