"""Containment as the client experiences it: 404, and absence from the list.

Two shapes here, and only the second says anything about *how* a task's
projects get resolved.

``spanning``'s tasks each declare exactly the projects their images sit in, so
on those rows reading ``TaskProject`` and walking the image links up to
``Patient.ProjectID`` return the same set. The first three tests below pass
under either mechanism -- and until the ones below them were written, so did
every other test in the repository: reinstating the image walk left 925 of 926
green, the single failure being the one test the switch itself had added.

``declared_beyond_images`` builds the row where the two part company, and the
tests under it are the ones that fail if the declaration switch is ever undone.
"""
from __future__ import annotations

import pytest

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


# --- the shape on which the declaration and the image walk disagree ----------


@pytest.fixture()
def declared_beyond_images(session, spanning):
    """A task declaring ``{A, B}`` whose one image sits in ``A``.

    The declaration is a strict superset of the projects the task's images
    occupy, which is the only way the two resolutions can differ: the walk
    answers ``{A}`` and shows the task to an ``A``-only member, the
    declaration answers ``{A, B}`` and hides it.

    **Do not "simplify" this back to declaration == image projects.** The
    divergence is not an artificial test shape -- extending a declaration
    (spec §6.3) writes exactly this row on purpose, because containment is an
    intersection and extending is therefore how visibility is *narrowed*. A
    task also sits in this shape from creation until an image has landed in
    each project it declared. Flatten the fixture and the tests below keep
    passing while proving nothing: they would run on rows where the two
    resolutions agree, and no behavioural test anywhere would notice the read
    predicate going back to the walk.

    Built here rather than added to ``spanning`` because ``spanning`` is shared
    and its row count is load-bearing elsewhere: ``test_task_list_query_budget``
    reasons about "the fixture seeds four", and the ORM-side ``spanning``
    backs an exact ``list_all() == ["empty"]``. A task deliberately visible to
    nobody outside both projects is not a safe thing to add to a fixture a
    dozen files share.
    """
    from eyened_orm import SubTask, Task, TaskProject
    from eyened_orm.task import SubTaskImageLink, SubTaskState, TaskState

    task = Task(
        TaskName="declared into B, imaged only in A",
        TaskDefinitionID=spanning["task_definition"],
        TaskState=TaskState.NotStarted,
    )
    session.add(task)
    session.flush()
    task_id = task.TaskID
    # Both declarations before the link, because the containment foreign key
    # checks (TaskID, ProjectID) against TaskProject as the link row lands.
    # B is the one that never receives an image -- that is the whole fixture.
    session.add_all([
        TaskProject(TaskID=task_id, ProjectID=spanning["projects"]["A"]),
        TaskProject(TaskID=task_id, ProjectID=spanning["projects"]["B"]),
    ])
    session.flush()
    subtask = SubTask(TaskID=task_id, TaskState=SubTaskState.NotStarted)
    session.add(subtask)
    session.flush()
    subtask_id = subtask.SubTaskID
    session.add(
        SubTaskImageLink(
            SubTaskID=subtask_id,
            ImageInstanceID=spanning["images"]["A"],
            ImageIndex=0,
        )
    )
    # Ids read out before the commit: expire_on_commit=True, so a live
    # instance would re-load through whatever session the test then holds.
    session.commit()
    return {"task": task_id, "subtask": subtask_id}


def test_a_task_declared_into_an_unheld_project_404s_though_its_images_do_not(
    client_scoped, spanning, declared_beyond_images
):
    """The declaration is what answers, not the images.

    Every image this task holds is inside ``A``, so the image walk finds
    nothing outside an ``A``-only scope and hands back 200. It is the declared
    ``B`` that hides the task.
    """
    client, set_scope = client_scoped
    set_scope(scope_for(spanning["projects"]["A"]))
    assert client.get(f"/task/{declared_beyond_images['task']}").status_code == 404
    # Not a blanket 404: the task whose declaration this scope *does* cover
    # still resolves, so the predicate is hiding one row rather than all of them.
    assert client.get(f"/task/{spanning['a_only']}").status_code == 200


