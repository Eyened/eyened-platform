"""Which projects does this object touch?

``Patient.ProjectID`` is the schema's only project *authority*, but no longer
the only place the answer lives: ``Study``, ``Series`` and ``ImageInstance``
each carry a copy that composite foreign keys hold equal to it, and a task's
project set is declared outright in ``TaskProject``. So an entity reaches its
project either on its own column or in one hop.

``SubTaskImageLink`` carries a fourth copy that is *not* a route: it is there
for containment -- ``(TaskID, ProjectID)`` references ``TaskProject``, which is
what refuses an image from a project its task never declared. It appears in
none of the registries below, so a scoped read of it raises rather than
resolving a route.

The route is declared **once**, in ``_OWN_PROJECT_COLUMN`` and ``_ONE_HOP_TO``,
and every consumer is built from that one definition: ``apply_scope``
correlates it into a read as an ``EXISTS``, writes execute it as a selectable,
``eorm grant-for-task`` calls the same function. Two implementations will
drift, and the failure mode is an administrator granting a set that does not
match what the API requires.

Both registries name **entities only**: the ``ProjectID`` column and each hop's
ON clause are *derived* from the entity and from the schema's own foreign keys
rather than written down beside them, so a pairing that is valid SQL with a
wrong answer cannot be written at all rather than merely being untested. Only a
wrong *entity* is expressible, and a reader can check that against the name
beside it.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from collections.abc import Set as AbstractSet
from typing import Protocol

from sqlalchemy import ColumnElement, Select, and_, exists, select
from sqlalchemy.orm import Mapped, Session
from sqlalchemy.sql import operators
from sqlalchemy.sql.elements import BinaryExpression, BooleanClauseList
from sqlalchemy.sql.util import join_condition

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
from ..task import SubTask, Task, TaskProject
from .scope import AccessScope

__all__ = [
    "PROJECT_IDS_OF",
    "SAFE_UNFILTERED_ENTITIES",
    "SET_VALUED_ENTITIES",
    "SINGLE_PROJECT_ENTITIES",
    "apply_scope",
    "image_project_pairs",
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
    "scope_criteria",
]


# --- the one route, consumed by both forms ---------------------------------
#
# The two consumers -- the selectable form (``project_ids_of_*``, executed by
# writes and the CLI) and the correlated ``EXISTS`` (``apply_scope``) -- build
# the same route with SQLAlchemy primitives that behave *oppositely* toward a
# table named in a predicate but present in no FROM. ``select().where()`` infers
# the FROM, so such a table is silently added, unjoined -- a cross join, legal
# SQL, every row returned. ``stmt.join()`` does not infer, so the same entry is
# a dangling reference and raises. One bad pairing would therefore widen every
# read while crashing the first write, and a test pointed at either consumer is
# no evidence about the other. Deriving both halves of the route removes the
# pairing rather than testing it twice.


class _CarriesProjectID(Protocol):
    """An entity whose route to its project ends on its own row."""

    ProjectID: Mapped[int]


# Entities carrying their own ProjectID: the route ends here, on *that
# entity's* column. A set, not a map, so that ``Series: Study.ProjectID``
# (valid SQL, wrong answer: cross-joins Study into the enclosing FROM and
# returns every Series row) and ``Series: Series.StudyID`` (valid SQL, no cross
# join, a StudyID judged against a project set, which on a fixture whose project
# ids and row ids coincide even gives the right answer) are unwriteable. The
# element type pins the column's *type* as well: MySQL coerces both sides of
# ``IN`` to DOUBLE, so a ``Mapped[str]`` anchor would match '03' and '3abc'
# against ``IN (3)`` where SQLite matches neither. Nothing checks the annotation
# today.
_OWN_PROJECT_COLUMN: frozenset[type[_CarriesProjectID]] = frozenset(
    {Patient, Study, Series, ImageInstance}
)

# One hop nearer a ProjectID column, named by the *parent* only; the ON clause
# comes from ``_hop_onclause``. A hand-written clause can key on the wrong
# column, key a table against itself -- which degenerates the EXISTS into "does
# any row in scope exist" and returns the whole table -- or name a parent no
# foreign key reaches; all three are valid SQL, all three are fail-open, and
# none of them is visible in the compiled statement's shape. A parent that is
# not a foreign-key neighbour raises at the first call instead.
_ONE_HOP_TO: dict[type[Base], type[Base]] = {
    Segmentation: ImageInstance,
    ModelSegmentation: ImageInstance,
    FormAnnotation: Patient,
    # A tag link carries no project of its own; it inherits its parent row's,
    # so it simply enters the chain one hop lower.
    StudyTagLink: Study,
    ImageInstanceTagLink: ImageInstance,
    SegmentationTagLink: Segmentation,
    FormAnnotationTagLink: FormAnnotation,
}

SINGLE_PROJECT_ENTITIES: frozenset[type[Base]] = (
    frozenset(_OWN_PROJECT_COLUMN) | frozenset(_ONE_HOP_TO)
)
SET_VALUED_ENTITIES: frozenset[type[Base]] = frozenset({Task, SubTask})

# Entities that carry no project anchor and are therefore safe to read
# unfiltered. Adding a name here is a claim that no membership governs the
# entity at all -- a creator, a hardware model, a segmentation feature, a form
# definition and a label exist independently of any project. Naming them is
# what lets ``scope_criteria`` fail closed on everything else instead of
# guessing, and the suite pins both directions: every member passes through,
# and a non-member raises.
SAFE_UNFILTERED_ENTITIES: frozenset[type[Base]] = frozenset(
    {Creator, DeviceInstance, DeviceModel, Feature, FormSchema, Tag}
)


def _hop_onclause(child: type[Base], parent: type[Base]) -> ColumnElement[bool]:
    """One hop's ON clause: the foreign key the schema already declares.

    Reading the constraint answers a written-out clause's failure modes
    outright: a parent no foreign key reaches raises ``NoForeignKeysError``, a
    pair with more than one candidate raises ``AmbiguousForeignKeysError``, and a
    composite key derives as the composite AND instead of one of its halves. All
    three are refusals at the first call, where the written-out version was legal
    SQL that returned too many rows.

    Each equality is then normalised child-first, because ``join_condition``
    renders the *referenced* column on the left whichever way round its
    arguments go: both orders emit ``ImageInstance.ImageInstanceID =
    Segmentation.ImageInstanceID``. ``=`` is commutative and both dialects
    agree, so the normalisation is cosmetic -- but without it every compiled
    statement that has a hop in it flips sides, and a diff of the scoped-SQL
    surface stops being evidence that the route itself has not moved.
    """
    condition = join_condition(child.__table__, parent.__table__)
    equalities = (
        condition.clauses
        if isinstance(condition, BooleanClauseList)
        else (condition,)
    )
    child_first = []
    for equality in equalities:
        if (
            not isinstance(equality, BinaryExpression)
            or equality.operator is not operators.eq
        ):
            # Unreachable for a foreign-key join; fails closed rather than let
            # an unrecognised clause through onto the authorization path.
            raise TypeError(
                f"{child.__name__} -> {parent.__name__} derived a non-equality "
                f"join condition: {equality!s}"
            )
        left, right = equality.left, equality.right
        if left.table is parent.__table__:
            left, right = right, left
        child_first.append(left == right)
    return and_(*child_first)


def _hops_to_column(
    entity: type[Base],
) -> tuple[list[tuple[type[Base], ColumnElement[bool]]], ColumnElement[int]]:
    """The one route: the hops to walk, and the ProjectID column they land on.

    The only reader of the two registries, so the correlated ``EXISTS`` and the
    executable ``Select`` are built from one declaration. The anchor is
    ``node.ProjectID`` on the entity that ends the route; each hop's ON clause
    comes from the schema.

    Bounded by ``len(_ONE_HOP_TO)`` hops -- today the longest chain is two
    (``SegmentationTagLink -> Segmentation -> ImageInstance``). A malformed map
    raises rather than looping, which matters because this sits on the
    authorization path.
    """
    joins: list[tuple[type[Base], ColumnElement[bool]]] = []
    node: type[Base] = entity
    for _ in range(len(_ONE_HOP_TO) + 1):
        if node in _OWN_PROJECT_COLUMN:
            return joins, node.ProjectID
        if node not in _ONE_HOP_TO:
            raise KeyError(
                f"{entity.__name__} has no route to a ProjectID column: "
                f"{node.__name__} is in neither _OWN_PROJECT_COLUMN nor _ONE_HOP_TO"
            )
        parent = _ONE_HOP_TO[node]
        joins.append((parent, _hop_onclause(node, parent)))
        node = parent
    raise ValueError(
        f"{entity.__name__}'s _ONE_HOP_TO chain did not reach a ProjectID column "
        f"in {len(joins)} hops -- it is likely cyclic"
    )


def _project_ids_from(
    anchor: type[Base], anchor_id_column: ColumnElement[int], entity_id: int
) -> Select:
    """The selectable form: the project one row of ``anchor`` sits in.

    No ``.distinct()``: the route ends at a column on a single row, so it
    returns exactly one by construction rather than by every hop happening to be
    many-to-one.
    """
    joins, column = _hops_to_column(anchor)
    stmt = select(column).select_from(anchor)
    for parent, onclause in joins:
        stmt = stmt.join(parent, onclause)
    return stmt.where(anchor_id_column == entity_id)


def _single_project_predicate(
    entity: type[Base], accessible: AbstractSet[int]
) -> ColumnElement[bool]:
    """``ProjectID IN (...)``, on the row's own column or through one hop.

    The four entities in ``_OWN_PROJECT_COLUMN`` get the bare column test: no
    subquery, nothing to correlate, nothing for the optimizer to get wrong. The
    two paragraphs below are about the seven that still emit an ``EXISTS``, and
    why it is an ``EXISTS`` rather than the obvious alternatives.

    ``ProjectID IN (...)`` is pushed **inside** that subquery rather than
    compared against a correlated scalar subquery in the outer WHERE. The
    scalar form is not sargable: MySQL 8.0.27 re-executes it once per outer
    row, which on 1.8M ``ImageInstance`` rows measured 687 ms for a matching
    scope and 10.2 s for a scope matching nothing -- an authenticated-user DoS
    surface, because the *empty* result is the expensive one. As an ``EXISTS``
    the optimizer decorrelates it into a semi-join that drives off the project
    index and never touches the outer table (0.005 ms on the same page). Those
    numbers were measured on a five-hop walk, but they are about the
    scalar-versus-``EXISTS`` shape rather than the length of the chain, so they
    still govern every entry that keeps a subquery.

    ``.correlate(entity)`` is load-bearing, not decoration. SQLAlchemy's
    *auto*-correlation strips from a subquery's FROM every table the enclosing
    query already has, and these subqueries select FROM tables real read queries
    also join -- ``Patient`` for the two ``FormAnnotation`` routes,
    ``ImageInstance`` for the segmentations and ``ImageInstanceTagLink``,
    ``Study`` for ``StudyTagLink``, all three of which the search layer's image
    statement holds at once. Auto-correlation would empty the FROM and raise
    ``InvalidRequestError: ... returned no FROM clauses due to
    auto-correlation``. Naming the single outer entity turns auto-correlation
    off and pins exactly one table as the correlated one, so the predicate is
    safe in any enclosing query by construction. Do not drop it because the
    subquery got smaller.
    """
    joins, column = _hops_to_column(entity)
    if not joins:
        return column.in_(accessible)
    first_parent, first_onclause = joins[0]
    inner = select(1).select_from(first_parent)
    for parent, onclause in joins[1:]:
        inner = inner.join(parent, onclause)
    return exists(
        inner.where(first_onclause).where(column.in_(accessible)).correlate(entity)
    )


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


def image_project_pairs(image_instance_ids: Sequence[int]) -> Select:
    """``(ImageInstanceID, ProjectID)`` for a batch of images, in one query.

    The batched sibling of ``project_ids_of_image``, for a gate that must judge
    a whole list of caller-supplied ids at once. It is the one selectable that
    could plausibly be hand-written, and is not: a change to the route reaches
    this gate with the read filters instead of leaving it resolving projects by
    a stale route with nothing red.

    Named for its rows rather than ``project_ids_of_images``: every
    ``project_ids_of_*`` selects one column and is consumed through
    ``session.scalars``, so under that name the same call would hand a caller
    column 0 -- *image* ids -- to feed ``AccessScope.require`` as a project set,
    wrong by construction with nothing to raise. Pairs, not bare project ids,
    because the caller needs to tell *which* id resolved to nothing: an id
    absent from the result is what its 404 is built on.

    No ``.distinct()``: the route is zero hops today -- ``ProjectID`` is a
    column on the image row itself -- so one image yields one row. What depends
    on that is not the wasted row (a duplicate pair is harmless) but the caller
    building a ``dict`` off these rows, where last-row-wins would silently keep
    one project per image. Should ``ImageInstance``'s route ever pass through a
    one-to-many hop, the gate would judge a *subset* of an image's projects
    while ``apply_scope``'s ``EXISTS`` still considers all of them; the caller
    must key by image differently before that route changes.
    """
    joins, column = _hops_to_column(ImageInstance)
    stmt = select(ImageInstance.ImageInstanceID, column).select_from(ImageInstance)
    for parent, onclause in joins:
        stmt = stmt.join(parent, onclause)
    return stmt.where(ImageInstance.ImageInstanceID.in_(image_instance_ids))


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


def project_ids_of_task(task_id: int) -> Select:
    """The projects this task declares."""
    return select(TaskProject.ProjectID).where(TaskProject.TaskID == task_id)


def project_ids_of_subtask(subtask_id: int) -> Select:
    """The **parent task's** declaration, not this subtask's own images.

    You get a whole task or none of it, so a subtask write is authorized
    against the whole task too.
    """
    parent = select(SubTask.TaskID).where(SubTask.SubTaskID == subtask_id)
    return select(TaskProject.ProjectID).where(TaskProject.TaskID.in_(parent))


def _set_valued_predicate(
    entity: type[Base], accessible: AbstractSet[int]
) -> ColumnElement[bool]:
    """NOT EXISTS (a project this task declares that is outside the scope).

    Reads the declaration rather than walking the image links, which is what
    makes this O(projects per task) instead of O(links in the task). Both
    entities key on their own ``TaskID`` column, so neither needs a join.
    ``projects_of`` dispatches to ``project_ids_of_task``/``_subtask``, which
    select from this same table -- the selectable form of what is correlated
    here, so read and write judge a task by the same set.

    Vacuity: a task declaring nothing produces no rows, so the EXISTS is false
    and NOT EXISTS is true -- it is visible to everyone. An actor with no
    memberships still sees only those, since ``NOT IN ()`` renders true and so
    excludes any task that declares anything.

    **Why the declaration cannot widen anything.** ``SubTaskImageLink`` carries
    ``(TaskID, ProjectID)`` under ``fk_SubTaskImageLink_TaskProject``, so an
    image from an undeclared project cannot be linked at all: the declaration is
    a *superset* of the projects a task's images sit in, held there by the
    database rather than by any writer. Judging the superset can only ever hide
    a task from someone who could otherwise see it, never the reverse. Where a
    declaration was seeded from the task's own images the two sets are in fact
    *equal*, which is why no pre-existing fixture or production task tells them
    apart.

    That narrowing is real, though, not a pure optimisation: a task declaring
    ``{A, B}`` whose images all sit in ``A`` is not visible to an ``A``-only
    member. Extending a declaration produces exactly that shape on purpose --
    fail-safe and deliberate, but a behaviour change.

    ``.correlate(entity)`` is load-bearing: the subquery's entire FROM is
    ``TaskProject``, so a read that joins ``TaskProject`` itself would have
    auto-correlation strip it and raise ``InvalidRequestError`` -- the failure
    that motivates the call in ``_single_project_predicate``. Naming the outer
    entity pins exactly one correlated table and turns auto-correlation off.
    """
    if entity is Task:
        task_id_column = Task.TaskID
    elif entity is SubTask:
        task_id_column = SubTask.TaskID
    else:
        raise KeyError(entity)
    inner = (
        select(1)
        .select_from(TaskProject)
        .where(TaskProject.TaskID == task_id_column)
        .where(TaskProject.ProjectID.notin_(accessible))
        .correlate(entity)
    )
    return ~exists(inner)


# Deliberately narrower than ``SINGLE_PROJECT_ENTITIES``: the four tag-link
# entities have a ``_ONE_HOP_TO`` entry above -- they must be filterable on the
# read path -- but no resolver here, so ``projects_of(session, StudyTagLink,
# ...)`` raises ``KeyError`` by design. A write that applies or removes a tag is
# authorized against its *parent* entity (the study, image, segmentation or form
# annotation being tagged), which does have a resolver. Either honour that, or
# add the four resolvers here and stop routing through the parent -- but not
# both, or the two paths will disagree.
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
    ``grant-for-task``. The read path correlates these same definitions, for
    every entity here including ``Task`` and ``SubTask``.
    """
    return set(session.scalars(PROJECT_IDS_OF[entity](entity_id)).all())


