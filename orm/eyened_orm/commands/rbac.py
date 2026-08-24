"""RBAC administration commands.

v0.3 places the CLI and ``eorm`` outside RBAC enforcement as trusted paths, so
these commands do not authorize their operator. They **do** attribute: every
state change writes an ``AuditLog`` row with ``TrustedPath`` set and ``ActorID``
NULL, which is what the AuditLog model documents that combination for. What
changes nothing writes nothing: a no-op branch (an already-revoked membership,
an already-inactive user) and read-only reports such as ``check-declarations``.
"""
from __future__ import annotations

import click

from ..authz.administration import (
    apply_grant_plan,
    apply_revoke_all,
    audit_trusted,
    deactivate,
    grant,
    grant_all,
    memberships_of,
    parse_role,
    plan_grant_for_tasks,
    reactivate,
    revoke,
    set_admin,
    set_password,
    unused_declarations,
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
        #
        # ``changes`` is built per outcome rather than hardcoded, so the row
        # claims only what the call actually did: ``is_admin`` appears when
        # administrator status was granted and not otherwise, and a credential
        # rotation says so. Never the password or the hash -- only that a reset
        # occurred.
        action: str | None
        changes: dict | None
        match outcome:
            case BootstrapOutcome.unchanged:
                action, changes = None, None
            case BootstrapOutcome.created:
                action = "INSERT"
                changes = {"username": username, "is_admin": True}
            case BootstrapOutcome.promoted:
                action = "UPDATE"
                changes = {"username": username, "is_admin": True}
            case BootstrapOutcome.password_reset:
                action = "UPDATE"
                changes = {"username": username, "password_changed": True}
            case BootstrapOutcome.promoted_and_password_reset:
                action = "UPDATE"
                changes = {
                    "username": username,
                    "is_admin": True,
                    "password_changed": True,
                }
            case BootstrapOutcome.reactivated:
                # Unreachable from this command -- init-admin never passes
                # reactivate=True; `eorm reactivate` is the recovery path. The
                # arm exists so a future caller cannot fall into the ValueError.
                action = "UPDATE"
                changes = {"username": username, "inactive": False}
            case _:
                raise ValueError(f"unhandled BootstrapOutcome: {outcome!r}")
        if action is not None:
            audit_trusted(
                session,
                command="init-admin",
                action=action,
                entity="Creator",
                entity_id=creator.CreatorID,
                changes={**changes, "outcome": outcome.value},
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
@click.option("--project", "project_name", required=False)
@click.option(
    "--all",
    "all_projects",
    is_flag=True,
    default=False,
    help="Remove every membership this user holds.",
)
@click.option("--yes", is_flag=True, default=False, help="Skip the confirmation.")
def revoke_cmd(
    username: str, project_name: str | None, all_projects: bool, yes: bool
):
    """Remove a user's membership in one project, or in every project."""
    # Click has no native "exactly one of these", so --project loses its
    # required=True and the requirement moves here. Defaulting either way turns
    # a typo into a silent no-op or a silent full revocation.
    if all_projects == bool(project_name):
        raise click.UsageError("pass exactly one of --project or --all")

    database = get_database()
    with database.get_session() as session:
        if not all_projects:
            try:
                removed = revoke(
                    session, username=username, project_name=project_name
                )
            except LookupError as exc:
                raise click.ClickException(str(exc)) from exc
            session.commit()
            click.echo(
                f"{username}: revoked from {project_name}"
                if removed
                else f"{username}: no membership in {project_name}; nothing to do"
            )
            return

        try:
            held = memberships_of(session, username=username)
        except LookupError as exc:
            raise click.ClickException(str(exc)) from exc
        if not held:
            click.echo(f"{username}: holds no memberships; nothing to do")
            return
        for _, name, role in held:
            click.echo(f"  REVOKE {role.name} in {name}")
        if not yes:
            click.confirm(
                f"Remove all {len(held)} membership(s) from {username}?", abort=True
            )
        apply_revoke_all(session, username=username, held=held)
        session.commit()
    click.echo(f"{username}: revoked from {len(held)} project(s)")


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


@click.command("grant-all")
@click.option("--yes", is_flag=True, default=False, help="Skip the confirmation.")
def grant_all_cmd(yes: bool):
    """Cutover step 3: grant grader in every project to every real user."""
    database = get_database()
    with database.get_session() as session:
        if not yes:
            click.confirm(
                "Grant grader in EVERY project to every creator that can "
                "authenticate? RBAC then permits everything until pruning.",
                abort=True,
            )
        creators, projects, written = grant_all(session)
        session.commit()
    click.echo(
        f"{written} membership(s) written for {creators} creator(s) "
        f"across {projects} project(s)."
    )
    click.echo(
        "RBAC is now installed and enforcing a policy that permits everything. "
        "The first revocation is the first real security improvement."
    )


@click.command("deactivate")
@click.option("--user", "username", required=True)
def deactivate_cmd(username: str):
    """Deactivate a user: they hold no access, and their work keeps its author."""
    database = get_database()
    with database.get_session() as session:
        try:
            changed = deactivate(session, username=username)
        except LookupError as exc:
            raise click.ClickException(str(exc)) from exc
        session.commit()
    click.echo(f"{username}: {'deactivated' if changed else 'already inactive'}")


@click.command("reactivate")
@click.option("--user", "username", required=True)
def reactivate_cmd(username: str):
    """Reactivate a user; their memberships were never removed."""
    database = get_database()
    with database.get_session() as session:
        try:
            changed = reactivate(session, username=username)
        except LookupError as exc:
            raise click.ClickException(str(exc)) from exc
        session.commit()
    click.echo(f"{username}: {'reactivated' if changed else 'already active'}")


@click.command("set-admin")
@click.option("--user", "username", required=True)
@click.option(
    "--on/--off",
    "is_admin",
    required=True,
    help="Grant (--on) or clear (--off) administrator status.",
)
def set_admin_cmd(username: str, is_admin: bool):
    """Set or clear administrator status on an existing account.

    `init-admin` is the bootstrap and can also promote; this is the flip, and
    the only way back down.
    """
    database = get_database()
    with database.get_session() as session:
        try:
            changed = set_admin(session, username=username, is_admin=is_admin)
        except LookupError as exc:
            raise click.ClickException(str(exc)) from exc
        session.commit()
    if changed:
        click.echo(
            f"{username}: is now an administrator"
            if is_admin
            else f"{username}: is no longer an administrator"
        )
    else:
        click.echo(
            f"{username}: already an administrator; no change"
            if is_admin
            else f"{username}: already not an administrator; no change"
        )


@click.command("set-password")
@click.option("--user", "username", required=True)
@click.option(
    "--password",
    type=str,
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help=(
        "Prompts twice without echoing input. Reads no environment variable: "
        "EYENED_API_ADMIN_PASSWORD belongs to init-admin, and honouring it "
        "here would set an arbitrary account's password to the "
        "administrator's."
    ),
)
def set_password_cmd(username: str, password: str):
    """Set an existing user's password."""
    # init-admin reads a blank password as "leave unchanged", which is
    # meaningless for a command whose only job is to change it.
    if not password:
        raise click.BadParameter("password must not be empty", param_hint="--password")
    database = get_database()
    with database.get_session() as session:
        try:
            set_password(session, username=username, password=password)
        except LookupError as exc:
            raise click.ClickException(str(exc)) from exc
        session.commit()
    click.echo(f"{username}: password set")


@click.command("check-declarations")
def check_declarations() -> None:
    """List (task, project) declarations no image link uses.

    Rows are expected rather than faults: a task declares its projects at
    creation and acquires its links afterwards, and removing a task's links
    leaves its declaration standing. No ``eorm`` operation removes one --
    this reports, it does not reconcile.
    """
    database = get_database()
    with database.get_session() as session:
        rows = unused_declarations(session)
    if not rows:
        click.echo("No unused declarations.")
        return
    for task_id, project_id in rows:
        click.echo(f"task {task_id}\tproject {project_id}")


rbac_commands = [
    init_admin, grant_cmd, revoke_cmd, grant_for_task_cmd,
    grant_all_cmd, deactivate_cmd, reactivate_cmd, set_admin_cmd,
    set_password_cmd, check_declarations,
]
