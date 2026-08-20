"""apply_scope: containment expressed as a query rather than as a raise."""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from eyened_orm import ImageInstance, Patient, SubTask, Task
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.authz.scope import AccessScope
from eyened_orm.authz.scoping import SAFE_UNFILTERED_ENTITIES, apply_scope
from eyened_orm.tag import TagType
from eyened_orm.task import SubTaskState, TaskState
from eyened_orm.utils.factories import (
    make_creator,
    make_device,
    make_feature,
    make_form_schema,
    make_image,
    make_patient,
    make_project,
    make_series,
    make_storage_backend,
    make_study,
    make_tag,
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
    from eyened_orm import SubTaskImageLink, TaskDefinition, TaskProject

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
    # Declared before the links, because Task 6's foreign key checks the
    # declaration at the moment a link is inserted. ``empty`` declares nothing
    # on purpose: it is this file's vacuity case and holds no links.
    for name in ("A", "B"):
        session.add(
            TaskProject(TaskID=spanning.TaskID, ProjectID=made[name][0].ProjectID)
        )
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


def test_every_safe_unfiltered_entity_is_returned_unfiltered(session):
    """The declared non-project entities pass straight through.

    Membership governs nothing about a creator, a device, a feature, a form
    definition or a label, so an actor with no memberships still has to be
    able to read them -- a passthrough, not an empty result and not a raise.
    Every one of the six entities is seeded with at least one row here
    (``_fixture`` only supplies a device, i.e. ``DeviceInstance`` and
    ``DeviceModel``): an empty table would make the equality below compare
    ``[] == []`` regardless of what ``apply_scope`` did, which is a second
    way this test could bless a fail-closed function that never passes
    anything through -- the non-empty assertion closes that gap. The
    ``len(...) == 6`` assertion closes the third: an emptied frozenset would
    make the loop iterate zero times and still report green.
    """
    from eyened_orm import Creator

    _fixture(session)
    creator = make_creator(session, "alice")
    make_feature(session, "feat-1")
    make_form_schema(session, "schema-1")
    make_tag(session, "tag-1", TagType.Study, creator)
    session.commit()

    assert len(SAFE_UNFILTERED_ENTITIES) == 6
    for entity in SAFE_UNFILTERED_ENTITIES:
        base = select(entity)
        rows = session.scalars(base).all()
        assert rows, f"{entity.__name__} table is empty -- passthrough is unproven"
        assert (
            session.scalars(apply_scope(base, entity, _scope())).all() == rows
        ), entity.__name__


def test_an_entity_in_no_registry_raises_rather_than_passing_through():
    """A silent passthrough is a no-op wearing a scoped name.

    Project is the real instance, not a hypothetical: it is the anchor every
    other entity's route leads *to*, so it has no route of its own and sits in
    none of the three sets. Before this raise existed, apply_scope(stmt,
    Project, scope) returned the statement untouched and looked like scoping.
    """
    from eyened_orm import Project

    with pytest.raises(KeyError, match="Project is in no scoping registry"):
        apply_scope(select(Project), Project, _scope())


def test_an_admin_scope_short_circuits_before_the_registry_check():
    """The raise must not fire for an administrator, who reads everything.

    is_admin returns before any registry is consulted, so an unregistered
    entity is not an error on that path -- pinned because reordering those
    two blocks would turn every admin read of a non-project entity into a
    crash, and no other test in this file would notice.
    """
    from eyened_orm import Project

    base = select(Project)
    assert apply_scope(base, Project, _scope(is_admin=True)) is base