def scope_criteria(
    entity: type[Base], scope: AccessScope
) -> ColumnElement[bool] | None:
    """The predicate ``apply_scope`` would add, as a standalone criterion.

    ``apply_scope`` filters one statement, which reaches the entity that
    statement selects and nothing else. A ``selectinload`` issues a *second*
    SELECT for the collection, which the root's WHERE never touches -- so a
    relationship whose target has a different project anchor from its parent
    (``ImageInstance.FormAnnotations`` is the one such load on the read path)
    needs the same predicate handed to ``with_loader_criteria`` instead. Both
    consume this function, so the collection is filtered off the same route
    declaration as the root rather than by a second hand-written rule.

    ``None`` means "add nothing": an admin scope, or an entity declared safe to
    read unfiltered. A tautology instead would put a
    ``with_loader_criteria(..., true())`` on every admin read and read as though
    a filter were in force.
    """
    if scope.is_admin:
        return None
    accessible = frozenset(scope.project_ids)
    if entity in SET_VALUED_ENTITIES:
        return _set_valued_predicate(entity, accessible)
    if entity in SINGLE_PROJECT_ENTITIES:
        return _single_project_predicate(entity, accessible)
    if entity in SAFE_UNFILTERED_ENTITIES:
        return None
    raise KeyError(
        f"{entity.__name__} is in no scoping registry and is not declared "
        "safe to read unfiltered; add it to SINGLE_PROJECT_ENTITIES, "
        "SET_VALUED_ENTITIES or SAFE_UNFILTERED_ENTITIES"
    )


