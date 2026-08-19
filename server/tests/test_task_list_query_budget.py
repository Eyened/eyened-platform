"""The task list must not grow queries as tasks are added.

The 14.5s regression shipped under a green suite because nothing counted
statements. SQLite won't reproduce MySQL's plan, so the batching is what gets
pinned -- it catches an N+1 and an unconditional span walk alike.
"""
from __future__ import annotations

import pytest
from sqlalchemy import event

from eyened_orm.repositories import SubTaskRepository, TaskRepository
from eyened_orm.utils.factories import admin_scope
from server.services.task_service import TaskService


@pytest.fixture
def selects(session):
    """Every SELECT issued on the session's connection."""
    seen: list[str] = []
    engine = session.get_bind()

    def hook(conn, cursor, statement, *_):
        if statement.lstrip().upper().startswith("SELECT"):
            seen.append(statement)

    event.listen(engine, "before_cursor_execute", hook)
    yield seen
    event.remove(engine, "before_cursor_execute", hook)


@pytest.fixture
def counting_service(session):
    """A TaskService over the seeded session, admin-scoped.

    Admin scope short-circuits apply_scope, which is what we want: the
    statement count is the property under test, and an admin scope keeps it
    free of the scoping predicate's own shape.
    """
    scope = admin_scope()
    return TaskService(
        TaskRepository(session, scope=scope),
        SubTaskRepository(session, scope=scope),
        scope=scope,
        audit=None,
    )


def test_span_lookup_costs_exactly_one_extra_statement(
    counting_service, selects, spanning
):
    """Spans are one batched query, not one per task.

    The *gap* is the property, deliberately, not either absolute count. The
    base moves with fixture shape -- every ``spanning`` task has a null
    CreatorID, so ``selectinload(Task.Creator)`` does not fire and
    ``selectinload(Task.TaskDefinition)`` does -- and pinning a number that
    an unrelated fixture edit can move is how a ratchet gets loosened. An N+1
    span lookup, by contrast, makes the gap grow with the number of tasks:
    the fixture seeds four, so it would read 4, not 1.
    """
    selects.clear()
    counting_service.list_tasks(include_projects=False)
    without = len(selects)

    selects.clear()
    counting_service.list_tasks(include_projects=True)
    with_spans = len(selects)

    assert with_spans - without == 1, "\n---\n".join(selects)


def test_the_gap_grows_if_the_span_lookup_stops_being_batched(
    counting_service, selects, spanning, monkeypatch
):
    """Negative control: the guard above must bite when batching is lost.

    Added because the test it controls passes the moment it is written -- it
    guards work Task 2 already did -- and a guard nobody has seen fail is a
    guard nobody knows is wired up. Monkeypatched rather than edited into the
    repository, so nothing tracked is mutated to run it.
    """
    repo = counting_service.tasks
    batched = repo.projects_for_tasks
    monkeypatch.setattr(
        repo, "projects_for_tasks", lambda ids: {t: batched([t])[t] for t in ids}
    )

    selects.clear()
    counting_service.list_tasks(include_projects=False)
    without = len(selects)

    selects.clear()
    counting_service.list_tasks(include_projects=True)
    with_spans = len(selects)

    assert with_spans - without == 4  # one per task in the fixture, not one total
