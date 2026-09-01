"""Populate the derived ``ProjectID`` columns from their parent rows.

``Patient.ProjectID`` is the sole authority. Study, Series, ImageInstance and
SubTaskImageLink each carry a copy so that ``apply_scope`` is an indexed lookup
rather than a five-hop walk, held equal to its parent by a composite foreign
key. SubTaskImageLink carries a copy of TaskID under one as well, and is held
inside its task's declaration by a third. The two listeners here fill the
columns for the writers the constraints alone cannot serve:

* **``before_flush``**, for writers that assign a raw foreign-key *id*:
  ``Study(PatientID=...)`` in the test factories, ``SubTaskRepository.add_link``.
  The parent row is already persistent, so it can be read -- and ``before_flush``
  is the moment where querying the database is legal. What it cannot resolve it
  leaves unset for foreign-key sync to fill during the flush.
  This pass is permanently load-bearing: foreign-key sync only ever copies a
  *relationship's* columns, and a raw-id writer never sets one. Measured with
  both listeners removed, a raw-id ``Study(PatientID=...)`` dies on ``NOT NULL
  constraint failed: Study.ProjectID``.
* **``before_insert``**, the backstop for a hierarchy still entirely pending at
  ``before_flush`` -- the importer's shape, nothing upstream holding a primary
  key yet.

**The ``before_insert`` backstop is a no-op, and is kept anyway.** Two
mechanisms reach the value before it runs: ``_project_of`` walks the *object*
graph, so the ``before_flush`` pass resolves a wholly-pending hierarchy from
memory; and SQLAlchemy's foreign-key sync copies ProjectID parent-to-child
during the flush for any writer that assigns the relationship. Measured over the
whole backend suite, the backstop fired 2228 times and set a value zero times;
with both listeners stripped, foreign-key sync alone fills all three levels of
the importer's shape. Removing a redundant safety net is a decision for whoever
weighs it deliberately, with those numbers in hand.

Neither listener is the enforcement. The foreign keys guarantee the value is
correct; these only spare each writer from having to know. Raw SQL bypasses
both and is caught by the constraint, which is the right way round.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapper, Session, UOWTransaction, object_session

from ..base import Base

if TYPE_CHECKING:
    # Deferred: importing ``..task`` at module scope closes a circular import
    # through ``eyened_orm.__init__``. ``from __future__ import annotations``
    # above means the annotation below is never evaluated at runtime.
    from ..task import SubTaskImageLink

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
    not depend on the order ``session.new`` iterates in. Bounded, so a malformed
    map raises instead of looping: this sits on the write path for every image.

    Args:
        required: whether a *deferrable* dead end is an error. ``False`` at
            ``before_flush``, where an ancestor may simply not have been
            inserted yet and foreign-key sync will fill the column during the
            flush; ``True`` at ``before_insert``, the last moment this listener
            could set it. It does not govern a parent id that reaches no row --
            see ``Raises``.

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
            # Reaching here with the id set means the id reaches no row: raised
            # whatever `required` says, for the reason given under Raises above.
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

    Anything still unresolvable here has an ancestor that is itself pending,
    and is deliberately left unset: the flush that follows copies the value
    down parent-to-child by foreign-key sync, not the ``before_insert``
    backstop.
    """
    from ..image_instance import ImageInstance
    from ..series import Series
    from ..study import Study
    from ..task import SubTaskImageLink

    # This tuple and the columns move together: `obj.ProjectID` on a class that
    # does not carry the column is an AttributeError, not a None, and a class
    # that carries it but is left out here gets no value from any raw-id writer
    # and dies on NOT NULL.
    for obj in session.new:
        # Checked first and `continue`d: a link has two columns to fill, and
        # the shared `ProjectID is not None` guard below would skip one whose
        # ProjectID is set but whose TaskID is not.
        if isinstance(obj, SubTaskImageLink):
            _populate_link(session, obj)
            continue
        if not isinstance(obj, (Study, Series, ImageInstance)):
            continue
        if obj.ProjectID is not None:
            continue
        project_id = _project_of(session, obj, required=False)
        if project_id is not None:
            obj.ProjectID = project_id


def _populate_link(session: Session, link: "SubTaskImageLink") -> None:
    """Fill a link's TaskID and ProjectID, where they can be known yet.

    ``TaskID`` is left alone when the parent SubTask is itself pending: its own
    ``TaskID`` is not assigned until the Task's INSERT, so there is nothing to
    copy. Foreign-key sync fills it during the flush -- the only mechanism that
    can, and the reason the columns and the composite key ship together.

    ``_project_of`` is called with its default ``required=True`` here, unlike
    the caller above: ``image`` is always persistent, so a dead end is a real
    error rather than something a later moment resolves. That is also why this
    table gets no ``before_insert`` backstop.
    """
    from ..image_instance import ImageInstance
    from ..task import SubTask

    if link.TaskID is None:
        subtask = link.SubTask
        if subtask is None and link.SubTaskID is not None:
            subtask = session.get(SubTask, link.SubTaskID)
        if subtask is not None and subtask.TaskID is not None:
            link.TaskID = subtask.TaskID
    if link.ProjectID is None:
        image = link.ImageInstance
        if image is None and link.ImageInstanceID is not None:
            image = session.get(ImageInstance, link.ImageInstanceID)
        if image is not None:
            link.ProjectID = _project_of(session, image)


def populate_project_id_on_insert(
    mapper: Mapper, connection: Connection, target: object
) -> None:
    """Last-moment fill for a hierarchy that was wholly pending at flush start.

    Emits no query of its own: the ancestors have been inserted by now, so the
    relationship walk runs entirely on loaded attributes. Modifying a
    column-based attribute here is the documented purpose of ``before_insert``
    and is picked up by the INSERT being assembled.

    A no-op in practice; see this module's docstring for why it is kept anyway.
    """
    if getattr(target, "ProjectID", None) is not None:
        return
    target.ProjectID = _project_of(object_session(target), target)


def register() -> None:
    """Attach the listeners to every Session and to every carrier class.

    The carriers are Study, Series and ImageInstance. Idempotent.
    """
    from ..image_instance import ImageInstance
    from ..series import Series
    from ..study import Study

    if not event.contains(Session, "before_flush", populate_project_ids):
        event.listen(Session, "before_flush", populate_project_ids)
    for cls in (Study, Series, ImageInstance):
        if not event.contains(cls, "before_insert", populate_project_id_on_insert):
            event.listen(cls, "before_insert", populate_project_id_on_insert)
