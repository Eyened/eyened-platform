"""Containment at the repository: a whole task, or none of it."""
from __future__ import annotations

from eyened_orm.repositories import SubTaskRepository, TaskRepository
from eyened_orm.utils.factories import admin_scope, scope_for


def test_a_member_of_one_project_does_not_see_a_spanning_task(session, spanning):
    """Absent from every read -- and the A-only task is still there, so the
    predicate is hiding the right row rather than hiding everything."""
    repo = TaskRepository(session, scope=scope_for(spanning["projects"]["A"]))
    assert repo.get_by_id(spanning["task"]) is None
    assert repo.get_with_relations(spanning["task"]) is None
    assert [t.TaskName for t in repo.list_all()] == ["empty", "a_only"]


def test_a_member_of_both_sees_the_task_and_every_subtask(session, spanning):
    scope = scope_for(*spanning["projects"].values())
    tasks = TaskRepository(session, scope=scope)
    subtasks = SubTaskRepository(session, scope=scope)
    assert tasks.get_by_id(spanning["task"]) is not None
    assert subtasks.count_for_task(spanning["task"]) == 2
    assert len(subtasks.list_for_task(spanning["task"], limit=10, offset=0)) == 2
    assert len(subtasks.all_ids_for_task(spanning["task"])) == 2


def test_a_subtask_of_a_hidden_task_is_not_reachable_on_its_own_merits(
    session, spanning
):
    """The A-side subtask sits entirely in A, but its parent task does not."""
    repo = SubTaskRepository(session, scope=scope_for(spanning["projects"]["A"]))
    assert repo.get_by_id(spanning["subtasks"]["spanning-A"]) is None
    assert repo.get_with_images(spanning["subtasks"]["spanning-A"]) is None
    assert repo.count_for_task(spanning["task"]) == 0
    assert repo.all_ids_for_task(spanning["task"]) == []
    assert repo.list_for_task(spanning["task"], limit=10, offset=0) == []
    # ... while the subtask of the A-only task, which IS contained, still reads.
    assert repo.get_by_id(spanning["subtasks"]["a_only-A"]) is not None
    assert len(repo.list_for_task(spanning["a_only"], limit=10, offset=0)) == 1


def test_subtask_counts_report_zero_for_a_hidden_task(session, spanning):
    """Never a partial view: not 'the task with fewer subtasks'."""
    repo = TaskRepository(session, scope=scope_for(spanning["projects"]["A"]))
    counts = repo.subtask_counts([spanning["task"], spanning["a_only"]])
    assert counts[spanning["task"]] == (0, 0)
    assert counts[spanning["a_only"]] == (1, 0)


def test_a_task_with_no_images_is_visible_to_anyone(session, spanning):
    """Vacuity, accepted in v0.3 (Visibility, consequence 4)."""
    repo = TaskRepository(session, scope=scope_for())
    assert repo.get_by_id(spanning["empty"]) is not None
    assert [t.TaskName for t in repo.list_all()] == ["empty"]


def test_an_admin_sees_the_spanning_task(session, spanning):
    assert TaskRepository(session, scope=admin_scope()).get_by_id(spanning["task"])
