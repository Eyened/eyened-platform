from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from eyened_orm import ImageInstance, ImageStorage, SubTask, SubTaskImageLink, Task
from eyened_orm.task import SubTaskState
from eyened_orm.authz.scope import AccessScope

# Load task metadata without eager-loading every SubTask row (mirrors the
# route's former ``_task_query_options``).
_TASK_RELATIONS = (
    selectinload(Task.Creator),
    selectinload(Task.TaskDefinition),
)


class TaskRepository:
    """Data access for Task rows and their subtask counts."""

    def __init__(self, session: Session, *, scope: AccessScope) -> None:
        self._session = session
        self._scope = scope

    def add(self, task: Task) -> None:
        """Stage a new task and flush so its PK is assigned."""
        self._session.add(task)
        self._session.flush()

    def delete(self, task: Task) -> None:
        """Delete a task and flush within the request transaction."""
        self._session.delete(task)
        self._session.flush()

    def get_by_id(self, task_id: int) -> Task | None:
        """Return the task with the given id, or None if absent."""
        return self._session.get(Task, task_id)

    def save(self, task: Task) -> None:
        """Persist in-place mutations to ``task`` within the request transaction.

        ``task`` names what is being saved; the flush covers the whole unit of
        work, deliberately not just this row.
        """
        self._session.flush()

    def get_with_relations(self, task_id: int) -> Task | None:
        """Return the task with Creator + TaskDefinition eager-loaded, or None."""
        return (
            self._session.execute(
                select(Task).options(*_TASK_RELATIONS).where(Task.TaskID == task_id)
            )
            .scalars()
            .first()
        )

    def list_all(self) -> list[Task]:
        """Return all tasks (TaskID order) with Creator + TaskDefinition loaded."""
        return list(
            self._session.execute(
                select(Task).options(*_TASK_RELATIONS).order_by(Task.TaskID)
            )
            .scalars()
            .all()
        )

    def subtask_counts(self, task_ids: list[int]) -> dict[int, tuple[int, int]]:
        """Return {task_id: (num_subtasks, num_ready)} for the given task ids.

        One grouped aggregate over ``SubTask`` (mirrors the route's former
        ``_subtask_counts_by_task_id``). Every requested id is present in the
        result: ids with no subtasks map to ``(0, 0)``.
        """
        if not task_ids:
            return {}
        rows = self._session.execute(
            select(
                SubTask.TaskID,
                func.count().label("num"),
                func.coalesce(
                    func.sum(
                        case((SubTask.TaskState == SubTaskState.Ready, 1), else_=0)
                    ),
                    0,
                ).label("ready"),
            )
            .where(SubTask.TaskID.in_(task_ids))
            .group_by(SubTask.TaskID)
        ).all()
        counts = {int(tid): (int(n), int(r)) for tid, n, r in rows}
        return {tid: counts.get(tid, (0, 0)) for tid in task_ids}


# Eager-load the subtask's images down to their storage backend (mirrors the
# route's former with_images option chain).
_SUBTASK_IMAGE_LOADER = (
    selectinload(SubTask.SubTaskImageLinks)
    .selectinload(SubTaskImageLink.ImageInstance)
    .selectinload(ImageInstance.ImageStorages)
    .selectinload(ImageStorage.StorageBackend)
)


class SubTaskRepository:
    """Data access for a task's SubTask rows and their image links."""

    def __init__(self, session: Session, *, scope: AccessScope) -> None:
        self._session = session
        self._scope = scope

    def add(self, subtask: SubTask) -> None:
        """Stage a new subtask and flush so its PK is assigned."""
        self._session.add(subtask)
        self._session.flush()

    def delete(self, subtask: SubTask) -> None:
        """Delete a subtask and flush within the request transaction."""
        self._session.delete(subtask)
        self._session.flush()

    def add_link(
        self, subtask_id: int, image_instance_id: int, image_index: int
    ) -> SubTaskImageLink:
        """Create a SubTask<->ImageInstance link and flush so its row is written."""
        link = SubTaskImageLink(
            SubTaskID=subtask_id,
            ImageInstanceID=image_instance_id,
            ImageIndex=image_index,
        )
        self._session.add(link)
        self._session.flush()
        return link

    def delete_link(self, link: SubTaskImageLink) -> None:
        """Delete an image link and flush within the request transaction."""
        self._session.delete(link)
        self._session.flush()

    def all_ids_for_task(self, task_id: int) -> list[int]:
        """Return the task's SubTaskIDs ordered ascending (backs absolute index)."""
        return list(
            self._session.execute(
                select(SubTask.SubTaskID)
                .where(SubTask.TaskID == task_id)
                .order_by(SubTask.SubTaskID)
            )
            .scalars()
            .all()
        )

    def count_for_task(
        self,
        task_id: int,
        *,
        status: SubTaskState | None = None,
    ) -> int:
        """Return the task's subtask count, optionally filtered by state."""
        stmt = select(func.count()).select_from(SubTask).where(
            SubTask.TaskID == task_id
        )
        if status is not None:
            stmt = stmt.where(SubTask.TaskState == status)
        return self._session.scalar(stmt) or 0

    def list_for_task(
        self,
        task_id: int,
        *,
        status: SubTaskState | None = None,
        limit: int,
        offset: int,
        with_images: bool = False,
    ) -> list[SubTask]:
        """Return a limit/offset window of the task's subtasks (SubTaskID order).

        Optionally filters by ``status`` and eager-loads each subtask's images.
        """
        stmt = select(SubTask).where(SubTask.TaskID == task_id)
        if status is not None:
            stmt = stmt.where(SubTask.TaskState == status)
        stmt = stmt.order_by(SubTask.SubTaskID)
        if with_images:
            stmt = stmt.options(_SUBTASK_IMAGE_LOADER)
        return list(
            self._session.execute(stmt.limit(limit).offset(offset)).scalars().all()
        )

    def get_by_id(self, subtask_id: int) -> SubTask | None:
        """Return the subtask with the given id, or None if absent."""
        return self._session.get(SubTask, subtask_id)

    def save(self, subtask: SubTask) -> None:
        """Persist in-place mutations to ``subtask`` within the request transaction.

        ``subtask`` names what is being saved; the flush covers the whole unit
        of work, deliberately not just this row.
        """
        self._session.flush()

    def get_with_images(self, subtask_id: int) -> SubTask | None:
        """Return the subtask with its image links eager-loaded, or None."""
        return (
            self._session.execute(
                select(SubTask)
                .options(_SUBTASK_IMAGE_LOADER)
                .where(SubTask.SubTaskID == subtask_id)
            )
            .scalars()
            .first()
        )

    def resolve_image_instance_id(self, public_id: str) -> int | None:
        """Return the ImageInstanceID for a PublicID, or None if no image matches."""
        return self._session.scalar(
            select(ImageInstance.ImageInstanceID).where(
                ImageInstance.PublicID == public_id
            )
        )

    def next_image_index(self, subtask_id: int) -> int:
        """Return the next ImageIndex for the subtask (max+1, or 0 if it has none)."""
        current_max = self._session.scalar(
            select(func.max(SubTaskImageLink.ImageIndex)).where(
                SubTaskImageLink.SubTaskID == subtask_id
            )
        )
        return 0 if current_max is None else current_max + 1

    def get_image_link(
        self, subtask_id: int, image_instance_id: int
    ) -> SubTaskImageLink | None:
        """Return the link for (subtask_id, image_instance_id), or None if absent."""
        return self._session.get(
            SubTaskImageLink,
            {"SubTaskID": subtask_id, "ImageInstanceID": image_instance_id},
        )
