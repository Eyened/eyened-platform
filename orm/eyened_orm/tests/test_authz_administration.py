"""Membership operations: idempotent, audited, and never silently lossy."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from eyened_orm import AuditLog, Project
from eyened_orm.authz.administration import deactivate, reactivate
from eyened_orm.authz.errors import AdminEntityNotFound
from eyened_orm.authz.roles import ProjectRole, parse_role
from eyened_orm.repositories import ProjectMemberRepository
from eyened_orm.utils.factories import make_creator, make_project


def _audit(session, command):
    return session.scalars(
        select(AuditLog).where(AuditLog.TrustedPath == f"eorm {command}")
    ).all()


def test_parse_role_accepts_every_role_name():
    """All three, not a sample: the CLI's vocabulary is the enum's."""
    assert {name: parse_role(name) for name in ("read_only", "grader", "project_admin")} == {
        "read_only": ProjectRole.read_only,
        "grader": ProjectRole.grader,
        "project_admin": ProjectRole.project_admin,
    }


def test_parse_role_names_the_valid_roles_on_a_bad_value():
    """Fails at the CLI boundary rather than surfacing a bare ValueError.

    Everything past the parse deals in the enum, so no downstream code
    compares role strings.
    """
    with pytest.raises(ValueError) as exc:
        parse_role("admin")
    for name in ("read_only", "grader", "project_admin"):
        assert name in str(exc.value)


def test_grant_creates_a_membership_and_audits_it(session, membership):
    make_creator(session, "alice")
    make_project(session, "A")
    session.commit()

    result = membership("grant").grant(
        username="alice", project_name="A", role=ProjectRole.grader
    )
    session.commit()

    assert result.changed is True and result.previous is None
    rows = session.scalars(
        select(AuditLog).where(AuditLog.Entity == "ProjectMember")
    ).all()
    assert len(rows) == 1
    assert rows[0].TrustedPath == "eorm grant"
    assert rows[0].ActorID is None
    assert rows[0].Action == "INSERT"
    assert rows[0].EntityID is None
    # AuditLog has no single integer id for a membership, so the pair rides in Changes.
    assert rows[0].Changes["project_name"] == "A"
    assert rows[0].Changes["role"] == "grader"


def test_an_unchanged_grant_writes_no_audit_row(session, membership):
    make_creator(session, "alice")
    make_project(session, "A")
    membership("grant").grant(username="alice", project_name="A", role=ProjectRole.grader)
    session.commit()

    result = membership("grant").grant(
        username="alice", project_name="A", role=ProjectRole.grader
    )
    session.commit()

    assert result.changed is False
    assert len(session.scalars(select(AuditLog)).all()) == 1


def test_changing_a_role_records_old_and_new(session, membership):
    make_creator(session, "alice")
    make_project(session, "A")
    membership("grant").grant(
        username="alice", project_name="A", role=ProjectRole.read_only
    )
    session.commit()

    result = membership("grant").grant(
        username="alice", project_name="A", role=ProjectRole.grader
    )
    session.commit()

    assert result.previous is ProjectRole.read_only
    latest = session.scalars(select(AuditLog).order_by(AuditLog.AuditLogID.desc())).first()
    assert latest.Action == "UPDATE"
    assert latest.Changes["role"] == {"old": "read_only", "new": "grader"}


def test_revoke_removes_the_membership_and_audits_it(session, membership):
    alice = make_creator(session, "alice")
    project = make_project(session, "A")
    membership("grant").grant(username="alice", project_name="A", role=ProjectRole.grader)
    session.commit()
    project_id = project.ProjectID  # captured before expiry

    assert membership("revoke").revoke(username="alice", project_name="A") is True
    session.commit()
    assert ProjectMemberRepository(session).roles_for(alice.CreatorID) == {}
    session.expunge_all()

    removal = session.scalars(select(AuditLog).where(AuditLog.Action == "DELETE")).all()
    assert len(removal) == 1
    assert removal[0].TrustedPath == "eorm revoke"
    assert removal[0].Entity == "ProjectMember"
    assert removal[0].ActorID is None
    assert removal[0].EntityID is None
    assert removal[0].Changes["role"] == "grader"
    # Behavior change 4 (the revoke counterpart of change 1): `revoke` now
    # passes `project_id=project.ProjectID` through to `audit.write`, same as
    # `grant`. Read after commit() + expunge_all() with the id captured
    # earlier, for the same reason as `test_a_grant_row_now_carries_the_project_it_named`:
    # reading `removal[0].ProjectID` off the live identity-mapped object would
    # pass whether or not the column was actually persisted.
    assert removal[0].ProjectID == project_id


def test_revoking_a_membership_that_does_not_exist_is_a_no_op(session, membership):
    make_creator(session, "alice")
    make_project(session, "A")
    session.commit()
    assert membership("revoke").revoke(username="alice", project_name="A") is False


def test_an_unknown_username_names_itself(session, membership):
    make_project(session, "A")
    session.commit()
    with pytest.raises(AdminEntityNotFound, match="nosuchuser"):
        membership("grant").grant(
            username="nosuchuser", project_name="A", role=ProjectRole.grader
        )


def test_an_unknown_project_names_itself(session, membership):
    """resolve_project's message is unpinned otherwise; only the creator's was."""
    make_creator(session, "alice")
    session.commit()
    with pytest.raises(AdminEntityNotFound, match="nosuchproject"):
        membership("grant").grant(
            username="alice", project_name="nosuchproject", role=ProjectRole.grader
        )


def test_memberships_of_lists_every_membership_ordered_by_project_name(
    session, membership
):
    """The only re-implemented method (the other six were copied verbatim), so
    its shape is asserted directly rather than inferred from a caller: a list
    of (project_id, project_name, role), sorted by project name -- not by
    insertion order or ProjectID. "Zebra" is granted first and holds the lower
    ProjectID, so a sort that silently degraded to `list_for_creator`'s
    ProjectID order would still put it first; only a real name sort puts
    "Apple" there instead."""
    alice = make_creator(session, "alice")
    zebra = make_project(session, "Zebra")
    apple = make_project(session, "Apple")
    session.commit()

    admin = membership("list")
    admin.grant(username="alice", project_name="Zebra", role=ProjectRole.grader)
    admin.grant(username="alice", project_name="Apple", role=ProjectRole.project_admin)
    session.commit()

    assert admin.memberships_of(username="alice") == [
        (apple.ProjectID, "Apple", ProjectRole.project_admin),
        (zebra.ProjectID, "Zebra", ProjectRole.grader),
    ]
    assert alice.CreatorID is not None  # sanity: the fixture built a real row


def test_apply_revoke_all_removes_every_membership_and_audits_each(session, membership):
    """Loops over `revoke`, so it inherits one DELETE audit row per membership
    -- not the single-summary-row shape `grant_all` uses at 1,408-row scale.
    Two memberships held, so exactly two DELETE rows, one per project."""
    alice = make_creator(session, "alice")
    make_project(session, "A")
    make_project(session, "B")
    session.commit()

    admin = membership("revoke")
    admin.grant(username="alice", project_name="A", role=ProjectRole.grader)
    admin.grant(username="alice", project_name="B", role=ProjectRole.read_only)
    session.commit()

    held = admin.memberships_of(username="alice")
    assert len(held) == 2  # both memberships actually held, per the fixture setup

    admin.apply_revoke_all(username="alice", held=held)
    session.commit()

    assert ProjectMemberRepository(session).roles_for(alice.CreatorID) == {}
    removals = session.scalars(
        select(AuditLog).where(AuditLog.Action == "DELETE")
    ).all()
    assert len(removals) == 2
    assert {r.Changes["project_name"] for r in removals} == {"A", "B"}
    assert {r.Entity for r in removals} == {"ProjectMember"}


def test_a_plan_lists_what_will_be_granted_and_what_is_already_held(
    session, spanning, membership
):
    """Review before apply. "Grant Alice access to task 70" may resolve to eight
    projects, each handing over every patient, image and task in it --
    permanently, until revoked. An administrator who reads the command name and
    not the effect will over-grant."""
    make_creator(session, "alice")
    membership("grant").grant(username="alice", project_name="A", role=ProjectRole.grader)
    session.commit()

    plan = membership("grant-for-task").plan_grant_for_tasks(
        username="alice", task_ids=[spanning["task"]], role=ProjectRole.grader
    )
    assert [name for _, name, _ in plan.to_grant] == ["B"]
    assert [name for _, name, _ in plan.already_held] == ["A"]


def test_a_plan_writes_nothing(session, spanning, membership):
    from eyened_orm.repositories.project_member_repository import (
        ProjectMemberRepository,
    )

    alice = make_creator(session, "alice")
    session.commit()
    membership("grant-for-task").plan_grant_for_tasks(
        username="alice", task_ids=[spanning["task"]], role=ProjectRole.grader
    )
    assert ProjectMemberRepository(session).roles_for(alice.CreatorID) == {}


def test_applying_a_plan_never_lowers_an_existing_role(session, spanning, membership):
    """A user who is already project_admin in one of the task's projects keeps it."""
    from eyened_orm.repositories.project_member_repository import (
        ProjectMemberRepository,
    )

    alice = make_creator(session, "alice")
    membership("grant").grant(
        username="alice", project_name="A", role=ProjectRole.project_admin
    )
    session.commit()

    admin = membership("grant-for-task")
    plan = admin.plan_grant_for_tasks(
        username="alice", task_ids=[spanning["task"]], role=ProjectRole.grader
    )
    admin.apply_grant_plan(plan=plan)
    session.commit()

    roles = ProjectMemberRepository(session).roles_for(alice.CreatorID)
    assert roles[spanning["projects"]["A"]] is ProjectRole.project_admin
    assert roles[spanning["projects"]["B"]] is ProjectRole.grader


