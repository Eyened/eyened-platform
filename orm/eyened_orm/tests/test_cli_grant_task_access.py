"""grant-task-access: one AuditLog row per write actually made, both behind one prompt."""
from contextlib import contextmanager

from click.testing import CliRunner
from sqlalchemy import func, select

from eyened_orm import (
    AuditLog, ProjectMember, SubTask, SubTaskImageLink, Task, TaskDefinition,
)
from eyened_orm.task import TaskState
from eyened_orm.utils.factories import make_creator, make_image_in_project, make_project
from eyened_orm.utils.sqlite_testdb import session  # noqa: F401


class _SessionBoundDatabase:
    def __init__(self, session) -> None:
        self._session = session

    @contextmanager
    def get_session(self):
        yield self._session


def _spanning_task(session):
    """A task whose images live in two projects -- the shape the command exists for."""
    a = make_project(session, "RS-I")
    b = make_project(session, "RS-II")
    td = TaskDefinition(TaskDefinitionName="td")
    session.add(td)
    session.flush()
    task = Task(
        TaskName="ERGO Naevi",
        TaskDefinitionID=td.TaskDefinitionID,
        TaskState=TaskState.NotStarted,
        ProjectID=a.ProjectID,
    )
    session.add(task)
    session.flush()
    for project, key in ((a, "rs1"), (b, "rs2")):
        image = make_image_in_project(session, project, key)
        st = SubTask(TaskID=task.TaskID)
        session.add(st)
        session.flush()
        session.add(
            SubTaskImageLink(
                SubTaskID=st.SubTaskID,
                ImageInstanceID=image.ImageInstanceID,
                ImageIndex=0,
            )
        )
    session.flush()
    session.commit()
    return task, a, b