def apply_scope(stmt: Select, entity: type[Base], scope: AccessScope) -> Select:
    """Restrict ``stmt`` to rows of ``entity`` the scope may read.

    An out-of-scope row is simply not returned, and the service's existing
    ``NotFoundError`` produces the 404 -- so reads never need ``scope.require``
    and there is no path where a row is fetched first and judged afterwards.

    The registry decisions are ``scope_criteria``'s, which the eager-load path
    also consumes: entities named in ``SAFE_UNFILTERED_ENTITIES`` pass through
    unfiltered, and any entity in no registry raises ``KeyError``. Returning
    such a statement unfiltered would be a silent no-op wearing a scoped name --
    an entity that ought to be scoped but was never registered would read as
    though it had been filtered -- so failing closed makes the omission a crash
    at the first call instead of a leak.

    ``scoped_one`` raises on a strictly larger set of entities: it has no
    ``SAFE_UNFILTERED_ENTITIES`` fallback, and it is unconditional where this
    one is not -- an admin scope short-circuits here before any registry is
    consulted, so ``scoped_one(session, Project, admin)`` raises while
    ``apply_scope(stmt, Project, admin)`` returns the statement untouched.
    """
    criteria = scope_criteria(entity, scope)
    return stmt if criteria is None else stmt.where(criteria)
