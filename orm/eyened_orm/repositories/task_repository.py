from __future__ import annotations

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session, selectinload

from eyened_orm import (
    ImageInstance,
    ImageStorage,
    Patient,
    Project,
    Series,
    Study,
    SubTask,
    SubTaskImageLink,
    Task,
    TaskProject,
)
from eyened_orm.task import SubTaskState
from eyened_orm.authz.scope import AccessScope
from eyened_orm.authz.scoping import apply_scope, projects_of

from ._scoped import scoped_one

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
        """Return the task with the given id, or None if absent or out of scope."""
        return scoped_one(self._session, Task, self._scope, Task.TaskID == task_id)

    def save(self, task: Task) -> None:
        """Persist in-place mutations to ``task`` within the request transaction.

        ``task`` names what is being saved; the flush covers the whole unit of
        work, deliberately not just this row.
        """
        self._session.flush()

    def get_with_relations(self, task_id: int) -> Task | None:
        """Return the task with Creator + TaskDefinition eager-loaded, or None."""
        return scoped_one(
            self._session,
            Task,
            self._scope,
            Task.TaskID == task_id,
            options=_TASK_RELATIONS,
        )

    def project_ids(self, task_id: int) -> set[int]:
        """The projects this task touches, for a write check to be judged on.

        The repository owns the Session, so the authz resolution runs here
        rather than a service reaching through for a Session it must not hold.
        Uses ``projects_of``, the one definition the reads and the CLI share.

        Deliberately unscoped: the returned set is the *input* to
        ``AccessScope.require``, so filtering it by the caller's scope would
        remove exactly the projects the check exists to catch and make every
        floor pass.
        """
        return projects_of(self._session, Task, task_id)

    def list_all(self) -> list[Task]:
        """Return every task the scope may read (TaskID order), relations loaded."""
        stmt = apply_scope(
            select(Task).options(*_TASK_RELATIONS).order_by(Task.TaskID),
            Task,
            self._scope,
        )
        return list(self._session.execute(stmt).scalars().all())

    def subtask_counts(self, task_ids: list[int]) -> dict[int, tuple[int, int]]:
        """Return {task_id: (num_subtasks, num_ready)} for the given task ids.

        Scoped through SubTask, so a hidden task reports (0, 0) rather than a
        partial view. Every requested id is still present in the result.
        """
        if not task_ids:
            return {}
        stmt = apply_scope(
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
            .select_from(SubTask)
            .where(SubTask.TaskID.in_(task_ids))
            .group_by(SubTask.TaskID),
            SubTask,
            self._scope,
        )
        rows = self._session.execute(stmt).all()
        counts = {int(tid): (int(n), int(r)) for tid, n, r in rows}
        return {tid: counts.get(tid, (0, 0)) for tid in task_ids}

    def _project_pairs_select(self, task_ids: list[int]) -> Select:
        """The walk to ``(task_id, project_id)`` pairs, de-duplicated, unscoped.

        ``Project`` is deliberately absent: joining it here puts a 44-row table
        in the same SELECT as ``apply_scope``'s correlated antijoin, and MySQL
        answers that by cross-joining the two and deferring the join condition
        to the last filter in the plan -- 933,108 driving rows instead of
        21,207, and every hop below it 44x wide. Measured at 12.2s versus 2.2s
        for the identical result. Names are joined to this subquery instead.

        Unscoped on purpose: the caller applies the scope, so that the call
        stays inside the public read method where the AST guard in
        ``server/tests/test_repository_reads_are_scoped.py`` can see it.

        ``.distinct()`` is load-bearing beyond de-duplication: it stops MySQL
        merging the derived table into the outer query, which would restore the
        plan this function exists to avoid.
        """
        return (
            select(
                SubTask.TaskID.label("task_id"),
                Patient.ProjectID.label("project_id"),
            )
            .select_from(SubTask)
            .join(SubTaskImageLink, SubTaskImageLink.SubTaskID == SubTask.SubTaskID)
            .join(
                ImageInstance,
                ImageInstance.ImageInstanceID == SubTaskImageLink.ImageInstanceID,
            )
            .join(Series, Series.SeriesID == ImageInstance.SeriesID)
            .join(Study, Study.StudyID == Series.StudyID)
            .join(Patient, Patient.PatientID == Study.PatientID)
            .where(SubTask.TaskID.in_(task_ids))
            .distinct()
        )

    @staticmethod
    def _names_for(pairs) -> Select:
        """Project names joined to an already-scoped pairs subquery."""
        return select(
            pairs.c.task_id, pairs.c.project_id, Project.ProjectName
        ).join(Project, Project.ProjectID == pairs.c.project_id)

    def projects_for_tasks(
        self, task_ids: list[int]
    ) -> dict[int, list[tuple[int, str]]]:
        """Return {task_id: [(project_id, project_name), ...]} for the given ids.

        Walks the same join path enforcement uses, re-expressed for batching
        and names: ``projects_of`` answers for one entity and returns bare ids,
        which cannot back a grouped, name-carrying query. The two must not
        drift -- grant-for-task and this endpoint are the two sides of one
        promise -- so a test pins them to the same answer.

        Every requested id is present in the result, and an empty list means
        one of *two* things: the task genuinely has no images, or the caller's
        scope cannot see the subtasks that carry them. Callers must not read
        ``[]`` as "spans nothing" on its own; the routes are safe because they
        404 an invisible task before the field is read.

        ``apply_scope`` is called here rather than inside ``_project_pairs_select``
        so that the repository read guard, which inspects this method's own body
        and does not follow calls, can see it.
        """
        if not task_ids:
            return {}
        pairs = apply_scope(
            self._project_pairs_select(task_ids), SubTask, self._scope
        ).subquery()
        rows = self._session.execute(self._names_for(pairs)).all()
        found: dict[int, list[tuple[int, str]]] = {}
        for task_id, project_id, project_name in rows:
            found.setdefault(int(task_id), []).append((int(project_id), project_name))
        return {tid: sorted(found.get(tid, [])) for tid in task_ids}

    def declared_projects(self, task_id: int) -> list[tuple[int, str]]:
        """The ``(id, name)`` pairs one task *declares*, for a response body.

        Reads ``TaskProject`` rather than the image walk ``projects_for_tasks``
        still performs, and the difference is the whole reason this exists: a
        task that declares projects it holds no image in yet resolves to what
        it declared instead of to nothing. Every task is in exactly that state
        the moment it is created, so the create route cannot answer from the
        walk.

        The scope predicate is a backstop, not a path: the only caller has
        already required the actor at ``grader`` in every project named here.
        It is applied to the *task*, so an invisible task resolves to ``[]``
        rather than leaking a project set.

        ``apply_scope`` is called in this method's own body, for the same
        reason ``projects_for_tasks`` documents: the read guard inspects the
        body and does not follow calls.
        """
        visible = apply_scope(
            select(Task.TaskID).where(Task.TaskID == task_id), Task, self._scope
        )
        rows = self._session.execute(
            select(TaskProject.ProjectID, Project.ProjectName)
            .join(Project, Project.ProjectID == TaskProject.ProjectID)
            .where(TaskProject.TaskID == task_id)
            .where(TaskProject.TaskID.in_(visible))
        ).all()
        return sorted((int(pid), name) for pid, name in rows)


