from __future__ import annotations

from eyened_orm import SubTask, Task
from eyened_orm.task import SubTaskState, TaskState
from eyened_orm.repositories.task_repository import SubTaskRepository, TaskRepository
from fastapi import Depends
from sqlalchemy.orm import Session

from ..db import get_db
from .acting_user import ActingUser
from .audit_service import AuditService, get_audit_service
from .exceptions import NotFoundError


class TaskService:
    """Business logic for tasks and their subtask listings."""

    def __init__(
        self,
        task_repository: TaskRepository,
        subtask_repository: SubTaskRepository,
        audit: AuditService | None = None,
    ) -> None:
        self.tasks = task_repository
        self.subtasks = subtask_repository
        self.audit = audit

    def create_task(
        self,
        name: str,
        description: str | None,
        contact_id: int | None,
        task_definition_id: int,
        actor: ActingUser,
    ) -> Task:
        """Create a task owned by the acting user (TaskState.NotStarted)."""
        task = Task(
            TaskName=name,
            Description=description,
            ContactID=contact_id,
            TaskDefinitionID=task_definition_id,
            CreatorID=actor.id,
            TaskState=TaskState.NotStarted,
        )
        self.tasks.add(task)
        task = self.tasks.get_with_relations(task.TaskID)
        if self.audit is not None:
            self.audit.record(
                action="INSERT",
                entity="Task",
                actor=actor,
                entity_id=task.TaskID,
                changes={
                    "name": task.TaskName,
                    "description": task.Description,
                    "contact_id": task.ContactID,
                    "task_definition_id": task.TaskDefinitionID,
                },
            )
        return task

    def list_tasks(self) -> tuple[list[Task], dict[int, tuple[int, int]]]:
        """Return all tasks (TaskID order) and their {id: (total, ready)} counts."""
        tasks = self.tasks.list_all()
        counts = self.tasks.subtask_counts([t.TaskID for t in tasks])
        return tasks, counts

    def get_task(self, task_id: int) -> tuple[Task, tuple[int, int]]:
        """Return a task and its (total, ready) subtask counts.

        Raises:
            NotFoundError: If the task does not exist.
        """
        task = self.tasks.get_with_relations(task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} not found")
        return task, self.tasks.subtask_counts([task_id])[task_id]

    def update_task(
        self,
        task_id: int,
        name: str | None,
        description: str | None,
        contact_id: int | None,
        task_definition_id: int | None,
        task_state: TaskState | None,
        actor: ActingUser,
    ) -> tuple[Task, tuple[int, int]]:
        """Update a task's mutable fields (each optional).

        Raises:
            NotFoundError: If the task does not exist.
        """
        task = self.tasks.get_by_id(task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} not found")

        if name is not None:
            task.TaskName = name
        if description is not None:
            task.Description = description
        if contact_id is not None:
            task.ContactID = contact_id
        if task_definition_id is not None:
            task.TaskDefinitionID = task_definition_id
        if task_state is not None:
            task.TaskState = task_state

        # Derive the scalar diff while the mutations are still pending — before
        # the get_with_relations() query below autoflushes (a flush clears the
        # pending attribute history).
        changes = AuditService.diff(
            task, "TaskName", "Description", "ContactID", "TaskDefinitionID", "TaskState"
        )

        task = self.tasks.get_with_relations(task_id)
        counts = self.tasks.subtask_counts([task_id])[task_id]
        if self.audit is not None:
            self.audit.record(
                action="UPDATE",
                entity="Task",
                actor=actor,
                entity_id=task_id,
                changes=changes if changes else None,
            )
        return task, counts

    def delete_task(self, task_id: int, actor: ActingUser) -> None:
        """Delete a task (its subtasks cascade at the DB level).

        Raises:
            NotFoundError: If the task does not exist.
        """
        task = self.tasks.get_by_id(task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} not found")

        deleted_data = {
            "name": task.TaskName,
            "description": task.Description,
            "contact_id": task.ContactID,
            "task_definition_id": task.TaskDefinitionID,
            "creator_id": task.CreatorID,
            "task_state": task.TaskState,
        }
        self.tasks.delete(task)
        if self.audit is not None:
            self.audit.record(
                action="DELETE",
                entity="Task",
                actor=actor,
                entity_id=task_id,
                changes=deleted_data,
            )
        return None

    def list_task_subtasks(
        self,
        task_id: int,
        *,
        with_images: bool,
        limit: int,
        page: int,
        status: SubTaskState | None,
    ) -> tuple[list[tuple[SubTask, int]], int]:
        """Return one page of a task's subtasks, each with its absolute index.

        ``absolute_index`` is the subtask's 0-based position within *all* the
        task's subtasks ordered by SubTaskID (computed before the ``status``
        filter). The returned count honors ``status``.

        Raises:
            NotFoundError: If the task does not exist.
        """
        if self.tasks.get_by_id(task_id) is None:
            raise NotFoundError(f"Task {task_id} not found")

        index_of = {
            sid: i for i, sid in enumerate(self.subtasks.all_ids_for_task(task_id))
        }
        rows = self.subtasks.list_for_task(
            task_id,
            status=status,
            limit=limit,
            offset=limit * page,
            with_images=with_images,
        )
        count = self.subtasks.count_for_task(task_id, status=status)
        # Every returned row is one of the task's subtasks, so its id is always
        # in index_of (rows are a subset of all_ids_for_task).
        return [(st, index_of[st.SubTaskID]) for st in rows], count

    def get_task_subtask(
        self,
        task_id: int,
        subtask_index: int,
        *,
        with_images: bool,
        with_next: bool,
    ) -> tuple[SubTask, SubTask | None]:
        """Return the subtask at ``subtask_index`` and, if asked, the next one.

        Raises:
            NotFoundError: If no subtask sits at ``subtask_index``.
        """
        rows = self.subtasks.list_for_task(
            task_id,
            status=None,
            limit=2 if with_next else 1,
            offset=subtask_index,
            with_images=with_images,
        )
        if not rows:
            raise NotFoundError("SubTask not found")
        nxt = rows[1] if (with_next and len(rows) > 1) else None
        return rows[0], nxt