def test_a_lower_existing_role_is_upgraded_not_reported_as_already_held(
    session, spanning, membership
):
    """`>= role` is the whole comparison: dropping the level check and keeping
    only 'has a membership' silently refuses the upgrade, and the administrator
    reads 'already holds read_only in A' as success."""
    make_creator(session, "alice")
    membership("grant").grant(
        username="alice", project_name="A", role=ProjectRole.read_only
    )
    session.commit()

    plan = membership("grant-for-task").plan_grant_for_tasks(
        username="alice", task_ids=[spanning["task"]], role=ProjectRole.grader
    )
    assert [name for _, name, _ in plan.to_grant] == ["A", "B"]
    assert plan.already_held == ()


def test_a_task_touching_no_projects_grants_nothing(session, spanning, membership):
    """Rather than reporting success for a no-op that, under vacuity, is a task
    everyone can already see."""
    make_creator(session, "alice")
    session.commit()
    plan = membership("grant-for-task").plan_grant_for_tasks(
        username="alice", task_ids=[spanning["empty"]], role=ProjectRole.grader
    )
    assert plan.to_grant == () and plan.already_held == ()


def test_an_unknown_task_id_among_valid_ones_is_an_error_not_a_silent_drop(
    session, spanning, membership
):
    """The MIXED case, deliberately, rather than an all-unknown one: a weaker
    guard written `if not found:` passes an all-unknown test while still
    happily granting the valid half, leaving the operator believing alice can
    work every task they typed when she can only work some of them. Only a bad
    id *among good ones* distinguishes the two guards. The message names only
    what the operator got wrong."""
    make_creator(session, "alice")
    session.commit()
    with pytest.raises(AdminEntityNotFound) as excinfo:
        membership("grant-for-task").plan_grant_for_tasks(
            username="alice",
            task_ids=[spanning["task"], 999999],
            role=ProjectRole.grader,
        )
    assert str(excinfo.value) == "no task with id 999999"


