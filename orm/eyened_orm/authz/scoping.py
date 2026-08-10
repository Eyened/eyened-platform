"""Which projects does this object touch?

``Patient.ProjectID`` is the schema's only project anchor. Every other
project-scoped entity reaches it by joins. That route is declared **once**, in
``_PARENT_OF``, and everything consumes that one definition: ``apply_scope``
correlates it into a read as an ``EXISTS``, writes execute it as a selectable,
and ``eorm grant-for-task`` executes the same function. Two implementations
will drift, and the failure mode is an administrator granting a set that does
not match what the API requires.
"""
from __future__ import annotations

from collections.abc import Callable
from collections.abc import Set as AbstractSet

from sqlalchemy import ColumnElement, Select, exists, select
from sqlalchemy.orm import Session, aliased
from sqlalchemy.orm.util import AliasedClass

from ..base import Base
from ..creator import Creator
from ..form_annotation import FormAnnotation, FormSchema
from ..image_instance import DeviceInstance, DeviceModel, ImageInstance
from ..patient import Patient
from ..segmentation import Feature, ModelSegmentation, Segmentation
from ..series import Series
from ..study import Study
from ..tag import (
    FormAnnotationTagLink,
    ImageInstanceTagLink,
    SegmentationTagLink,
    StudyTagLink,
    Tag,
)
from ..task import SubTask, SubTaskImageLink, Task
from .scope import AccessScope

