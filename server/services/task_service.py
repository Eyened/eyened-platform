from __future__ import annotations

from sqlalchemy.orm import Session

from eyened_orm import Creator, SubTask, SubTaskImageLink, Task
from eyened_orm.task import SubTaskState, TaskState
from eyened_orm.repositories.task_repository import SubTaskRepository, TaskRepository

from ..utils.db_logging import DatabaseModificationLogger, get_db_logger
from .acting_user import ActingUser
from .exceptions import BadRequestError, ConflictError, NotFoundError


class TaskService:
    """Business logic for tasks and their subtask listings."""

    def __init__(
        self,
        task_repository: TaskRepository,
        subtask_repository: SubTaskRepository,
        logger: DatabaseModificationLogger | None = None,
    ) -> None:
        self.tasks = task_repository
        self.subtasks = subtask_repository
        self.logger = logger

    def create_task(
        self,
        session: Session,
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
        session.add(task)
        session.commit()
        task = self.tasks.get_with_relations(session, task.TaskID)
        if self.logger is not None:
            self.logger.log_insert(
                user=actor.username,
                user_id=actor.id,
                endpoint="POST /api/task",
                entity="Task",
                entity_id=task.TaskID,
                fields={
                    "name": task.TaskName,
                    "description": task.Description,
                    "contact_id": task.ContactID,
                    "task_definition_id": task.TaskDefinitionID,
                },
            )
        return task

    def list_tasks(
        self, session: Session
    ) -> tuple[list[Task], dict[int, tuple[int, int]]]:
        """Return all tasks (TaskID order) and their {id: (total, ready)} counts."""
        tasks = self.tasks.list_all(session)
        counts = self.tasks.subtask_counts(session, [t.TaskID for t in tasks])
        return tasks, counts

    def get_task(
        self, session: Session, task_id: int
    ) -> tuple[Task, tuple[int, int]]:
        """Return a task and its (total, ready) subtask counts.

        Raises:
            NotFoundError: If the task does not exist.
        """
        task = self.tasks.get_with_relations(session, task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} not found")
        return task, self.tasks.subtask_counts(session, [task_id])[task_id]

    def update_task(
        self,
        session: Session,
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
        task = self.tasks.get_by_id(session, task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} not found")

        changes: dict[str, str] = {}
        if name is not None:
            changes["name"] = f"{task.TaskName} -> {name}"
            task.TaskName = name
        if description is not None:
            changes["description"] = f"{task.Description} -> {description}"
            task.Description = description
        if contact_id is not None:
            changes["contact_id"] = f"{task.ContactID} -> {contact_id}"
            task.ContactID = contact_id
        if task_definition_id is not None:
            changes["task_definition_id"] = (
                f"{task.TaskDefinitionID} -> {task_definition_id}"
            )
            task.TaskDefinitionID = task_definition_id
        if task_state is not None:
            changes["task_state"] = f"{task.TaskState} -> {task_state}"
            task.TaskState = task_state

        session.commit()
        task = self.tasks.get_with_relations(session, task_id)
        counts = self.tasks.subtask_counts(session, [task_id])[task_id]
        if self.logger is not None:
            self.logger.log_update(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"PATCH /api/task/{task_id}",
                entity="Task",
                entity_id=task_id,
                changes=changes if changes else None,
            )
        return task, counts

    def delete_task(
        self, session: Session, task_id: int, actor: ActingUser
    ) -> None:
        """Delete a task (its subtasks cascade at the DB level).

        Raises:
            NotFoundError: If the task does not exist.
        """
        task = self.tasks.get_by_id(session, task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} not found")

        deleted_data = {
            "name": task.TaskName,
            "description": task.Description,
            "contact_id": task.ContactID,
            "task_definition_id": task.TaskDefinitionID,
            "creator_id": task.CreatorID,
            "task_state": str(task.TaskState) if task.TaskState else None,
        }
        session.delete(task)
        session.commit()
        if self.logger is not None:
            self.logger.log_delete(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"DELETE /api/task/{task_id}",
                entity="Task",
                entity_id=task_id,
                deleted_data=deleted_data,
            )
        return None

    def list_task_subtasks(
        self,
        session: Session,
        task_id: int,
        *,
        with_images: bool,
        limit: int,
        page: int,
        status: SubTaskState | None,
        creator_id: int | None = None,
        unassigned: bool = False,
    ) -> tuple[list[tuple[SubTask, int]], int]:
        """Return one page of a task's subtasks, each with its absolute index.

        ``absolute_index`` is the subtask's 0-based position within *all* the
        task's subtasks ordered by SubTaskID (computed before status/assignee
        filters). The returned count honors the filters.

        Raises:
            NotFoundError: If the task does not exist.
            BadRequestError: If both ``unassigned`` and ``creator_id`` are set.
        """
        if unassigned and creator_id is not None:
            raise BadRequestError(
                "unassigned and creator_id are mutually exclusive"
            )
        if self.tasks.get_by_id(session, task_id) is None:
            raise NotFoundError(f"Task {task_id} not found")

        index_of = {
            sid: i
            for i, sid in enumerate(self.subtasks.all_ids_for_task(session, task_id))
        }
        rows = self.subtasks.list_for_task(
            session,
            task_id,
            status=status,
            creator_id=creator_id,
            unassigned=unassigned,
            limit=limit,
            offset=limit * page,
            with_images=with_images,
        )
        count = self.subtasks.count_for_task(
            session,
            task_id,
            status=status,
            creator_id=creator_id,
            unassigned=unassigned,
        )
        # Every returned row is one of the task's subtasks, so its id is always
        # in index_of (rows are a subset of all_ids_for_task).
        return [(st, index_of[st.SubTaskID]) for st in rows], count

    def list_subtask_assignees(
        self, session: Session, task_id: int
    ) -> list[Creator]:
        """Return distinct creators assigned to any subtask of this task.

        Raises:
            NotFoundError: If the task does not exist.
        """
        if self.tasks.get_by_id(session, task_id) is None:
            raise NotFoundError(f"Task {task_id} not found")
        return self.subtasks.list_assignees_for_task(session, task_id)

    def get_task_subtask(
        self,
        session: Session,
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
            session,
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
        logger: DatabaseModificationLogger | None = None,
    ) -> None:
        self.subtasks = subtask_repository
        self.logger = logger

    def get_subtask(
        self, session: Session, subtask_id: int, *, with_images: bool
    ) -> SubTask:
        """Return a subtask, image-loaded iff ``with_images``.

        Raises:
            NotFoundError: If the subtask does not exist.
        """
        subtask = (
            self.subtasks.get_with_images(session, subtask_id)
            if with_images
            else self.subtasks.get_by_id(session, subtask_id)
        )
        if subtask is None:
            raise NotFoundError(f"SubTask {subtask_id} not found")
        return subtask

    def update_subtask(
        self,
        session: Session,
        subtask_id: int,
        comments: str | None,
        task_state: SubTaskState | None,
        actor: ActingUser,
        claim: bool | None = None,
    ) -> SubTask:
        """Update a subtask's comments/state (each optional).

        If ``claim`` is True, explicitly assign the subtask to ``actor``,
        raising ConflictError if it is already assigned.
        If ``claim`` is False, release the assignment only when the actor
        currently owns it (cannot unclaim someone else's subtask).
        Otherwise, comments/state edits auto-claim an unassigned subtask.

        Raises:
            NotFoundError: If the subtask does not exist.
            ConflictError: If ``claim`` is True and already assigned, or
                ``claim`` is False and assigned to a different creator.
        """
        subtask = self.subtasks.get_by_id(session, subtask_id)
        if subtask is None:
            raise NotFoundError(f"SubTask {subtask_id} not found")

        changes: dict[str, str] = {}
        if comments is not None:
            changes["comments"] = f"{subtask.Comments} -> {comments}"
            subtask.Comments = comments
        if task_state is not None:
            changes["task_state"] = f"{subtask.TaskState} -> {task_state}"
            subtask.TaskState = task_state

        if claim is True:
            # Conditional UPDATE is the source of truth (covers concurrent claims).
            if not self.subtasks.claim_if_unassigned(
                session, subtask_id, actor.id
            ):
                session.refresh(subtask)
                raise ConflictError(
                    {
                        "code": "subtask_already_claimed",
                        "message": "SubTask is already assigned",
                        "creator_id": subtask.CreatorID,
                    }
                )
            changes["creator_id"] = f"None -> {actor.id}"
        elif claim is False:
            if subtask.CreatorID is None:
                pass
            elif subtask.CreatorID != actor.id:
                raise ConflictError(
                    {
                        "code": "subtask_not_owned",
                        "message": "Only the assignee can unclaim this SubTask",
                        "creator_id": subtask.CreatorID,
                    }
                )
            else:
                changes["creator_id"] = f"{subtask.CreatorID} -> None"
                subtask.CreatorID = None
        elif comments is not None or task_state is not None:
            self.subtasks.claim_if_unassigned(session, subtask_id, actor.id)

        session.commit()
        session.refresh(subtask)
        if self.logger is not None:
            self.logger.log_update(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"PATCH /api/subtasks/{subtask_id}",
                entity="SubTask",
                entity_id=subtask_id,
                changes=changes if changes else None,
            )
        return subtask

    def delete_subtask(
        self, session: Session, subtask_id: int, actor: ActingUser
    ) -> None:
        """Delete a subtask (its image links cascade at the DB level).

        Raises:
            NotFoundError: If the subtask does not exist.
        """
        subtask = self.subtasks.get_by_id(session, subtask_id)
        if subtask is None:
            raise NotFoundError(f"SubTask {subtask_id} not found")

        deleted_data = {
            "task_id": subtask.TaskID,
            "comments": subtask.Comments,
            "task_state": str(subtask.TaskState) if subtask.TaskState else None,
            "creator_id": subtask.CreatorID,
        }
        session.delete(subtask)
        session.commit()
        if self.logger is not None:
            self.logger.log_delete(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"DELETE /api/subtasks/{subtask_id}",
                entity="SubTask",
                entity_id=subtask_id,
                deleted_data=deleted_data,
            )
        return None

    def add_image(
        self,
        session: Session,
        subtask_id: int,
        image_public_id: str,
        actor: ActingUser,
    ) -> SubTask:
        """Link an image (by PublicID) to a subtask at the next ImageIndex.

        Raises:
            NotFoundError: If the subtask or the image does not exist.
        """
        if self.subtasks.get_by_id(session, subtask_id) is None:
            raise NotFoundError(f"SubTask {subtask_id} not found")
        image_instance_id = self.subtasks.resolve_image_instance_id(
            session, image_public_id
        )
        if image_instance_id is None:
            raise NotFoundError("ImageInstance not found")

        link = SubTaskImageLink(
            SubTaskID=subtask_id,
            ImageInstanceID=image_instance_id,
            ImageIndex=self.subtasks.next_image_index(session, subtask_id),
        )
        session.add(link)
        session.commit()
        if self.logger is not None:
            self.logger.log_insert(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"POST /api/subtasks/{subtask_id}/images",
                entity="SubTaskImageLink",
                fields={
                    "subtask_id": subtask_id,
                    "image_instance_id": image_instance_id,
                },
            )
        return self.subtasks.get_with_images(session, subtask_id)

    def remove_image(
        self,
        session: Session,
        subtask_id: int,
        image_public_id: str,
        actor: ActingUser,
    ) -> SubTask:
        """Unlink an image (by PublicID) from a subtask.

        Raises:
            NotFoundError: If the image or the (subtask, image) link is absent.
        """
        image_instance_id = self.subtasks.resolve_image_instance_id(
            session, image_public_id
        )
        if image_instance_id is None:
            raise NotFoundError("ImageInstance not found")
        link = self.subtasks.get_image_link(session, subtask_id, image_instance_id)
        if link is None:
            raise NotFoundError("Link not found")

        session.delete(link)
        session.commit()
        if self.logger is not None:
            self.logger.log_delete(
                user=actor.username,
                user_id=actor.id,
                endpoint=(
                    f"DELETE /api/subtasks/{subtask_id}/images/{image_public_id}"
                ),
                entity="SubTaskImageLink",
                deleted_data={
                    "subtask_id": subtask_id,
                    "image_instance_id": image_instance_id,
                },
            )
        return self.subtasks.get_with_images(session, subtask_id)


def get_task_service() -> TaskService:
    """Default TaskService wiring for FastAPI ``Depends()``."""
    return TaskService(
        TaskRepository(), SubTaskRepository(), logger=get_db_logger()
    )


def get_subtask_service() -> SubTaskService:
    """Default SubTaskService wiring for FastAPI ``Depends()``."""
    return SubTaskService(SubTaskRepository(), logger=get_db_logger())