def test_the_plan_uses_the_same_definition_enforcement_uses(session, spanning, membership):
    """Two implementations of "which projects does this task touch" will drift,
    and the failure mode is an administrator granting a set that does not match
    what the API requires."""
    from eyened_orm import Task
    from eyened_orm.authz.scoping import projects_of

    make_creator(session, "alice")
    session.commit()
    plan = membership("grant-for-task").plan_grant_for_tasks(
        username="alice", task_ids=[spanning["task"]], role=ProjectRole.grader
    )
    assert {pid for pid, _, _ in plan.to_grant} == projects_of(
        session, Task, spanning["task"]
    )


def test_applying_a_plan_audits_every_grant(session, spanning, membership):
    """apply_grant_plan goes through `grant`, so each membership carries the
    trusted-path attribution -- naming `grant-for-task`, the command the
    operator actually ran, rather than the `grant` it delegates to. A loop that
    upserted directly would write the same rows with no audit trail at all."""
    make_creator(session, "alice")
    session.commit()
    admin = membership("grant-for-task")
    plan = admin.plan_grant_for_tasks(
        username="alice", task_ids=[spanning["task"]], role=ProjectRole.grader
    )
    admin.apply_grant_plan(plan=plan)
    session.commit()

    rows = session.scalars(
        select(AuditLog).where(AuditLog.Entity == "ProjectMember")
    ).all()
    assert {r.Changes["project_name"] for r in rows} == {"A", "B"}
    assert {(r.ActorID, r.TrustedPath) for r in rows} == {(None, "eorm grant-for-task")}


