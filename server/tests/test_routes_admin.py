"""The admin endpoints: who is refused, what the payload says, what a write records."""
from __future__ import annotations

from typing import get_args

import pytest
from sqlalchemy import select

from eyened_orm import AuditLog, ProjectMember
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.repositories import ProjectMemberRepository
from eyened_orm.utils.factories import admin_scope, make_creator, make_project, scope_for


@pytest.fixture()
def seeded(session):
    """Alice with one grader membership, Dave with none; one project of each."""
    alice = make_creator(session, "alice")
    alice.PasswordHash = "$argon2id$v=19$m=65536,t=3,p=4$placeholder"
    alice.EmployeeIdentifier = "E-1"
    dave = make_creator(session, "dave")
    graded = make_project(session, "Graded")
    empty = make_project(session, "Empty")
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
        "empty": empty.ProjectID,
    }
    # The route re-reads through the same Session; expunge so the assertions are
    # about what the query returns rather than about the identity map.
    session.expunge_all()
    return ids


# One gate in AdminService.__init__ covers all six routes. The gate fires
# before any id is resolved, so the ids are arbitrary.
ADMIN_ROUTES = [
    ("GET", "/admin/users"),
    ("GET", "/admin/users/1/memberships"),
    ("GET", "/admin/projects"),
    ("PUT", "/admin/projects/1/members/1"),
    ("DELETE", "/admin/projects/1/members/1"),
    ("GET", "/admin/users/1/grant-preview?task_id=1&role=grader"),
]


def _send(client, method, path):
    return client.request(
        method, path, json={"role": "grader"} if method == "PUT" else None
    )


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_an_empty_scope_is_refused(client_scoped, method, path):
    """The scope most likely to pass by vacuity: no memberships at all."""
    client, set_scope = client_scoped
    set_scope(scope_for())

    assert _send(client, method, path).status_code == 403


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_a_project_admin_is_not_a_platform_admin(client_scoped, seeded, method, path):
    """Without this, the test above is satisfied by any membership check."""
    client, set_scope = client_scoped
    set_scope(scope_for(seeded["graded"], role=ProjectRole.project_admin))

    assert _send(client, method, path).status_code == 403


def test_an_unauthenticated_caller_is_refused(client_anonymous):
    """`client` and `client_scoped` are both authenticated, so nothing else here
    reaches the 401."""
    assert client_anonymous.get("/admin/users").status_code == 401


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


def _member_audit_rows(session):
    return session.scalars(
        select(AuditLog).where(AuditLog.Entity == "ProjectMember")
    ).all()


def test_a_grant_is_attributed_to_the_calling_admin(client_scoped, session, seeded):
    """4242 is not admin_scope's default actor, so a hardcoded id fails."""
    client, set_scope = client_scoped
    set_scope(admin_scope(actor_id=4242))

    response = client.put(
        f"/admin/projects/{seeded['empty']}/members/{seeded['dave']}",
        json={"role": "grader"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "project_id": seeded["empty"],
        "project_name": "Empty",
        "user_id": seeded["dave"],
        "role": "grader",
        "changed": True,
    }
    [row] = _member_audit_rows(session)
    assert (row.Action, row.ActorID, row.TrustedPath, row.ProjectID) == (
        "INSERT", 4242, None, seeded["empty"]
    )


def test_revoking_a_membership_is_204(client, session, seeded):
    response = client.delete(
        f"/admin/projects/{seeded['graded']}/members/{seeded['alice']}"
    )

    assert response.status_code == 204
    assert ProjectMemberRepository(session).roles_for(seeded["alice"]) == {}


def test_revoking_an_absent_membership_is_still_204(client, seeded):
    """A retried DELETE never fails."""
    response = client.delete(
        f"/admin/projects/{seeded['graded']}/members/{seeded['dave']}"
    )

    assert response.status_code == 204


@pytest.mark.parametrize(
    "method,path,detail",
    [
        ("PUT", "/admin/projects/{graded}/members/999999", "no creator with id 999999"),
        ("DELETE", "/admin/projects/999999/members/{alice}", "no project with id 999999"),
        ("GET", "/admin/users/{alice}/grant-preview?task_id=999999&role=grader",
         "no task with id 999999"),
    ],
    ids=["grant-user", "revoke-project", "preview-task"],
)
def test_an_unknown_id_is_404_naming_it(client, seeded, method, path, detail):
    """One case per service method and per resolver: each untranslated one is a 500."""
    response = _send(client, method, path.format(**seeded))

    assert response.status_code == 404
    assert response.json()["detail"] == detail


def test_the_preview_splits_what_would_be_granted_from_what_is_held(
    client, session, spanning
):
    alice = make_creator(session, "alice")
    session.add(
        ProjectMember(
            CreatorID=alice.CreatorID,
            ProjectID=spanning["projects"]["A"],
            Role=ProjectRole.grader,
        )
    )
    session.commit()
    alice_id = alice.CreatorID

    response = client.get(
        f"/admin/users/{alice_id}/grant-preview",
        params={"task_id": [spanning["task"]], "role": "read_only"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": alice_id,
        "role": "read_only",
        "to_grant": [
            {"project_id": spanning["projects"]["B"], "project_name": "B", "role": "read_only"}
        ],
        "already_held": [
            {"project_id": spanning["projects"]["A"], "project_name": "A", "role": "grader"}
        ],
    }
