"""Role floors on task content, and the before-and-after union."""
from __future__ import annotations

from eyened_orm.authz.roles import ProjectRole
from eyened_orm.authz.scope import AccessScope
from eyened_orm.utils.factories import scope_for


# The `spanning` fixture is shared (server/tests/conftest.py): the same four
# tasks back the containment-route tests, so a floor asserted here and a 404
# asserted there are talking about the same rows.


def _scope_holding(roles: dict[int, ProjectRole]) -> AccessScope:
    """A non-admin scope holding a *different* role per project.

    ``scope_for`` applies one role to every project it is given, which cannot
    express the only shape that discriminates the *after* half of the union:
    an actor who can see project B (so the post-write re-read succeeds) but is
    under the floor there (so the union rejects). See
    ``test_a_grader_in_a_who_only_reads_b_cannot_add_an_image_from_b``.
    """
    return AccessScope(actor_id=1, username="tester", is_admin=False, roles=roles)


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
    """An actor blind to B cannot pull a B image into a task they can see.

    404, not 403: B is not visible to this actor at all. This case does **not**
    discriminate the union -- with only ``projects_before`` consulted the write
    would commit and the post-write scoped re-read would then fail, so the 404
    survives either way. It is kept for the path it does pin: an unseeable
    project is answered 404, never 403. The union itself is pinned by the
    read-only-in-B case below.
    """
    client, set_scope = client_scoped
    set_scope(scope_for(spanning["projects"]["A"], role=ProjectRole.grader))
    resp = client.post(
        f"/subtasks/{spanning['subtasks']['a_only-A']}/images",
        json={"instance_id": spanning["public_ids"]["B"]},
    )
    assert resp.status_code == 404


def test_a_grader_in_a_who_only_reads_b_cannot_add_an_image_from_b(
    session, client_scoped, spanning
):
    """The *after* half, discriminated: 403, and no link committed.

    The roles are deliberately unequal. ``read_only`` in B keeps the task
    visible after the write -- so the post-write re-read cannot be what refuses
    -- while leaving the actor under ``grader`` there. Only the *after* half of
    ``projects_before | projects_after`` sees B; consult ``projects_before``
    alone and this request is a 200 with the link committed.

    403 rather than 404 because the actor holds every project involved and is
    merely under the floor in one of them.
    """
    from eyened_orm import SubTaskImageLink

    client, set_scope = client_scoped
    set_scope(
        _scope_holding(
            {
                spanning["projects"]["A"]: ProjectRole.grader,
                spanning["projects"]["B"]: ProjectRole.read_only,
            }
        )
    )
    subtask_id = spanning["subtasks"]["a_only-A"]
    resp = client.post(
        f"/subtasks/{subtask_id}/images",
        json={"instance_id": spanning["public_ids"]["B"]},
    )
    assert resp.status_code == 403

    session.expire_all()
    assert (
        session.query(SubTaskImageLink)
        .filter_by(
            SubTaskID=subtask_id, ImageInstanceID=spanning["images"]["B"]
        )
        .count()
        == 0
    )


def test_a_grader_in_both_can_add_an_image_from_either(client_scoped, spanning):
    client, set_scope = client_scoped
    set_scope(scope_for(*spanning["projects"].values(), role=ProjectRole.grader))
    resp = client.post(
        f"/subtasks/{spanning['subtasks']['a_only-A']}/images",
        json={"instance_id": spanning["public_ids"]["B"]},
    )
    assert resp.status_code == 200


def test_removing_an_image_from_a_partly_visible_task_is_404(client_scoped, spanning):
    """A subtask of a task the actor cannot fully see is not reachable at all.

    What refuses here is ``remove_image``'s leading visibility check, **not** its
    floor: the parent task spans A and B, the actor holds only A, so the scoped
    ``get_by_id`` returns nothing and the method raises before the floor is
    consulted. Delete the floor and this test still passes -- by design; the
    floor is pinned by ``test_read_only_in_every_project_cannot_remove_an_image``
    below, which is written on a fully visible task for exactly that reason.
    """
    client, set_scope = client_scoped
    set_scope(scope_for(spanning["projects"]["A"], role=ProjectRole.grader))
    resp = client.delete(
        f"/subtasks/{spanning['subtasks']['spanning-A']}"
        f"/images/{spanning['public_ids']['A']}"
    )
    assert resp.status_code == 404


