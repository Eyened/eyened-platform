"""One project-resolution rule per entity, shared by reads, writes and the CLI."""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import sqlite

from eyened_orm import (
    FormAnnotation,
    ImageInstance,
    Patient,
    Series,
    Study,
    SubTask,
    Task,
)
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.authz.scope import AccessScope
from eyened_orm.authz.scoping import (
    SINGLE_PROJECT_ENTITIES,
    apply_scope,
    projects_of,
)
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


def _image_in(session, project_name, public_id, backend, device):
    project = make_project(session, project_name)
    patient = make_patient(session, project, f"pat-{project_name}")
    study = make_study(session, patient, date(2024, 1, 1))
    series = make_series(session, study)
    image = make_image(session, series, device, backend, public_id)
    return project, image


def _task_over(session, images, *, name="T"):
    from eyened_orm import TaskDefinition

    images = list(images)
    taskdef = TaskDefinition(TaskDefinitionName=f"def-{name}")
    session.add(taskdef)
    session.flush()
    task = Task(TaskName=name, TaskDefinitionID=taskdef.TaskDefinitionID,
                TaskState=TaskState.NotStarted)
    session.add(task)
    session.flush()
    subtask = SubTask(TaskID=task.TaskID, TaskState=SubTaskState.NotStarted)
    session.add(subtask)
    session.flush()
    from eyened_orm import SubTaskImageLink, TaskProject

    # Declared before the links, because Task 6's foreign key checks the
    # declaration at the moment a link is inserted. An empty ``images``
    # declares nothing, which is the no-images case one caller relies on.
    for project_id in sorted({image.ProjectID for image in images}):
        session.add(TaskProject(TaskID=task.TaskID, ProjectID=project_id))
    session.flush()
    for index, image in enumerate(images):
        session.add(
            SubTaskImageLink(
                SubTaskID=subtask.SubTaskID,
                ImageInstanceID=image.ImageInstanceID,
                ImageIndex=index,
            )
        )
    session.flush()
    return task, subtask


def test_an_image_resolves_to_its_patients_project(session):
    backend = make_storage_backend(session)
    device = make_device(session, "d")
    project, image = _image_in(session, "A", "img-a", backend, device)
    # A second project + patient, so a resolver that returned *every* project in
    # the database would fail this assertion instead of passing it.
    make_patient(session, make_project(session, "B"), "pat-B")
    session.commit()
    assert projects_of(session, ImageInstance, image.ImageInstanceID) == {
        project.ProjectID
    }


def test_a_task_resolves_to_every_project_its_images_touch(session):
    backend = make_storage_backend(session)
    device = make_device(session, "d")
    project_a, image_a = _image_in(session, "A", "img-a", backend, device)
    project_b, image_b = _image_in(session, "B", "img-b", backend, device)
    task, _ = _task_over(session, [image_a, image_b])
    session.commit()
    assert projects_of(session, Task, task.TaskID) == {
        project_a.ProjectID,
        project_b.ProjectID,
    }


def test_a_subtask_resolves_to_its_parent_tasks_projects(session):
    """A superset of its own images: you see a whole task or none of it.

    v0.3 can be read both ways -- its Visibility table says a subtask's projects
    are "the projects of its images", consequence 1 says a user missing any of a
    task's projects sees no part of it. The stricter reading wins, per v0.3's
    own tie-breaker: prefer the rule that can be tightened later without
    withdrawing something users already have.
    """
    backend = make_storage_backend(session)
    device = make_device(session, "d")
    project_a, image_a = _image_in(session, "A", "img-a", backend, device)
    project_b, image_b = _image_in(session, "B", "img-b", backend, device)

    from eyened_orm import SubTaskImageLink, TaskDefinition, TaskProject

    taskdef = TaskDefinition(TaskDefinitionName="def")
    session.add(taskdef)
    session.flush()
    task = Task(TaskName="T", TaskDefinitionID=taskdef.TaskDefinitionID,
                TaskState=TaskState.NotStarted)
    session.add(task)
    session.flush()
    only_a = SubTask(TaskID=task.TaskID, TaskState=SubTaskState.NotStarted)
    only_b = SubTask(TaskID=task.TaskID, TaskState=SubTaskState.NotStarted)
    session.add_all([only_a, only_b])
    session.flush()
    # Declared before the links: Task 6's foreign key checks the declaration at
    # the moment a link is inserted, and this task spans both projects.
    session.add_all([
        TaskProject(TaskID=task.TaskID, ProjectID=project_a.ProjectID),
        TaskProject(TaskID=task.TaskID, ProjectID=project_b.ProjectID),
    ])
    session.flush()
    session.add_all([
        SubTaskImageLink(SubTaskID=only_a.SubTaskID,
                         ImageInstanceID=image_a.ImageInstanceID, ImageIndex=0),
        SubTaskImageLink(SubTaskID=only_b.SubTaskID,
                         ImageInstanceID=image_b.ImageInstanceID, ImageIndex=0),
    ])
    session.commit()

    both = {project_a.ProjectID, project_b.ProjectID}
    assert projects_of(session, SubTask, only_a.SubTaskID) == both
    assert projects_of(session, SubTask, only_b.SubTaskID) == both


