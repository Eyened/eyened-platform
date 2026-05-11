import pytest

from server.config import OIDCSettings, Settings

OPENID_CONFIG = {
    "authorization_endpoint": "https://example.com/api/authorize",
    "token_endpoint": "https://example.com/api/token",
    "userinfo_endpoint": "https://example.com/api/userinfo",
    "issuer": "https://example.com/api",
}
"""Mock OpenID Connect configuration data as returned from a configuration URL"""


def test_oidc_settings_from_env(monkeypatch):
    monkeypatch.setenv("EYENED_OIDC_CLIENT_ID", 'client_id')
    monkeypatch.setenv("EYENED_OIDC_CLIENT_SECRET", 'client_secret')
    monkeypatch.setenv("EYENED_API_AUTH_OIDC_ENABLED", "true")

    settings = Settings()
    assert settings.oidc.client_id == "client_id"
    assert settings.oidc.client_secret == "client_secret"
    assert settings.auth_oidc_enabled is True


@pytest.mark.asyncio
async def test_oidc_settings_valid(httpx_mock):
    httpx_mock.add_response(json=OPENID_CONFIG)

    oidc_settings = OIDCSettings(client_id="client_id", client_secret="client_secret", connect_url="https://example.com/api/.well-known/openid-configuration")
    assert await oidc_settings.get_authorize_url() == "https://example.com/api/authorize"


@pytest.mark.asyncio
async def test_oidc_connect_url_returns_invalid_status(httpx_mock):
    httpx_mock.add_response(status_code=401)

    oidc_settings = OIDCSettings(connect_url="https://example.com/api/.well-known/openid-configuration")
    with pytest.raises(ValueError, match="HTTP status code returned: 401"):
        await oidc_settings.get_authorize_url()


@pytest.mark.asyncio
async def test_oidc_connect_url_returns_invalid_data(httpx_mock):
    httpx_mock.add_response(text="Text response indicating this is not JSON data")

    oidc_settings = OIDCSettings(connect_url="https://example.com/api/.well-known/openid-configuration")
    with pytest.raises(ValueError, match="OIDC connect URL returned unparsable JSON data"):
        await oidc_settings.get_authorize_url()


@pytest.mark.asyncio
async def test_oidc_missing_authorize_url(httpx_mock):
    response_data = OPENID_CONFIG.copy()
    del response_data["authorization_endpoint"]
    httpx_mock.add_response(json=response_data)

    oidc_settings = OIDCSettings(connect_url="https://example.com/api/.well-known/openid-configuration")
    with pytest.raises(ValueError, match="OIDC connect URL response is missing required key 'authorization_endpoint'"):
        await oidc_settings.get_authorize_url()
