# Keycloak OIDC (dev)

A local OIDC provider for testing the login flow. It's fully optional and isolated
from the base dev stack — use it only when you want to exercise OIDC locally.

## Start

From the `dev` folder:

```bash
./keycloak/up.sh up -d
```

(equivalent to `docker compose -f docker-compose.yml -f keycloak/docker-compose.keycloak.yml up -d`)

Then in `.env`:

- set `DEV_PUBLIC_HOST` to the hostname/IP you use in the browser
- set `EYENED_API_AUTH_OIDC_ENABLED=true`

Open `http://<DEV_PUBLIC_HOST>:<DEV_NGINX_PORT>/users/login` and sign in with **`testuser` / `testuser`**.

## How it fits together

- `docker-compose.keycloak.yml` — override that adds the Keycloak service and the
  server's OIDC URLs (derived from `DEV_PUBLIC_HOST`).
- `entrypoint.sh` + `realm-eyened-dev.json.template` — import a ready-made realm,
  client (`eyened-platform` / `eyened-dev-secret`) and test user.
- The remaining OIDC settings live in `.env` (`EYENED_OIDC_CLIENT_ID`,
  `EYENED_OIDC_CLIENT_SECRET`, `EYENED_OIDC_PROVIDER_NAME`, `EYENED_OIDC_CREATE_NEW_ACCOUNTS`).

To test against a real provider (e.g. SURFconext) instead, skip this folder entirely
and just set the `EYENED_OIDC_*` values in `.env`.
