# Keycloak OIDC (dev)

A local OIDC provider for testing the login flow. It is defined in the base
`deploy/compose.yaml` behind the `oidc` profile, so it stays off — and its image is
never pulled — until you ask for it.

## Start

In `deploy/.env`, **before starting the stack**:

- set `PUBLIC_HOST` to the hostname/IP you use in the browser
- set `EYENED_API_AUTH_OIDC_ENABLED=true`
- add `oidc` to `COMPOSE_PROFILES`

`PUBLIC_HOST` comes first because the realm's redirect URI is baked from it when the
container starts: set it afterwards and the first boot registers a URI built from the old
value. (It corrects itself the next time the container is recreated, but the login in
between fails Keycloak's exact-match check.)

Then:

```bash
make up
```

Open `http://<PUBLIC_HOST>:<HTTP_PORT>/users/login` and sign in with **`testuser` / `testuser`**.

## How it fits together

- `entrypoint.sh` + `realm-eyened-dev.json.template` — import a ready-made realm,
  client (`eyened-platform` / `eyened-dev-secret`) and test user.
- The remaining OIDC settings live in `.env` (`EYENED_OIDC_CLIENT_ID`,
  `EYENED_OIDC_CLIENT_SECRET`, `EYENED_OIDC_PROVIDER_NAME`, `EYENED_OIDC_CREATE_NEW_ACCOUNTS`).
- `PUBLIC_URL` moves the realm's redirect URI and `webOrigins` — but **not** Keycloak's
  own `KC_HOSTNAME`, so this bundled provider is for **direct-access development only**.
  Behind a TLS-terminating proxy the browser would be sent to an `authorization_endpoint`
  on `http://<PUBLIC_HOST>:<KEYCLOAK_PORT>`, a port such a deployment does not publish.
  Nobody has run that topology; do not assume `PUBLIC_URL` alone makes it work. To put a
  proxy in front, either route `/realms/` through it and move `KC_HOSTNAME`, the `iss=`
  in `EYENED_OIDC_ADDITIONAL_TOKEN_VALIDATIONS` and `EYENED_OIDC_METADATA_URL` together
  (`deploy/compose.yaml` says so at each of them), or use a real IdP instead.

To test against a real provider (e.g. SURFconext) instead, skip this folder entirely
and just set the `EYENED_OIDC_*` values in `.env`.
