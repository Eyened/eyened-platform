"""The server log of an OIDC login holds no identity data.

Each path in ``PATHS`` logs in against the SURFconext-shaped fake provider
(the ``oidc_provider`` fixture), and the captured log must hold none of the
test's claim values, expected values, usernames or identifiers. Add a new OIDC
path as one more ``OidcPath`` row.
"""

import logging
from dataclasses import dataclass, field

import pytest

from eyened_orm import Creator

SUB = "sub-7f3a9c41"
OTHER_SUB = "sub-0b8e2d17"
EMAIL = "jdoe.leak@example.org"
USERNAME = "jdoe-leak"
NAME = "Jane Leakdoe"
HOME_ORG = "leak-university.example"
EXPECTED_HOME_ORG = "allowed-university.example"

# Synthetic identity data; none of it may reach the log.
SECRETS = [SUB, OTHER_SUB, EMAIL, USERNAME, NAME, HOME_ORG, EXPECTED_HOME_ORG]
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
    id_token_claims: dict = field(default_factory=lambda: {"sub": SUB})
    userinfo: dict = field(default_factory=lambda: dict(ALL_CLAIMS))
    userinfo_status: int = 200
    token_issuer: str | None = None  # None: the provider's own issuer
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
    OidcPath(
        id="institution-not-allowed",
        status=403,
        detail="Your institution is not allowed to log in to EyeNED.",
        account={"EmployeeIdentifier": f"oidc:sub:{SUB}"},
        oidc_settings={"allowed_home_organizations": EXPECTED_HOME_ORG},
    ),
    OidcPath(
        id="wrong-issuer",
        status=401,
        detail="Invalid ID token",
        account={"EmployeeIdentifier": f"oidc:sub:{SUB}"},
        token_issuer="https://other-provider.example",
    ),
    OidcPath(
        id="userinfo-sub-mismatch",
        status=401,
        detail="Userinfo validation failed",
        account={"EmployeeIdentifier": f"oidc:sub:{SUB}"},
        userinfo={**ALL_CLAIMS, "sub": OTHER_SUB},
    ),
    OidcPath(
        id="userinfo-failed",
        status=500,
        detail="Userinfo request failed",
        account={"EmployeeIdentifier": f"oidc:sub:{SUB}"},
        userinfo_status=503,
    ),
]


@pytest.mark.parametrize("path", PATHS, ids=lambda p: p.id)
def test_oidc_login_logs_no_identity_data(
    path, client_anonymous, session, oidc_provider, oidc_settings, caplog
):
    if path.account is not None:
        session.add(Creator(CreatorName=USERNAME, IsHuman=True, **path.account))
        session.commit()
    oidc_settings(**path.oidc_settings)
    oidc_provider.id_token_claims = path.id_token_claims
    oidc_provider.userinfo = path.userinfo
    oidc_provider.userinfo_status = path.userinfo_status
    if path.token_issuer is not None:
        oidc_provider.token_issuer = path.token_issuer

    caplog.set_level(logging.DEBUG)
    response = oidc_provider.login(client_anonymous)

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
