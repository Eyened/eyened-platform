"""Membership administration: grants, revocations, and the task-grant plan.

The Click commands in ``commands/rbac.py`` are thin shells over this class, and
the admin API of step 2 will be another. It holds repositories and never a
``Session``, which is what lets one implementation serve both.

v0.3 places the CLI outside RBAC enforcement as a trusted path, so nothing here
authorizes its operator. Everything here **attributes**: each state change
writes an ``AuditLog`` row naming the ``Actor`` this instance was constructed
with. What changes nothing writes nothing -- an idempotent grant, an
already-revoked membership -- and the read-only methods
(``memberships_of``, ``plan_grant_for_tasks``) write no row at all.

Split from account lifecycle (``account_admin.py``) along the dependency seam:
these seven methods use four repositories between them, the lifecycle methods
use one. Membership changes for RBAC-policy reasons; credentials change for
identity reasons.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ..audit_writer import AuditWriter
from ..creator import Creator
from ..project import Project
from ..repositories.creator_repository import CreatorRepository
from ..repositories.project_member_repository import ProjectMemberRepository
from ..repositories.project_repository import ProjectRepository
from ..repositories.task_repository import TaskRepository
from .actor import Actor
from .errors import AdminEntityNotFound
from .roles import ProjectRole

__all__ = ["GrantResult", "MembershipAdministration", "TaskGrantPlan"]


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


class MembershipAdministration:
    """Grant and revoke project membership, attributed to one ``Actor``.

    ``actor`` is constructor state, matching every service in the repo (which
    derive theirs as ``ActingUser.from_scope(scope)`` in ``__init__``). Injected
    rather than derived only because ``TrustedPath`` carries a name no
    ``AccessScope`` knows.

    Holding it here also removes a fail-open a per-method ``actor`` would
    reintroduce: ``apply_grant_plan`` calls ``grant`` and ``apply_revoke_all``
    calls ``revoke``, and a forwarding parameter that one of them forgot would
    be silently unattributed.

    ``audit`` is required with no default, unlike the seven server services'
    ``audit: AuditService | None = None``. Attribution is this class's entire
    job, so a sink that defaults to None is fail-open on precisely the property
    it exists to protect.

    Takes no ``AccessScope``: the repositories arrive constructed, and whoever
    builds them owns the scope.
    """

    def __init__(
        self,
        creators: CreatorRepository,
        projects: ProjectRepository,
        members: ProjectMemberRepository,
        tasks: TaskRepository,
        *,
        audit: AuditWriter,
        actor: Actor,
    ) -> None:
        self._creators = creators
        self._projects = projects
        self._members = members
        self._tasks = tasks
        self._audit = audit
        self._actor = actor

    # --- resolution -------------------------------------------------------
    #
    # Two helpers rather than a None check repeated at every entry point. The
    # message text is read by operators -- the CLI prints it verbatim through
    # ClickException(str(exc)) -- so it is preserved exactly, ``!r`` included.

    def _creator(self, username: str) -> Creator:
        creator = self._creators.get_by_name(username)
        if creator is None:
            raise AdminEntityNotFound(
                f"no creator named {username!r}", entity="Creator"
            )
        return creator

    def _project(self, project_name: str) -> Project:
        project = self._projects.get_by_name(project_name)
        if project is None:
            raise AdminEntityNotFound(
                f"no project named {project_name!r}", entity="Project"
            )
        return project

    # --- membership -------------------------------------------------------

    def grant(
        self, *, username: str, project_name: str, role: ProjectRole
    ) -> GrantResult:
        """Grant or change a role. Idempotent: an unchanged grant writes no audit row."""
        creator = self._creator(username)
        project = self._project(project_name)

        existing = self._members.get(creator.CreatorID, project.ProjectID)
        if existing is not None and existing.Role is role:
            return GrantResult(
                creator_id=creator.CreatorID,
                project_id=project.ProjectID,
                project_name=project_name,
                previous=role,
                role=role,
                changed=False,
            )

        _, previous = self._members.upsert(
            creator.CreatorID, project.ProjectID, role
        )
        self._audit.write(
            actor=self._actor,
            action="INSERT" if previous is None else "UPDATE",
            entity="ProjectMember",
            # `audit_trusted` dropped this and buried the id in Changes instead.
            project_id=project.ProjectID,
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

    def revoke(self, *, username: str, project_name: str) -> bool:
        """Remove a membership. Returns False when there was nothing to remove."""
        creator = self._creator(username)
        project = self._project(project_name)

        member = self._members.get(creator.CreatorID, project.ProjectID)
        if member is None:
            return False
        previous = member.Role
        self._members.delete(member)
        self._audit.write(
            actor=self._actor,
            action="DELETE",
            entity="ProjectMember",
            project_id=project.ProjectID,
            changes={
                "creator_id": creator.CreatorID,
                "username": username,
                "project_id": project.ProjectID,
                "project_name": project_name,
                "role": previous.name,
            },
        )
        return True

    def grant_all(self, *, role: ProjectRole = ProjectRole.grader) -> tuple[int, int, int]:
        """Grant ``role`` in every project to every creator that can authenticate.

        Cutover step 3, and nothing else. `grader` rather than `project_admin`
        because the two are identical in security terms on day one -- everyone
        holds every project either way -- but they converge differently: pruning
        means removing projects from people, not adjusting roles, so
        `project_admin` everywhere would leave over-privileged survivors and a
        second cleanup pass that is easy to forget.

        Writes one summary AuditLog row rather than one per membership: the
        per-row detail is the ProjectMember table itself, and 1,408 audit rows
        for a single operator action is noise, not attribution. The row carries
        no ``project_id`` for the same reason -- it names no single project.

        Which creators count is ``CreatorRepository.list_authenticatable``'s
        decision; read its docstring before changing the set.
        """
        creators = self._creators.list_authenticatable()
        project_ids = self._projects.all_ids()

        written = 0
        for creator in creators:
            held = self._members.roles_for(creator.CreatorID)
            for project_id in project_ids:
                if held.get(project_id) is not None:
                    continue
                self._members.upsert(creator.CreatorID, project_id, role)
                written += 1

        self._audit.write(
            actor=self._actor,
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

    def memberships_of(self, *, username: str) -> list[tuple[int, str, ProjectRole]]:
        """Every membership a user holds, as (project_id, project_name, role).

        Ordered by project name so the review block a command prints is stable
        between runs. Read-only: the administrator sees the list before
        confirming, and no audit row is written.
        """
        creator = self._creator(username)
        members = self._members.list_for_creator(creator.CreatorID)
        names = self._projects.names_for(m.ProjectID for m in members)
        return sorted(
            ((m.ProjectID, names[m.ProjectID], m.Role) for m in members),
            key=lambda row: row[1],
        )

    # --- task-driven grants -----------------------------------------------

    def plan_grant_for_tasks(
        self, *, username: str, task_ids: Sequence[int], role: ProjectRole
    ) -> TaskGrantPlan:
        """Resolve the projects the tasks touch and diff them against what is held.

        Writes nothing: the administrator reviews and confirms first. Uses
        ``TaskRepository.project_ids``, which wraps ``projects_of`` -- the same
        definition enforcement uses -- so the CLI and the API cannot answer
        "which projects does this task touch" differently.

        An existing role is never lowered: a user who is already project_admin
        in one of the task's projects keeps it.

        An id with no task is an error, not an empty result: it is otherwise
        indistinguishable from a task that touches no projects, and the operator
        reads a typo as a successful no-op.
        """
        if not task_ids:
            raise ValueError("'task_ids' must not be empty")

        creator = self._creator(username)
        held = self._members.roles_for(creator.CreatorID)

        found = self._tasks.existing_ids(task_ids)
        missing = [t for t in dict.fromkeys(task_ids) if t not in found]
        if missing:
            label = "id" if len(missing) == 1 else "ids"
            raise AdminEntityNotFound(
                f"no task with {label} {', '.join(map(str, missing))}", entity="Task"
            )

        needed: set[int] = set()
        for task_id in task_ids:
            needed |= self._tasks.project_ids(task_id)

        names = self._projects.names_for(needed)

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

    def apply_grant_plan(self, *, plan: TaskGrantPlan) -> list[GrantResult]:
        """Apply a reviewed plan. The result is ordinary project membership --
        revoked the same way, and carrying the same access to that project's data
        outside the task.

        Aborts on the first failure rather than reporting per-item outcomes,
        which is the existing behavior and is safe here: every name in
        ``to_grant`` was resolved out of the database inside this transaction by
        ``plan_grant_for_tasks``, so ``grant`` has nothing left to fail to find.
        The parent spec's per-item rule is about the HTTP surface, where the
        caller supplies the ids -- it lands with the write endpoints in step 3.
        """
        return [
            self.grant(username=plan.username, project_name=name, role=role)
            for _, name, role in plan.to_grant
        ]

    def apply_revoke_all(
        self, *, username: str, held: Sequence[tuple[int, str, ProjectRole]]
    ) -> None:
        """Remove every membership in a list already produced by `memberships_of`.

        Takes the list rather than recomputing it, mirroring
        `apply_grant_plan(plan=...)`: the command has already printed this exact
        set and had it confirmed, so re-deriving it would both repeat the query
        and let the set applied drift from the set reviewed.

        Loops over `revoke` rather than issuing one bulk DELETE, exactly as
        `apply_grant_plan` loops over `grant`. That inherits one audit row per
        membership, which is right at this scale: a user holds at most one row
        per project, so this is bounded by the project count -- not the
        1,408-row scale that made `grant_all` write a single summary row.

        Aborts on the first failure, for the same reason `apply_grant_plan`
        does: ``held`` came from ``memberships_of`` in this transaction.
        """
        for _, project_name, _ in held:
            self.revoke(username=username, project_name=project_name)
