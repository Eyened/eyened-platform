"""RBAC administration commands.

v0.3 places the CLI and ``eorm`` outside RBAC enforcement as trusted paths, so
these commands do not authorize their operator. They **do** attribute: every one
writes an ``AuditLog`` row with ``TrustedPath`` set and ``ActorID`` NULL, which
is what the AuditLog model documents that combination for.
"""
from __future__ import annotations

import click

from ..authz.administration import audit_trusted, grant, parse_role, revoke
from ..authz.bootstrap import BootstrapOutcome, ensure_admin
from ..authz.roles import ProjectRole
from .shared import get_database


@click.command("init-admin")
@click.option(
    "--username", type=str, prompt=True, help="Must match EYENED_API_ADMIN_USERNAME."
)
@click.option(
    "--password",
    type=str,
    envvar="EYENED_API_ADMIN_PASSWORD",
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help=(
        "Reads EYENED_API_ADMIN_PASSWORD if set; otherwise prompts twice without "
        "echoing input. Leave blank to leave password login disabled (or "
        "unchanged, for an existing account)."
    ),
)
def init_admin(username: str, password: str) -> None:
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
            audit_trusted(
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


_ROLE_HELP = "One of: read_only, grader, project_admin."


def _parse_role_or_fail(value: str) -> ProjectRole:
    try:
        return parse_role(value)
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc


@click.command("grant")
@click.option("--user", "username", required=True)
@click.option("--project", "project_name", required=True)
@click.option("--role", required=True, help=_ROLE_HELP)
def grant_cmd(username: str, project_name: str, role: str):
    """Grant a user a role in a project (idempotent)."""
    parsed = _parse_role_or_fail(role)
    database = get_database()
    with database.get_session() as session:
        try:
            result = grant(
                session, username=username, project_name=project_name, role=parsed
            )
        except LookupError as exc:
            raise click.ClickException(str(exc)) from exc
        session.commit()
    if result.changed:
        was = "" if result.previous is None else f" (was {result.previous.name})"
        click.echo(f"{username}: {parsed.name} in {project_name}{was}")
    else:
        click.echo(f"{username}: already {parsed.name} in {project_name}; no change")


@click.command("revoke")
@click.option("--user", "username", required=True)
@click.option("--project", "project_name", required=True)
def revoke_cmd(username: str, project_name: str):
    """Remove a user's membership in a project."""
    database = get_database()
    with database.get_session() as session:
        try:
            removed = revoke(session, username=username, project_name=project_name)
        except LookupError as exc:
            raise click.ClickException(str(exc)) from exc
        session.commit()
    click.echo(
        f"{username}: revoked from {project_name}"
        if removed
        else f"{username}: no membership in {project_name}; nothing to do"
    )


rbac_commands = [init_admin, grant_cmd, revoke_cmd]
