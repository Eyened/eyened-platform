"""Populate the derived ``ProjectID`` columns from their parent rows.

``Patient.ProjectID`` is the sole authority. Study, Series, ImageInstance and
SubTaskImageLink are each meant to carry a copy so that ``apply_scope`` is an
indexed lookup rather than a five-hop walk, with each copy held equal to its
parent by a composite foreign key (see the containment design, section 4.5).
That foreign key does not exist yet -- ``ImageInstance.ProjectID`` today
carries no foreign key at all, deliberately -- so two listeners fill the
column instead, and they cover different writers:

* **This listener, at ``before_flush``**, for writers that assign a raw
  foreign-key *id*: ``Study(PatientID=...)`` in the test factories,
  ``SubTaskRepository.add_link``. There the parent row is already persistent,
  so it can simply be read. ``before_flush`` is where querying the database is
  legal, so it resolves what it can and leaves the rest to the listener below.
* **The ``before_insert`` listener**, the backstop for a hierarchy that was
  still entirely pending at ``before_flush`` -- the importer's shape, where
  nothing upstream had a primary key yet, so ``before_flush`` found no row to
  read and left the column unset. By the time a child's INSERT is assembled,
  the unit of work has already inserted its ancestors, so the same walk now
  succeeds on in-memory attributes alone, with no query.

Neither listener is the enforcement. The foreign keys are what will guarantee
the value is correct; these only spare each writer from having to know. Raw
SQL bypasses both, and once the composite foreign keys land it will be caught
by the constraint, which is the right way round.

Task 5 adds those composite foreign keys. From then on, SQLAlchemy's own
foreign-key sync fills the column during the flush for any writer that
assigns the *relationship* (the importer's shape), and the ``before_insert``
backstop becomes a no-op. The ``before_flush`` pass here stays load-bearing
permanently, though: foreign-key sync only ever copies a relationship's
columns, and a raw-id writer never sets one, so sync never fires for that
case.
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
        required: whether a *deferrable* dead end is an error. ``False`` at
            ``before_flush``, where an ancestor may simply not have been
            inserted yet and the ``before_insert`` backstop will get a second,
            better-informed try; ``True`` at ``before_insert``, the last moment
            the value can still be set. It does not govern a parent id that
            reaches no row -- see ``Raises``.

    Returns:
        The governing ``ProjectID``, or ``None`` when the walk dead-ends on an
        ancestor that is merely pending and ``required`` is false.

    Raises:
        ValueError: naming the object and the hop that dead-ended, when either

            * a hop's id attribute is set and reaches no row. Raised whatever
              ``required`` says, because no later moment will make that id
              resolve, and deferring it only moves the failure past the
              ancestors' INSERTs, where it arrives as ``PendingRollbackError``;
            * or ``required`` and the walk dead-ends any other way.

            The composite foreign keys are still the enforcement; this only
            makes the ergonomic layer in front of them fail legibly.
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
            if parent_id is None:
                # The ancestor is merely pending -- no relationship, no id yet.
                # That is the one dead end a later moment can still resolve.
                if not required:
                    return None
            else:
                parent = session.get(parent_class, parent_id)
        if parent is None:
            # Reaching here with the id set means the id reaches no row.
            # Nothing later will make it resolve, so it is raised whatever
            # `required` says: deferring only moves the failure past the
            # ancestors' INSERTs, where it surfaces as PendingRollbackError
            # instead of as this message, before any SQL.
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
