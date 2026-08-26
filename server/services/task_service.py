from __future__ import annotations

from eyened_orm import Creator, SubTask, Task
from eyened_orm.task import SubTaskState, TaskState
from eyened_orm.repositories.task_repository import SubTaskRepository, TaskRepository
from eyened_orm.authz.errors import NotVisibleError
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.authz.scope import AccessScope
from fastapi import Depends
from sqlalchemy.orm import Session

from ..db import get_db
from .access_scope import get_access_scope
from .acting_user import ActingUser
from .audit_service import AuditService, get_audit_service
from .exceptions import BadRequestError, ConflictError, NotFoundError


class TaskService:
    """Business logic for tasks and their subtask listings."""

    def __init__(
        self,
        task_repository: TaskRepository,
        subtask_repository: SubTaskRepository,
        *,
        scope: AccessScope,
        audit: AuditService | None = None,
    ) -> None:
        self.tasks = task_repository
        self.subtasks = subtask_repository
        self.scope = scope
        self._actor = ActingUser.from_scope(scope)
        self.audit = audit

    def create_task(
        self,
        name: str,
        description: str | None,
        contact_id: int | None,
        task_definition_id: int,
    ) -> Task:
        """Create a task owned by the acting user (TaskState.NotStarted)."""
        task = Task(
            TaskName=name,
            Description=description,
            ContactID=contact_id,
            TaskDefinitionID=task_definition_id,
            CreatorID=self.scope.actor_id,
            TaskState=TaskState.NotStarted,
        )
        self.tasks.add(task)
        task = self.tasks.get_with_relations(task.TaskID)
        if self.audit is not None:
            self.audit.record(
                action="INSERT",
                entity="Task",
                actor=self._actor,
                entity_id=task.TaskID,
                changes={
                    "name": task.TaskName,
                    "description": task.Description,
                    "contact_id": task.ContactID,
                    "task_definition_id": task.TaskDefinitionID,
                },
            )
        return task

    def list_tasks(
        self, *, include_projects: bool = False
    ) -> tuple[
        list[Task],
        dict[int, tuple[int, int]],
        dict[int, list[tuple[int, str]]] | None,
    ]:
        """Return all tasks (TaskID order), their {id: (total, ready)} counts
        and, when asked, the projects each one spans.

        Spans are opt-in because resolving them walks every image link of every
        task in the result, which dominates the request. ``None`` means "not
        requested" and is passed through to the DTO as such -- see
        ``DTOConverter.task_to_get``.
        """
        tasks = self.tasks.list_all()
        task_ids = [t.TaskID for t in tasks]
        counts = self.tasks.subtask_counts(task_ids)
        projects = (
            self.tasks.projects_for_tasks(task_ids) if include_projects else None
        )
        return tasks, counts, projects

    def get_task(
        self, task_id: int
    ) -> tuple[Task, tuple[int, int], list[tuple[int, str]]]:
        """Return a task, its (total, ready) subtask counts and the projects it spans.

        Raises:
            NotFoundError: If the task does not exist.
        """
        task = self.tasks.get_with_relations(task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} not found")
        return (
            task,
            self.tasks.subtask_counts([task_id])[task_id],
            self.tasks.projects_for_tasks([task_id])[task_id],
        )

    def update_task(
        self,
        task_id: int,
        name: str | None,
        description: str | None,
        contact_id: int | None,
        task_definition_id: int | None,
        task_state: TaskState | None,
    ) -> tuple[Task, tuple[int, int], list[tuple[int, str]]]:
        """Update a task's mutable fields (each optional).

        The floor depends on which fields the request actually changes:
        project_admin if name or description move, grader if only the status
        does. v0.3's matrix separates "create/delete tasks" from "update tasks
        status", and renaming belongs with administering the task.

        Raises:
            NotFoundError: If the task does not exist.
            NotVisibleError: If the task touches a project the actor lacks.
            PermissionDeniedError: If the actor is under the floor.
        """
        task = self.tasks.get_by_id(task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} not found")

        administrative = name is not None or description is not None
        self.scope.require(
            self.tasks.project_ids(task_id),
            ProjectRole.project_admin if administrative else ProjectRole.grader,
            entity="Task",
            entity_id=task_id,
        )

        before = AuditService.snapshot(
            task, "TaskName", "Description", "ContactID", "TaskDefinitionID", "TaskState"
        )
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

        changes = AuditService.diff(before, task)
        self.tasks.save(task)

        task = self.tasks.get_with_relations(task_id)
        counts = self.tasks.subtask_counts([task_id])[task_id]
        projects = self.tasks.projects_for_tasks([task_id])[task_id]
        if self.audit is not None:
            self.audit.record(
                action="UPDATE",
                entity="Task",
                actor=self._actor,
                entity_id=task_id,
                changes=changes if changes else None,
            )
        return task, counts, projects

    def delete_task(self, task_id: int) -> None:
        """Delete a task (its subtasks cascade at the DB level).

        Requires ``project_admin`` in every project the task touches, resolved
        before the delete: afterwards the subtask/link join path the resolution
        walks is gone.

        Raises:
            NotFoundError: If the task does not exist.
            NotVisibleError: If the task touches a project the actor lacks.
            PermissionDeniedError: If the actor is under the floor.
        """
        task = self.tasks.get_by_id(task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} not found")

        self.scope.require(
            self.tasks.project_ids(task_id),
            ProjectRole.project_admin,
            entity="Task",
            entity_id=task_id,
        )

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
                actor=self._actor,
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
        if self.tasks.get_by_id(task_id) is None:
            raise NotFoundError(f"Task {task_id} not found")

        index_of = {
            sid: i for i, sid in enumerate(self.subtasks.all_ids_for_task(task_id))
        }
        rows = self.subtasks.list_for_task(
            task_id,
            status=status,
            creator_id=creator_id,
            unassigned=unassigned,
            limit=limit,
            offset=limit * page,
            with_images=with_images,
        )
        count = self.subtasks.count_for_task(
            task_id,
            status=status,
            creator_id=creator_id,
            unassigned=unassigned,
        )
        # Every returned row is one of the task's subtasks, so its id is always
        # in index_of (rows are a subset of all_ids_for_task).
        return [(st, index_of[st.SubTaskID]) for st in rows], count

    def list_subtask_assignees(self, task_id: int) -> list[Creator]:
        """Return distinct creators assigned to any subtask of this task.

        Raises:
            NotFoundError: If the task does not exist.
        """
        if self.tasks.get_by_id(task_id) is None:
            raise NotFoundError(f"Task {task_id} not found")
        return self.subtasks.list_assignees_for_task(task_id)

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
        *,
        scope: AccessScope,
        audit: AuditService | None = None,
    ) -> None:
        self.subtasks = subtask_repository
        self.scope = scope
        self._actor = ActingUser.from_scope(scope)
        self.audit = audit

    def _task_projects(self, subtask_id: int) -> set[int]:
        """The parent task's project set -- what every subtask mutation is judged on."""
        return self.subtasks.project_ids(subtask_id)

    def _reread_with_images(self, subtask_id: int) -> SubTask:
        """Re-read the mutated subtask, refusing rather than returning ``None``.

        ``get_with_images`` is scope-filtered, so a write that pushes the task
        out of the caller's reach makes it ``None`` -- and the response
        converter dereferences that straight into an AttributeError, i.e. a 500
        on a request that was authorized. The floors above close every path
        that gets here; this is what turns a regression in them back into an
        authorization answer instead of a crash.
        """
        subtask = self.subtasks.get_with_images(subtask_id)
        if subtask is None:
            raise NotVisibleError(
                actor_id=self.scope.actor_id,
                entity="SubTask",
                entity_id=subtask_id,
                projects=frozenset(),
            )
        return subtask

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
        claim: bool | None = None,
    ) -> SubTask:
        """Update a subtask's comments/state (each optional).

        Requires ``grader`` in every project the parent task touches.

        If ``claim`` is True, explicitly assign the subtask to the actor,
        raising ConflictError if it is already assigned.
        If ``claim`` is False, release the assignment only when the actor
        currently owns it (cannot unclaim someone else's subtask).
        Otherwise, comments/state edits auto-claim an unassigned subtask.

        Raises:
            NotFoundError: If the subtask does not exist.
            NotVisibleError: If the task touches a project the actor lacks.
            PermissionDeniedError: If the actor is under the floor.
            ConflictError: If ``claim`` is True and already assigned, or
                ``claim`` is False and assigned to a different creator.
        """
        subtask = self.subtasks.get_by_id(subtask_id)
        if subtask is None:
            raise NotFoundError(f"SubTask {subtask_id} not found")

        self.scope.require(
            self._task_projects(subtask_id),
            ProjectRole.grader,
            entity="SubTask",
            entity_id=subtask_id,
        )

        before = AuditService.snapshot(
            subtask, "Comments", "TaskState", "CreatorID"
        )
        if comments is not None:
            subtask.Comments = comments
        if task_state is not None:
            subtask.TaskState = task_state

        actor = self._actor
        if claim is True:
            # Conditional UPDATE is the source of truth (covers concurrent claims).
            if not self.subtasks.claim_if_unassigned(subtask_id, actor.id):
                current = self.subtasks.get_by_id(subtask_id)
                if current is None:
                    raise NotFoundError(f"SubTask {subtask_id} not found")
                if current.CreatorID == actor.id:
                    subtask.CreatorID = actor.id
                else:
                    raise ConflictError(
                        {
                            "code": "subtask_already_claimed",
                            "message": "SubTask is already assigned",
                            "creator_id": current.CreatorID,
                        }
                    )
            else:
                subtask.CreatorID = actor.id
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
                subtask.CreatorID = None
        elif comments is not None or task_state is not None:
            if self.subtasks.claim_if_unassigned(subtask_id, actor.id):
                subtask.CreatorID = actor.id

        # SubTask has no server-generated columns a caller reads, so no
        # re-fetch is needed after the save.
        changes = AuditService.diff(before, subtask)
        self.subtasks.save(subtask)

        if self.audit is not None:
            self.audit.record(
                action="UPDATE",
                entity="SubTask",
                actor=self._actor,
                entity_id=subtask_id,
                changes=changes if changes else None,
            )
        return subtask

    def delete_subtask(self, subtask_id: int) -> None:
        """Delete a subtask (its image links cascade at the DB level).

        Requires ``grader`` in every project the parent task touches, resolved
        **before** the delete: the resolution walks this subtask's own links,
        and the delete destroys them.

        Raises:
            NotFoundError: If the subtask does not exist.
            NotVisibleError: If the task touches a project the actor lacks.
            PermissionDeniedError: If the actor is under the floor.
        """
        subtask = self.subtasks.get_by_id(subtask_id)
        if subtask is None:
            raise NotFoundError(f"SubTask {subtask_id} not found")

        self.scope.require(
            self._task_projects(subtask_id),
            ProjectRole.grader,
            entity="SubTask",
            entity_id=subtask_id,
        )

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
                actor=self._actor,
                entity_id=subtask_id,
                changes=deleted_data,
            )
        return None

    def add_image(self, subtask_id: int, image_public_id: str) -> SubTask:
        """Link an image (by PublicID) to a subtask at the next ImageIndex.

        Requires ``grader`` in every project the task touches **before** the
        change and every project it touches **after** it. Adding grows the set,
        so the union is ``after``; the before half is already loaded for the
        visibility check, so the extra cost is one project lookup for the image.
        Without the after half a grader could link an image out of a project
        they hold nothing in, laundering it into a task they can see.

        Raises:
            NotFoundError: If the subtask or the image does not exist.
            NotVisibleError: If either side touches a project the actor lacks.
            PermissionDeniedError: If the actor is under the floor.
        """
        if self.subtasks.get_by_id(subtask_id) is None:
            raise NotFoundError(f"SubTask {subtask_id} not found")
        image_instance_id = self.subtasks.resolve_image_instance_id(image_public_id)
        if image_instance_id is None:
            raise NotFoundError("ImageInstance not found")

        projects_before = self._task_projects(subtask_id)
        projects_after = projects_before | self.subtasks.project_ids_of_image(
            image_instance_id
        )
        self.scope.require(
            projects_before | projects_after,
            ProjectRole.grader,
            entity="SubTask",
            entity_id=subtask_id,
        )

        self.subtasks.add_link(
            subtask_id, image_instance_id, self.subtasks.next_image_index(subtask_id)
        )
        if self.audit is not None:
            self.audit.record(
                action="INSERT",
                entity="SubTaskImageLink",
                actor=self._actor,
                changes={
                    "subtask_id": subtask_id,
                    "image_instance_id": image_instance_id,
                },
            )
        return self._reread_with_images(subtask_id)

    def remove_image(self, subtask_id: int, image_public_id: str) -> SubTask:
        """Unlink an image (by PublicID) from a subtask.

        Requires ``grader`` in every project the task touches. Removing shrinks
        the set, so the union of before and after is ``before`` -- and it is
        resolved before the delete, which destroys the link the resolution
        walks.

        The leading visibility check is not optional, and the floor does not
        subsume it. Without it this method reaches ``get_image_link`` -- a bare
        ``session.get``, which no scope touches -- on a subtask the caller
        cannot see. Before the floor existed that deleted the link outright.
        With the floor the status is 404 either way, but the *body* is not: a
        linked image is refused by the floor ("Not found") and an unlinked one
        by the link lookup that ran first ("Link not found"), which confirms a
        link on a row the caller may not know exists. Ids are sequential
        autoincrement, so that difference is an enumeration oracle. The
        ordering here is visibility, then projects, then floor, then mutate.

        Raises:
            NotFoundError: If the subtask, the image or the link is absent.
            NotVisibleError: If the task touches a project the actor lacks.
            PermissionDeniedError: If the actor is under the floor.
        """
        if self.subtasks.get_by_id(subtask_id) is None:
            raise NotFoundError(f"SubTask {subtask_id} not found")
        image_instance_id = self.subtasks.resolve_image_instance_id(image_public_id)
        if image_instance_id is None:
            raise NotFoundError("ImageInstance not found")
        link = self.subtasks.get_image_link(subtask_id, image_instance_id)
        if link is None:
            raise NotFoundError("Link not found")

        self.scope.require(
            self._task_projects(subtask_id),
            ProjectRole.grader,
            entity="SubTask",
            entity_id=subtask_id,
        )

        self.subtasks.delete_link(link)
        if self.audit is not None:
            self.audit.record(
                action="DELETE",
                entity="SubTaskImageLink",
                actor=self._actor,
                changes={
                    "subtask_id": subtask_id,
                    "image_instance_id": image_instance_id,
                },
            )
        return self._reread_with_images(subtask_id)


def get_task_service(
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
) -> TaskService:
    """Default TaskService wiring for FastAPI ``Depends()``."""
    return TaskService(
        TaskRepository(db, scope=scope),
        SubTaskRepository(db, scope=scope),
        scope=scope,
        audit=get_audit_service(db),
    )


def get_subtask_service(
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
) -> SubTaskService:
    """Default SubTaskService wiring for FastAPI ``Depends()``."""
    return SubTaskService(
        SubTaskRepository(db, scope=scope),
        scope=scope,
        audit=get_audit_service(db),
    )