def test_grant_task_access_grants_exactly_the_anchor_membership(session, monkeypatch):
    """Two rows and no more: one UPDATE Task, one ProjectMember in the anchor."""
    import eyened_orm.cli as cli

    monkeypatch.setattr(cli, "get_database", lambda *a, **k: _SessionBoundDatabase(session))
    task, _rs1, rs2 = _spanning_task(session)
    anna = make_creator(session, "anna")
    session.commit()

    result = CliRunner().invoke(
        cli.eorm,
        ["grant-task-access", str(task.TaskID), "--user", "anna",
         "--role", "grader", "--anchor", str(rs2.ProjectID)],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    session.rollback()
    grants = session.scalars(
        select(ProjectMember).where(ProjectMember.CreatorID == anna.CreatorID)
    ).all()
    # Exactly one membership, the anchor's -- the task's other project is named
    # in the prompt but never granted.
    assert [g.ProjectID for g in grants] == [rs2.ProjectID]
    assert session.get(Task, task.TaskID).ProjectID == rs2.ProjectID


def test_grant_task_access_affirming_the_anchor_leaves_it_unchanged(session, monkeypatch):
    """The ordinary second grant must not silently re-anchor the task."""
    import eyened_orm.cli as cli

    monkeypatch.setattr(cli, "get_database", lambda *a, **k: _SessionBoundDatabase(session))
    task, _rs1, rs2 = _spanning_task(session)
    make_creator(session, "anna")
    bob = make_creator(session, "bob")
    session.commit()

    runner = CliRunner()
    runner.invoke(
        cli.eorm,
        ["grant-task-access", str(task.TaskID), "--user", "anna",
         "--role", "grader", "--anchor", str(rs2.ProjectID)],
        input="y\n",
    )
    session.rollback()
    # anna's grant already wrote a Task UPDATE row (the anchor moved rs1 ->
    # rs2); watermark it so bob's grant below can be checked in isolation.
    watermark = session.scalar(select(func.max(AuditLog.AuditLogID))) or 0

    result = runner.invoke(
        cli.eorm,
        ["grant-task-access", str(task.TaskID), "--user", "bob",
         "--role", "read_only", "--anchor", str(rs2.ProjectID)],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    session.rollback()
    assert session.get(Task, task.TaskID).ProjectID == rs2.ProjectID
    assert session.scalar(
        select(func.count()).select_from(ProjectMember)
        .where(ProjectMember.CreatorID == bob.CreatorID)
    ) == 1
    # The anchor did not move for bob's grant -- no Task row, only the
    # membership INSERT. A `_audit` call made unconditional on `report.
    # anchor_project_id` as `old` would add a false Task row here.
    rows = session.scalars(
        select(AuditLog).where(AuditLog.AuditLogID > watermark)
        .order_by(AuditLog.AuditLogID)
    ).all()
    assert [(r.Entity, r.Action) for r in rows] == [("ProjectMember", "INSERT")]


def test_grant_task_access_declined_writes_nothing(session, monkeypatch):
    """click.Abort fires before the first write, so nothing is committed."""
    import eyened_orm.cli as cli

    monkeypatch.setattr(cli, "get_database", lambda *a, **k: _SessionBoundDatabase(session))
    task, rs1, rs2 = _spanning_task(session)
    anna = make_creator(session, "anna")
    session.commit()

    result = CliRunner().invoke(
        cli.eorm,
        ["grant-task-access", str(task.TaskID), "--user", "anna",
         "--role", "grader", "--anchor", str(rs2.ProjectID)],
        input="n\n",
    )

    assert result.exit_code != 0            # click.Abort
    session.rollback()
    assert session.get(Task, task.TaskID).ProjectID == rs1.ProjectID
    assert session.scalar(
        select(func.count()).select_from(ProjectMember)
        .where(ProjectMember.CreatorID == anna.CreatorID)
    ) == 0
    assert session.scalar(select(func.count()).select_from(AuditLog)) == 0


def test_grant_task_access_audits_each_write_as_a_trusted_path(session, monkeypatch):
    """Two writes, two rows: the anchor move and the membership, actor NULL."""
    import eyened_orm.cli as cli

    monkeypatch.setattr(cli, "get_database", lambda *a, **k: _SessionBoundDatabase(session))
    task, rs1, rs2 = _spanning_task(session)
    anna = make_creator(session, "anna")
    session.commit()
    anna_id, from_id, to_id = anna.CreatorID, rs1.ProjectID, rs2.ProjectID

    result = CliRunner().invoke(
        cli.eorm,
        ["grant-task-access", str(task.TaskID), "--user", "anna",
         "--role", "grader", "--anchor", str(to_id)],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    session.rollback()
    rows = session.scalars(select(AuditLog).order_by(AuditLog.AuditLogID)).all()
    assert [(r.Entity, r.Action) for r in rows] == [
        ("Task", "UPDATE"),
        ("ProjectMember", "INSERT"),
    ]
    # A CLI has no verifiable actor; the path is what identifies the writer.
    assert {(r.ActorID, r.TrustedPath) for r in rows} == {(None, "cli:grant-task-access")}
    assert {r.ProjectID for r in rows} == {to_id}
    assert rows[0].EntityID == str(task.TaskID)
    assert rows[0].Changes == {"ProjectID": {"old": from_id, "new": to_id}}
    assert rows[1].EntityID == f"{anna_id}:{to_id}"
    # Role is stored as its *name*, not the enum: this row is built directly by
    # `_audit`, without `AuditService.record`'s JSON normalization.
    assert rows[1].Changes == {"Role": {"old": None, "new": "grader"}}


def test_grant_task_access_moving_the_anchor_with_an_unchanged_role_audits_only_the_task(
    session, monkeypatch
):
    """Anchor moves, role at the destination already matches: one row, not two.

    This is the only way to reach ``MembershipOutcome.unchanged``: a same-role
    re-grant at the SAME anchor hits the "Nothing changed." early return
    instead and never calls `ensure_membership` at all.
    """
    import eyened_orm.cli as cli
    from eyened_orm.project_member import ProjectRole
    from eyened_orm.utils.db_users import ensure_membership

    monkeypatch.setattr(cli, "get_database", lambda *a, **k: _SessionBoundDatabase(session))
    task, rs1, rs2 = _spanning_task(session)
    anna = make_creator(session, "anna")
    # anna already holds `grader` in rs2 -- set up directly, not through the
    # CLI, so this doesn't itself write an audit row.
    ensure_membership(
        session, creator_id=anna.CreatorID, project_id=rs2.ProjectID,
        role=ProjectRole.grader,
    )
    session.commit()

    result = CliRunner().invoke(
        cli.eorm,
        ["grant-task-access", str(task.TaskID), "--user", "anna",
         "--role", "grader", "--anchor", str(rs2.ProjectID)],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    session.rollback()
    assert session.get(Task, task.TaskID).ProjectID == rs2.ProjectID
    rows = session.scalars(select(AuditLog).order_by(AuditLog.AuditLogID)).all()
    assert [(r.Entity, r.Action) for r in rows] == [("Task", "UPDATE")]


def test_grant_task_access_changing_the_role_audits_the_diff(session, monkeypatch):
    """The Changes payload names both roles, not just that something changed."""
    import eyened_orm.cli as cli
    from eyened_orm.project_member import ProjectRole
    from eyened_orm.utils.db_users import ensure_membership

    monkeypatch.setattr(cli, "get_database", lambda *a, **k: _SessionBoundDatabase(session))
    task, _rs1, rs2 = _spanning_task(session)
    task.ProjectID = rs2.ProjectID  # anchor already at the target: only the role moves
    anna = make_creator(session, "anna")
    ensure_membership(
        session, creator_id=anna.CreatorID, project_id=rs2.ProjectID,
        role=ProjectRole.read_only,
    )
    session.commit()

    result = CliRunner().invoke(
        cli.eorm,
        ["grant-task-access", str(task.TaskID), "--user", "anna",
         "--role", "project_admin", "--anchor", str(rs2.ProjectID)],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    session.rollback()
    rows = session.scalars(select(AuditLog).order_by(AuditLog.AuditLogID)).all()
    assert [(r.Entity, r.Action) for r in rows] == [("ProjectMember", "UPDATE")]
    assert rows[0].Changes == {"Role": {"old": "read_only", "new": "project_admin"}}


def test_grant_task_access_park_writes_no_membership_row(session, monkeypatch):
    """--park moves the anchor but never touches ProjectMember.

    The sentinel has NO MEMBERS by design (SENTINEL_DESCRIPTION); --park takes
    no --user/--role, so there is nothing to grant even defensively.
    """
    import eyened_orm.cli as cli

    monkeypatch.setattr(cli, "get_database", lambda *a, **k: _SessionBoundDatabase(session))
    task, rs1, _rs2 = _spanning_task(session)
    session.commit()

    result = CliRunner().invoke(
        cli.eorm,
        ["grant-task-access", str(task.TaskID), "--park"],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    session.rollback()
    anchored = session.get(Task, task.TaskID).ProjectID
    assert anchored != rs1.ProjectID
    rows = session.scalars(select(AuditLog).order_by(AuditLog.AuditLogID)).all()
    assert [(r.Entity, r.Action) for r in rows] == [("Task", "UPDATE")]
    assert session.scalar(
        select(func.count()).select_from(ProjectMember)
        .where(ProjectMember.ProjectID == anchored)
    ) == 0


def test_grant_task_access_refuses_membership_when_anchor_resolves_to_the_sentinel(
    session, monkeypatch
):
    """Defense in depth: naming the sentinel's numeric id via --anchor must
    refuse the membership grant too -- the RESOLVED project decides, not
    whether the operator got there via --park."""
    import eyened_orm.cli as cli
    from eyened_orm.utils.task_projects import ensure_sentinel

    monkeypatch.setattr(cli, "get_database", lambda *a, **k: _SessionBoundDatabase(session))
    task, _rs1, _rs2 = _spanning_task(session)
    sentinel_id, _ = ensure_sentinel(session, "_unresolved_legacy_tasks")
    anna = make_creator(session, "anna")
    session.commit()

    result = CliRunner().invoke(
        cli.eorm,
        ["grant-task-access", str(task.TaskID), "--user", "anna",
         "--role", "grader", "--anchor", str(sentinel_id), "--force"],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    session.rollback()
    assert session.get(Task, task.TaskID).ProjectID == sentinel_id
    assert session.scalar(
        select(func.count()).select_from(ProjectMember)
        .where(ProjectMember.CreatorID == anna.CreatorID)
    ) == 0


def test_grant_task_access_refuses_membership_when_sentinel_name_flag_is_wrong(
    session, monkeypatch
):
    """The --sentinel-name flag is operator-supplied and easy to forget or
    mistype. Minting the sentinel under one name, then reaching it by id while
    passing a DIFFERENT --sentinel-name, must still refuse the membership
    grant -- the name-only check would say False here and let the grant
    through, which is exactly the hole this test pins shut.
    """
    import eyened_orm.cli as cli
    from eyened_orm.utils.task_projects import ensure_sentinel

    monkeypatch.setattr(cli, "get_database", lambda *a, **k: _SessionBoundDatabase(session))
    task, _rs1, _rs2 = _spanning_task(session)
    sentinel_id, _ = ensure_sentinel(session, "_parked")
    anna = make_creator(session, "anna")
    session.commit()

    result = CliRunner().invoke(
        cli.eorm,
        ["grant-task-access", str(task.TaskID), "--user", "anna",
         "--role", "grader", "--anchor", str(sentinel_id), "--force",
         "--sentinel-name", "_not_the_actual_sentinel_name"],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    session.rollback()
    assert session.get(Task, task.TaskID).ProjectID == sentinel_id
    assert session.scalar(
        select(func.count()).select_from(ProjectMember)
        .where(ProjectMember.CreatorID == anna.CreatorID)
    ) == 0


def test_grant_task_access_park_rejects_user_and_role(session, monkeypatch):
    """--park never grants membership -- passing --user/--role with it must be
    rejected before anything is resolved or written."""
    import eyened_orm.cli as cli

    monkeypatch.setattr(cli, "get_database", lambda *a, **k: _SessionBoundDatabase(session))
    task, _rs1, _rs2 = _spanning_task(session)
    make_creator(session, "anna")
    session.commit()

    result = CliRunner().invoke(
        cli.eorm,
        ["grant-task-access", str(task.TaskID), "--park",
         "--user", "anna", "--role", "grader"],
    )

    assert result.exit_code != 0
    assert "--user" in result.output or "--role" in result.output
    session.rollback()
    assert session.scalar(select(func.count()).select_from(AuditLog)) == 0


def test_grant_task_access_requires_user_and_role_unless_parked(session, monkeypatch):
    """A real --anchor without --user/--role is not implicitly a park."""
    import eyened_orm.cli as cli

    monkeypatch.setattr(cli, "get_database", lambda *a, **k: _SessionBoundDatabase(session))
    task, _rs1, rs2 = _spanning_task(session)
    session.commit()

    result = CliRunner().invoke(
        cli.eorm,
        ["grant-task-access", str(task.TaskID), "--anchor", str(rs2.ProjectID)],
    )

    assert result.exit_code != 0
    assert "--user" in result.output or "--role" in result.output
    session.rollback()
    assert session.scalar(select(func.count()).select_from(AuditLog)) == 0