class SubTaskService:
    """Business logic for individual subtasks and their image links."""

    def __init__(
        self,
        subtask_repository: SubTaskRepository,
        audit: AuditService | None = None,
    ) -> None:
        self.subtasks = subtask_repository
        self.audit = audit

    def get_subtask(self, subtask_id: int, *, with_images: bool) -> SubTask:
        """Return a subtask, image-loaded iff ``with_images``.

        Raises:
            NotFoundError: If the subtask does not exist.
        """
        subtask = (
            self.subtasks.get_with_images(subtask_id)
            if with_images
            else self.subtasks.get_by_id(subtask_id)
        )
        if subtask is None:
            raise NotFoundError(f"SubTask {subtask_id} not found")
        return subtask

    def update_subtask(
        self,
        subtask_id: int,
        comments: str | None,
        task_state: SubTaskState | None,
        actor: ActingUser,
    ) -> SubTask:
        """Update a subtask's comments/state (each optional).

        Raises:
            NotFoundError: If the subtask does not exist.
        """
        subtask = self.subtasks.get_by_id(subtask_id)
        if subtask is None:
            raise NotFoundError(f"SubTask {subtask_id} not found")

        if comments is not None:
            subtask.Comments = comments
        if task_state is not None:
            subtask.TaskState = task_state

        # Derive the scalar diff while the mutations are still pending — before
        # any flush clears the pending attribute history (SubTask has no
        # server-generated columns a caller reads, so no re-fetch is needed).
        changes = AuditService.diff(subtask, "Comments", "TaskState")

        if self.audit is not None:
            self.audit.record(
                action="UPDATE",
                entity="SubTask",
                actor=actor,
                entity_id=subtask_id,
                changes=changes if changes else None,
            )
        return subtask

    def delete_subtask(self, subtask_id: int, actor: ActingUser) -> None:
        """Delete a subtask (its image links cascade at the DB level).

        Raises:
            NotFoundError: If the subtask does not exist.
        """
        subtask = self.subtasks.get_by_id(subtask_id)
        if subtask is None:
            raise NotFoundError(f"SubTask {subtask_id} not found")

        deleted_data = {
            "task_id": subtask.TaskID,
            "comments": subtask.Comments,
            "task_state": subtask.TaskState,
            "creator_id": subtask.CreatorID,
        }
        self.subtasks.delete(subtask)
        if self.audit is not None:
            self.audit.record(
                action="DELETE",
                entity="SubTask",
                actor=actor,
                entity_id=subtask_id,
                changes=deleted_data,
            )
        return None

    def add_image(
        self, subtask_id: int, image_public_id: str, actor: ActingUser
    ) -> SubTask:
        """Link an image (by PublicID) to a subtask at the next ImageIndex.

        Raises:
            NotFoundError: If the subtask or the image does not exist.
        """
        if self.subtasks.get_by_id(subtask_id) is None:
            raise NotFoundError(f"SubTask {subtask_id} not found")
        image_instance_id = self.subtasks.resolve_image_instance_id(image_public_id)
        if image_instance_id is None:
            raise NotFoundError("ImageInstance not found")

        self.subtasks.add_link(
            subtask_id, image_instance_id, self.subtasks.next_image_index(subtask_id)
        )
        if self.audit is not None:
            self.audit.record(
                action="INSERT",
                entity="SubTaskImageLink",
                actor=actor,
                changes={
                    "subtask_id": subtask_id,
                    "image_instance_id": image_instance_id,
                },
            )
        return self.subtasks.get_with_images(subtask_id)

    def remove_image(
        self, subtask_id: int, image_public_id: str, actor: ActingUser
    ) -> SubTask:
        """Unlink an image (by PublicID) from a subtask.

        Raises:
            NotFoundError: If the image or the (subtask, image) link is absent.
        """
        image_instance_id = self.subtasks.resolve_image_instance_id(image_public_id)
        if image_instance_id is None:
            raise NotFoundError("ImageInstance not found")
        link = self.subtasks.get_image_link(subtask_id, image_instance_id)
        if link is None:
            raise NotFoundError("Link not found")

        self.subtasks.delete_link(link)
        if self.audit is not None:
            self.audit.record(
                action="DELETE",
                entity="SubTaskImageLink",
                actor=actor,
                changes={
                    "subtask_id": subtask_id,
                    "image_instance_id": image_instance_id,
                },
            )
        return self.subtasks.get_with_images(subtask_id)


def get_task_service(db: Session = Depends(get_db)) -> TaskService:
    """Default TaskService wiring for FastAPI ``Depends()``."""
    return TaskService(
        TaskRepository(db), SubTaskRepository(db), audit=get_audit_service(db)
    )


def get_subtask_service(db: Session = Depends(get_db)) -> SubTaskService:
    """Default SubTaskService wiring for FastAPI ``Depends()``."""
    return SubTaskService(SubTaskRepository(db), audit=get_audit_service(db))