def test_read_only_in_every_project_cannot_remove_an_image(
    session, client_scoped, spanning
):
    """``remove_image``'s floor, on a task the actor can fully see.

    read_only in both A and B, so the parent task of ``spanning-A`` is visible
    and the leading check passes; only the ``grader`` floor stands between this
    request and the delete. Delete the floor and the link goes.
    """
    from eyened_orm import SubTaskImageLink

    client, set_scope = client_scoped
    set_scope(scope_for(*spanning["projects"].values(), role=ProjectRole.read_only))
    subtask_id = spanning["subtasks"]["spanning-A"]
    resp = client.delete(
        f"/subtasks/{subtask_id}/images/{spanning['public_ids']['A']}"
    )
    assert resp.status_code == 403

    session.expire_all()
    assert (
        session.query(SubTaskImageLink).filter_by(SubTaskID=subtask_id).count() == 1
    )


def test_read_only_in_every_project_cannot_delete_a_subtask(
    session, client_scoped, spanning
):
    """``delete_subtask``'s floor, on a task the actor can fully see."""
    from eyened_orm import SubTask

    client, set_scope = client_scoped
    set_scope(scope_for(*spanning["projects"].values(), role=ProjectRole.read_only))
    subtask_id = spanning["subtasks"]["spanning-A"]
    assert client.delete(f"/subtasks/{subtask_id}").status_code == 403

    session.expire_all()
    assert session.get(SubTask, subtask_id) is not None


def test_read_only_in_every_project_cannot_update_a_subtask(
    session, client_scoped, spanning
):
    """``update_subtask``'s floor through a *role*, not through the empty set.

    The empty-set case (``test_a_stranger_cannot_mutate_a_task_that_touches_no
    _projects``) reaches ``require``'s fail-closed guard, which fires whatever
    floor is passed -- so it cannot tell ``grader`` from ``read_only`` and
    survives a floor lowered to ``read_only``. This case is the one that reads
    the floor argument: the actor sees every project the task touches, so only
    the role comparison can refuse.
    """
    from eyened_orm import SubTask

    client, set_scope = client_scoped
    set_scope(scope_for(*spanning["projects"].values(), role=ProjectRole.read_only))
    subtask_id = spanning["subtasks"]["spanning-A"]
    resp = client.patch(f"/subtasks/{subtask_id}", json={"comments": "hijacked"})
    assert resp.status_code == 403

    session.expire_all()
    assert session.get(SubTask, subtask_id).Comments != "hijacked"


def test_a_grader_unlinks_the_last_image_of_a_visible_subtask(
    session, client_scoped, spanning
):
    """The happy path that pins *resolve the projects before you mutate*.

    ``b_only_single`` holds exactly one link, so the delete empties its parent
    task's project set. Resolved before the delete the set is ``{B}`` and this
    grader passes; resolved after, it is the empty set, which ``require`` now
    fails closed -- a 404 with the delete rolled back. That is what makes the
    ordering observable rather than merely correct.
    """
    from eyened_orm import SubTaskImageLink

    client, set_scope = client_scoped
    set_scope(scope_for(spanning["projects"]["B"], role=ProjectRole.grader))
    subtask_id = spanning["b_only_single"]
    resp = client.delete(
        f"/subtasks/{subtask_id}/images/{spanning['public_ids']['B']}"
    )
    assert resp.status_code == 200

    session.expire_all()
    assert (
        session.query(SubTaskImageLink).filter_by(SubTaskID=subtask_id).count() == 0
    )


# --- F1 and F2 (Phase C review findings, folded into this task) ---


def test_a_stranger_cannot_unlink_the_last_image_of_a_hidden_subtask(
    client_scoped, spanning
):
    """F1: a hidden subtask is answered identically whether or not it holds the link.

    The status code alone is not the pin -- see the second probe below.
    """
    client, set_scope = client_scoped
    set_scope(scope_for(spanning["projects"]["A"], role=ProjectRole.project_admin))
    resp = client.delete(
        f"/subtasks/{spanning['b_only_single']}"
        f"/images/{spanning['public_ids']['B']}"
    )
    assert resp.status_code == 404

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