# Eager-load the subtask's images down to their storage backend (mirrors the
# route's former with_images option chain).
#
# The last two legs are redundant and deliberately kept: ImageInstance.
# ImageStorages and ImageStorage.StorageBackend are lazy="selectin" on the
# mappers, so removing them here changes nothing (measured: identical statement
# count, zero lazy loads on a detached walk). They stay because this chain is
# the contract subtask DTO conversion depends on and the mapper defaults are
# not this module's to rely on. What guards the chain is the detached walk in
# test_task_repository.py, which covers it whichever declaration provides it --
# not the presence of these two lines.
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
        stmt = apply_scope(
            select(SubTask.SubTaskID)
            .where(SubTask.TaskID == task_id)
            .order_by(SubTask.SubTaskID),
            SubTask,
            self._scope,
        )
        return list(self._session.execute(stmt).scalars().all())

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
        stmt = apply_scope(stmt, SubTask, self._scope)
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
        stmt = apply_scope(stmt, SubTask, self._scope)
        return list(
            self._session.execute(stmt.limit(limit).offset(offset)).scalars().all()
        )

    def get_by_id(self, subtask_id: int) -> SubTask | None:
        """Return the subtask with the given id, or None if absent or out of scope."""
        return scoped_one(
            self._session, SubTask, self._scope, SubTask.SubTaskID == subtask_id
        )

    def save(self, subtask: SubTask) -> None:
        """Persist in-place mutations to ``subtask`` within the request transaction.

        ``subtask`` names what is being saved; the flush covers the whole unit
        of work, deliberately not just this row.
        """
        self._session.flush()

    def get_with_images(self, subtask_id: int) -> SubTask | None:
        """Return the subtask with its image links eager-loaded, or None."""
        return scoped_one(
            self._session,
            SubTask,
            self._scope,
            SubTask.SubTaskID == subtask_id,
            options=(_SUBTASK_IMAGE_LOADER,),
        )

    def project_ids(self, subtask_id: int) -> set[int]:
        """The **parent task's** project set -- what a subtask write is judged on.

        A superset of the subtask's own images, matching the read predicate:
        you get a whole task or none of it, so a mutation is authorized against
        the whole task too.

        Deliberately unscoped, for the same reason as ``TaskRepository`` -- see
        the note there. This is project resolution, not row access.
        """
        return projects_of(self._session, SubTask, subtask_id)

    def project_ids_of_image(self, image_instance_id: int) -> set[int]:
        """The project an image sits in, for the *after* half of a link write.

        Lives here rather than on ``ImageInstanceRepository`` because this
        repository already resolves image ids (``resolve_image_instance_id``)
        on behalf of the link writes that are its only caller.

        Deliberately unscoped: same reason as ``project_ids`` above. Scoping it
        would silently drop the out-of-scope project whose presence is the
        whole point of the *after* check.
        """
        return projects_of(self._session, ImageInstance, image_instance_id)

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
