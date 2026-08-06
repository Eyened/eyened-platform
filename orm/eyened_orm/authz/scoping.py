"""Which projects does this object touch?

``Patient.ProjectID`` is the schema's only project anchor. Every other
project-scoped entity reaches it by joins. The rule is declared **once per
entity, as a selectable**, and everything consumes that one definition: reads
correlate it into the query, writes execute it, and ``eorm grant-for-task``
executes the same function. Two implementations will drift, and the failure
mode is an administrator granting a set that does not match what the API
requires.
"""
from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, aliased

from ..base import Base
from ..form_annotation import FormAnnotation
from ..image_instance import ImageInstance
from ..patient import Patient
from ..segmentation import ModelSegmentation, Segmentation
from ..series import Series
from ..study import Study
from ..tag import (
    FormAnnotationTagLink,
    ImageInstanceTagLink,
    SegmentationTagLink,
    StudyTagLink,
)
from ..task import SubTask, SubTaskImageLink, Task

__all__ = [
    "PROJECT_IDS_OF",
    "SET_VALUED_ENTITIES",
    "SINGLE_PROJECT_ENTITIES",
    "project_id_of_column",
    "project_ids_of_form_annotation",
    "project_ids_of_image",
    "project_ids_of_model_segmentation",
    "project_ids_of_patient",
    "project_ids_of_segmentation",
    "project_ids_of_series",
    "project_ids_of_study",
    "project_ids_of_subtask",
    "project_ids_of_task",
    "projects_of",
]


# --- the correlated column form, consumed by apply_scope -------------------
#
# Each entry answers "the ProjectID of *this row*" as an expression that can be
# dropped into an outer query's WHERE clause. Patient is the anchor, so its
# entry is the column itself; everything else is a correlated scalar subquery.


def _project_id_of_study():
    return (
        select(Patient.ProjectID)
        .where(Patient.PatientID == Study.PatientID)
        .scalar_subquery()
    )


def _project_id_of_series():
    return (
        select(Patient.ProjectID)
        .join(Study, Study.PatientID == Patient.PatientID)
        .where(Study.StudyID == Series.StudyID)
        .scalar_subquery()
    )


def _project_id_of_image():
    return (
        select(Patient.ProjectID)
        .join(Study, Study.PatientID == Patient.PatientID)
        .join(Series, Series.StudyID == Study.StudyID)
        .where(Series.SeriesID == ImageInstance.SeriesID)
        .scalar_subquery()
    )


def _project_id_via_image(image_id_column):
    return (
        select(Patient.ProjectID)
        .join(Study, Study.PatientID == Patient.PatientID)
        .join(Series, Series.StudyID == Study.StudyID)
        .join(ImageInstance, ImageInstance.SeriesID == Series.SeriesID)
        .where(ImageInstance.ImageInstanceID == image_id_column)
        .scalar_subquery()
    )


def _project_id_via_patient(patient_id_column):
    return (
        select(Patient.ProjectID)
        .where(Patient.PatientID == patient_id_column)
        .scalar_subquery()
    )


def _project_id_via_study(study_id_column):
    return (
        select(Patient.ProjectID)
        .join(Study, Study.PatientID == Patient.PatientID)
        .where(Study.StudyID == study_id_column)
        .scalar_subquery()
    )


def _project_id_via_segmentation(segmentation_id_column):
    return (
        select(Patient.ProjectID)
        .join(Study, Study.PatientID == Patient.PatientID)
        .join(Series, Series.StudyID == Study.StudyID)
        .join(ImageInstance, ImageInstance.SeriesID == Series.SeriesID)
        .join(Segmentation, Segmentation.ImageInstanceID == ImageInstance.ImageInstanceID)
        .where(Segmentation.SegmentationID == segmentation_id_column)
        .scalar_subquery()
    )


def _project_id_via_form_annotation(annotation_id_column):
    return (
        select(Patient.ProjectID)
        .join(FormAnnotation, FormAnnotation.PatientID == Patient.PatientID)
        .where(FormAnnotation.FormAnnotationID == annotation_id_column)
        .scalar_subquery()
    )


_PROJECT_ID_OF: dict[type[Base], Callable[[], object]] = {
    Patient: lambda: Patient.ProjectID,
    Study: _project_id_of_study,
    Series: _project_id_of_series,
    ImageInstance: _project_id_of_image,
    Segmentation: lambda: _project_id_via_image(Segmentation.ImageInstanceID),
    ModelSegmentation: lambda: _project_id_via_image(ModelSegmentation.ImageInstanceID),
    FormAnnotation: lambda: _project_id_via_patient(FormAnnotation.PatientID),
    StudyTagLink: lambda: _project_id_via_study(StudyTagLink.StudyID),
    ImageInstanceTagLink: lambda: _project_id_via_image(
        ImageInstanceTagLink.ImageInstanceID
    ),
    SegmentationTagLink: lambda: _project_id_via_segmentation(
        SegmentationTagLink.SegmentationID
    ),
    FormAnnotationTagLink: lambda: _project_id_via_form_annotation(
        FormAnnotationTagLink.FormAnnotationID
    ),
}

SINGLE_PROJECT_ENTITIES: frozenset[type[Base]] = frozenset(_PROJECT_ID_OF)
SET_VALUED_ENTITIES: frozenset[type[Base]] = frozenset({Task, SubTask})


def project_id_of_column(entity: type[Base]):
    """The ProjectID of one row of ``entity``, as a correlated expression."""
    return _PROJECT_ID_OF[entity]()