__all__ = [
    "PROJECT_IDS_OF",
    "SAFE_UNFILTERED_ENTITIES",
    "SET_VALUED_ENTITIES",
    "SINGLE_PROJECT_ENTITIES",
    "apply_scope",
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


# --- the one join chain, consumed by both forms ----------------------------
#
# ``_PARENT_OF`` is the *only* place an entity's route to ``Patient`` is
# written down. Each entry names the next table up and the ON clause that gets
# there; ``_join_to_patient`` walks the links until it reaches the anchor. Both
# consumers below are built from that one walk -- the selectable form
# (``project_ids_of_*``, executed by writes and the CLI) and the correlated
# ``EXISTS`` predicate (``apply_scope``, correlated into a read). Two hand-
# written implementations of the same route is exactly the drift this module's
# docstring says it exists to prevent.


_PARENT_OF: dict[type[Base], tuple[type[Base], Callable[[], ColumnElement[bool]]]] = {
    Study: (Patient, lambda: Study.PatientID == Patient.PatientID),
    Series: (Study, lambda: Series.StudyID == Study.StudyID),
    ImageInstance: (Series, lambda: ImageInstance.SeriesID == Series.SeriesID),
    Segmentation: (
        ImageInstance,
        lambda: Segmentation.ImageInstanceID == ImageInstance.ImageInstanceID,
    ),
    ModelSegmentation: (
        ImageInstance,
        lambda: ModelSegmentation.ImageInstanceID == ImageInstance.ImageInstanceID,
    ),
    FormAnnotation: (Patient, lambda: FormAnnotation.PatientID == Patient.PatientID),
    # A tag link carries no project of its own; it inherits the one its parent
    # row resolves to, so it simply enters the chain one hop lower.
    StudyTagLink: (Study, lambda: StudyTagLink.StudyID == Study.StudyID),
    ImageInstanceTagLink: (
        ImageInstance,
        lambda: ImageInstanceTagLink.ImageInstanceID == ImageInstance.ImageInstanceID,
    ),
    SegmentationTagLink: (
        Segmentation,
        lambda: SegmentationTagLink.SegmentationID == Segmentation.SegmentationID,
    ),
    FormAnnotationTagLink: (
        FormAnnotation,
        lambda: FormAnnotationTagLink.FormAnnotationID
        == FormAnnotation.FormAnnotationID,
    ),
}

SINGLE_PROJECT_ENTITIES: frozenset[type[Base]] = frozenset(_PARENT_OF) | {Patient}
SET_VALUED_ENTITIES: frozenset[type[Base]] = frozenset({Task, SubTask})

# Entities that carry no project anchor and are therefore safe to read
# unfiltered. This list is the *reason* apply_scope may return a statement
# untouched; naming it is what lets that function fail closed on everything
# else instead of guessing. An entity is only safe here because a membership
# governs nothing about it -- a creator, a hardware model, a segmentation
# feature, a form definition and a label all exist independently of any
# project. Adding a name is a claim of exactly that, and the suite pins both
# directions: every member passes through, and a non-member raises.
SAFE_UNFILTERED_ENTITIES: frozenset[type[Base]] = frozenset(
    {Creator, DeviceInstance, DeviceModel, Feature, FormSchema, Tag}
)


def _join_to_patient(stmt: Select, node: type[Base]) -> Select:
    """Join ``stmt`` -- already selecting FROM ``node`` -- up to ``Patient``.

    Bounded by ``len(_PARENT_OF)`` hops: that is the longest a chain through
    the map can legitimately be, since each hop consumes one entry and none
    are revisited on a well-formed map. A malformed ``_PARENT_OF`` -- a cycle,
    or a chain that dead-ends without reaching ``Patient`` -- raises instead of
    looping forever, which matters here because this walk sits on the
    authorization path.
    """
    start = node
    for _ in range(len(_PARENT_OF) + 1):
        if node is Patient:
            return stmt
        if node not in _PARENT_OF:
            raise KeyError(
                f"{start.__name__} has no route to Patient: "
                f"{node.__name__} is not registered in _PARENT_OF"
            )
        parent, onclause = _PARENT_OF[node]
        stmt = stmt.join(parent, onclause())
        node = parent
    raise ValueError(
        f"{start.__name__}'s _PARENT_OF chain did not reach Patient within "
        f"{len(_PARENT_OF)} hops -- it is likely cyclic"
    )


def _project_ids_from(
    anchor: type[Base], anchor_id_column: ColumnElement[int], entity_id: int
) -> Select:
    """The selectable form: every project one row of ``anchor`` reaches."""
    return (
        _join_to_patient(select(Patient.ProjectID).select_from(anchor), anchor)
        .where(anchor_id_column == entity_id)
        .distinct()
    )


def _single_project_predicate(
    entity: type[Base], accessible: AbstractSet[int]
) -> ColumnElement[bool]:
    """``EXISTS`` up the chain from ``entity`` to an accessible ``Patient``.

    ``Patient.ProjectID IN (...)`` is pushed **inside** the subquery rather than
    compared against a correlated scalar subquery in the outer WHERE. The scalar
    form is not sargable: MySQL 8.0.27 re-executes it once per outer row, which
    on 1.8M ``ImageInstance`` rows measured 687 ms for a matching scope and
    10.2 s for a scope matching nothing -- an authenticated-user DoS surface,
    because the *empty* result is the expensive one. As an ``EXISTS`` the
    optimizer decorrelates it into a semi-join that drives off the project index
    and never touches the outer table (0.005 ms on the same page).

    ``.correlate(entity)`` is load-bearing, not decoration. SQLAlchemy's
    *auto*-correlation strips from a subquery's FROM every table the enclosing
    query already has, and this subquery joins tables (``Patient``, ``Study``)
    that real read queries also join -- ``join_from(Study, Patient, ...)`` is a
    shape the search layer builds today. Auto-correlation would empty the FROM
    and raise ``InvalidRequestError: ... returned no FROM clauses due to
    auto-correlation``. Naming the single outer entity turns auto-correlation
    off and pins exactly one table as the correlated one, so the predicate is
    safe in any enclosing query by construction rather than by accident.
    """
    if entity is Patient:
        return Patient.ProjectID.in_(accessible)
    parent, onclause = _PARENT_OF[entity]
    inner = (
        _join_to_patient(select(1).select_from(parent), parent)
        .where(onclause())
        .where(Patient.ProjectID.in_(accessible))
        .correlate(entity)
    )
    return exists(inner)


# --- the selectable form, consumed by writes and the CLI -------------------


def project_ids_of_patient(patient_id: int) -> Select:
    return _project_ids_from(Patient, Patient.PatientID, patient_id)


def project_ids_of_study(study_id: int) -> Select:
    return _project_ids_from(Study, Study.StudyID, study_id)


def project_ids_of_series(series_id: int) -> Select:
    return _project_ids_from(Series, Series.SeriesID, series_id)


def project_ids_of_image(image_instance_id: int) -> Select:
    return _project_ids_from(
        ImageInstance, ImageInstance.ImageInstanceID, image_instance_id
    )


def project_ids_of_segmentation(segmentation_id: int) -> Select:
    return _project_ids_from(Segmentation, Segmentation.SegmentationID, segmentation_id)


def project_ids_of_model_segmentation(model_segmentation_id: int) -> Select:
    return _project_ids_from(
        ModelSegmentation,
        ModelSegmentation.ModelSegmentationID,
        model_segmentation_id,
    )


def project_ids_of_form_annotation(form_annotation_id: int) -> Select:
    return _project_ids_from(
        FormAnnotation, FormAnnotation.FormAnnotationID, form_annotation_id
    )


def _subtask_images_to_patient(
    subtask: type[SubTask] | AliasedClass[SubTask],
) -> Select:
    """SELECT ... FROM <subtask> -> its images -> up the shared chain to Patient.

    The join deliberately does **not** filter ``ImageInstance.Inactive``: a
    soft-deleted image still ties its project to the task, and excluding it
    would silently widen who can see the task -- the one direction this design
    must never move in by accident.
    """
    return _join_to_patient(
        select(Patient.ProjectID)
        .select_from(subtask)
        .join(SubTaskImageLink, SubTaskImageLink.SubTaskID == subtask.SubTaskID)
        .join(
            ImageInstance,
            ImageInstance.ImageInstanceID == SubTaskImageLink.ImageInstanceID,
        ),
        ImageInstance,
    )


def project_ids_of_task(task_id: int) -> Select:
    """The projects every image of every subtask of this task sits in."""
    return (
        _subtask_images_to_patient(SubTask).where(SubTask.TaskID == task_id).distinct()
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
        _subtask_images_to_patient(sibling)
        .where(sibling.TaskID.in_(parent))
        .distinct()
    )


def _set_valued_predicate(
    entity: type[Base], accessible: AbstractSet[int]
) -> ColumnElement[bool]:
    """NOT EXISTS (a project of this row that is outside the accessible set).

    Gives vacuity for free: a task with no images produces no rows, so the
    EXISTS is false and NOT EXISTS is true -- visible to everyone, which is what
    v0.3 specifies. It also behaves correctly for an actor with no memberships:
    ``NOT IN ()`` renders true, so any task with at least one project is
    excluded and only the empty ones remain.

    Built on the same ``_subtask_images_to_patient`` chain as
    ``project_ids_of_task``, and correlated explicitly for the same reason as
    ``_single_project_predicate``.
    """
    sibling = aliased(SubTask)
    # SubTask is scoped by its *parent task*, not only by its own images, so
    # both branches walk every sibling subtask of the same task.
    if entity is Task:
        task_id_column = Task.TaskID
    elif entity is SubTask:
        task_id_column = SubTask.TaskID
    else:
        raise KeyError(entity)
    inner = (
        _subtask_images_to_patient(sibling)
        .where(sibling.TaskID == task_id_column)
        .where(Patient.ProjectID.notin_(accessible))
        .correlate(entity)
    )
    return ~exists(inner)


# Deliberately narrower than ``SINGLE_PROJECT_ENTITIES``: the four tag-link
# entities (``StudyTagLink``, ``ImageInstanceTagLink``, ``SegmentationTagLink``,
# ``FormAnnotationTagLink``) have a ``_PARENT_OF`` entry above -- they must be
# filterable on the read path -- but no ``projects_of`` resolver here,
# so ``projects_of(session, StudyTagLink, ...)`` raises ``KeyError`` by design.
# A tag link carries no project of its own; a write that applies or removes one
# is authorized against its *parent* entity (the study, image, segmentation or
# form annotation being tagged), which does have a resolver. Tag authorization
# must honour that, or add the four resolvers here and stop routing through the
# parent -- but not both, or the two paths will disagree.
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


def apply_scope(stmt: Select, entity: type[Base], scope: AccessScope) -> Select:
    """Restrict ``stmt`` to rows of ``entity`` the scope may read.

    An out-of-scope row is simply not returned, and the service's existing
    ``NotFoundError`` produces the 404 -- so reads never need ``scope.require``
    and there is no path where a row is fetched first and judged afterwards.

    Entities with no project anchor pass through unfiltered; that is
    deliberate, not an omission, and ``SAFE_UNFILTERED_ENTITIES`` is the list
    -- named rather than implied, so the coverage test in the suite can pin
    both directions of it.

    Raises ``KeyError`` for any other entity. Returning such a statement
    unfiltered would be a silent no-op wearing a scoped name: an entity that
    ought to be scoped but was never registered would read as though it had
    been filtered. Failing closed makes the omission a crash at the first call
    instead of a leak.

    ``scoped_one`` raises for a related but strictly narrower condition: it
    has no ``SAFE_UNFILTERED_ENTITIES`` fallback, so it raises on an entity
    this function would pass through unfiltered, and it only reaches this
    function at all once its own, earlier check has cleared.
    """
    if scope.is_admin:
        return stmt
    accessible = frozenset(scope.project_ids)
    if entity in SET_VALUED_ENTITIES:
        return stmt.where(_set_valued_predicate(entity, accessible))
    if entity in SINGLE_PROJECT_ENTITIES:
        return stmt.where(_single_project_predicate(entity, accessible))
    if entity in SAFE_UNFILTERED_ENTITIES:
        return stmt
    raise KeyError(
        f"{entity.__name__} is in no scoping registry and is not declared "
        "safe to read unfiltered; add it to SINGLE_PROJECT_ENTITIES, "
        "SET_VALUED_ENTITIES or SAFE_UNFILTERED_ENTITIES"
    )