def test_grant_all_skips_creators_that_cannot_authenticate(session, membership):
    """AI models and attribution-only rows would get memberships that can never
    be used, inflating the list somebody later has to prune."""
    from eyened_orm.repositories.project_member_repository import (
        ProjectMemberRepository,
    )
    from eyened_orm.utils.db_users import create_user

    human = create_user(session, "alice", "pw")
    model = make_creator(session, "cfi-quality-v3", is_human=False)
    attribution_only = make_creator(session, "Consensus")
    make_project(session, "A")
    make_project(session, "B")
    session.commit()

    creators, projects, written = membership("grant-all").grant_all()
    session.commit()

    assert (creators, projects, written) == (1, 2, 2)
    repo = ProjectMemberRepository(session)
    assert len(repo.roles_for(human.CreatorID)) == 2
    assert repo.roles_for(model.CreatorID) == {}
    assert repo.roles_for(attribution_only.CreatorID) == {}


def test_grant_all_writes_one_summary_audit_row(session, membership):
    from eyened_orm.utils.db_users import create_user

    create_user(session, "alice", "pw")
    make_project(session, "A")
    make_project(session, "B")
    session.commit()

    membership("grant-all").grant_all()
    session.commit()

    rows = session.scalars(
        select(AuditLog).where(AuditLog.TrustedPath == "eorm grant-all")
    ).all()
    assert len(rows) == 1
    assert rows[0].Action == "INSERT"
    assert rows[0].Entity == "ProjectMember"
    assert rows[0].EntityID is None
    assert rows[0].Changes == {
        "role": "grader",
        "creators": 1,
        "projects": 2,
        "memberships_written": 2,
    }


def test_grant_all_is_idempotent(session, membership):
    from eyened_orm.utils.db_users import create_user

    create_user(session, "alice", "pw")
    make_project(session, "A")
    session.commit()

    membership("grant-all").grant_all()
    session.commit()
    _, _, written = membership("grant-all").grant_all()
    assert written == 0


def test_grant_all_skips_a_model_that_has_a_password_hash(session, membership):
    """The plan's own test cannot see the IsHuman filter: its model has a NULL
    PasswordHash too, so the password filter alone still passes it."""
    from eyened_orm.repositories.project_member_repository import (
        ProjectMemberRepository,
    )
    from eyened_orm.utils.db_users import create_user

    model = create_user(session, "cfi-quality-v3", "pw", is_human=False)
    make_project(session, "A")
    session.commit()

    creators, _, written = membership("grant-all").grant_all()
    session.commit()

    assert (creators, written) == (0, 0)
    assert ProjectMemberRepository(session).roles_for(model.CreatorID) == {}


def test_grant_all_skips_a_deactivated_creator(session, membership):
    """Otherwise the cutover re-grants everyone an administrator deactivated."""
    from eyened_orm.repositories.project_member_repository import (
        ProjectMemberRepository,
    )
    from eyened_orm.utils.db_users import create_user

    bob = create_user(session, "bob", "pw")
    bob.Inactive = True
    make_project(session, "A")
    session.commit()

    creators, _, written = membership("grant-all").grant_all()
    session.commit()

    assert (creators, written) == (0, 0)
    assert ProjectMemberRepository(session).roles_for(bob.CreatorID) == {}


def test_grant_all_honours_the_role_it_is_given(session, membership):
    """`role` is a parameter, not decoration: nothing else pins it."""
    from eyened_orm.repositories.project_member_repository import (
        ProjectMemberRepository,
    )
    from eyened_orm.utils.db_users import create_user

    alice = create_user(session, "alice", "pw")
    make_project(session, "A")
    session.commit()

    membership("grant-all").grant_all(role=ProjectRole.project_admin)
    session.commit()

    roles = ProjectMemberRepository(session).roles_for(alice.CreatorID)
    assert set(roles.values()) == {ProjectRole.project_admin}


