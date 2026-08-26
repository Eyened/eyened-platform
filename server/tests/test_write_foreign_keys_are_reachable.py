"""A write may not point a new row at an object the caller cannot reach.

``FormAnnotationService.create`` already resolves ``image_id`` through the
**scoped** ``ImageInstanceRepository``, so an image in another project reads as
not-found. Its sibling foreign keys -- ``study_id``, ``sub_task_id``,
``form_annotation_reference_id``, and on the segmentation side ``subtask_id``
and ``reference_segmentation_id`` -- were written straight from the request
body with no reach check at all.

These are unauthorized writes in their own right, and they are the substrate
that produces a row whose anchors disagree: the mis-scoped shape the eager-load
filter now has to defend against on the read side.

``feature_id`` is deliberately absent from this file: a ``Feature`` is
annotation vocabulary with no project anchor (``SAFE_UNFILTERED_ENTITIES``), so
there is nothing to be out of reach of.
"""
from datetime import date
from types import SimpleNamespace

import numpy as np
import pytest

from eyened_orm import SubTask, Task, TaskDefinition
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.repositories.form_annotation_repository import (
    FormAnnotationRepository,
)
from eyened_orm.repositories.image_instance_repository import (
    ImageInstanceRepository,
)
from eyened_orm.repositories.segmentation_repository import SegmentationRepository
from eyened_orm.repositories.tag_repository import TagRepository
from eyened_orm.repositories.task_repository import SubTaskRepository
from eyened_orm.segmentation import DataRepresentation, Datatype
from eyened_orm.task import SubTaskImageLink, SubTaskState, TaskState
from eyened_orm.utils.factories import (
    make_creator,
    make_device,
    make_feature,
    make_form_annotation,
    make_form_schema,
    make_image,
    make_patient,
    make_project,
    make_segmentation,
    make_series,
    make_storage_backend,
    make_study,
    scope_for,
)

from server.services.exceptions import NotFoundError
from server.services.form_annotation_service import FormAnnotationService
from server.services.segmentation_service import SegmentationService
from server.tests.test_segmentation_service import FakeSegmentationDataStore


@pytest.fixture()
def two_projects(session):
    """One patient/study/image/subtask/annotation/segmentation in each project.

    Every id the tests point at exists in **both** projects, so each negative
    case has a positive twin of the same shape: a refusal then means "out of
    reach", not "this field is rejected".

    Ids are read out before ``commit()`` and the session emptied after it, so
    the scoped lookups under test issue real SELECTs rather than being answered
    from the identity map.
    """
    backend = make_storage_backend(session)
    device = make_device(session, "fk")
    schema = make_form_schema(session, "fk-schema")
    feature = make_feature(session, "fk-feature")
    author = make_creator(session, "fk-author")
    taskdef = TaskDefinition(TaskDefinitionName="fk-def")
    session.add(taskdef)
    session.flush()

    per_project = {}
    for name in ("A", "B"):
        project = make_project(session, f"fk-{name}")
        patient = make_patient(session, project, f"fk-pat-{name}")
        study = make_study(session, patient, date(2024, 1, 1))
        series = make_series(session, study)
        image = make_image(session, series, device, backend, f"fk-img-{name}")

        task = Task(
            TaskName=f"fk-task-{name}",
            TaskDefinitionID=taskdef.TaskDefinitionID,
            TaskState=TaskState.NotStarted,
        )
        session.add(task)
        session.flush()
        subtask = SubTask(TaskID=task.TaskID, TaskState=SubTaskState.NotStarted)
        session.add(subtask)
        session.flush()
        # The link is what puts the subtask in a project at all: a subtask whose
        # task holds no images touches no project and is visible to everyone.
        session.add(
            SubTaskImageLink(
                SubTaskID=subtask.SubTaskID,
                ImageInstanceID=image.ImageInstanceID,
                ImageIndex=0,
            )
        )
        session.flush()

        annotation = make_form_annotation(session, schema, patient, author)
        segmentation = make_segmentation(session, image, feature, author)

        per_project[name] = SimpleNamespace(
            project=project.ProjectID,
            patient=patient.PatientID,
            study=study.StudyID,
            image=image.PublicID,
            subtask=subtask.SubTaskID,
            annotation=annotation.FormAnnotationID,
            segmentation=segmentation.SegmentationID,
        )

    data = SimpleNamespace(
        a=per_project["A"],
        b=per_project["B"],
        schema=schema.FormSchemaID,
        feature=feature.FeatureID,
        author=author.CreatorID,
    )
    session.commit()
    session.expunge_all()
    return data


def _scope(two_projects):
    """Grader in project A only, acting as the author of every seeded row."""
    return scope_for(
        two_projects.a.project,
        role=ProjectRole.grader,
        actor_id=two_projects.author,
    )


def _annotations(session, scope) -> FormAnnotationService:
    return FormAnnotationService(
        FormAnnotationRepository(session, scope=scope),
        ImageInstanceRepository(session, scope=scope),
        TagRepository(session, scope=scope),
        SubTaskRepository(session, scope=scope),
        scope=scope,
        audit=None,
    )


