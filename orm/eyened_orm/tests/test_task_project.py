"""The declaration table."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from eyened_orm import Task, TaskProject


def test_deleting_a_task_removes_its_declaration(session, spanning):
    """A declaration is owned by its task and must not outlive it.

    The `spanning` fixture declares A on `a_only`, so this reads that
    declaration rather than writing its own -- writing one here would
    duplicate the fixture's row on its composite primary key.

    Placed here rather than with the constraint tests because Task 6 adds a
    RESTRICT foreign key from SubTaskImageLink to this table, and that is what
    turns an ORM-ordered delete into an IntegrityError. This passes now and
    must still pass then -- it is the regression test for the cascade
    configuration below, not for the composite primary key.

    Its subject must stay `a_only`, the task that *has* images: from Task 6
    the declaration it deletes is referenced by a live RESTRICT foreign key,
    which is a shape the link-less `empty` task cannot reach.
    """
    task_id = spanning["a_only"]
    assert session.scalars(
        select(TaskProject).where(TaskProject.TaskID == task_id)
    ).all(), "the fixture should have made this task declare its project"

    session.delete(session.get(Task, task_id))
    session.commit()
    session.expunge_all()

    assert (
        session.scalars(
            select(TaskProject).where(TaskProject.TaskID == task_id)
        ).all()
        == []
    )


def test_create_from_imagesets_declares_the_images_projects(session, spanning):
    """projects=None derives the declaration from the images given."""
    task = Task.create_from_imagesets(
        session, "def", "derived",
        imagesets=[[spanning["images"]["A"], spanning["images"]["B"]]],
    )
    session.add(task)
    session.flush()
    declared = set(
        session.scalars(
            select(TaskProject.ProjectID).where(TaskProject.TaskID == task.TaskID)
        )
    )
    assert declared == set(spanning["projects"].values())


def test_create_from_imagesets_takes_an_explicit_declaration(session, spanning):
    """The stricter form: declare exactly these, whatever the images are."""
    task = Task.create_from_imagesets(
        session, "def", "explicit",
        imagesets=[[spanning["images"]["A"]]],
        projects=[spanning["projects"]["A"]],
    )
    session.add(task)
    session.flush()
    declared = set(
        session.scalars(
            select(TaskProject.ProjectID).where(TaskProject.TaskID == task.TaskID)
        )
    )
    assert declared == {spanning["projects"]["A"]}


def test_a_task_that_would_declare_nothing_is_refused(session, spanning):
    """Global Constraints: a task with an empty declaration is a dead end."""
    with pytest.raises(ValueError, match="at least one project"):
        Task.create_from_imagesets(session, "def", "empty", imagesets=[[]])
