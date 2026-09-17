import json
from datetime import datetime, timedelta, timezone
from hashlib import pbkdf2_hmac
from types import SimpleNamespace
from urllib.parse import quote

import jwt
import pytest
from sqlalchemy import select

from eyened_orm import AuditLog, Creator, CreatorTagLink
from eyened_orm.tag import TagType
from eyened_orm.utils.db_users import hash_password
from eyened_orm.utils.factories import make_tag

from server.config import settings
from server.routes.auth import (
    create_access_token,
    generate_secure_token,
    validate_secure_token,
)


def test_generate_verify_secure_token():
    """Test that we can generate and validate a token"""
    secret_key = "some-secret-key"
    token, token_hash = generate_secure_token(secret_key)
    assert token is not None
    assert token_hash is not None
    assert token != token_hash

    assert validate_secure_token(token, token_hash, secret_key)


def _legacy_hash(password: str) -> bytes:
    """Reproduce AuthService.authenticate's legacy pbkdf2 hash for seeding a pre-migration Creator."""
    return pbkdf2_hmac("sha256", password.encode(), "6f4b661212".encode(), 10000)


def test_login_with_legacy_password_migrates_hash_and_audits_once(
    client, session, signed_jwts
):
    """Legacy-hash login migrates PasswordHash/clears Password and records exactly
    one AuditLog UPDATE row for Creator -- committed only at the request boundary
    (get_db), not mid-handler inside AuthService.authenticate."""
    creator = Creator(
        CreatorName="legacy-user",
        Password=_legacy_hash("old-password"),
        PasswordHash=None,
        IsHuman=True,
    )
    session.add(creator)
    session.commit()
    creator_id = creator.CreatorID

    original_commit = session.commit
    commit_calls = []

    def _tracking_commit():
        commit_calls.append(1)
        return original_commit()

    session.commit = _tracking_commit

    response = client.post(
        "/auth/login",
        json={"username": "legacy-user", "password": "old-password"},
    )

    assert response.status_code == 200, response.text

    migrated = session.get(Creator, creator_id)
    assert migrated.Password is None
    assert migrated.PasswordHash is not None

    audit_rows = (
        session.query(AuditLog)
        .filter_by(Entity="Creator", EntityID=str(creator_id))
        .all()
    )
    assert len(audit_rows) == 1
    assert audit_rows[0].Action == "UPDATE"
    assert audit_rows[0].Changes == {"password_hash": "migrated from legacy"}

    # Exactly one commit -- get_db's request-boundary commit. A second commit here
    # would mean AuthService.authenticate is still committing mid-handler.
    assert commit_calls == [1]


def test_refresh_with_valid_token_returns_the_user(
    client, session, signed_jwts
):
    """A valid refresh-token cookie yields 200 with the refreshed user's info."""
    from server.routes.auth import create_refresh_token

    creator = Creator(CreatorName="refresh-user", IsHuman=True)
    session.add(creator)
    session.commit()
    refresh_cookie = create_refresh_token(creator.CreatorID)

    client.cookies.set("refresh_token", refresh_cookie)
    response = client.post("/auth/refresh")

    assert response.status_code == 200, response.text
    assert response.json()["username"] == "refresh-user"


def test_refresh_without_cookie_returns_401(client):
    """No refresh-token cookie hits the endpoint's explicit 401 branch."""
    response = client.post("/auth/refresh")

    assert response.status_code == 401


def test_refresh_with_garbage_token_returns_401(client):
    """An unparseable refresh-token cookie is caught by the endpoint's blanket 401."""
    client.cookies.set("refresh_token", "not-a-jwt")
    response = client.post("/auth/refresh")

    assert response.status_code == 401