def _segmentations(session, scope) -> SegmentationService:
    return SegmentationService(
        SegmentationRepository(session, scope=scope),
        ImageInstanceRepository(session, scope=scope),
        TagRepository(session, scope=scope),
        FakeSegmentationDataStore(),
        SubTaskRepository(session, scope=scope),
        scope=scope,
        audit=None,
    )


def _create_kwargs(two_projects, **overrides):
    """A create call that succeeds untouched; each test breaks one field."""
    return {
        "form_schema_id": two_projects.schema,
        "patient_id": two_projects.a.patient,
        "study_id": None,
        "image_id": None,
        "laterality": None,
        "sub_task_id": None,
        "form_data": {"answer": 1},
        "form_annotation_reference_id": None,
        **overrides,
    }


def _segmentation_kwargs(two_projects, **overrides):
    return {
        "image_id": two_projects.a.image,
        "feature_id": two_projects.feature,
        "subtask_id": None,
        "data_type": Datatype.R8UI,
        "data_representation": DataRepresentation.Binary,
        "depth": 1,
        "height": 4,
        "width": 4,
        "sparse_axis": None,
        "image_projection_matrix": None,
        "scan_indices": None,
        "threshold": None,
        "reference_segmentation_id": None,
        "array": np.zeros((1, 4, 4), dtype=np.uint8),
        **overrides,
    }


@pytest.mark.parametrize(
    "field",
    ["study_id", "sub_task_id", "form_annotation_reference_id"],
)
def test_annotation_create_refuses_an_out_of_reach_foreign_key(
    session, two_projects, field
):
    """Each id is resolved through the caller's scope, exactly as image_id is."""
    out_of_reach = {
        "study_id": two_projects.b.study,
        "sub_task_id": two_projects.b.subtask,
        "form_annotation_reference_id": two_projects.b.annotation,
    }[field]

    with pytest.raises(NotFoundError):
        _annotations(session, _scope(two_projects)).create(
            **_create_kwargs(two_projects, **{field: out_of_reach})
        )


def test_annotation_create_accepts_the_same_foreign_keys_inside_the_project(
    session, two_projects
):
    """The control: the refusals above are about reach, not about the fields."""
    created = _annotations(session, _scope(two_projects)).create(
        **_create_kwargs(
            two_projects,
            study_id=two_projects.a.study,
            sub_task_id=two_projects.a.subtask,
            form_annotation_reference_id=two_projects.a.annotation,
        )
    )

    assert created.StudyID == two_projects.a.study
    assert created.SubTaskID == two_projects.a.subtask
    assert created.FormAnnotationReferenceID == two_projects.a.annotation


@pytest.mark.parametrize(
    "field",
    ["study_id", "sub_task_id", "form_annotation_reference_id"],
)
def test_annotation_update_refuses_an_out_of_reach_foreign_key(
    session, two_projects, field
):
    """update writes the same three ids through _FIELD_MAP, so it checks them too."""
    out_of_reach = {
        "study_id": two_projects.b.study,
        "sub_task_id": two_projects.b.subtask,
        "form_annotation_reference_id": two_projects.b.annotation,
    }[field]

    with pytest.raises(NotFoundError):
        _annotations(session, _scope(two_projects)).update(
            two_projects.a.annotation, {field: out_of_reach}
        )


@pytest.mark.parametrize("field", ["subtask_id", "reference_segmentation_id"])
def test_segmentation_create_refuses_an_out_of_reach_foreign_key(
    session, two_projects, field
):
    """A segmentation on an in-reach image may not cite out-of-reach rows."""
    out_of_reach = {
        "subtask_id": two_projects.b.subtask,
        "reference_segmentation_id": two_projects.b.segmentation,
    }[field]

    with pytest.raises(NotFoundError):
        _segmentations(session, _scope(two_projects)).create(
            **_segmentation_kwargs(two_projects, **{field: out_of_reach})
        )


def test_segmentation_create_accepts_the_same_foreign_keys_inside_the_project(
    session, two_projects
):
    """The control for the two refusals above."""
    created = _segmentations(session, _scope(two_projects)).create(
        **_segmentation_kwargs(
            two_projects,
            subtask_id=two_projects.a.subtask,
            reference_segmentation_id=two_projects.a.segmentation,
        )
    )

    assert created.SubTaskID == two_projects.a.subtask
    assert created.ReferenceSegmentationID == two_projects.a.segmentation


def test_segmentation_patch_refuses_an_out_of_reach_reference(session, two_projects):
    """patch writes ReferenceSegmentationID on an existing row; same rule."""
    with pytest.raises(NotFoundError):
        _segmentations(session, _scope(two_projects)).patch(
            two_projects.a.segmentation,
            reference_segmentation_id=two_projects.b.segmentation,
            feature_id=None,
            threshold=None,
        )
