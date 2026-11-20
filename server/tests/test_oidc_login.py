"""SSO login through /auth/oidc/authorize and /auth/oidc/authenticate.

Each test logs in against the SURFconext-shaped fake provider (the
``oidc_provider`` fixture), which puts only ``sub`` in the ID token and the
rest on userinfo.
"""

import pytest
from sqlalchemy import select

from eyened_orm import AuditLog, Creator, CreatorTagLink
from eyened_orm.tag import TagType
from eyened_orm.utils.factories import make_tag

SUB = "sub-1f2e3d"
EMAIL = "j.doe@example.org"


def _seed(session, name, identifier, **fields):
    creator = Creator(CreatorName=name, EmployeeIdentifier=identifier, IsHuman=True, **fields)
    session.add(creator)
    session.commit()
    return creator


def test_an_account_linked_by_sub_logs_in(client_anonymous, session, oidc_provider):
    """A linked account gets its own user response, with its starred tags."""
    creator = _seed(session, "oidc-user", f"oidc:sub:{SUB}")
    tag_id = make_tag(session, "oidc-star", TagType.Study, creator).TagID
    session.add(CreatorTagLink(CreatorID=creator.CreatorID, TagID=tag_id))
    session.commit()
    oidc_provider.id_token_claims = {"sub": SUB}
    oidc_provider.userinfo = {"sub": SUB, "email": EMAIL}

    response = oidc_provider.login(client_anonymous)

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["id"], body["username"]) == (creator.CreatorID, "oidc-user")
    # control: a star only the starred-tags read can supply
    assert body["starred_tags"] == [tag_id]


def test_an_id_token_from_another_issuer_is_refused(client_anonymous, session, oidc_provider):
    """OIDC Core 3.1.3.7: ``iss`` must exactly match the provider's issuer."""
    _seed(session, "oidc-user", f"oidc:sub:{SUB}")
    oidc_provider.id_token_claims = {"sub": SUB}
    oidc_provider.userinfo = {"sub": SUB}
    oidc_provider.token_issuer = "https://other-provider.example"

    response = oidc_provider.login(client_anonymous)

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid ID token"}
    # userinfo comes after ID-token validation, so a refused token never reaches it
    assert "https://connect.surfconext.nl/userinfo" not in oidc_provider.requested


def test_a_discovery_issuer_that_differs_from_its_url_turns_sso_off(
    client_anonymous, oidc_provider
):
    """OIDC Discovery 4.3: the issuer must be identical to the discovery URL
    minus ``/.well-known/openid-configuration``. The login page then offers no SSO."""
    assert client_anonymous.get("/auth/options").json()["oidc_enabled"] is True  # control

    from server.config import get_oidc_metadata

    get_oidc_metadata.cache_clear()
    oidc_provider.issuer = "https://connect.surfconext.nl/"

    assert client_anonymous.get("/auth/options").json()["oidc_enabled"] is False


def test_the_account_lookup_sees_the_userinfo_email(client_anonymous, session, oidc_provider):
    """SURFconext sends email only on userinfo; an account linked by email still logs in."""
    creator = _seed(session, "linked-by-email", f"oidc:email:{EMAIL}")
    oidc_provider.id_token_claims = {"sub": SUB}
    oidc_provider.userinfo = {"sub": SUB, "email": EMAIL}

    response = oidc_provider.login(client_anonymous)

    assert response.status_code == 200, response.text
    assert response.json()["id"] == creator.CreatorID


def test_userinfo_with_another_sub_is_refused(client_anonymous, session, oidc_provider):
    """OIDC Core 5.3.2: the userinfo ``sub`` must exactly match the ID token's."""
    _seed(session, "oidc-user", f"oidc:sub:{SUB}")
    oidc_provider.id_token_claims = {"sub": SUB}
    oidc_provider.userinfo = {"sub": "another-sub", "email": EMAIL}

    response = oidc_provider.login(client_anonymous)

    assert response.status_code == 401
    assert response.json() == {"detail": "Userinfo validation failed"}


def test_a_failed_userinfo_call_fails_the_login(client_anonymous, session, oidc_provider):
    _seed(session, "oidc-user", f"oidc:sub:{SUB}")
    oidc_provider.id_token_claims = {"sub": SUB}
    oidc_provider.userinfo_status = 503

    response = oidc_provider.login(client_anonymous)

    assert response.status_code == 500
    assert response.json() == {"detail": "Userinfo request failed"}