def test_change_password_persists_new_password_and_invalidates_old(
    client, session, signed_jwts
):
    """POST /auth/change-password persists the new password to the request
    boundary (not mid-handler): a follow-up /auth/login succeeds with the new
    password and fails (401) with the old one."""
    creator = Creator(
        # Must match the `client` fixture's overridden CurrentUser (username="tester"):
        # change_password looks the acting user up by current_user.username.
        CreatorName="tester",
        PasswordHash=hash_password("old-password"),
        IsHuman=True,
    )
    session.add(creator)
    session.commit()

    response = client.post(
        "/auth/change-password",
        json={"old_password": "old-password", "new_password": "new-password"},
    )
    assert response.status_code == 200, response.text

    old_login = client.post(
        "/auth/login", json={"username": "tester", "password": "old-password"}
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/auth/login", json={"username": "tester", "password": "new-password"}
    )
    assert new_login.status_code == 200


def test_check_oidc_login_creates_new_account_but_does_not_commit(session, monkeypatch):
    """check_oidc_login creates a new Creator for an unknown OIDC subject but
    only flushes -- a rollback (get_db's, on a later exception) discards the
    new account entirely, since neither it nor create_user commits."""
    import server.routes.auth as auth_module
    from server.routes.auth import check_oidc_login

    monkeypatch.setattr(
        auth_module,
        "settings",
        SimpleNamespace(oidc=SimpleNamespace(create_new_accounts=True)),
    )

    claims = {"sub": "abc123", "preferred_username": "new-oidc-user"}
    creator = check_oidc_login(claims, session)

    assert creator.CreatorName == "new-oidc-user"
    assert creator.EmployeeIdentifier == "oidc:sub:abc123"

    session.rollback()  # get_db does this in production on a later exception
    assert session.query(Creator).filter_by(CreatorName="new-oidc-user").count() == 0


def test_check_oidc_login_migrates_non_subject_identifier_but_does_not_commit(session):
    """check_oidc_login replaces a non-Subject OIDC identifier with the
    Subject-claim identifier, but only flushes -- same request-boundary-owns-
    the-commit property as new-account creation above."""
    from server.routes.auth import check_oidc_login

    creator = Creator(
        CreatorName="legacy-oidc-user",
        EmployeeIdentifier="oidc:email:old@example.com",
        IsHuman=True,
    )
    session.add(creator)
    session.commit()
    creator_id = creator.CreatorID

    claims = {"sub": "sub-999", "email": "old@example.com"}
    found = check_oidc_login(claims, session)

    assert found.CreatorID == creator_id
    assert found.EmployeeIdentifier == "oidc:sub:sub-999"

    session.rollback()  # get_db does this in production on a later exception
    reloaded = session.get(Creator, creator_id)
    assert reloaded.EmployeeIdentifier == "oidc:email:old@example.com"


def test_dev_bypass_promotes_the_configured_account_to_administrator(
    session, monkeypatch
):
    """Otherwise a pre-cutover dump shows a developer an empty platform."""
    from fastapi.testclient import TestClient

    import server.db as server_db
    from server.config import Settings
    from server.main import app_api
    from server.tests.conftest import _SessionBoundDatabase

    monkeypatch.setattr(server_db, "database", _SessionBoundDatabase(session))
    monkeypatch.setattr(
        # get_current_user moved to server/services/current_user.py (to delete
        # the services -> routes import edge); it reads `settings` from that
        # module's namespace, so this is the target that must be patched.
        "server.services.current_user.settings",
        Settings(public_auth_disabled=True, admin_username="devadmin"),
    )

    with TestClient(app_api) as client:
        resp = client.get("/auth/me")

    assert resp.status_code == 200
    assert resp.json()["username"] == "devadmin"

    from eyened_orm import Creator
    from sqlalchemy import select

    creator = session.scalars(
        select(Creator).where(Creator.CreatorName == "devadmin")
    ).first()
    assert creator.IsAdmin is True


