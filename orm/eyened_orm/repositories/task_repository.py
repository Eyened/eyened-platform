from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from eyened_orm import SubTask, Task
from eyened_orm.task import SubTaskState

# Load task metadata without eager-loading every SubTask row (mirrors the
# route's former ``_task_query_options``).
_TASK_RELATIONS = (
    selectinload(Task.Creator),
    selectinload(Task.TaskDefinition),
)


class TaskRepository:
    """Data access for Task rows and their subtask counts."""

    def get_by_id(self, session: Session, task_id: int) -> Task | None:
        """Return the task with the given id, or None if absent."""
        return session.get(Task, task_id)

    def get_with_relations(self, session: Session, task_id: int) -> Task | None:
        """Return the task with Creator + TaskDefinition eager-loaded, or None."""
        return (
            session.execute(
                select(Task).options(*_TASK_RELATIONS).where(Task.TaskID == task_id)
            )
            .scalars()
            .first()
        )

    def list_all(self, session: Session) -> list[Task]:
        """Return all tasks (TaskID order) with Creator + TaskDefinition loaded."""
        return list(
            session.execute(
                select(Task).options(*_TASK_RELATIONS).order_by(Task.TaskID)
            )
            .scalars()
            .all()
        )

    def subtask_counts(
        self, session: Session, task_ids: list[int]
    ) -> dict[int, tuple[int, int]]:
        """Return {task_id: (num_subtasks, num_ready)} for the given task ids.

        One grouped aggregate over ``SubTask`` (mirrors the route's former
        ``_subtask_counts_by_task_id``). Every requested id is present in the
        result: ids with no subtasks map to ``(0, 0)``.
        """
        if not task_ids:
            return {}
        rows = session.execute(
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