# --- the selectable form, consumed by writes and the CLI -------------------


def project_ids_of_patient(patient_id: int) -> Select:
    return (
        select(Patient.ProjectID).where(Patient.PatientID == patient_id).distinct()
    )


def project_ids_of_study(study_id: int) -> Select:
    return (
        select(Patient.ProjectID)
        .select_from(Study)
        .join(Patient, Patient.PatientID == Study.PatientID)
        .where(Study.StudyID == study_id)
        .distinct()
    )


def project_ids_of_series(series_id: int) -> Select:
    return (
        select(Patient.ProjectID)
        .select_from(Series)
        .join(Study, Study.StudyID == Series.StudyID)
        .join(Patient, Patient.PatientID == Study.PatientID)
        .where(Series.SeriesID == series_id)
        .distinct()
    )


def project_ids_of_image(image_instance_id: int) -> Select:
    return (
        select(Patient.ProjectID)
        .select_from(ImageInstance)
        .join(Series, Series.SeriesID == ImageInstance.SeriesID)
        .join(Study, Study.StudyID == Series.StudyID)
        .join(Patient, Patient.PatientID == Study.PatientID)
        .where(ImageInstance.ImageInstanceID == image_instance_id)
        .distinct()
    )


def project_ids_of_segmentation(segmentation_id: int) -> Select:
    return (
        select(Patient.ProjectID)
        .select_from(Segmentation)
        .join(ImageInstance, ImageInstance.ImageInstanceID == Segmentation.ImageInstanceID)
        .join(Series, Series.SeriesID == ImageInstance.SeriesID)
        .join(Study, Study.StudyID == Series.StudyID)
        .join(Patient, Patient.PatientID == Study.PatientID)
        .where(Segmentation.SegmentationID == segmentation_id)
        .distinct()
    )


def project_ids_of_model_segmentation(model_segmentation_id: int) -> Select:
    return (
        select(Patient.ProjectID)
        .select_from(ModelSegmentation)
        .join(
            ImageInstance,
            ImageInstance.ImageInstanceID == ModelSegmentation.ImageInstanceID,
        )
        .join(Series, Series.SeriesID == ImageInstance.SeriesID)
        .join(Study, Study.StudyID == Series.StudyID)
        .join(Patient, Patient.PatientID == Study.PatientID)
        .where(ModelSegmentation.ModelSegmentationID == model_segmentation_id)
        .distinct()
    )


def project_ids_of_form_annotation(form_annotation_id: int) -> Select:
    return (
        select(Patient.ProjectID)
        .select_from(FormAnnotation)
        .join(Patient, Patient.PatientID == FormAnnotation.PatientID)
        .where(FormAnnotation.FormAnnotationID == form_annotation_id)
        .distinct()
    )


def project_ids_of_task(task_id: int) -> Select:
    """The projects every image of every subtask of this task sits in.

    The join deliberately does **not** filter ``ImageInstance.Inactive``: a
    soft-deleted image still ties its project to the task, and excluding it
    would silently widen who can see the task -- the one direction this design
    must never move in by accident.
    """
    return (
        select(Patient.ProjectID)
        .select_from(SubTask)
        .join(SubTaskImageLink, SubTaskImageLink.SubTaskID == SubTask.SubTaskID)
        .join(
            ImageInstance,
            ImageInstance.ImageInstanceID == SubTaskImageLink.ImageInstanceID,
        )
        .join(Series, Series.SeriesID == ImageInstance.SeriesID)
        .join(Study, Study.StudyID == Series.StudyID)
        .join(Patient, Patient.PatientID == Study.PatientID)
        .where(SubTask.TaskID == task_id)
        .distinct()
    )


def project_ids_of_subtask(subtask_id: int) -> Select:
    """The **parent task's** project set, not only this subtask's own images.

    A superset of its own, which collapses v0.3's two readings into the
    stricter one and keeps a single mental model: you see a whole task or none
    of it. See the spec's amendment note (section 12, item 3).
    """
    parent = select(SubTask.TaskID).where(SubTask.SubTaskID == subtask_id)
    sibling = aliased(SubTask)
    return (
        select(Patient.ProjectID)
        .select_from(sibling)
        .join(SubTaskImageLink, SubTaskImageLink.SubTaskID == sibling.SubTaskID)
        .join(
            ImageInstance,
            ImageInstance.ImageInstanceID == SubTaskImageLink.ImageInstanceID,
        )
        .join(Series, Series.SeriesID == ImageInstance.SeriesID)
        .join(Study, Study.StudyID == Series.StudyID)
        .join(Patient, Patient.PatientID == Study.PatientID)
        .where(sibling.TaskID.in_(parent))
        .distinct()
    )


PROJECT_IDS_OF: dict[type[Base], Callable[[int], Select]] = {
    Patient: project_ids_of_patient,
    Study: project_ids_of_study,
    Series: project_ids_of_series,
    ImageInstance: project_ids_of_image,
    Segmentation: project_ids_of_segmentation,
    ModelSegmentation: project_ids_of_model_segmentation,
    FormAnnotation: project_ids_of_form_annotation,
    Task: project_ids_of_task,
    SubTask: project_ids_of_subtask,
}


def projects_of(session: Session, entity: type[Base], entity_id: int) -> set[int]:
    """Execute the entity's rule and return its project set.

    Used by writes (``scope.require(projects_of(...), floor)``) and by the CLI's
    ``grant-for-task``. Reads correlate the same definitions instead.
    """
    return set(session.scalars(PROJECT_IDS_OF[entity](entity_id)).all())
