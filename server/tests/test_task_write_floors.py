"""Role floors on task content, and the before-and-after union."""
from __future__ import annotations

from eyened_orm.authz.roles import ProjectRole
from eyened_orm.utils.factories import scope_for


# The `spanning` fixture is shared (server/tests/conftest.py): the same four
# tasks back the containment-route tests, so a floor asserted here and a 404
# asserted there are talking about the same rows.


def test_grader_updates_task_status(client_scoped, spanning):
    client, set_scope = client_scoped
    set_scope(scope_for(*spanning["projects"].values(), role=ProjectRole.grader))
    resp = client.patch(f"/task/{spanning['task']}", json={"task_state": "Busy"})
    assert resp.status_code == 200


def test_grader_cannot_rename_a_task(client_scoped, spanning):
    """v0.3 separates 'update tasks status' (grader) from administering a task."""
    client, set_scope = client_scoped
    set_scope(scope_for(*spanning["projects"].values(), role=ProjectRole.grader))
    resp = client.patch(f"/task/{spanning['task']}", json={"name": "renamed"})
    assert resp.status_code == 403


def test_project_admin_renames_a_task(client_scoped, spanning):
    client, set_scope = client_scoped
    set_scope(
        scope_for(*spanning["projects"].values(), role=ProjectRole.project_admin)
    )
    assert client.patch(
        f"/task/{spanning['task']}", json={"name": "renamed"}
    ).status_code == 200


def test_grader_cannot_delete_a_populated_task(client_scoped, spanning):
    client, set_scope = client_scoped
    set_scope(scope_for(*spanning["projects"].values(), role=ProjectRole.grader))
    assert client.delete(f"/task/{spanning['task']}").status_code == 403


def test_read_only_cannot_update_task_status(client_scoped, spanning):
    client, set_scope = client_scoped
    set_scope(scope_for(*spanning["projects"].values(), role=ProjectRole.read_only))
    assert client.patch(
        f"/task/{spanning['task']}", json={"task_state": "Busy"}
    ).status_code == 403


def test_anyone_can_create_a_task(session, client_scoped, spanning):
    """A new task holds no images and therefore touches no projects.

    v0.3's matrix marks create/delete tasks project-admin-only, but its own
    project permission note says creation is unrestricted. The row is two cells,
    and this is the create half asserting the vacuous behaviour, not the matrix.
    """
    from eyened_orm.utils.factories import make_creator

    # Task.CreatorID is a real FK and SQLite enforces it here (PRAGMA
    # foreign_keys=ON), so the acting user needs a row to point at.
    creator_id = make_creator(session, "author").CreatorID
    session.commit()

    client, set_scope = client_scoped
    set_scope(scope_for(actor_id=creator_id))
    resp = client.post(
        "/task",
        json={
            "name": "brand new",
            "task_definition_id": spanning["task_definition"],
        },
    )
    assert resp.status_code == 200


def test_a_grader_in_a_cannot_add_an_image_from_b(client_scoped, spanning):
    """Without the *after* half, this would launder B data into a visible task.

    404, not 403: B is not visible to this actor at all.
    """
    client, set_scope = client_scoped
    set_scope(scope_for(spanning["projects"]["A"], role=ProjectRole.grader))
    resp = client.post(
        f"/subtasks/{spanning['subtasks']['a_only-A']}/images",
        json={"instance_id": spanning["public_ids"]["B"]},
    )
    assert resp.status_code == 404


def test_a_grader_in_both_can_add_an_image_from_either(client_scoped, spanning):
    client, set_scope = client_scoped
    set_scope(scope_for(*spanning["projects"].values(), role=ProjectRole.grader))
    resp = client.post(
        f"/subtasks/{spanning['subtasks']['a_only-A']}/images",
        json={"instance_id": spanning["public_ids"]["B"]},
    )
    assert resp.status_code == 200


