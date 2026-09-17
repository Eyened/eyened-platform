"""The three admin read endpoints: who is refused, and what the payload says."""
from __future__ import annotations

from typing import get_args

import pytest

from eyened_orm import ProjectMember
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.utils.factories import make_creator, make_project, scope_for


@pytest.fixture()
def seeded(session):
    """Alice with one grader membership, Dave with none; one project of each."""
    alice = make_creator(session, "alice")
    alice.PasswordHash = "$argon2id$v=19$m=65536,t=3,p=4$placeholder"
    alice.EmployeeIdentifier = "E-1"
    dave = make_creator(session, "dave")
    graded = make_project(session, "Graded")
    make_project(session, "Empty")
    session.add(
        ProjectMember(
            CreatorID=alice.CreatorID,
            ProjectID=graded.ProjectID,
            Role=ProjectRole.grader,
        )
    )
    session.commit()
    ids = {
        "alice": alice.CreatorID,
        "dave": dave.CreatorID,
        "graded": graded.ProjectID,
    }
    # The route re-reads through the same Session; expunge so the assertions are
    # about what the query returns rather than about the identity map.
    session.expunge_all()
    return ids


def test_an_empty_scope_is_refused(client_scoped):
    """The scope most likely to pass by vacuity: no memberships at all."""
    client, set_scope = client_scoped
    set_scope(scope_for())

    assert client.get("/admin/users").status_code == 403


def test_a_project_admin_is_not_a_platform_admin(client_scoped, seeded):
    """Without this, the test above is satisfied by any membership check."""
    client, set_scope = client_scoped
    set_scope(scope_for(seeded["graded"], role=ProjectRole.project_admin))

    assert client.get("/admin/users").status_code == 403


def test_the_user_list_reports_per_row_state(client, seeded):
    """Positive control -- the refusals above pass against a route that 403s
    unconditionally."""
    response = client.get("/admin/users")

    assert response.status_code == 200
    rows = {row["username"]: row for row in response.json()}
    assert rows["alice"] == {
        "id": seeded["alice"],
        "username": "alice",
        "is_admin": False,
        "active": True,
        "has_credential": True,
        "employee_identifier": "E-1",
    }


def test_a_legacy_password_only_row_has_a_credential(client, session):
    """15 human rows in production authenticate through Creator.Password with no
    PasswordHash. Reading only PasswordHash reports every one as credential-less."""
    legacy = make_creator(session, "carol")
    legacy.Password = b"0" * 32
    session.commit()
    session.expunge_all()

    rows = {row["username"]: row for row in client.get("/admin/users").json()}
    assert rows["carol"]["has_credential"] is True


def test_memberships_serialize_the_role_as_its_name(client, seeded):
    """ProjectRole is an IntEnum, so a field typed as the enum puts {"role": 2}
    on the wire. P3's writes inherit whatever ships here."""
    response = client.get(f"/admin/users/{seeded['alice']}/memberships")

    assert response.status_code == 200
    assert response.json() == [
        {"project_id": seeded["graded"], "project_name": "Graded", "role": "grader"}
    ]


def test_the_role_union_covers_every_project_role():
    """The Literal restates roles.py by hand. A member added there without this
    union raises pydantic ValidationError in the handler -- which no registered
    handler maps, so a read endpoint 500s."""
    from server.routes.admin import MembershipResponse

    annotation = MembershipResponse.model_fields["role"].annotation
    assert set(get_args(annotation)) == {role.name for role in ProjectRole}


def test_a_user_with_no_memberships_is_200_and_empty(client, seeded):
    """Not 404. This is the population the cutover backlog item exists to find
    (a credential, no grants), and it is what separates the specified
    ``get_by_id is None`` check from an ``if not members`` one."""
    response = client.get(f"/admin/users/{seeded['dave']}/memberships")

    assert response.status_code == 200
    assert response.json() == []


def test_memberships_of_a_nonexistent_user_is_404(client):
    """The body is asserted because Starlette 404s an unregistered path too --
    without it this test passes before the route exists."""
    response = client.get("/admin/users/999999/memberships")

    assert response.status_code == 404
    assert response.json()["detail"] == "User 999999 not found"


def test_the_project_list_keeps_a_project_with_no_members(client, seeded):
    response = client.get("/admin/projects")

    assert response.status_code == 200
    counts = {row["name"]: row["member_count"] for row in response.json()}
    assert counts == {"Empty": 0, "Graded": 1}
