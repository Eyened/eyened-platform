"""One project-resolution rule per entity, shared by reads, writes and the CLI."""
from __future__ import annotations

from datetime import date

from eyened_orm import (
    FormAnnotation,
    ImageInstance,
    SubTask,
    Task,
)
from eyened_orm.authz.scoping import projects_of
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
    from eyened_orm import SubTaskImageLink

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

    from eyened_orm import SubTaskImageLink, TaskDefinition

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
    """Excluding soft-deleted images would silently *widen* who sees the task."""
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


def test_a_task_with_no_images_touches_no_projects(session):
    task, _ = _task_over(session, [])
    session.commit()
    assert projects_of(session, Task, task.TaskID) == set()


def test_a_form_annotation_resolves_through_its_patient(session):
    """Patient.ProjectID is the sole project authority for a form annotation."""
    from eyened_orm import FormSchema
    from eyened_orm.form_annotation import EntityType

    project = make_project(session, "A")
    patient = make_patient(session, project, "pat-A")
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