def test_an_inactive_image_still_ties_its_project_to_the_task(session):
    """Excluding soft-deleted images would silently *widen* who sees the task.

    No longer what this asserts. ``projects_of`` reads ``TaskProject``, so this
    now only pins that ``_task_over`` wrote a declaration covering both
    projects -- not that the resolution declines to filter ``Inactive``, which
    it no longer walks at all. The behaviour named above moved to the
    backfill's SQL, which is where it is guarded now. Kept rather than deleted
    because the assertion is still true and still worth holding: a soft-deleted
    image must not cost its task a declared project.
    """
    backend = make_storage_backend(session)
    device = make_device(session, "d")
    project_a, image_a = _image_in(session, "A", "img-a", backend, device)

    project_b = make_project(session, "B")
    patient_b = make_patient(session, project_b, "pat-B")
    study_b = make_study(session, patient_b, date(2024, 1, 1))
    series_b = make_series(session, study_b)
    image_b = make_image(session, series_b, device, backend, "img-b", inactive=True)

    task, _ = _task_over(session, [image_a, image_b])
    session.commit()
    assert projects_of(session, Task, task.TaskID) == {
        project_a.ProjectID,
        project_b.ProjectID,
    }


def test_a_task_that_declares_nothing_touches_no_projects(session):
    """The empty declaration -- the shape ``require`` fails closed on.

    ``projects_of`` reads ``TaskProject``, so what produces the empty set is
    the empty declaration and not the absence of images: ``_task_over``
    declares one project per distinct image project, and an empty ``images``
    list declares none.
    """
    task, _ = _task_over(session, [])
    session.commit()
    assert projects_of(session, Task, task.TaskID) == set()


def test_a_form_annotation_resolves_through_its_patient(session):
    """Patient.ProjectID is the sole project authority for a form annotation."""
    from eyened_orm import FormSchema
    from eyened_orm.form_annotation import EntityType

    project = make_project(session, "A")
    patient = make_patient(session, project, "pat-A")
    # A second project + patient, so a resolver returning every project in the
    # database fails here rather than passing by accident.
    make_patient(session, make_project(session, "B"), "pat-B")
    creator = make_creator(session, "alice")
    schema = FormSchema(SchemaName="s", Schema={}, EntityType=EntityType.ImageInstance)
    session.add(schema)
    session.flush()
    annotation = FormAnnotation(
        FormSchemaID=schema.FormSchemaID,
        PatientID=patient.PatientID,
        CreatorID=creator.CreatorID,
    )
    session.add(annotation)
    session.commit()
    assert projects_of(session, FormAnnotation, annotation.FormAnnotationID) == {
        project.ProjectID
    }


# --- the correlated EXISTS predicate that apply_scope emits ------------------
#
# These three retarget Task 4's guards from the scalar-subquery form
# (``project_id_of_column``, removed) onto the EXISTS form that replaced it.
# The hazard they guard -- auto-correlation emptying the subquery's FROM -- is
# unchanged by the shape of the subquery, so the coverage had to move, not go.


def _grader_scope(*project_ids: int) -> AccessScope:
    return AccessScope(
        actor_id=7,
        username="alice",
        is_admin=False,
        roles={p: ProjectRole.grader for p in project_ids},
    )


@pytest.mark.parametrize(
    "entity", sorted(SINGLE_PROJECT_ENTITIES, key=lambda e: e.__name__),
    ids=lambda e: e.__name__,
)
def test_apply_scope_compiles_inside_a_query_that_also_joins_patient(entity):
    """Every entry must survive an enclosing query that already selects Patient.

    Without this: SQLAlchemy *auto*-correlation strips from a subquery's FROM
    every table the enclosing query already has. The Study and FormAnnotation
    entries used to reach Patient with no explicit ``.correlate(...)``, so an
    outer query holding both Patient and the entity emptied their FROM and
    SQLAlchemy raised ``InvalidRequestError: ... returned no FROM clauses due to
    auto-correlation``. The search layer builds exactly that shape
    (``join_from(Study, Patient, ...)``), so the read path would 500. The other
    entries only survived by accident -- their FROM is a single Join object that
    never matches an enclosing table by identity -- which an innocuous edit to
    any helper would remove. Parametrized over the registry so a future entity
    is covered without anyone remembering to add a case.
    """
    outer = apply_scope(
        select(entity).select_from(entity, Patient), entity, _grader_scope(1)
    )
    sql = str(outer.compile(dialect=sqlite.dialect()))
    assert "ProjectID" in sql


def test_apply_scope_filters_a_study_to_one_project(session):
    """Compiling is not filtering: prove the correlation binds to the outer row.

    Without this a degenerate predicate -- correlated against the wrong table,
    or not correlated at all -- would still compile and still pass the test
    above while returning every study or none.
    """
    backend = make_storage_backend(session)
    device = make_device(session, "d")
    project_a, image_a = _image_in(session, "A", "img-a", backend, device)
    _image_in(session, "B", "img-b", backend, device)
    session.commit()
    project_a_id = project_a.ProjectID
    study_a_id = session.scalars(
        select(Series.StudyID).where(Series.SeriesID == image_a.SeriesID)
    ).one()

    found = session.scalars(
        apply_scope(
            select(Study.StudyID).join(Patient, Patient.PatientID == Study.PatientID),
            Study,
            _grader_scope(project_a_id),
        )
    ).all()
    assert set(found) == {study_a_id}


def test_apply_scope_filters_an_image_to_one_project(session):
    """The same proof one level deeper, through Series and Study.

    Without this, an image-level predicate that resolved to the wrong join
    chain would be caught only in the API.
    """
    backend = make_storage_backend(session)
    device = make_device(session, "d")
    project_a, image_a = _image_in(session, "A", "img-a", backend, device)
    _image_in(session, "B", "img-b", backend, device)
    session.commit()
    project_a_id = project_a.ProjectID
    image_a_id = image_a.ImageInstanceID

    found = session.scalars(
        apply_scope(
            select(ImageInstance.ImageInstanceID)
            .join(Series, Series.SeriesID == ImageInstance.SeriesID)
            .join(Study, Study.StudyID == Series.StudyID)
            .join(Patient, Patient.PatientID == Study.PatientID),
            ImageInstance,
            _grader_scope(project_a_id),
        )
    ).all()
    assert set(found) == {image_a_id}
