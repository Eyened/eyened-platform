#!/bin/bash
set -euo pipefail

# Mirrors compose.yaml's EYENED_OIDC_REDIRECT_URL: with a TLS-terminating
# proxy in front (PUBLIC_URL set) the browser's origin is not this stack's
# host:port, and Keycloak compares redirect URIs by exact string, so the URI
# registered here must follow the same rule as the one the server sends.
#
# Not the same TEXT, though: compose.yaml defaults the missing names
# (${PUBLIC_HOST:-localhost}, ${HTTP_PORT:-8080}) where this file demands them
# (${PUBLIC_HOST:?}). The two agree only because the keycloak service passes
# PUBLIC_HOST/HTTP_PORT/PUBLIC_URL in already defaulted — so half of this
# invariant lives in compose.yaml. Stop passing one of those three into the
# container, or change a default on one side only, and the two sides drift.
# The :? is deliberate: better to fail before kc.sh than to register a URI
# nothing will ever match.
#
# ${PUBLIC_HOST:?} inside the fallback is evaluated ONLY when PUBLIC_URL is
# unset or empty (compose passes it as "" when the user leaves it out) —
# which is correct: with PUBLIC_URL set, neither name is needed here.
ORIGIN="${PUBLIC_URL:-http://${PUBLIC_HOST:?}:${HTTP_PORT:?}}"
REDIRECT_URI="${ORIGIN}/users/oidc-callback"
WEB_ORIGIN="${ORIGIN}"

mkdir -p /opt/keycloak/data/import
sed \
  -e "s|__REDIRECT_URI__|${REDIRECT_URI}|g" \
  -e "s|__WEB_ORIGIN__|${WEB_ORIGIN}|g" \
  /opt/keycloak/import-template/realm-eyened-dev.json \
  > /opt/keycloak/data/import/realm-eyened-dev.json

exec /opt/keycloak/bin/kc.sh start-dev --import-realm
