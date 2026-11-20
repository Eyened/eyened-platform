"""The server log of an OIDC login holds no identity data.

Each path in ``PATHS`` drives ``/auth/oidc/authenticate`` against a fake
provider that signs a real RS256 ID token, and the captured log must hold none
of the test's claim values, expected values, usernames or identifiers. Add a
new OIDC path as one more ``OidcPath`` row.
"""

import json
import logging
from dataclasses import dataclass, field
from types import SimpleNamespace
from urllib.parse import quote

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from eyened_orm import Creator

from server.config import settings
from server.routes.auth import generate_secure_token

CLIENT_ID = "eyened-test-client"
SUB = "sub-7f3a9c41"
EMAIL = "jdoe.leak@example.org"
USERNAME = "jdoe-leak"
NAME = "Jane Leakdoe"
HOME_ORG = "leak-university.example"
EXPECTED_HOME_ORG = "allowed-university.example"

# Synthetic identity data; none of it may reach the log.
SECRETS = [SUB, EMAIL, USERNAME, NAME, HOME_ORG, EXPECTED_HOME_ORG]
ALL_CLAIMS = {
    "sub": SUB,
    "email": EMAIL,
    "preferred_username": USERNAME,
    "name": NAME,
    "schac_home_organization": HOME_ORG,
}


@dataclass(frozen=True)
class OidcPath:
    id: str
    status: int
    detail: str | None = None  # the refusal's detail, so each path reaches its own branch
    claims: dict = field(default_factory=lambda: dict(ALL_CLAIMS))
    account: dict | None = None  # Creator fields seeded before the login
    oidc_settings: dict = field(default_factory=dict)
    # The Account row after the login, as (CreatorName, EmployeeIdentifier).
    row_after: tuple | None = None


PATHS = [
    OidcPath(
        id="logged-in",
        status=200,
        account={"EmployeeIdentifier": f"oidc:sub:{SUB}"},
        row_after=(USERNAME, f"oidc:sub:{SUB}"),
    ),
    OidcPath(
        id="re-pinned",
        status=200,
        account={"EmployeeIdentifier": f"oidc:email:{EMAIL}"},
        row_after=(USERNAME, f"oidc:sub:{SUB}"),
    ),
    OidcPath(
        id="created",
        status=200,
        oidc_settings={"create_new_accounts": True},
        row_after=(USERNAME, f"oidc:sub:{SUB}"),
    ),
    OidcPath(
        id="deactivated",
        status=401,
        detail="OIDC account not authorized",
        account={"EmployeeIdentifier": f"oidc:sub:{SUB}", "Inactive": True},
        row_after=(USERNAME, f"oidc:sub:{SUB}"),
    ),
    OidcPath(id="refused", status=401, detail="OIDC account not authorized"),
    OidcPath(
        id="claim-check-failed",
        status=401,
        detail="ID token validation failed",
        oidc_settings={
            "additional_token_validations": f"schac_home_organization={EXPECTED_HOME_ORG}"
        },
    ),
]


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _FakeProvider:
    """Answers the server's token and JWKS requests with a signed ID token."""

    def __init__(self, signing_key, claims):
        self._key = signing_key
        self._claims = claims

    def __call__(self):  # stands in for httpxyz.AsyncClient()
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def post(self, url, data):
        id_token = jwt.encode(
            {**self._claims, "aud": CLIENT_ID},
            self._key,
            algorithm="RS256",
            headers={"kid": "k1"},
        )
        return SimpleNamespace(is_success=True, json=lambda: {"id_token": id_token})

    async def get(self, url):
        jwk = {**RSAAlgorithm.to_jwk(self._key.public_key(), as_dict=True), "kid": "k1"}
        return SimpleNamespace(is_success=True, json=lambda: {"keys": [jwk]})


@pytest.mark.parametrize("path", PATHS, ids=lambda p: p.id)
def test_oidc_login_logs_no_identity_data(
    path, client_anonymous, session, signed_jwts, signing_key, monkeypatch, caplog
):
    import server.routes.auth as auth

    if path.account is not None:
        session.add(Creator(CreatorName=USERNAME, IsHuman=True, **path.account))
        session.commit()

    # Settings is frozen: replace the module's object rather than patch a field.
    oidc = settings.oidc.model_copy(update={"client_id": CLIENT_ID, **path.oidc_settings})
    monkeypatch.setattr(auth, "settings", settings.model_copy(update={"oidc": oidc}))
    monkeypatch.setattr(
        auth,
        "_oidc_metadata",
        lambda: SimpleNamespace(token_endpoint="https://idp/token", jwks_uri="https://idp/jwks"),
    )
    nonce, nonce_hash = generate_secure_token(settings.secret_key_value)
    claims = {**path.claims, "nonce": nonce}
    monkeypatch.setattr(auth.httpxyz, "AsyncClient", _FakeProvider(signing_key, claims))

    csrf_token, csrf_hash = generate_secure_token(settings.secret_key_value)
    client_anonymous.cookies.set("oidc_csrf_token", csrf_token)
    client_anonymous.cookies.set("oidc_nonce", nonce_hash)
    state = quote(json.dumps({"next": "", "csrf": csrf_hash}))

    caplog.set_level(logging.DEBUG)
    response = client_anonymous.post(
        "/auth/oidc/authenticate", json={"code": "the-code", "state": state}
    )

    assert response.status_code == path.status, response.text
    # control: the path logged something, and the values did reach the server
    assert any(r.name == "server.routes.auth" for r in caplog.records)
    if path.status == 200:
        assert response.json()["username"] == USERNAME
    else:
        assert response.json() == {"detail": path.detail}
    if path.row_after is not None:
        row = session.query(Creator).filter_by(CreatorName=USERNAME).one()
        assert (row.CreatorName, row.EmployeeIdentifier) == path.row_after

    # ASSUMPTION: the eyened.audit stream mirrors the audit row, which keeps the
    # new account's name and identifier; it is the audit trail, not the app log.
    log = "\n".join(r.getMessage() for r in caplog.records if r.name != "eyened.audit")
    leaked = [value for value in SECRETS if value in log]
    assert leaked == []
