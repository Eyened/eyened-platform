# Keycloak OIDC (dev)

A local OIDC provider for testing the login flow. It is defined in the base
`deploy/compose.yaml` behind the `oidc` profile, so it stays off — and its image is
never pulled — until you ask for it.

## Start

In `deploy/.env`, **before starting the stack**:

- set `PUBLIC_HOST` to the hostname or LAN IP you type in the browser — **not `localhost`**,
  which is what `.env.example` ships. Inside the server container that name resolves to the
  container itself, and while `oidc` is enabled `doctor.sh` treats it as a hard failure and
  refuses to build anything (see
  [Troubleshooting](../README.md#troubleshooting) in `deploy/README.md`).
- set `EYENED_API_AUTH_OIDC_ENABLED=true`
- set `EYENED_OIDC_CLIENT_ID=eyened-platform`
- set `EYENED_OIDC_CLIENT_SECRET=eyened-dev-secret`
- add `oidc` to `COMPOSE_PROFILES`

`KEYCLOAK_ADMIN_PASSWORD` is **not** in that list: `install.sh` generates it into
`deploy/.env` on first run, alongside the database passwords and the API signing key. Read
it out of that file when you need the admin console. It is on the list only if you wrote
`deploy/.env` by hand or your copy predates that behaviour — see below.

The two `EYENED_OIDC_CLIENT_*` lines ship **commented out** in `deploy/.env.example`, and
`server/config.py` defaults both to the empty string with no validation error. Leave them
commented and everything still starts and looks healthy — then Keycloak rejects the
authorization request for an unknown client, with nothing on either side naming the empty
`client_id` as the cause. The two values above are not examples: they are what
`realm-eyened-dev.json.template` registers, and Keycloak matches them exactly.

`PUBLIC_HOST` comes first because the realm's redirect URI is baked from it when the
container starts: set it afterwards and the first boot registers a URI built from the old
value. (It corrects itself the next time the container is recreated, but the login in
between fails Keycloak's exact-match check.)

## The admin console, and why the password carries the weight

Unlike adminer, Keycloak is published on **every interface** (`KEYCLOAK_BIND`, default
`0.0.0.0`), and it has to be. The server container fetches the metadata document *through
the host* rather than over the compose network, so a loopback-only bind leaves OIDC login
failing at the metadata fetch while every container reports healthy — `doctor.sh` refuses
that combination for exactly that reason. The port being reachable is the point, which is
why the credential is what has to carry the weight: that console administers the realm the
platform trusts for logins.

So `install.sh` generates the password rather than shipping one, and `doctor.sh` refuses to
build with the `oidc` profile while it is absent, empty, `admin` or `change_me` — the
backstop for a hand-written `deploy/.env`, or one created before generation existed.

## It is a development provider, and its state is disposable

`entrypoint.sh` runs `kc.sh start-dev`, and the service declares **no volume**. Both are
deliberate, and together they mean:

- Keycloak runs in development mode — embedded H2, no HTTPS enforcement. Keycloak's own
  documentation says not to run this configuration in production. This is a provider for
  testing the login flow, not for protecting real accounts; point the platform at a real
  IdP (see below) for anything else.
- **Everything inside it is lost when the container is recreated.** The realm is re-imported
  from `realm-eyened-dev.json.template` on every boot, so any user, client or setting you
  create in the admin console disappears — including on `docker compose up -d --build`,
  which is the documented upgrade step. Treat the console as somewhere to look, not
  somewhere to keep things.
- For the same reason `KEYCLOAK_ADMIN_PASSWORD` is re-applied on every recreate rather than
  only at first boot. Editing it and running `docker compose restart` changes nothing; the
  container has to be recreated.

One setting is genuinely optional:

- `KEYCLOAK_PORT` — the host port Keycloak is published on, default `8180`. Change it if
  `8180` is already taken; the metadata URL and the `iss=` token check are both derived
  from it.

Then:

```bash
make up
```

Open `http://<PUBLIC_HOST>:<HTTP_PORT>/users/login` and sign in with **`testuser` / `testuser`**.

## How it fits together

- `entrypoint.sh` + `realm-eyened-dev.json.template` — import a ready-made realm,
  client (`eyened-platform` / `eyened-dev-secret`) and test user.
- Every `EYENED_OIDC_*` setting is read from `.env`. `deploy/compose.yaml` passes all seven
  through as `${EYENED_OIDC_…:-<default>}`, so four of them (`CLIENT_ID`, `CLIENT_SECRET`,
  `PROVIDER_NAME`, `CREATE_NEW_ACCOUNTS`) are yours to fill in, and three
  (`METADATA_URL`, `REDIRECT_URL`, `ADDITIONAL_TOKEN_VALIDATIONS`) default to a derivation
  from this folder's Keycloak that you can override.
- `PUBLIC_URL` moves the realm's redirect URI and `webOrigins` — but **not** Keycloak's
  own `KC_HOSTNAME`, so this bundled provider is for **direct-access development only**.
  Behind a TLS-terminating proxy the browser would be sent to an `authorization_endpoint`
  on `http://<PUBLIC_HOST>:<KEYCLOAK_PORT>`, a port such a deployment does not publish.
  Nobody has run that topology; do not assume `PUBLIC_URL` alone makes it work. To put a
  proxy in front, either route `/realms/` through it and move `KC_HOSTNAME`, the `iss=`
  in `EYENED_OIDC_ADDITIONAL_TOKEN_VALIDATIONS` and `EYENED_OIDC_METADATA_URL` together
  (`deploy/compose.yaml` says so at each of them), or use a real IdP instead.

## Against a real provider

To use a real IdP (e.g. SURFconext) instead, skip this folder entirely: leave `oidc` out of
`COMPOSE_PROFILES`, keep `EYENED_API_AUTH_OIDC_ENABLED=true`, and set the `EYENED_OIDC_*`
values in `deploy/.env`. All seven reach the server from there.

Three of them must move **together**: `EYENED_OIDC_METADATA_URL`, `EYENED_OIDC_REDIRECT_URL`
and `EYENED_OIDC_ADDITIONAL_TOKEN_VALIDATIONS`. Their defaults are all derived from this
folder's Keycloak, so overriding one and not the others leaves a mismatched set — a metadata
URL at the real provider next to an `iss=` still naming the dev realm, say — and that fails
token validation with nothing in the log to say why.
