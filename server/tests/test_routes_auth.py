from hashlib import pbkdf2_hmac
from types import SimpleNamespace

import pytest

from eyened_orm import AuditLog, Creator
from eyened_orm.utils.db_users import hash_password

from server.routes.auth import generate_secure_token, validate_secure_token


def test_generate_verify_secure_token():
    """Test that we can generate and validate a token"""
    secret_key = "some-secret-key"
    token, token_hash = generate_secure_token(secret_key)
    assert token is not None
    assert token_hash is not None
    assert token != token_hash

    assert validate_secure_token(token, token_hash, secret_key)


def _legacy_hash(password: str) -> bytes:
    """Reproduce check_login's legacy pbkdf2 hash for seeding a pre-migration Creator."""
    return pbkdf2_hmac("sha256", password.encode(), "6f4b661212".encode(), 10000)


def test_login_with_legacy_password_migrates_hash_and_audits_once(
    client, session, signed_jwts
):
    """Legacy-hash login migrates PasswordHash/clears Password and records exactly
    one AuditLog UPDATE row for Creator -- committed only at the request boundary
    (get_db), not mid-handler inside check_login."""
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
    # would mean check_login is still committing mid-handler.
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
    # The bypass caches the bootstrapped account's id at module scope to avoid
    # re-running ensure_admin per request. That models one id surviving for
    # the life of a process; this test's `session` fixture is a fresh
    # database standing in for a fresh process, so the leftover id from
    # another test must not leak in here.
    monkeypatch.setattr(
        "server.services.current_user._BYPASS_CREATOR_ID", None, raising=False
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
    # See the identical comment in
    # test_dev_bypass_promotes_the_configured_account_to_administrator: the
    # bypass's process-scoped id cache must not survive into this test's own
    # fresh database.
    monkeypatch.setattr(
        "server.services.current_user._BYPASS_CREATOR_ID", None, raising=False
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
    # See the identical comment in
    # test_dev_bypass_promotes_the_configured_account_to_administrator: the
    # bypass's process-scoped id cache must not survive into this test's own
    # fresh database. Without this reset the assertion below passes only by
    # coincidence, because the seeded creator happens to land on the same id
    # a prior test cached.
    monkeypatch.setattr(
        "server.services.current_user._BYPASS_CREATOR_ID", None, raising=False
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
    fix to ``check_login``/``/auth/refresh``/``check_oidc_login`` does not and
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
    """``create_user`` raises a bare ``ValueError`` for a taken name, which the
    route did not catch, so ``main.py``'s blanket handler turned it into a 500.
    An unauthenticated caller could then tell 200 (name free) from 500 (name
    taken) and enumerate every account name on the platform.

    A 409 does not remove the distinction -- a registration endpoint cannot
    hide a collision and still refuse the write -- and the endpoint staying
    unauthenticated is separately an accepted risk. What it removes is the
    server error: the collision is now an answer the route gives on purpose,
    matching ``check_oidc_login``'s handling of the same ``ValueError`` in
    this same module.

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
