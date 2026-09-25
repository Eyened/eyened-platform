"""`eorm bootstrap`: bring a deployment's database to a usable state.

The deploy stack's `init` service runs it before the server on every
`docker compose up`, so it is idempotent and never prompts.
"""
from __future__ import annotations

import click
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..audit_writer import AuditWriter
from ..authz.actor import TrustedPath
from ..authz.bootstrap import count_admins, ensure_admin
from ..creator import Creator
from ..form_schemas import seed_form_schemas
from ..utils.alembic_utils import (
    get_current_alembic_revision,
    get_head_revision,
    upgrade_to_head,
)
from ..utils.db_users import WeakPasswordError
from .shared import get_database


@click.command("bootstrap")
@click.option(
    "--auto-migrate/--no-auto-migrate",
    default=False,
    show_default=True,
    envvar="EYENED_AUTO_MIGRATE",
    help="Apply pending migrations to an existing schema. Reads EYENED_AUTO_MIGRATE.",
)
@click.option(
    "--username",
    default="admin",
    show_default=True,
    envvar="EYENED_API_ADMIN_USERNAME",
    help="First administrator's name. Reads EYENED_API_ADMIN_USERNAME.",
)
@click.option(
    "--password",
    default=None,
    envvar="EYENED_API_ADMIN_PASSWORD",
    help="First administrator's password, used only when no account exists. "
    "Reads EYENED_API_ADMIN_PASSWORD.",
)
def bootstrap(auto_migrate: bool, username: str, password: str | None) -> None:
    """Migrate, seed and create the first administrator as needed (idempotent)."""
    database = get_database()
    head = get_head_revision()
    current = get_current_alembic_revision(database.engine)

    if current is None:
        click.echo(f"Empty database: migrating to {head} and seeding form schemas.")
        current = upgrade_to_head(database.engine)
        with database.get_session() as session:
            seed_form_schemas(session)
    elif current != head:
        if auto_migrate:
            click.echo(f"Migrating {current} -> {head}.")
            current = upgrade_to_head(database.engine)
        else:
            click.echo(
                "Pending migrations not applied (EYENED_AUTO_MIGRATE=false): "
                f"{current} -> {head}."
            )

    with database.get_session() as session:
        if _count_accounts(session) == 0:
            _create_first_admin(session, username, password)
        accounts = _count_accounts(session)
        admins = count_admins(session)
    click.echo(
        f"Schema at {current} (head {head}), {accounts} account(s), "
        f"{admins} active admin(s)."
    )


def _count_accounts(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Creator)) or 0


def _create_first_admin(session: Session, username: str, password: str | None) -> None:
    # Only ever on an empty Creator table: ensure_admin re-hashes a password that
    # does not verify, so running it every boot would undo a rotation.
    if not password:
        raise click.ClickException(
            "No accounts exist. Set EYENED_API_ADMIN_PASSWORD to create the "
            "first administrator."
        )
    try:
        creator, outcome = ensure_admin(session, username, password)
    except WeakPasswordError as exc:
        raise click.ClickException(f"EYENED_API_ADMIN_PASSWORD: {exc}") from exc
    AuditWriter(session).write(
        actor=TrustedPath("eorm bootstrap"),
        action="INSERT",
        entity="Creator",
        entity_id=creator.CreatorID,
        changes={"username": username, "is_admin": True, "outcome": outcome.value},
    )
    session.commit()
    click.echo(f"Created administrator {username}.")
