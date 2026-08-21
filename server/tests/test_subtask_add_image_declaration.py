"""Adding an image outside the task's declaration is a 409, not a 500."""
from __future__ import annotations

import pytest

from eyened_orm.authz.roles import ProjectRole
from eyened_orm.utils.factories import scope_for


@pytest.fixture()
def acting_creator(session):
    """A Creator row the ``client`` fixture's actor id points at.

    ``client`` overrides the scope with ``admin_scope()`` and the current user
    with ``CurrentUser(creator_id=1, ...)``, neither of which seeds a row --
    conftest says so, and deliberately, to keep the search-signature creator
    list clean. ``Task.CreatorID`` is a real foreign key and SQLite enforces it
    (PRAGMA foreign_keys=ON), so without this every ``POST /task`` under
    ``client`` is a 500 from the flush rather than the answer under test. The
    id is pinned rather than read back for the same reason it must exist at
    all: it has to be the id the fixture already claims.
    """
    from eyened_orm import Creator

    creator = Creator(CreatorID=1, CreatorName="tester", IsHuman=True)
    session.add(creator)
    session.flush()
    return creator.CreatorID


def test_adding_an_undeclared_image_returns_409(client, spanning):
    """Hard refusal, with a code the client can branch on."""
    response = client.post(
        f"/subtasks/{spanning['subtasks']['a_only-A']}/images",
        json={"instance_id": spanning["public_ids"]["B"]},
    )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "image_outside_task_declaration"
    assert detail["image_projects"] == [spanning["projects"]["B"]]


def test_creating_a_task_without_projects_is_refused(client, spanning, acting_creator):
    """A task declaring nothing is visible to everyone and can never take an
    image -- so it cannot be created."""
    response = client.post(
        "/task", json={"name": "undeclared", "task_definition_id": spanning["task_definition"]}
    )
    assert response.status_code == 422


def test_creating_a_task_with_projects_declares_them(client, spanning, acting_creator):
    """The declaration is written at creation, from the request."""
    response = client.post(
        "/task",
        json={
            "name": "declared",
            "task_definition_id": spanning["task_definition"],
            "projects": [spanning["projects"]["A"]],
        },
    )
    assert response.status_code == 200
    assert [p["id"] for p in response.json()["projects"]] == [spanning["projects"]["A"]]


def test_a_grader_in_both_is_refused_an_undeclared_image(client_scoped, spanning):
    """Containment refuses the grader who clears the role floor and holds both projects.

    Distinct from the admin tests above: this is the actor production has. Holding
    B is what makes 409 -- not 403 -- the correct answer, so this pins containment
    rather than authorization.
    """
    client, set_scope = client_scoped
    set_scope(scope_for(*spanning["projects"].values(), role=ProjectRole.grader))
    resp = client.post(
        f"/subtasks/{spanning['subtasks']['a_only-A']}/images",
        json={"instance_id": spanning["public_ids"]["B"]},
    )
    assert resp.status_code == 409
