"""apply_scope: containment expressed as a query rather than as a raise."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select

from eyened_orm import ImageInstance, Patient, SubTask, Task
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.authz.scope import AccessScope
from eyened_orm.authz.scoping import apply_scope
from eyened_orm.task import SubTaskState, TaskState
from eyened_orm.utils.factories import (
    make_creator,
    make_device,
    make_image,
    make_patient,
    make_project,
    make_series,
    make_storage_backend,
    make_study,
)


def _scope(*project_ids: int, is_admin: bool = False) -> AccessScope:
    return AccessScope(
        actor_id=7,
        username="alice",
        is_admin=is_admin,
        roles={p: ProjectRole.grader for p in project_ids},
    )


def _fixture(session):
    """Two projects, one image each, and a task spanning both."""
    from eyened_orm import SubTaskImageLink, TaskDefinition

    backend = make_storage_backend(session)
    device = make_device(session, "d")
    made = {}
    for name in ("A", "B"):
        project = make_project(session, name)
        patient = make_patient(session, project, f"pat-{name}")
        # StudyDate is NOT NULL; the brief's ``None`` fails at insert.
        study = make_study(session, patient, date(2024, 1, 1))
        series = make_series(session, study)
        image = make_image(session, series, device, backend, f"img-{name}")
        made[name] = (project, patient, image)

    taskdef = TaskDefinition(TaskDefinitionName="def")
    session.add(taskdef)
    session.flush()
    spanning = Task(TaskName="spanning", TaskDefinitionID=taskdef.TaskDefinitionID,
                    TaskState=TaskState.NotStarted)
    empty = Task(TaskName="empty", TaskDefinitionID=taskdef.TaskDefinitionID,
                 TaskState=TaskState.NotStarted)
    session.add_all([spanning, empty])
    session.flush()
    subtask = SubTask(TaskID=spanning.TaskID, TaskState=SubTaskState.NotStarted)
    lone = SubTask(TaskID=empty.TaskID, TaskState=SubTaskState.NotStarted)
    session.add_all([subtask, lone])
    session.flush()
    for index, name in enumerate(("A", "B")):
        session.add(
            SubTaskImageLink(
                SubTaskID=subtask.SubTaskID,
                ImageInstanceID=made[name][2].ImageInstanceID,
                ImageIndex=index,
            )
        )
    session.commit()
    return made, spanning, empty, subtask, lone


def test_an_admin_scope_returns_the_statement_untouched(session):
    made, _, _, _, _ = _fixture(session)
    stmt = apply_scope(select(Patient), Patient, _scope(is_admin=True))
    assert len(session.scalars(stmt).all()) == 2


def test_a_single_project_entity_is_filtered_by_its_join_path(session):
    made, _, _, _, _ = _fixture(session)
    project_a = made["A"][0].ProjectID
    stmt = apply_scope(select(ImageInstance), ImageInstance, _scope(project_a))
    rows = session.scalars(stmt).all()
    assert [r.PublicID for r in rows] == ["img-A"]


def test_a_spanning_task_is_invisible_to_a_member_of_only_one_project(session):
    """Containment: missing one project hides the whole task."""
    made, spanning, empty, _, _ = _fixture(session)
    project_a = made["A"][0].ProjectID
    stmt = apply_scope(select(Task), Task, _scope(project_a))
    assert [t.TaskName for t in session.scalars(stmt).all()] == ["empty"]


def test_a_spanning_task_is_visible_to_a_member_of_both(session):
    made, spanning, empty, _, _ = _fixture(session)
    both = (made["A"][0].ProjectID, made["B"][0].ProjectID)
    stmt = apply_scope(select(Task), Task, _scope(*both))
    assert sorted(t.TaskName for t in session.scalars(stmt).all()) == [
        "empty",
        "spanning",
    ]


def test_a_task_with_no_images_is_visible_to_an_actor_with_no_memberships(session):
    """Vacuity, and NOT IN () rendering true, in one assertion."""
    made, spanning, empty, _, _ = _fixture(session)
    stmt = apply_scope(select(Task), Task, _scope())
    assert [t.TaskName for t in session.scalars(stmt).all()] == ["empty"]


def test_a_subtask_is_hidden_by_its_parents_projects_not_its_own(session):
    """The A-only subtask of a spanning task must not be reachable on its merits."""
    made, spanning, empty, subtask, lone = _fixture(session)
    from eyened_orm import SubTaskImageLink

    a_only = SubTask(TaskID=spanning.TaskID, TaskState=SubTaskState.NotStarted)
    session.add(a_only)
    session.flush()
    session.add(
        SubTaskImageLink(
            SubTaskID=a_only.SubTaskID,
            ImageInstanceID=made["A"][2].ImageInstanceID,
            ImageIndex=0,
        )
    )
    session.commit()

    project_a = made["A"][0].ProjectID
    stmt = apply_scope(select(SubTask), SubTask, _scope(project_a))
    visible = {s.SubTaskID for s in session.scalars(stmt).all()}
    assert a_only.SubTaskID not in visible
    assert lone.SubTaskID in visible


def test_an_unregistered_entity_is_returned_unfiltered(session):
    """Non-project entities (Creator, Feature, Tag, ...) pass straight through.

    A registry miss must be a passthrough, not a KeyError and not an empty
    result -- an actor with no memberships still has to be able to read them.
    """
    from eyened_orm import Creator

    _fixture(session)
    make_creator(session, "alice")
    session.commit()
    base = select(Creator)
    assert (
        session.scalars(apply_scope(base, Creator, _scope())).all()
        == session.scalars(base).all()
    )