def test_dev_bypass_works_without_configuring_a_password(session, monkeypatch):
    """The dev bypass never authenticates with a password, so a deployment
    that configures only ``admin_username`` (the common case -- password
    login for the bootstrapped account is optional) must still work. Without
    this test, a future change that makes ``get_current_user`` unconditionally
    reach for a password would 500 every such dev-bypass request and nothing
    here would catch it.
    """
    from fastapi.testclient import TestClient

    import server.db as server_db
    from server.config import Settings
    from server.main import app_api
    from server.tests.conftest import _SessionBoundDatabase

    monkeypatch.setattr(server_db, "database", _SessionBoundDatabase(session))
    monkeypatch.setattr(
        # get_current_user moved to server/services/current_user.py (to delete
        # the services -> routes import edge); it reads `settings` from that
        # module's namespace, so this is the target that must be patched.
        "server.services.current_user.settings",
        Settings(public_auth_disabled=True, admin_username="devadmin"),
    )

    with TestClient(app_api) as client:
        assert client.get("/auth/me").status_code == 200


def test_dev_bypass_never_forwards_a_password_to_ensure_admin(session, monkeypatch):
    """The dev bypass calls ``ensure_admin`` for its promote-to-admin side
    effect, not to authenticate -- it must pass no password. ``Settings`` has
    no password field to leak, but ``get_current_user`` could still pass a
    literal string through; if it did, every single dev-bypass request would
    silently overwrite whatever password an operator set on this account
    (e.g. via ``eorm init-admin --password``), because ``server/db.py``'s
    ``get_db`` commits the session. This seeds an account with a known
    password, makes a bypass request, and asserts the original password
    still verifies -- it fails against a version of ``get_current_user``
    that forwards any password to ``ensure_admin``.
    """
    from fastapi.testclient import TestClient
    from sqlalchemy import select

    import server.db as server_db
    from eyened_orm import Creator
    from eyened_orm.utils.db_users import hash_password, verify_password
    from server.config import Settings
    from server.main import app_api
    from server.tests.conftest import _SessionBoundDatabase

    creator = Creator(
        CreatorName="devadmin",
        IsHuman=True,
        IsAdmin=True,
        Inactive=False,
        PasswordHash=hash_password("operator-set-password"),
    )
    session.add(creator)
    session.flush()

    monkeypatch.setattr(server_db, "database", _SessionBoundDatabase(session))
    monkeypatch.setattr(
        # get_current_user moved to server/services/current_user.py (to delete
        # the services -> routes import edge); it reads `settings` from that
        # module's namespace, so this is the target that must be patched.
        "server.services.current_user.settings",
        Settings(
            public_auth_disabled=True,
            admin_username="devadmin",
        ),
    )

    with TestClient(app_api) as client:
        assert client.get("/auth/me").status_code == 200

    reloaded = session.scalars(
        select(Creator).where(Creator.CreatorName == "devadmin")
    ).first()
    assert verify_password("operator-set-password", reloaded.PasswordHash)


def _seed_deactivatable_account(session):
    """A creator with a real password, a project membership, and a patient in it.

    The membership is load-bearing: without it the active control's
    ``GET /patients/{id}`` would 404 for want of reach, and the deactivated
    401 would then be indistinguishable from "this account never had access".
    """
    from eyened_orm.authz.roles import ProjectRole
    from eyened_orm.repositories.project_member_repository import (
        ProjectMemberRepository,
    )
    from eyened_orm.utils.factories import make_patient, make_project

    creator = Creator(
        CreatorName="revoked",
        PasswordHash=hash_password("pw0"),
        IsHuman=True,
        Inactive=False,
    )
    session.add(creator)
    session.flush()
    project = make_project(session, "revoked-P")
    patient = make_patient(session, project, "revoked-pat")
    ProjectMemberRepository(session).upsert(
        creator.CreatorID, project.ProjectID, ProjectRole.grader
    )
    creator_id = creator.CreatorID
    patient_id = patient.PatientID
    session.commit()
    return creator_id, patient_id