def test_the_list_omits_a_task_declared_into_an_unheld_project(
    client_scoped, spanning, declared_beyond_images
):
    """The same rule on the collection route, which filters rather than 404s.

    Asserted as an exact list: "the new task is absent" alone would also hold
    for a list that had gone empty.
    """
    client, set_scope = client_scoped
    set_scope(scope_for(spanning["projects"]["A"]))
    resp = client.get("/task")
    assert resp.status_code == 200
    assert [t["id"] for t in resp.json()] == [spanning["empty"], spanning["a_only"]]


def test_the_subtask_of_such_a_task_is_hidden_on_its_own_merits(
    client_scoped, spanning, declared_beyond_images
):
    """``SubTask``'s half of the predicate, on the route that resolves an id.

    ``GET /subtasks/{id}`` resolves the subtask directly, with no task lookup
    ahead of it, so the ``SubTask`` branch answers alone here. It is **one of
    two** such routes, not the only one: ``get_task_subtask`` behind
    ``GET /task/{task_id}/subtask/{subtask_index}`` goes straight to
    ``list_for_task`` with nothing resolved ahead of it either, and the test
    below covers it. ``GET /task/{task_id}/subtasks`` is the contrast --
    ``list_task_subtasks`` resolves the task first, so ``Task``'s branch
    answers before ``SubTask``'s is reached. A half-revert -- declaration for
    ``Task``, image walk for ``SubTask`` -- left the suite fully green before
    these two tests.

    Under the walk the subtask's own image, and every sibling's, sits in ``A``,
    so an ``A``-only scope sees it. Under the declaration its parent task
    reaches into ``B``, and you get a whole task or none of it.
    """
    client, set_scope = client_scoped
    set_scope(scope_for(spanning["projects"]["A"]))
    hidden = declared_beyond_images["subtask"]
    assert client.get(f"/subtasks/{hidden}").status_code == 404
    # The control: a subtask whose parent's declaration this scope does cover.
    assert (
        client.get(f"/subtasks/{spanning['subtasks']['a_only-A']}").status_code == 200
    )


def test_the_by_index_route_hides_the_subtask_too(
    client_scoped, spanning, declared_beyond_images
):
    """The same branch on the route the viewer actually navigates with.

    ``get_task_subtask`` calls ``list_for_task`` with no task lookup ahead of
    it, so ``apply_scope(..., SubTask, ...)`` is the only thing here that can
    produce a 404 -- the ``SubTask`` branch answering alone, as in the test
    above. Pinned separately because this is the route the client's
    ``fetchSubTaskByIndex`` drives for viewer navigation, which makes it the
    per-click read the measured win belongs to; covering only ``/subtasks/{id}``
    would leave the hot path free to revert to the image walk unnoticed.

    Same row and same scope as above: under the walk the subtask's own image
    sits in ``A`` and an ``A``-only member is served it; under the declaration
    its parent reaches into ``B`` and it is not.
    """
    client, set_scope = client_scoped
    set_scope(scope_for(spanning["projects"]["A"]))
    task = declared_beyond_images["task"]
    assert client.get(f"/task/{task}/subtask/0").status_code == 404
    # The control: the same route on a task whose declaration this scope covers,
    # so a 404 that came from the index rather than the scope would show up.
    assert client.get(f"/task/{spanning['a_only']}/subtask/0").status_code == 200


def test_a_member_of_both_declared_projects_sees_the_task_and_its_subtask(
    client_scoped, spanning, declared_beyond_images
):
    """The other direction, and the control the two tests above need.

    Narrowing, not hiding: hold every project the task declares and both reads
    answer 200. Without this, a predicate that excluded the task from
    everybody would satisfy every assertion above.
    """
    client, set_scope = client_scoped
    set_scope(scope_for(*spanning["projects"].values()))
    assert client.get(f"/task/{declared_beyond_images['task']}").status_code == 200
    subtask = declared_beyond_images["subtask"]
    assert client.get(f"/subtasks/{subtask}").status_code == 200