def test_an_id_token_claim_wins_over_the_same_userinfo_claim(
    client_anonymous, session, oidc_provider
):
    """Userinfo claims merge under the ID-token claims."""
    creator = _seed(session, "linked-by-email", f"oidc:email:{EMAIL}")
    oidc_provider.id_token_claims = {"sub": SUB, "email": EMAIL}
    oidc_provider.userinfo = {"sub": SUB, "email": "someone.else@example.org"}

    response = oidc_provider.login(client_anonymous)

    assert response.status_code == 200, response.text
    assert response.json()["id"] == creator.CreatorID


def test_a_deactivated_account_is_refused(client_anonymous, session, oidc_provider):
    """Same revocation as the password path, a different front door."""
    _seed(session, "oidc-active", "oidc:sub:live")
    _seed(session, "oidc-revoked", "oidc:sub:dead", Inactive=True)

    # control: the same seed without the flag logs in
    oidc_provider.id_token_claims = oidc_provider.userinfo = {"sub": "live"}
    assert oidc_provider.login(client_anonymous).json()["username"] == "oidc-active"

    oidc_provider.id_token_claims = oidc_provider.userinfo = {"sub": "dead"}
    response = oidc_provider.login(client_anonymous)

    assert response.status_code == 401
    assert response.json() == {"detail": "OIDC account not authorized"}


def test_a_first_login_records_a_provisioning_audit_row(
    client_anonymous, session, oidc_provider, oidc_settings
):
    """Auto-provisioning attributes the new account to its own trusted path."""
    oidc_settings(create_new_accounts=True)
    oidc_provider.id_token_claims = {"sub": SUB}
    oidc_provider.userinfo = {"sub": SUB, "email": EMAIL, "preferred_username": "new-oidc-user"}

    response = oidc_provider.login(client_anonymous)

    assert response.status_code == 200, response.text
    [row] = session.scalars(select(AuditLog).where(AuditLog.Entity == "Creator")).all()
    assert (row.Action, row.ActorID, row.TrustedPath, row.EntityID) == (
        "INSERT",
        None,
        "auth:oidc-provision",
        str(response.json()["id"]),
    )


def test_the_claim_check_sees_a_userinfo_claim(
    client_anonymous, session, oidc_provider, oidc_settings
):
    """SURFconext sends ``schac_home_organization`` only on userinfo."""
    _seed(session, "oidc-user", f"oidc:sub:{SUB}")
    oidc_settings(additional_token_validations="schac_home_organization=erasmusmc.nl")
    oidc_provider.id_token_claims = {"sub": SUB}

    # control: without the claim the check refuses
    oidc_provider.userinfo = {"sub": SUB}
    response = oidc_provider.login(client_anonymous)
    assert response.status_code == 401
    assert response.json() == {"detail": "ID token validation failed"}

    oidc_provider.userinfo = {"sub": SUB, "schac_home_organization": "erasmusmc.nl"}
    response = oidc_provider.login(client_anonymous)

    assert response.status_code == 200, response.text


def test_the_claim_check_passes_a_list_claim_that_holds_the_value(
    client_anonymous, session, oidc_provider, oidc_settings
):
    """A multi-valued claim passes when one of its values is the expected one."""
    _seed(session, "oidc-user", f"oidc:sub:{SUB}")
    oidc_settings(additional_token_validations="eduperson_affiliation=employee")
    oidc_provider.id_token_claims = {"sub": SUB}

    # control: a list without the value is refused
    oidc_provider.userinfo = {"sub": SUB, "eduperson_affiliation": ["member", "student"]}
    response = oidc_provider.login(client_anonymous)
    assert response.status_code == 401
    assert response.json() == {"detail": "ID token validation failed"}

    oidc_provider.userinfo = {"sub": SUB, "eduperson_affiliation": ["member", "employee"]}
    response = oidc_provider.login(client_anonymous)

    assert response.status_code == 200, response.text


@pytest.mark.parametrize(
    "allowed, home_org, status",
    [
        ("", "other-university.example", 200),
        ("erasmusmc.nl,uu.nl", "uu.nl", 200),
        ("erasmusmc.nl,uu.nl", "other-university.example", 403),
    ],
    ids=["empty-admits-all", "listed-admitted", "unlisted-refused"],
)
def test_the_institution_allow_list(
    allowed, home_org, status, client_anonymous, session, oidc_provider, oidc_settings
):
    _seed(session, "oidc-user", f"oidc:sub:{SUB}")
    oidc_settings(allowed_home_organizations=allowed)
    oidc_provider.id_token_claims = {"sub": SUB}
    oidc_provider.userinfo = {"sub": SUB, "schac_home_organization": home_org}

    response = oidc_provider.login(client_anonymous)

    assert response.status_code == status, response.text
    if status == 403:
        assert response.json() == {
            "detail": "Your institution is not allowed to log in to EyeNED."
        }
