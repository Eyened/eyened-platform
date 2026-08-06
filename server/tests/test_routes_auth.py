from hashlib import pbkdf2_hmac
from types import SimpleNamespace

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
        "server.routes.auth.settings",
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
        "server.routes.auth.settings",
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
        "server.routes.auth.settings",
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
