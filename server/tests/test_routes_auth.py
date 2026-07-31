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


def _dev_bypass_settings(monkeypatch, **overrides):
    """Swap the module-level `settings` for a fresh instance.

    Settings is frozen=True, so assigning to a field raises ValidationError;
    rebinding the module attribute is the way to vary config in a test. auth.py
    holds `settings` as a module global (`from ..config import ... settings`), so
    this is the name its handlers actually read.
    """
    import server.routes.auth as auth_module
    from server.config import Settings

    monkeypatch.setattr(
        auth_module,
        "settings",
        Settings(public_auth_disabled=True, **overrides),
    )


@pytest.mark.anyio
async def test_dev_bypass_resolves_a_real_system_admin(session, monkeypatch):
    """Local dev must work with no extra seeding -- and the account the bypass
    resolves is only a superuser if its Role is system_admin."""
    from eyened_orm import Creator, is_system_admin
    from server.routes.auth import get_current_user

    _dev_bypass_settings(monkeypatch, admin_username="dev-admin")

    current = await get_current_user(session=session)

    assert current.username == "dev-admin"
    admin = session.query(Creator).filter_by(CreatorName="dev-admin").one()
    assert is_system_admin(admin) is True
    assert admin.Inactive is False
    assert current.id == admin.CreatorID


@pytest.mark.anyio
async def test_dev_bypass_promotes_an_existing_non_admin(session, monkeypatch):
    """The pre-existing bug: the old branch auto-created (or found) a Role=NULL
    account, which after P4 would see no data at all."""
    from eyened_orm import is_system_admin
    from eyened_orm.utils.db_users import create_user
    from server.routes.auth import get_current_user

    existing = create_user(session, "dev-admin", "pw")
    assert existing.Role is None
    session.commit()

    _dev_bypass_settings(monkeypatch, admin_username="dev-admin")
    await get_current_user(session=session)

    assert is_system_admin(existing) is True


@pytest.mark.anyio
async def test_dev_bypass_creates_no_duplicate_on_a_second_request(
    session, monkeypatch
):
    from eyened_orm import Creator
    from server.routes.auth import get_current_user

    _dev_bypass_settings(monkeypatch, admin_username="dev-admin")

    await get_current_user(session=session)
    await get_current_user(session=session)

    assert session.query(Creator).filter_by(CreatorName="dev-admin").count() == 1


@pytest.mark.anyio
async def test_dev_bypass_works_with_no_admin_password_configured(
    session, monkeypatch
):
    """admin_password defaults to None, so an unconditional .get_secret_value()
    would AttributeError -- reintroducing the very failure this task removes. A
    None password means password login is disabled, which is correct for a bypass
    that never posts credentials."""
    import server.routes.auth as auth_module
    from eyened_orm import Creator
    from server.routes.auth import get_current_user

    _dev_bypass_settings(monkeypatch, admin_username="dev-admin")
    assert auth_module.settings.admin_password is None  # the default this guards

    await get_current_user(session=session)

    admin = session.query(Creator).filter_by(CreatorName="dev-admin").one()
    assert admin.PasswordHash is not None  # disabled, not absent


def test_register_never_grants_a_system_role(client, session):
    """POST /auth/register is unauthenticated and takes no role field -- pins
    that the resulting Creator lands at Role=None, so a future change that
    starts passing a role through create_user at this call site would fail
    this test rather than slip by as a silent escalation path."""
    response = client.post(
        "/auth/register",
        json={"username": "self-registered", "password": "some-password"},
    )
    assert response.status_code == 200, response.text

    created = session.query(Creator).filter_by(CreatorName="self-registered").one()
    assert created.Role is None


@pytest.mark.anyio
async def test_dev_bypass_does_not_reactivate_a_deactivated_admin(
    session, monkeypatch
):
    """The bypass must not undo a deliberate deactivation. It calls ensure_admin
    on every request; unconditional reactivation would make deactivating a
    compromised admin a permanent no-op on any host with the flag left on --
    and the reactivation would outlive the flag being turned back off."""
    from eyened_orm import Creator, SystemRole
    from eyened_orm.utils.db_users import create_user
    from server.routes.auth import get_current_user

    existing = create_user(
        session, "dev-admin", "pw", role=SystemRole.system_admin
    )
    existing.Inactive = True
    session.commit()

    _dev_bypass_settings(monkeypatch, admin_username="dev-admin")
    await get_current_user(session=session)

    admin = session.query(Creator).filter_by(CreatorName="dev-admin").one()
    assert admin.Inactive is True


@pytest.mark.anyio
async def test_dev_bypass_uses_a_configured_admin_password(session, monkeypatch):
    """The configured-password branch: admin_password is a SecretStr, so it must
    be unwrapped before it reaches hash_password. Passing the wrapper through
    raises TypeError -- every request 500s -- and all the other bypass tests
    leave admin_password=None, so nothing else exercises this line."""
    from eyened_orm import Creator
    from eyened_orm.utils.db_users import verify_password
    from server.routes.auth import get_current_user

    _dev_bypass_settings(
        monkeypatch, admin_username="dev-admin", admin_password="s3cret"
    )

    await get_current_user(session=session)

    admin = session.query(Creator).filter_by(CreatorName="dev-admin").one()
    assert verify_password("s3cret", admin.PasswordHash) is True


@pytest.mark.anyio
async def test_dev_bypass_logs_the_grant_of_system_admin(
    session, monkeypatch, caplog
):
    """The most privileged write in the codebase must leave a trace. Under the
    dev bypass there is no operator watching a terminal -- unlike `eorm
    init-admin`, which prints -- so this log line is the only record that a
    superuser grant happened, to whom, and when."""
    import logging

    from eyened_orm.utils.db_users import create_user
    from server.routes.auth import get_current_user

    create_user(session, "dev-admin", "pw")
    session.commit()
    _dev_bypass_settings(monkeypatch, admin_username="dev-admin")

    with caplog.at_level(logging.WARNING, logger="server.routes.auth"):
        await get_current_user(session=session)

    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "server.routes.auth"
    ]
    # "'dev-admin'" quoted, matching the template: an unquoted "admin" would
    # also match the literal "system_admin" in the message and prove nothing.
    assert any(
        "promoted" in message and "'dev-admin'" in message for message in messages
    )


@pytest.mark.anyio
async def test_dev_bypass_logs_nothing_when_the_admin_is_unchanged(
    session, monkeypatch, caplog
):
    """A no-op re-run must stay quiet, or the signal is worthless -- and the
    bypass re-runs on every single request."""
    import logging

    from server.routes.auth import get_current_user

    _dev_bypass_settings(monkeypatch, admin_username="dev-admin")
    await get_current_user(session=session)  # first request: creates, and logs
    # caplog accumulates for the whole test, not just inside at_level() -- so
    # without this the create above lands in the assertion below.
    caplog.clear()

    with caplog.at_level(logging.WARNING, logger="server.routes.auth"):
        await get_current_user(session=session)  # second request: unchanged

    assert [
        record for record in caplog.records if record.name == "server.routes.auth"
    ] == []
