"""A fake OIDC provider shaped like SURFconext, at the server's outgoing HTTP calls.

It answers discovery, JWKS, token and userinfo. The ID token is a real RS256
token holding only ``sub``, ``iss``, ``aud`` and ``nonce``; email, name and
``schac_home_organization`` come from userinfo, as SURFconext sends them.
Tests change its public attributes to shape one login.
"""

from functools import cache
from urllib.parse import parse_qs, urlsplit

import httpxyz
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

ISSUER = "https://connect.surfconext.nl"
DISCOVERY_URL = f"{ISSUER}/.well-known/openid-configuration"
CLIENT_ID = "eyened-test-client"
ACCESS_TOKEN = "fake-access-token"
KID = "fake-key-1"


@cache
def _signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class FakeOidcProvider:
    def __init__(self, sub: str = "fake-sub"):
        # The discovery document's issuer, and the ID token's ``iss``.
        self.issuer = ISSUER
        self.token_issuer = ISSUER
        # Claims beyond sub, iss, aud and nonce in the ID token.
        self.id_token_claims: dict = {"sub": sub}
        self.userinfo: dict = {"sub": sub}
        self.userinfo_status = 200
        # The nonce from the authorization request, as the provider keeps it.
        self.nonce: str | None = None
        self.requested: list[str] = []

    def discovery(self) -> dict:
        return {
            "issuer": self.issuer,
            "authorization_endpoint": f"{ISSUER}/authorize",
            "token_endpoint": f"{ISSUER}/token",
            "jwks_uri": f"{ISSUER}/jwks",
            "userinfo_endpoint": f"{ISSUER}/userinfo",
        }

    def login(self, client, code: str = "the-code"):
        """Drive /auth/oidc/authorize, then /auth/oidc/authenticate, as the browser does."""
        authorize = client.get("/auth/oidc/authorize")
        assert authorize.status_code == 200, authorize.text
        query = parse_qs(urlsplit(authorize.json()["url"]).query)
        self.nonce = query["nonce"][0]
        return client.post(
            "/auth/oidc/authenticate", json={"code": code, "state": query["state"][0]}
        )

    def _id_token(self) -> str:
        claims = {
            **self.id_token_claims,
            "iss": self.token_issuer,
            "aud": CLIENT_ID,
            "nonce": self.nonce,
        }
        return jwt.encode(claims, _signing_key(), algorithm="RS256", headers={"kid": KID})

    def _answer(self, method: str, url: str, headers: dict | None = None) -> httpxyz.Response:
        self.requested.append(url)
        endpoints = self.discovery()
        if (method, url) == ("GET", DISCOVERY_URL):
            return httpxyz.Response(200, json=endpoints)
        if (method, url) == ("GET", endpoints["jwks_uri"]):
            jwk = {**RSAAlgorithm.to_jwk(_signing_key().public_key(), as_dict=True), "kid": KID}
            return httpxyz.Response(200, json={"keys": [jwk]})
        if (method, url) == ("POST", endpoints["token_endpoint"]):
            return httpxyz.Response(
                200,
                json={"access_token": ACCESS_TOKEN, "token_type": "Bearer", "id_token": self._id_token()},
            )
        if (method, url) == ("GET", endpoints["userinfo_endpoint"]):
            if (headers or {}).get("Authorization") != f"Bearer {ACCESS_TOKEN}":
                return httpxyz.Response(401)
            if self.userinfo_status != 200:
                return httpxyz.Response(self.userinfo_status)
            return httpxyz.Response(200, json=self.userinfo)
        raise AssertionError(f"unexpected request to the OIDC provider: {method} {url}")

    def sync_client(self, *args, **kwargs):
        """Stands in for httpxyz.Client()."""
        return _Client(self)

    def async_client(self, *args, **kwargs):
        """Stands in for httpxyz.AsyncClient()."""
        return _AsyncClient(self)


class _Client:
    def __init__(self, provider):
        self._provider = provider

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def get(self, url, headers=None):
        return self._provider._answer("GET", url, headers)


class _AsyncClient:
    def __init__(self, provider):
        self._provider = provider

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def get(self, url, headers=None):
        return self._provider._answer("GET", url, headers)

    async def post(self, url, data=None):
        return self._provider._answer("POST", url)