def test_grant_all_never_changes_a_role_already_held(session, membership):
    """A cutover re-run must not quietly lower a project_admin to grader --
    and `written == 0` is not evidence of that: a mutation that re-upserts
    without counting reports 0 while rewriting every role it touches."""
    from eyened_orm.repositories.project_member_repository import (
        ProjectMemberRepository,
    )
    from eyened_orm.utils.db_users import create_user

    alice = create_user(session, "alice", "pw")
    for name in ("A", "B", "C"):
        make_project(session, name)
    session.commit()
    membership("grant").grant(
        username="alice", project_name="A", role=ProjectRole.project_admin
    )
    membership("grant").grant(
        username="alice", project_name="B", role=ProjectRole.read_only
    )
    session.commit()

    _, _, written = membership("grant-all").grant_all()
    session.commit()

    roles = ProjectMemberRepository(session).roles_for(alice.CreatorID)
    names = dict(session.execute(select(Project.ProjectID, Project.ProjectName)).all())
    by_name = {names[pid]: role for pid, role in roles.items()}
    assert by_name["A"] is ProjectRole.project_admin   # not lowered
    assert by_name["B"] is ProjectRole.read_only       # not raised either
    assert by_name["C"] is ProjectRole.grader
    assert written == 1


def test_deactivate_sets_the_flag_and_leaves_memberships_in_place(session, membership):
    """Reactivation should restore the state that existed rather than require
    it to be rebuilt from memory."""
    alice = make_creator(session, "alice")
    make_project(session, "A")
    membership("grant").grant(username="alice", project_name="A", role=ProjectRole.grader)
    session.commit()
    creator_id = alice.CreatorID

    assert deactivate(session, username="alice") is True
    session.commit()
    assert alice.Inactive is True
    assert len(ProjectMemberRepository(session).roles_for(alice.CreatorID)) == 1

    rows = _audit(session, "deactivate")
    assert len(rows) == 1
    assert rows[0].ActorID is None
    assert rows[0].Action == "UPDATE"
    assert rows[0].Entity == "Creator"
    assert rows[0].EntityID == str(creator_id)
    assert rows[0].Changes == {
        "username": "alice",
        "inactive": {"old": False, "new": True},
    }


def test_deactivating_the_only_administrator_is_allowed(session):
    """No last-admin guard in this pass: the operator running `eorm` already has
    the database access that recovery needs."""
    from eyened_orm.authz.bootstrap import count_admins, ensure_admin

    root, _ = ensure_admin(session, "root", None)
    session.commit()

    assert deactivate(session, username="root") is True
    session.commit()
    assert root.Inactive is True
    assert count_admins(session) == 0


def test_reactivate_clears_the_flag_and_audits(session):
    alice = make_creator(session, "alice")
    session.commit()
    creator_id = alice.CreatorID
    deactivate(session, username="alice")
    session.commit()

    assert reactivate(session, username="alice") is True
    session.commit()
    assert alice.Inactive is False

    rows = _audit(session, "reactivate")
    assert len(rows) == 1
    assert rows[0].ActorID is None
    assert rows[0].Action == "UPDATE"
    assert rows[0].Entity == "Creator"
    assert rows[0].EntityID == str(creator_id)
    assert rows[0].Changes == {
        "username": "alice",
        "inactive": {"old": True, "new": False},
    }


def test_deactivating_an_already_inactive_user_is_a_no_op(session):
    make_creator(session, "alice")
    session.commit()
    deactivate(session, username="alice")
    session.commit()
    assert deactivate(session, username="alice") is False
    assert len(_audit(session, "deactivate")) == 1


def test_reactivating_an_already_active_user_is_a_no_op(session):
    """The symmetric guard: the plan tests it for `deactivate` only."""
    make_creator(session, "alice")
    session.commit()
    assert reactivate(session, username="alice") is False
    assert _audit(session, "reactivate") == []


@pytest.mark.parametrize("command", (deactivate, reactivate))
def test_an_unknown_username_names_itself_for_deactivate_and_reactivate(session, command):
    with pytest.raises(LookupError, match="nosuchuser"):
        command(session, username="nosuchuser")


