import pytest

import server.config as config
from server.config import OIDCSettings, Settings, get_oidc_metadata, validate_oidc_metadata

OPENID_CONFIG = {
    "authorization_endpoint": "https://example.com/api/authorize",
    "jwks_uri": "https://example.com/api/jwks",
    "token_endpoint": "https://example.com/api/token",
    "userinfo_endpoint": "https://example.com/api/userinfo",
    "issuer": "https://example.com/api",
}
"""Mock OpenID Connect configuration data as returned from a configuration URL"""

METADATA_URL = "https://example.com/api/.well-known/openid-configuration"


class FakeResponse:
    def __init__(self, *, status_code=200, json_data=None, json_error=None):
        self.status_code = status_code
        self._json_data = json_data
        self._json_error = json_error

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._json_data


@pytest.fixture(autouse=True)
def clear_oidc_metadata_cache():
    get_oidc_metadata.cache_clear()
    yield
    get_oidc_metadata.cache_clear()


@pytest.fixture
def fake_oidc_metadata_client(monkeypatch):
    class FakeClient:
        requested_urls: list[str] = []
        response = FakeResponse(json_data=OPENID_CONFIG)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def get(self, url: str):
            self.requested_urls.append(url)
            return self.response

    monkeypatch.setattr(config.httpxyz, "Client", FakeClient)
    return FakeClient


def test_oidc_settings_from_env(monkeypatch):
    monkeypatch.setenv("EYENED_OIDC_CLIENT_ID", 'client_id')
    monkeypatch.setenv("EYENED_OIDC_CLIENT_SECRET", 'client_secret')
    monkeypatch.setenv("EYENED_API_AUTH_OIDC_ENABLED", "true")

    settings = Settings()
    assert settings.oidc.client_id == "client_id"
    assert settings.oidc.client_secret.get_secret_value() == "client_secret"
    assert settings.auth_oidc_enabled is True


def test_oidc_metadata_is_cached_by_url(fake_oidc_metadata_client):
    metadata = get_oidc_metadata(METADATA_URL)
    assert metadata.authorization_endpoint == "https://example.com/api/authorize"
    assert get_oidc_metadata(METADATA_URL).token_endpoint == "https://example.com/api/token"
    assert fake_oidc_metadata_client.requested_urls == [METADATA_URL]


def test_oidc_metadata_url_returns_invalid_status(fake_oidc_metadata_client):
    fake_oidc_metadata_client.response = FakeResponse(status_code=401)

    with pytest.raises(ValueError, match="HTTP status code returned: 401"):
        get_oidc_metadata(METADATA_URL)


def test_oidc_metadata_url_returns_invalid_data(fake_oidc_metadata_client):
    fake_oidc_metadata_client.response = FakeResponse(json_error=config.JSONDecodeError("invalid json", "", 0))

    with pytest.raises(ValueError, match="OIDC metadata URL returned unparsable JSON data"):
        get_oidc_metadata(METADATA_URL)


def test_valid_oidc_metadata_is_returned_unchanged():
    metadata = validate_oidc_metadata(OPENID_CONFIG)
    assert metadata.authorization_endpoint == "https://example.com/api/authorize"
    assert metadata.token_endpoint == "https://example.com/api/token"
    assert metadata.jwks_uri == "https://example.com/api/jwks"


@pytest.mark.parametrize("metadata_key", ["authorization_endpoint", "jwks_uri", "token_endpoint"])
def test_oidc_missing_required_metadata(metadata_key):
    response_data = OPENID_CONFIG.copy()
    del response_data[metadata_key]

    with pytest.raises(ValueError, match=f"OIDC metadata URL response is missing required key '{metadata_key}'"):
        validate_oidc_metadata(response_data)
