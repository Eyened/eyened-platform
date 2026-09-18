# Follow-up: bundled Keycloak network topology and prod gating

- **Source:** DevOps analysis during the `deploy/` consolidation whole-branch review,
  2026-08-14. Raised while deciding the default for `KEYCLOAK_BIND`; both items were
  deliberately left out of that landing because neither can be verified without a running
  stack.
- **Files:** `deploy/compose.yaml` (keycloak service, `EYENED_OIDC_METADATA_URL`),
  `deploy/compose.oidc.yaml` (`extra_hosts`), `deploy/keycloak/README.md`.

---

## 1. The server reaches Keycloak through the host, not over the compose network

**Status:** open

`server` and `keycloak` are on the same compose network, so the server could fetch the
OIDC metadata document at `http://keycloak:8080/...` directly. It does not. Its
`EYENED_OIDC_METADATA_URL` is the **browser-facing** URL (`${PUBLIC_HOST}:${KEYCLOAK_PORT}`),
so the call leaves the container, goes out to the published host port, and comes back in —
which is why `compose.oidc.yaml` has to alias `PUBLIC_HOST` to `host-gateway`.

The reason it uses the browser-facing URL is real: the issuer the server validates has to be
byte-identical to the one the browser was redirected to, and
`EYENED_OIDC_ADDITIONAL_TOKEN_VALIDATIONS` compares `iss=` by exact string.

**Consequences today:**

- `KEYCLOAK_BIND` cannot be set to a loopback address. It looks like a hardening knob, and
  setting it leaves every container healthy while token exchange fails. Nothing refuses it;
  `deploy/keycloak/README.md` documents it.
- The bundled Keycloak has to be published on `0.0.0.0` — on a shared host, that is an
  admin console for the realm the platform trusts, exposed to the network. The mitigation
  in place is the required `KEYCLOAK_ADMIN_PASSWORD`, not the bind address.
- `compose.oidc.yaml` carries an `extra_hosts` entry that exists only for this.

**Proposed fix** (needs a running stack to verify, which is why it is here):

1. Default `EYENED_OIDC_METADATA_URL` to the internal service URL,
   `http://keycloak:8080/realms/eyened-dev/.well-known/openid-configuration`.
2. Add `KC_HOSTNAME_BACKCHANNEL_DYNAMIC: "true"` to the keycloak service, so back-channel
   endpoints follow the request host (`keycloak:8080`) while front-channel URLs and the
   issuer stay pinned to `KC_HOSTNAME` — which is already an absolute URL for exactly this
   reason.
3. If that holds, `KEYCLOAK_BIND` can default to `127.0.0.1` and `extra_hosts` can go.

**What this does NOT solve:** the developer's **browser** still reaches Keycloak at
`PUBLIC_HOST:KEYCLOAK_PORT`. A loopback bind therefore only works for someone running the
browser on the same machine as the stack. Anyone working against a remote shared host still
needs the port on the network — the same requirement the application itself already has via
`HTTP_PORT`. So the fix makes loopback *viable*, not universal, and the default would need
to follow whichever case is normal for the deployment.

**Verification when this is picked up:** the failure mode is silent, so assert on a real
login, not on container health. Prove both directions — the metadata fetch succeeding from
inside the `server` container, and a token whose `iss` still matches the browser-facing
issuer.

---

## 2. Nothing gates the `oidc` layer against the prod layer

**Status:** open — mechanism updated, gap unchanged

`:compose.oidc.yaml` can be appended to `COMPOSE_FILE` alongside `:compose.prod.yaml`, and
nothing refuses that combination.

The bundled Keycloak runs `kc.sh start-dev` with no volume: embedded H2, no HTTPS
enforcement, all state discarded on every container recreate. Keycloak's own documentation
says not to run that configuration in production. On a production install it would be
protecting real accounts with a development-mode identity provider whose realm resets on the
next upgrade.

The route concern this item originally raised no longer applies: the `host-gateway` alias
that lets the server reach the published Keycloak port lives in `compose.oidc.yaml` itself
now, added whenever that layer is in `COMPOSE_FILE` rather than only under
`compose.dev.yaml` — so the metadata fetch has a route under the prod layer too. The
identity-provider concern above (dev-mode Keycloak, no volume, no HTTPS enforcement) is
unaffected and remains the actual open item.

**Proposed fix:** document, or have the CI config matrix reject, `:compose.oidc.yaml` together
with the prod layer, pointing the operator at an external IdP — the configuration the
`EYENED_OIDC_*` settings already support. Decide first whether the combination is genuinely
unsupported or merely unwise; the refusal should match.