def test_a_deactivated_account_cannot_authenticate(
    client_anonymous, session, signed_jwts
):
    """v0.3: "A deactivated user cannot authenticate and holds no access."

    Six lines of the same probe, run twice against the same account -- once
    active, once deactivated -- through the real ``get_current_user`` and
    ``get_access_scope`` (this is why the fixture is ``client_anonymous``: the
    ``client`` fixture overrides both and the probe would prove nothing).

    The active half is not decoration. Every 401 below must mean "deactivated";
    with no positive control a route that is simply broken, or a password that
    never verified, produces exactly the same six 401s.

    ``GET /auth/me`` is pinned at 200 in *both* halves on purpose. It is
    decided entirely by the signature on an already-issued access token --
    ``get_current_user`` makes no database read on the header path -- so the
    fix to ``AuthService.authenticate``/``/auth/refresh``/``check_oidc_login`` does not and
    should not move it. Pinning it states that residual rather than leaving it
    unmeasured: a deactivated holder of an unexpired token can still read back
    their own username until it expires, and reaches no data with it.
    """
    from server.routes.auth import create_access_token, create_refresh_token

    creator_id, patient_id = _seed_deactivatable_account(session)
    bearer = {"Authorization": f"Bearer {create_access_token(creator_id, 'revoked')}"}
    client_anonymous.cookies.set("refresh_token", create_refresh_token(creator_id))

    # --- active: the probe's positive control -------------------------------
    assert client_anonymous.get(f"/patients/{patient_id}", headers=bearer).status_code == 200
    assert client_anonymous.post(
        "/auth/login", json={"username": "revoked", "password": "pw0"}
    ).status_code == 200
    assert client_anonymous.post(
        "/auth/token", json={"username": "revoked", "password": "pw0"}
    ).status_code == 200
    assert client_anonymous.get("/auth/me", headers=bearer).status_code == 200
    assert client_anonymous.post(
        "/auth/change-password",
        json={"old_password": "pw0", "new_password": "pw1"},
        headers=bearer,
    ).status_code == 200
    assert client_anonymous.post("/auth/refresh").status_code == 200

    session.get(Creator, creator_id).Inactive = True
    session.commit()

    # --- deactivated --------------------------------------------------------
    assert client_anonymous.get(f"/patients/{patient_id}", headers=bearer).status_code == 401
    assert client_anonymous.post(
        "/auth/login", json={"username": "revoked", "password": "pw1"}
    ).status_code == 401
    assert client_anonymous.post(
        "/auth/token", json={"username": "revoked", "password": "pw1"}
    ).status_code == 401
    assert client_anonymous.get("/auth/me", headers=bearer).status_code == 200
    assert client_anonymous.post(
        "/auth/change-password",
        json={"old_password": "pw1", "new_password": "pw2"},
        headers=bearer,
    ).status_code == 401
    assert client_anonymous.post("/auth/refresh").status_code == 401

    # The refusal must not have been a silent success: the password the
    # deactivated call tried to set must not be the one on the row.
    from eyened_orm.utils.db_users import verify_password

    assert verify_password("pw1", session.get(Creator, creator_id).PasswordHash)


def test_a_deactivated_account_cannot_authenticate_through_oidc(session):
    """``check_oidc_login`` resolves an existing account by claim and never
    looked at ``Inactive`` -- the same revocation, a different front door.

    The active control shares the seed and differs only in the flag, so the
    401 means "deactivated" rather than "this identifier does not resolve".
    """
    from fastapi import HTTPException

    from server.routes.auth import check_oidc_login

    active = Creator(
        CreatorName="oidc-active", EmployeeIdentifier="oidc:sub:live", IsHuman=True,
        Inactive=False,
    )
    revoked = Creator(
        CreatorName="oidc-revoked", EmployeeIdentifier="oidc:sub:dead", IsHuman=True,
        Inactive=True,
    )
    session.add_all([active, revoked])
    session.commit()

    assert check_oidc_login({"sub": "live"}, session).CreatorName == "oidc-active"

    with pytest.raises(HTTPException) as exc:
        check_oidc_login({"sub": "dead"}, session)
    assert exc.value.status_code == 401


