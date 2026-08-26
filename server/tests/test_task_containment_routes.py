"""Containment as the client experiences it: 404, and absence from the list."""
from __future__ import annotations

from eyened_orm.utils.factories import scope_for


def test_a_only_member_gets_404_on_a_spanning_task(client_scoped, spanning):
    client, set_scope = client_scoped
    set_scope(scope_for(spanning["projects"]["A"]))
    assert client.get(f"/task/{spanning['task']}").status_code == 404
    # Not a blanket 404: the task that IS contained still resolves.
    assert client.get(f"/task/{spanning['a_only']}").status_code == 200


def test_a_only_member_does_not_see_the_task_in_the_list(client_scoped, spanning):
    """Collections filter and return 200; they never 404."""
    client, set_scope = client_scoped
    set_scope(scope_for(spanning["projects"]["A"]))
    resp = client.get("/task")
    assert resp.status_code == 200
    assert [t["id"] for t in resp.json()] == [spanning["empty"], spanning["a_only"]]


def test_a_member_of_both_gets_the_task_with_every_subtask(client_scoped, spanning):
    client, set_scope = client_scoped
    set_scope(scope_for(*spanning["projects"].values()))
    resp = client.get(f"/task/{spanning['task']}")
    assert resp.status_code == 200
    assert resp.json()["num_tasks"] == 2
