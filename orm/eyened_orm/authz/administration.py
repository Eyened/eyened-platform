"""Membership administration, as plain functions over a Session.

The Click commands in ``commands/rbac.py`` are thin shells over these: the
logic is here so it can be unit-tested against the in-memory SQLite suite,
which cannot build the real ``Database()`` the CLI opens.

v0.3 places the CLI outside RBAC enforcement as a trusted path, so nothing here
authorizes its operator. Everything here **attributes**: each state change
writes an AuditLog row with TrustedPath set and ActorID NULL, which is the
combination the AuditLog model documents for exactly this.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit_log import AuditLog
from ..creator import Creator
from ..project import Project
from ..repositories.project_member_repository import ProjectMemberRepository
from ..utils.db_users import hash_password
from .roles import ProjectRole

__all__ = [
    "GrantResult",
    "TaskGrantPlan",
    "apply_grant_plan",
    "apply_revoke_all",
    "audit_trusted",
    "deactivate",
    "grant",
    "grant_all",
    "memberships_of",
    "parse_role",
    "plan_grant_for_tasks",
    "reactivate",
    "resolve_creator",
    "resolve_project",
    "revoke",
    "set_admin",
    "set_password",
]


def parse_role(value: str) -> ProjectRole:
    """Convert a CLI string to a ProjectRole, naming the valid roles on failure.

    The conversion happens once, at the boundary; everything past it deals in
    the enum, so no downstream code compares role strings.
    """
    try:
        return ProjectRole[value]
    except KeyError:
        valid = ", ".join(r.name for r in ProjectRole)
        raise ValueError(f"unknown role {value!r}; valid roles are: {valid}") from None


def resolve_creator(session: Session, username: str) -> Creator:
    creator = session.scalars(
        select(Creator).where(Creator.CreatorName == username)
    ).first()
    if creator is None:
        raise LookupError(f"no creator named {username!r}")
    return creator


def resolve_project(session: Session, project_name: str) -> Project:
    project = session.scalars(
        select(Project).where(Project.ProjectName == project_name)
    ).first()
    if project is None:
        raise LookupError(f"no project named {project_name!r}")
    return project


def audit_trusted(
    session: Session,
    *,
    command: str,
    action: str,
    entity: str,
    entity_id: int | None = None,
    changes: dict | None = None,
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


@dataclass(frozen=True)
class GrantResult:
    """The outcome of a `grant` call.

    ``previous`` is only meaningful when ``changed`` is True (the role that
    was replaced, or None for a brand-new membership). On the unchanged path
    it is set to the current ``role`` rather than None -- callers must guard
    on ``changed`` before reading it, not treat ``previous`` as authoritative
    on its own.
    """

    creator_id: int
    project_id: int
    project_name: str
    previous: ProjectRole | None
    role: ProjectRole
    changed: bool


def grant(
    session: Session, *, username: str, project_name: str, role: ProjectRole
) -> GrantResult:
    """Grant or change a role. Idempotent: an unchanged grant writes no audit row."""
    creator = resolve_creator(session, username)
    project = resolve_project(session, project_name)
    repository = ProjectMemberRepository(session)

    existing = repository.get(creator.CreatorID, project.ProjectID)
    if existing is not None and existing.Role is role:
        return GrantResult(
            creator_id=creator.CreatorID,
            project_id=project.ProjectID,
            project_name=project_name,
            previous=role,
            role=role,
            changed=False,
        )

    _, previous = repository.upsert(creator.CreatorID, project.ProjectID, role)
    audit_trusted(
        session,
        command="grant",
        action="INSERT" if previous is None else "UPDATE",
        entity="ProjectMember",
        changes={
            "creator_id": creator.CreatorID,
            "username": username,
            "project_id": project.ProjectID,
            "project_name": project_name,
            "role": role.name
            if previous is None
            else {"old": previous.name, "new": role.name},
        },
    )
    return GrantResult(
        creator_id=creator.CreatorID,
        project_id=project.ProjectID,
        project_name=project_name,
        previous=previous,
        role=role,
        changed=True,
    )


@dataclass(frozen=True)
class TaskGrantPlan:
    """What ``grant-for-task`` would do, resolved but not yet applied.

    Both tuple lists are ``(project_id, project_name, role)`` -- but the role
    means different things: in ``to_grant`` it is the role that will be
    written, in ``already_held`` it is the role the user already has (which is
    at or above the requested one, which is why it is not being written).

    ``username`` is part of the plan, not a separate argument to
    ``apply_grant_plan``: the diff is only meaningful for the user it was
    computed against, and applying it to anyone else silently under-grants.
    """

    username: str
    task_ids: tuple[int, ...]
    to_grant: tuple[tuple[int, str, ProjectRole], ...]
    already_held: tuple[tuple[int, str, ProjectRole], ...]


def plan_grant_for_tasks(
    session: Session, *, username: str, task_ids: Sequence[int], role: ProjectRole
) -> TaskGrantPlan:
    """Resolve the projects the tasks touch and diff them against what is held.

    Writes nothing: the administrator reviews and confirms first. Uses
    ``projects_of``, the same definition enforcement uses -- so the CLI and the
    API cannot answer "which projects does this task touch" differently.

    An existing role is never lowered: a user who is already project_admin in
    one of the task's projects keeps it.

    An id with no task is an error, not an empty result: it is otherwise
    indistinguishable from a task that touches no projects, and the operator
    reads a typo as a successful no-op.
    """
    from .scoping import projects_of  # local: scoping imports the model layer
    from ..task import Task

    if not task_ids:
        raise ValueError("'task_ids' must not be empty")

    creator = resolve_creator(session, username)
    held = ProjectMemberRepository(session).roles_for(creator.CreatorID)

    found = set(
        session.scalars(select(Task.TaskID).where(Task.TaskID.in_(task_ids))).all()
    )
    missing = [t for t in dict.fromkeys(task_ids) if t not in found]
    if missing:
        label = "id" if len(missing) == 1 else "ids"
        raise LookupError(f"no task with {label} {', '.join(map(str, missing))}")

    needed: set[int] = set()
    for task_id in task_ids:
        needed |= projects_of(session, Task, task_id)

    names = dict(
        session.execute(
            select(Project.ProjectID, Project.ProjectName).where(
                Project.ProjectID.in_(needed)
            )
        ).all()
    )

    to_grant: list[tuple[int, str, ProjectRole]] = []
    already_held: list[tuple[int, str, ProjectRole]] = []
    for project_id in sorted(needed, key=lambda pid: names[pid]):
        current = held.get(project_id)
        if current is not None and current >= role:
            already_held.append((project_id, names[project_id], current))
        else:
            to_grant.append((project_id, names[project_id], role))
    return TaskGrantPlan(
        username=username,
        task_ids=tuple(task_ids),
        to_grant=tuple(to_grant),
        already_held=tuple(already_held),
    )


def apply_grant_plan(session: Session, *, plan: TaskGrantPlan) -> list[GrantResult]:
    """Apply a reviewed plan. The result is ordinary project membership --
    revoked the same way, and carrying the same access to that project's data
    outside the task."""
    return [
        grant(session, username=plan.username, project_name=name, role=role)
        for _, name, role in plan.to_grant
    ]


def grant_all(
    session: Session, *, role: ProjectRole = ProjectRole.grader
) -> tuple[int, int, int]:
    """Grant ``role`` in every project to every creator that can authenticate.

    Cutover step 3, and nothing else. `grader` rather than `project_admin`
    because the two are identical in security terms on day one -- everyone
    holds every project either way -- but they converge differently: pruning
    means removing projects from people, not adjusting roles, so
    `project_admin` everywhere would leave over-privileged survivors and a
    second cleanup pass that is easy to forget.

    Writes one summary AuditLog row rather than one per membership: the
    per-row detail is the ProjectMember table itself, and 1,408 audit rows for
    a single operator action is noise, not attribution.

    ``PasswordHash.is_not(None)`` rather than a password-validity check on
    purpose. ``disable_password`` writes ``'!'``, a valid hash that verifies
    nothing, and OIDC-provisioned accounts get exactly that (auth.py's
    create_user call passes password=None). They can authenticate -- just not
    by password -- so they belong in the cutover grant. Only rows with no
    PasswordHash at all (AI models, attribution-only creators) are skipped.
    """
    creators = session.scalars(
        select(Creator).where(
            Creator.IsHuman.is_(True),
            Creator.Inactive.is_(False),
            Creator.PasswordHash.is_not(None),
        )
    ).all()
    project_ids = list(session.scalars(select(Project.ProjectID)).all())
    repository = ProjectMemberRepository(session)

    written = 0
    for creator in creators:
        held = repository.roles_for(creator.CreatorID)
        for project_id in project_ids:
            if held.get(project_id) is not None:
                continue
            repository.upsert(creator.CreatorID, project_id, role)
            written += 1

    audit_trusted(
        session,
        command="grant-all",
        action="INSERT",
        entity="ProjectMember",
        changes={
            "role": role.name,
            "creators": len(creators),
            "projects": len(project_ids),
            "memberships_written": written,
        },
    )
    return len(creators), len(project_ids), written


def revoke(session: Session, *, username: str, project_name: str) -> bool:
    """Remove a membership. Returns False when there was nothing to remove."""
    creator = resolve_creator(session, username)
    project = resolve_project(session, project_name)
    repository = ProjectMemberRepository(session)

    member = repository.get(creator.CreatorID, project.ProjectID)
    if member is None:
        return False
    previous = member.Role
    repository.delete(member)
    audit_trusted(
        session,
        command="revoke",
        action="DELETE",
        entity="ProjectMember",
        changes={
            "creator_id": creator.CreatorID,
            "username": username,
            "project_id": project.ProjectID,
            "project_name": project_name,
            "role": previous.name,
        },
    )
    return True


def memberships_of(
    session: Session, *, username: str
) -> list[tuple[int, str, ProjectRole]]:
    """Every membership a user holds, as (project_id, project_name, role).

    Ordered by project name so the review block a command prints is stable
    between runs. Read-only: the administrator sees the list before confirming.
    """
    creator = resolve_creator(session, username)
    members = ProjectMemberRepository(session).list_for_creator(creator.CreatorID)
    names = dict(
        session.execute(
            select(Project.ProjectID, Project.ProjectName).where(
                Project.ProjectID.in_([m.ProjectID for m in members])
            )
        ).all()
    )
    return sorted(
        ((m.ProjectID, names[m.ProjectID], m.Role) for m in members),
        key=lambda row: row[1],
    )


def apply_revoke_all(
    session: Session,
    *,
    username: str,
    held: Sequence[tuple[int, str, ProjectRole]],
) -> None:
    """Remove every membership in a list already produced by `memberships_of`.

    Takes the list rather than recomputing it, mirroring
    `apply_grant_plan(session, plan=...)`: the command has already printed this
    exact set and had it confirmed, so re-deriving it would both repeat the
    query and let the set applied drift from the set reviewed.

    Loops over `revoke` rather than issuing one bulk DELETE, exactly as
    `apply_grant_plan` loops over `grant`. That inherits one audit row per
    membership, which is right at this scale: a user holds at most one row per
    project, so this is bounded by the project count -- not the 1,408-row scale
    that made `grant_all` write a single summary row instead.
    """
    for _, project_name, _ in held:
        revoke(session, username=username, project_name=project_name)


def deactivate(session: Session, *, username: str) -> bool:
    """Revoke everything, without deleting the row.

    v0.3 requires that administrators can *delete* users and defines that as
    deactivation: Creator is referenced by Segmentation, FormAnnotation,
    SubTask, Task, Tag and Annotation, so a real delete either fails on the
    foreign keys or destroys the attribution that is the entire compliance
    rationale.

    Memberships are left in place, so reactivation restores the state that
    existed rather than requiring it to be rebuilt from memory.

    Deactivating the last administrator is permitted: recovery is an UPDATE
    against the database, which is access the operator running this command
    already has.
    """
    creator = resolve_creator(session, username)
    if creator.Inactive:
        return False
    creator.Inactive = True
    session.flush()
    audit_trusted(
        session,
        command="deactivate",
        action="UPDATE",
        entity="Creator",
        entity_id=creator.CreatorID,
        changes={"username": username, "inactive": {"old": False, "new": True}},
    )
    return True


def reactivate(session: Session, *, username: str) -> bool:
    creator = resolve_creator(session, username)
    if not creator.Inactive:
        return False
    creator.Inactive = False
    session.flush()
    audit_trusted(
        session,
        command="reactivate",
        action="UPDATE",
        entity="Creator",
        entity_id=creator.CreatorID,
        changes={"username": username, "inactive": {"old": True, "new": False}},
    )
    return True


def set_admin(session: Session, *, username: str, is_admin: bool) -> bool:
    """Set or clear administrator status on an existing account.

    Returns False when the account is already in the requested state, so an
    unchanged call writes no audit row -- the same idempotence rule `grant`
    follows.

    Creating is not offered: `init-admin` is the bootstrap (it create-or-
    promotes and owns the password), and this is the flip on an account that
    already exists.

    **Demoting the last administrator is permitted.** `deactivate` above
    already commits to this for the equivalent risk, and recovery here is
    strictly cheaper than it is there: `eorm init-admin --username U` restores
    administrator status from the CLI, with no database access at all. A guard
    would block a state that one documented command undoes.
    """
    creator = resolve_creator(session, username)
    if bool(creator.IsAdmin) is is_admin:
        return False
    creator.IsAdmin = is_admin
    session.flush()
    audit_trusted(
        session,
        command="set-admin",
        action="UPDATE",
        entity="Creator",
        entity_id=creator.CreatorID,
        changes={
            "username": username,
            "is_admin": {"old": not is_admin, "new": is_admin},
        },
    )
    return True


def set_password(session: Session, *, username: str, password: str) -> None:
    """Replace an existing user's password.

    Unconditional -- there is no "unchanged" case to detect. Hashing is salted,
    so re-hashing the same password yields a different string, and a command
    whose only job is to set the password has no reason to skip the write.

    `init-admin` owns the administrator's credential and reads
    EYENED_API_ADMIN_PASSWORD; this owns everyone else's and reads no
    environment variable at all.
    """
    creator = resolve_creator(session, username)
    creator.PasswordHash = hash_password(password)
    # check_login falls through to this legacy pbkdf2 column when PasswordHash
    # misses. Leaving it set would let the password this command is resetting
    # away from keep authenticating -- a reset that doesn't reset. Do not
    # "simplify" this away: on a row with no legacy hash it is a no-op, but on
    # one that still carries it, it is the only line that actually revokes the
    # old credential.
    creator.Password = None
    session.flush()
    audit_trusted(
        session,
        command="set-password",
        action="UPDATE",
        entity="Creator",
        entity_id=creator.CreatorID,
        # Never the password and never the hash -- only that a reset occurred,
        # the same rule init-admin follows.
        changes={"username": username, "password_changed": True},
    )