def test_removing_an_image_checks_the_projects_held_before(client_scoped, spanning):
    """Without the *before* half, a grader could alter a task they hold nothing in.

    The *spanning* subtask, deliberately: its parent task's before-set holds B,
    which this actor lacks. On the a_only subtask the actor holds everything and
    the request would 200 -- passing for a reason the name does not claim.
    """
    client, set_scope = client_scoped
    set_scope(scope_for(spanning["projects"]["A"], role=ProjectRole.grader))
    resp = client.delete(
        f"/subtasks/{spanning['subtasks']['spanning-A']}"
        f"/images/{spanning['public_ids']['A']}"
    )
    assert resp.status_code == 404


# --- F1 and F2 (Phase C review findings, folded into this task) ---


def test_a_stranger_cannot_unlink_the_last_image_of_a_hidden_subtask(
    session, client_scoped, spanning
):
    """F1: 404 and the link survives -- not 403, and not a committed delete."""
    from eyened_orm import SubTaskImageLink

    client, set_scope = client_scoped
    set_scope(scope_for(spanning["projects"]["A"], role=ProjectRole.project_admin))
    resp = client.delete(
        f"/subtasks/{spanning['b_only_single']}"
        f"/images/{spanning['public_ids']['B']}"
    )
    assert resp.status_code == 404
    assert resp.json().get("comments") is None  # the 200 body disclosed the row

    # ...and the same request for an image that is NOT linked to that subtask
    # must be answered identically. The status code alone cannot tell the two
    # orderings apart -- the floor 404s either way -- but the body can: without
    # the leading visibility check the bare, unscoped ``get_image_link`` runs
    # first, so a linked image answers "Not found" (from the floor) and an
    # unlinked one answers "Link not found". That difference confirms a link on
    # a subtask the caller may not know exists.
    other = client.delete(
        f"/subtasks/{spanning['b_only_single']}"
        f"/images/{spanning['public_ids']['A']}"
    )
    assert (other.status_code, other.json()) == (resp.status_code, resp.json())

    session.expire_all()
    assert (
        session.query(SubTaskImageLink)
        .filter_by(SubTaskID=spanning["b_only_single"])
        .count()
        == 1
    )


def test_zero_memberships_cannot_unlink_anything(client_scoped, spanning):
    """The cold-cutover shape: on day one every existing user holds nothing."""
    client, set_scope = client_scoped
    set_scope(scope_for())
    resp = client.delete(
        f"/subtasks/{spanning['b_only_single']}"
        f"/images/{spanning['public_ids']['B']}"
    )
    assert resp.status_code == 404


def test_a_stranger_cannot_mutate_a_task_that_touches_no_projects(
    client_scoped, spanning
):
    """F2, write half: the empty set must not satisfy the floor vacuously."""
    client, set_scope = client_scoped
    set_scope(scope_for())
    assert client.patch(
        f"/subtasks/{spanning['empty_subtask']}", json={"comments": "hijacked"}
    ).status_code == 404
    assert client.delete(f"/task/{spanning['empty']}").status_code == 404


def test_a_member_cannot_mutate_a_task_that_touches_no_projects(
    client_scoped, spanning
):
    """Holding project_admin somewhere does not reach a task that touches nowhere.

    Pinned separately from the zero-membership case: an implementation that
    checked `self.scope.roles` rather than the resolved project set would pass
    the test above and fail here.
    """
    client, set_scope = client_scoped
    set_scope(scope_for(spanning["projects"]["A"], role=ProjectRole.project_admin))
    assert client.delete(f"/task/{spanning['empty']}").status_code == 404


def test_an_admin_still_reaches_a_task_that_touches_no_projects(client_scoped, spanning):
    """The fail-closed empty set must not lock the data superuser out."""
    from eyened_orm.utils.factories import admin_scope

    client, set_scope = client_scoped
    set_scope(admin_scope())
    assert client.delete(f"/task/{spanning['empty']}").status_code in (200, 204)
