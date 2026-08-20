"""The declaration table."""
from __future__ import annotations

from sqlalchemy import select

from eyened_orm import Task, TaskProject


def test_deleting_a_task_removes_its_declaration(session, spanning):
    """A declaration is owned by its task and must not outlive it.

    Placed here rather than with the constraint tests because Task 6 adds a
    RESTRICT foreign key from SubTaskImageLink to this table, and that is what
    turns an ORM-ordered delete into an IntegrityError. This passes now and
    must still pass then -- it is the regression test for the cascade
    configuration below, not for the composite primary key.
    """
    task_id = spanning["a_only"]
    session.add(TaskProject(TaskID=task_id, ProjectID=spanning["projects"]["A"]))
    session.commit()

    session.delete(session.get(Task, task_id))
    session.commit()
    session.expunge_all()

    assert (
        session.scalars(
            select(TaskProject).where(TaskProject.TaskID == task_id)
        ).all()
        == []
    )