def test_registering_a_taken_username_is_a_409_not_a_500(client, session):
    """``AuthService.register`` checks ``CreatorRepository.get_by_name`` for a
    taken name and raises ``ConflictError`` directly, rather than letting the
    insert fail; uncaught, a taken name would reach ``main.py``'s blanket
    handler as a 500. An unauthenticated caller could then tell 200 (name free)
    from 500 (name taken) and enumerate every account name on the platform.

    A 409 does not remove the distinction -- a registration endpoint cannot
    hide a collision and still refuse the write -- and the endpoint staying
    unauthenticated is separately an accepted risk. What it removes is the
    server error: the collision is now an answer the route gives on purpose.
    ``check_oidc_login`` answers its own auto-provision collision the same way,
    but by a different path -- it catches ``create_user``'s ``ValueError`` in
    ``routes/auth.py``, where this raises ``ConflictError`` from the service.

    The free-name control is what makes the 409 mean "taken" rather than
    "registration is broken".
    """
    first = client.post(
        "/auth/register", json={"username": "newcomer", "password": "pw"}
    )
    assert first.status_code == 200, first.text

    again = client.post(
        "/auth/register", json={"username": "newcomer", "password": "other"}
    )
    assert again.status_code == 409, again.text
    assert again.json() == {"detail": "An account with this username already exists."}

    # The refusal must not have created a second row under the same name.
    assert session.query(Creator).filter_by(CreatorName="newcomer").count() == 1


def test_the_access_token_no_longer_carries_a_role_claim(signed_jwts):
    """Only one thing in the system is called 'role', and it is not the token."""
    import jwt

    from server.config import settings
    from server.routes.auth import create_access_token

    payload = jwt.decode(
        create_access_token(1, "alice"),
        settings.secret_key_value,
        algorithms=[settings.jwt_algorithm],
    )
    assert "role" not in payload


def _seed_user(session, name, *, password="pw0", is_admin=False):
    """A password account, committed; its id is read before the commit expires it."""
    creator = Creator(
        CreatorName=name,
        PasswordHash=hash_password(password),
        IsHuman=True,
        IsAdmin=is_admin,
    )
    session.add(creator)
    session.flush()
    creator_id = creator.CreatorID
    session.commit()
    return creator_id


def _bearer(creator_id, username):
    """An Authorization header carrying a real access token for this account."""
    return {"Authorization": f"Bearer {create_access_token(creator_id, username)}"}


def test_me_reports_is_admin_for_an_administrator_and_for_everyone_else(
    client_anonymous, session, signed_jwts
):
    """/auth/me's is_admin is true for an administrator and false for a non-administrator."""
    admin_id = _seed_user(session, "an-admin", is_admin=True)
    member_id = _seed_user(session, "a-member")

    as_admin = client_anonymous.get("/auth/me", headers=_bearer(admin_id, "an-admin"))
    as_member = client_anonymous.get("/auth/me", headers=_bearer(member_id, "a-member"))

    assert as_admin.status_code == 200, as_admin.text
    assert as_member.status_code == 200, as_member.text
    # control: both directions at once, so a hard-coded value fails one of them
    assert (as_admin.json()["is_admin"], as_member.json()["is_admin"]) == (True, False)


def _audit_ids(session):
    """Every AuditLog id present now, to diff against after the act."""
    return set(session.scalars(select(AuditLog.AuditLogID)))


def _new_audit_rows(session, before):
    """AuditLog rows written since ``before`` was taken, oldest first."""
    return [
        row
        for row in session.scalars(select(AuditLog).order_by(AuditLog.AuditLogID))
        if row.AuditLogID not in before
    ]


