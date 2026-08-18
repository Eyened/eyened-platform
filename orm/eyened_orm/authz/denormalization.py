"""Populate the derived ``ProjectID`` columns from their parent rows.

``Patient.ProjectID`` is the sole authority. Study, Series, ImageInstance and
SubTaskImageLink each carry a copy so that ``apply_scope`` is an indexed lookup
rather than a five-hop walk, and each copy is held equal to its parent by a
composite foreign key (see the containment design, section 4.5).

Two mechanisms fill those columns, and they cover different writers:

* **Foreign-key sync.** Where a writer assigns the *relationship* -- the
  importer does, at ``importer/importer.py:342`` -- SQLAlchemy's unit of work
  copies both columns of the composite key from parent to child during the
  flush. It is the only mechanism that can work when the parent is itself
  pending, because the parent's primary key does not exist until its INSERT.
* **This listener**, for writers that assign a raw foreign-key *id* instead:
  ``Study(PatientID=...)`` in the test factories, ``SubTaskRepository.add_link``.
  There the parent row is already persistent, so it can simply be read.

Neither is the enforcement. The foreign keys are what guarantee the value is
correct; these only spare each writer from having to know. Raw SQL bypasses both
and is caught by the constraint, which is the right way round.

The listener runs at two moments, because those two writers need different
ones:

* ``before_flush`` is where querying the database is legal, so it is where a
  raw-id parent gets read. It resolves what it can and leaves the rest.
* ``before_insert`` is the backstop for a hierarchy that was still entirely
  pending at ``before_flush`` -- the importer's shape, where nothing upstream
  had a primary key yet. By the time a child's INSERT is assembled the unit of
  work has already inserted its ancestors and synced their foreign keys, so the
  same walk now succeeds on in-memory attributes alone, with no query. Until
  the composite foreign keys exist, this backstop is the *only* thing that
  fills the column for that writer.
"""
from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapper, Session, UOWTransaction, object_session

from ..base import Base

__all__ = ["populate_project_id_on_insert", "populate_project_ids", "register"]

_PARENT_REF_CACHE: dict[type[Base], tuple[str, str, type[Base]]] | None = None


def _parent_ref() -> dict[type[Base], tuple[str, str, type[Base]]]:
    """``(relationship attribute, id attribute, parent class)`` for each hop.

    Built on first use rather than at import: importing the models at module
    scope closes a circular import through ``eyened_orm.__init__``.
    """
    global _PARENT_REF_CACHE
    if _PARENT_REF_CACHE is None:
        from ..image_instance import ImageInstance
        from ..patient import Patient
        from ..series import Series
        from ..study import Study

        _PARENT_REF_CACHE = {
            Study: ("Patient", "PatientID", Patient),
            Series: ("Study", "StudyID", Study),
            ImageInstance: ("Series", "SeriesID", Series),
        }
    return _PARENT_REF_CACHE


def _project_of(session: Session, obj: object, *, required: bool = True) -> int | None:
    """Walk from ``obj`` up to the ``ProjectID`` that governs it.

    Follows the *object* graph first, so a parent that is still pending -- no
    primary key, no row -- is read from memory. Only when the relationship is
    unset does it load the parent by id, which is the raw-id writer's case and
    exactly where the row does exist. Because the walk carries itself, it does
    not depend on the order ``session.new`` iterates in.

    Bounded like ``_join_to_patient``: a malformed map raises instead of
    looping, because this sits on the write path for every image.

    Args:
        required: whether a dead end is an error. ``False`` at ``before_flush``,
            where an ancestor may simply not have been inserted yet and the
            ``before_insert`` backstop will get a second, better-informed try;
            ``True`` there, at the last moment the value can still be set.

    Returns:
        The governing ``ProjectID``, or ``None`` when the walk dead-ends and
        ``required`` is false.

    Raises:
        ValueError: when ``required`` and neither route reaches a project,
            naming the object and the hop that dead-ended. The composite
            foreign keys are still the enforcement; this only makes the
            ergonomic layer in front of them fail legibly.
    """
    refs = _parent_ref()
    start = obj
    for _ in range(len(refs) + 1):
        project_id = getattr(obj, "ProjectID", None)
        if project_id is not None:
            return project_id
        ref = refs.get(type(obj))
        if ref is None:
            break
        attribute, id_attribute, parent_class = ref
        parent = getattr(obj, attribute, None)
        if parent is None:
            parent_id = getattr(obj, id_attribute, None)
            parent = (
                None if parent_id is None else session.get(parent_class, parent_id)
            )
        if parent is None:
            if not required:
                return None
            raise ValueError(
                f"cannot resolve ProjectID for {type(start).__name__}: "
                f"{type(obj).__name__}.{attribute} is unset and "
                f"{type(obj).__name__}.{id_attribute}="
                f"{getattr(obj, id_attribute, None)!r} reaches no "
                f"{parent_class.__name__} row. Assign the parent relationship "
                "or a valid parent id before flushing."
            )
        obj = parent
    if not required:
        return None
    raise ValueError(
        f"cannot resolve ProjectID for {type(start).__name__}: the walk "
        f"toward Patient.ProjectID ended at {type(obj).__name__}, which "
        "carries no ProjectID and has no known parent"
    )


def populate_project_ids(
    session: Session,
    flush_context: UOWTransaction,
    instances: Iterable[object] | None,
) -> None:
    """Fill any unset derived ``ProjectID`` before the flush that writes it.

    Anything still unresolvable here has an ancestor that is itself pending, so
    it is left to ``populate_project_id_on_insert``.
    """
    from ..image_instance import ImageInstance

    # Only ImageInstance carries the column at this point. Task 2 adds Study
    # and Series to this tuple along with their columns -- the two must move
    # together, because `obj.ProjectID` on a class that has no such column is
    # an AttributeError, not a None.
    for obj in session.new:
        if not isinstance(obj, ImageInstance):
            continue
        if obj.ProjectID is not None:
            continue
        project_id = _project_of(session, obj, required=False)
        if project_id is not None:
            obj.ProjectID = project_id


def populate_project_id_on_insert(
    mapper: Mapper, connection: Connection, target: object
) -> None:
    """Last-moment fill for a hierarchy that was wholly pending at flush start.

    Emits no query of its own: the ancestors have been inserted by now, so the
    relationship walk runs entirely on loaded attributes. Modifying a
    column-based attribute here is the documented purpose of ``before_insert``
    and is picked up by the INSERT being assembled.
    """
    if getattr(target, "ProjectID", None) is not None:
        return
    target.ProjectID = _project_of(object_session(target), target)


def register() -> None:
    """Attach the listeners to every Session and to ImageInstance. Idempotent."""
    from ..image_instance import ImageInstance

    if not event.contains(Session, "before_flush", populate_project_ids):
        event.listen(Session, "before_flush", populate_project_ids)
    if not event.contains(ImageInstance, "before_insert", populate_project_id_on_insert):
        event.listen(ImageInstance, "before_insert", populate_project_id_on_insert)
