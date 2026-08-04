"""grant-task-access: one UPDATE Task, one ProjectMember, both behind one prompt."""
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
    # Role is stored as its *name*, not the enum: this row is built directly,
    # without AuditService.record's JSON normalization (see Step 7).
    assert rows[1].Changes == {"Role": {"old": None, "new": "grader"}}