def test_unused_declarations_reports_a_project_no_link_uses(session, spanning):
    """A declared project no link uses -- fail-safe, but worth surfacing."""
    from eyened_orm import TaskProject
    from eyened_orm.repositories import TaskRepository
    from eyened_orm.utils.factories import admin_scope

    session.add(
        TaskProject(TaskID=spanning["a_only"], ProjectID=spanning["projects"]["B"])
    )
    session.commit()

    found = TaskRepository(session, scope=admin_scope()).unused_declarations()
    assert (spanning["a_only"], spanning["projects"]["B"]) in found
    # ...and it does not report the ones that ARE used, or the report is noise.
    assert (spanning["a_only"], spanning["projects"]["A"]) not in found


def test_admin_entity_not_found_is_not_a_lookup_error():
    """LookupError is the base class of KeyError and IndexError, so catching it
    to build a 404 -- or a clean ClickException -- turns any dict or list miss
    inside the call into "not found". The dedicated type catches only what was
    raised on purpose."""
    assert not issubclass(AdminEntityNotFound, LookupError)


def test_admin_entity_not_found_names_which_lookup_failed():
    """The 404 it becomes in step 2 carries no body, so the entity has to ride
    on the exception -- the same argument errors.py already makes for
    AuthorizationError. The message stays the operator-facing string."""
    exc = AdminEntityNotFound("no creator named 'bob'", entity="Creator")
    assert exc.entity == "Creator"
    assert str(exc) == "no creator named 'bob'"


def test_list_authenticatable_includes_an_account_whose_password_is_disabled(session):
    """`disable_password` writes '!' -- a valid hash that verifies nothing --
    and OIDC-provisioned accounts get exactly that. They can authenticate, just
    not by password, so they belong in the cutover grant. Only rows with no
    PasswordHash at all are skipped."""
    from eyened_orm.repositories import CreatorRepository
    from eyened_orm.utils.db_users import create_user
    from eyened_orm.utils.factories import admin_scope

    create_user(session, "oidc-user", None)
    model = create_user(session, "a-model", None)
    model.IsHuman = False
    inactive = create_user(session, "gone", "pw")
    inactive.Inactive = True
    session.commit()

    names = {
        c.CreatorName
        for c in CreatorRepository(session, scope=admin_scope()).list_authenticatable()
    }
    assert "oidc-user" in names
    assert "a-model" not in names
    assert "gone" not in names


@pytest.fixture()
def membership(session):
    """Build a MembershipAdministration attributed to the named `eorm` command.

    A factory rather than a plain fixture because `actor` is constructor state:
    a `grant` and a `revoke` are two different instances, which is exactly what
    makes each row stamp the command that actually ran.
    """
    from eyened_orm.audit_writer import AuditWriter
    from eyened_orm.authz.actor import TrustedPath
    from eyened_orm.authz.membership_admin import MembershipAdministration
    from eyened_orm.repositories import (
        CreatorRepository,
        ProjectMemberRepository,
        ProjectRepository,
        TaskRepository,
    )
    from eyened_orm.utils.factories import admin_scope

    def _build(command: str) -> MembershipAdministration:
        scope = admin_scope()
        return MembershipAdministration(
            CreatorRepository(session, scope=scope),
            ProjectRepository(session, scope=scope),
            ProjectMemberRepository(session),
            TaskRepository(session, scope=scope),
            audit=AuditWriter(session),
            actor=TrustedPath(f"eorm {command}"),
        )

    return _build


def test_a_grant_row_now_carries_the_project_it_named(session, membership):
    """Behavior change 1. `audit_trusted` dropped ProjectID -- including in
    `grant`, which had resolved the project two lines earlier and buried the id
    in Changes.

    Asserted after commit() + expunge_all(), not on the live object: reading
    row.ProjectID straight after the write consults the identity map, not the
    database, so the assertion would pass whether or not the column was
    populated. For a change whose entire point is "ProjectID is now populated",
    that is the assertion most likely to pass for the wrong reason.
    """
    make_creator(session, "alice")
    project = make_project(session, "A")
    session.commit()
    project_id = project.ProjectID  # captured before expiry

    membership("grant").grant(
        username="alice", project_name="A", role=ProjectRole.grader
    )
    session.commit()
    session.expunge_all()

    row = session.scalars(
        select(AuditLog).where(AuditLog.Entity == "ProjectMember")
    ).one()
    assert row.ProjectID == project_id
