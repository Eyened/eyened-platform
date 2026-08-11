"""RBAC administration commands.

v0.3 places the CLI and ``eorm`` outside RBAC enforcement as trusted paths, so
these commands do not authorize their operator. They **do** attribute: every one
writes an ``AuditLog`` row with ``TrustedPath`` set and ``ActorID`` NULL, which
is what the AuditLog model documents that combination for.
"""
from __future__ import annotations

import click

from ..authz.administration import (
    apply_grant_plan,
    audit_trusted,
    grant,
    parse_role,
    plan_grant_for_tasks,
    revoke,
)
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


@click.command("grant-for-task")
@click.option("--user", "username", required=True)
@click.option("--task", "task_ids", type=int, multiple=True, required=True)
@click.option("--role", required=True, help=_ROLE_HELP)
@click.option("--yes", is_flag=True, default=False, help="Skip the confirmation.")
def grant_for_task_cmd(
    username: str, task_ids: tuple[int, ...], role: str, yes: bool
) -> None:
    """Grant a user membership in every project the given tasks touch.

    A convenience over granting projects, not a new kind of grant.
    """
    parsed = _parse_role_or_fail(role)
    database = get_database()
    with database.get_session() as session:
        try:
            plan = plan_grant_for_tasks(
                session, username=username, task_ids=task_ids, role=parsed
            )
        except LookupError as exc:
            raise click.ClickException(str(exc)) from exc

        if not plan.to_grant and not plan.already_held:
            click.echo(
                f"Task(s) {', '.join(map(str, task_ids))} touch no projects; "
                "nothing to grant."
            )
            return

        for _, name, held in plan.already_held:
            click.echo(f"  already holds {held.name} in {name}")
        for _, name, role_to_grant in plan.to_grant:
            click.echo(f"  GRANT {role_to_grant.name} in {name}")
        if not plan.to_grant:
            click.echo("Nothing to grant.")
            return
        # Each project hands over every patient, image and task in it,
        # permanently, until revoked.
        if not yes:
            roles = ", ".join(sorted({r.name for _, _, r in plan.to_grant}))
            click.confirm(
                f"Grant {username} {roles} in {len(plan.to_grant)} project(s)?",
                abort=True,
            )
        apply_grant_plan(session, plan=plan)
        session.commit()
    click.echo(f"{username}: granted in {len(plan.to_grant)} project(s)")


rbac_commands = [init_admin, grant_cmd, revoke_cmd, grant_for_task_cmd]