def _decode(token):
    """The claims of a token this process signed."""
    return jwt.decode(
        token, settings.secret_key_value, algorithms=[settings.jwt_algorithm]
    )


def test_me_returns_the_callers_starred_tags_and_no_one_elses(
    client_anonymous, session, signed_jwts
):
    """/auth/me's starred_tags are exactly the caller's stars."""
    alice_id = _seed_user(session, "alice")
    bob_id = _seed_user(session, "bob")
    alice = session.get(Creator, alice_id)
    tag_ids = [
        make_tag(session, name, TagType.Study, alice).TagID for name in ("t1", "t2", "t3")
    ]
    session.add_all(
        [
            CreatorTagLink(CreatorID=alice_id, TagID=tag_ids[0]),
            CreatorTagLink(CreatorID=alice_id, TagID=tag_ids[2]),
            # control: another user's star, which a read missing its filter would return
            CreatorTagLink(CreatorID=bob_id, TagID=tag_ids[1]),
        ]
    )
    session.commit()

    response = client_anonymous.get("/auth/me", headers=_bearer(alice_id, "alice"))

    assert response.status_code == 200, response.text
    assert sorted(response.json()["starred_tags"]) == sorted([tag_ids[0], tag_ids[2]])


def test_unknown_deactivated_and_wrong_password_logins_get_one_answer(
    client_anonymous, session, signed_jwts
):
    """An unknown user, a deactivated account and a wrong password are indistinguishable 401s."""
    _seed_user(session, "active")
    revoked_id = _seed_user(session, "revoked")
    session.get(Creator, revoked_id).Inactive = True
    session.commit()

    def login(username, password):
        response = client_anonymous.post(
            "/auth/login", json={"username": username, "password": password}
        )
        return response.status_code, response.json()

    # control: the right password succeeds, so a 401 below is a refusal, not a broken login
    assert login("active", "pw0")[0] == 200
    refused = (401, {"detail": "Invalid credentials"})
    assert login("nobody", "pw0") == refused
    assert login("revoked", "pw0") == refused
    assert login("active", "wrong") == refused


def test_token_returns_the_user_and_a_token_minted_for_them(
    client_anonymous, session, signed_jwts
):
    """/auth/token returns the authenticated user and an access token minted for them."""
    creator_id = _seed_user(session, "token-user")

    response = client_anonymous.post(
        "/auth/token", json={"username": "token-user", "password": "pw0"}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["user"]["id"], body["user"]["username"]) == (creator_id, "token-user")
    # control: the token's claims name this user, so a token for anyone else fails
    claims = _decode(body["access_token"])
    assert (claims["type"], claims["sub"]) == ("access", str(creator_id))


def test_change_password_writes_one_audit_row_attributed_to_the_caller(
    client_anonymous, session, signed_jwts
):
    """A password change adds exactly one Creator UPDATE row naming the caller as actor."""
    creator_id = _seed_user(session, "changer", password="old")
    before = _audit_ids(session)

    response = client_anonymous.post(
        "/auth/change-password",
        json={"old_password": "old", "new_password": "new"},
        headers=_bearer(creator_id, "changer"),
    )

    assert response.status_code == 200, response.text
    # control: only rows written by the act are counted, so a pre-existing row cannot satisfy this
    [row] = _new_audit_rows(session, before)
    assert (row.Action, row.Entity, row.EntityID) == ("UPDATE", "Creator", str(creator_id))
    assert (row.ActorID, row.TrustedPath) == (creator_id, None)
    assert row.Changes == {"password_hash": "updated"}


def test_register_writes_one_audit_row_on_the_auth_register_trusted_path(
    client_anonymous, session
):
    """Registration adds exactly one Creator INSERT row attributed to TrustedPath auth:register."""
    before = _audit_ids(session)

    response = client_anonymous.post(
        "/auth/register", json={"username": "newcomer", "password": "pw"}
    )

    assert response.status_code == 200, response.text
    # control: only rows written by the act are counted, so a pre-existing row cannot satisfy this
    [row] = _new_audit_rows(session, before)
    assert (row.Action, row.Entity, row.EntityID) == (
        "INSERT",
        "Creator",
        str(response.json()["id"]),
    )
    assert (row.ActorID, row.TrustedPath) == (None, "auth:register")
    assert row.Changes == {"username": "newcomer", "is_human": True}


