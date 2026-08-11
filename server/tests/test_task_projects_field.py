"""A task names the projects it spans, for anyone who can see the task."""
from __future__ import annotations


def test_a_member_of_both_sees_both_project_names(client_scoped, spanning):
    """This discloses nothing: a task is only visible to a member of every
    project it spans, so anyone who can see it is already a member of every
    project named. There is no filtering to do on the list itself."""
    from eyened_orm.utils.factories import scope_for

    client, set_scope = client_scoped
    set_scope(scope_for(*spanning["projects"].values()))
    resp = client.get(f"/task/{spanning['task']}")
    assert resp.status_code == 200
    assert sorted(p["name"] for p in resp.json()["projects"]) == ["A", "B"]


def test_a_task_with_no_images_reports_an_empty_list(client_scoped, spanning):
    """An honest empty list, not an error."""
    from eyened_orm.utils.factories import scope_for

    client, set_scope = client_scoped
    set_scope(scope_for())
    resp = client.get(f"/task/{spanning['empty']}")
    assert resp.status_code == 200
    assert resp.json()["projects"] == []


def test_the_task_list_carries_the_field_too(client_scoped, spanning):
    from eyened_orm.utils.factories import scope_for

    client, set_scope = client_scoped
    set_scope(scope_for(*spanning["projects"].values()))
    rows = client.get("/task").json()
    by_id = {t["id"]: t for t in rows}
    assert sorted(p["name"] for p in by_id[spanning["task"]]["projects"]) == ["A", "B"]


def test_it_agrees_with_the_enforcement_path(session, spanning):
    """The batched query and projects_of must not answer differently:
    grant-for-task and this endpoint are the two sides of one promise."""
    from eyened_orm import Task
    from eyened_orm.authz.scoping import projects_of
    from eyened_orm.repositories.task_repository import TaskRepository
    from eyened_orm.utils.factories import admin_scope

    repo = TaskRepository(session, scope=admin_scope())
    ids = [spanning[k] for k in ("task", "empty", "a_only", "b_only")]
    batched = repo.projects_for_tasks(ids)
    for tid in ids:
        assert {pid for pid, _ in batched[tid]} == projects_of(session, Task, tid)