def test_registering_then_authenticating_with_the_same_password_succeeds(
    client_anonymous, signed_jwts
):
    """A password set by /auth/register authenticates through /auth/token."""
    register = client_anonymous.post(
        "/auth/register", json={"username": "fresh-account", "password": "pw0"}
    )
    assert register.status_code == 200, register.text

    right = client_anonymous.post(
        "/auth/token", json={"username": "fresh-account", "password": "pw0"}
    )
    assert right.status_code == 200, right.text

    # control: a wrong password must still be refused, so a register that
    # stores an unusable hash -- or a verify that accepts anything -- cannot
    # satisfy the assertion above
    wrong = client_anonymous.post(
        "/auth/token", json={"username": "fresh-account", "password": "not-pw0"}
    )
    assert wrong.status_code == 401, wrong.text


@pytest.mark.parametrize(
    "claims, detail",
    [
        ({"type": "access", "sub": "1"}, "Invalid token type"),
        ({"type": "refresh", "sub": "not-an-id"}, "Invalid refresh token"),
    ],
    ids=["access-token-as-refresh", "non-numeric-subject"],
)
def test_refresh_rejects_a_well_signed_token_it_cannot_use(
    client_anonymous, claims, detail, signed_jwts
):
    """A validly signed refresh cookie with the wrong type or a non-numeric subject is a 401."""
    token = jwt.encode(
        {**claims, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        settings.secret_key_value,
        algorithm=settings.jwt_algorithm,
    )
    client_anonymous.cookies.set(settings.refresh_cookie_name, token)

    response = client_anonymous.post("/auth/refresh")

    assert response.status_code == 401
    # control: each branch has its own detail, so reaching a different 401 fails
    assert response.json() == {"detail": detail}


def test_oidc_authenticate_logs_in_a_linked_account(
    client_anonymous, session, signed_jwts, monkeypatch
):
    """A validated OIDC code for a linked account returns that account, with its starred tags."""
    import server.routes.auth as auth

    creator_id = _seed_user(session, "oidc-user")
    creator = session.get(Creator, creator_id)
    creator.EmployeeIdentifier = "oidc:sub:abc"
    tag_id = make_tag(session, "oidc-star", TagType.Study, creator).TagID
    session.add(CreatorTagLink(CreatorID=creator_id, TagID=tag_id))
    session.commit()

    class _TokenEndpointClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def post(self, url, data):
            return SimpleNamespace(is_success=True, json=lambda: {"id_token": "stub"})

    async def _validated_claims(id_token, nonce_hash):
        return {"sub": "abc"}

    monkeypatch.setattr(
        auth, "_oidc_metadata", lambda: SimpleNamespace(token_endpoint="https://idp/token")
    )
    monkeypatch.setattr(auth.httpxyz, "AsyncClient", _TokenEndpointClient)
    monkeypatch.setattr(auth, "validate_id_token", _validated_claims)

    csrf_token, csrf_hash = generate_secure_token(settings.secret_key_value)
    client_anonymous.cookies.set("oidc_csrf_token", csrf_token)
    client_anonymous.cookies.set("oidc_nonce", "nonce-hash")
    state = quote(json.dumps({"next": "", "csrf": csrf_hash}))

    response = client_anonymous.post(
        "/auth/oidc/authenticate", json={"code": "the-code", "state": state}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["id"], body["username"]) == (creator_id, "oidc-user")
    # control: a star only the starred-tags read can supply, so a response built without it fails
    assert body["starred_tags"] == [tag_id]
