#!/bin/bash
set -euo pipefail

# Must agree with the operator's own EYENED_OIDC_REDIRECT_URL (deploy/.env,
# read by the server via compose.yaml): with a TLS-terminating proxy in front
# (PUBLIC_URL set) the browser's origin is not this stack's host:port, and
# Keycloak compares redirect URIs by exact string, so the URI registered here
# must be built from the same PUBLIC_HOST/HTTP_PORT/PUBLIC_URL the operator
# used for EYENED_OIDC_REDIRECT_URL.
#
# Not the same TEXT, though: compose.oidc.yaml defaults the names it passes in
# (${PUBLIC_HOST:-localhost}, ${HTTP_PORT:-8080}, ${PUBLIC_URL:-}) where this
# file demands PUBLIC_HOST and HTTP_PORT (${PUBLIC_HOST:?}, ${HTTP_PORT:?}).
# The two agree only because compose.oidc.yaml's keycloak service passes them
# in already defaulted — so half of this invariant lives there, not in
# compose.yaml. Change a default on one side only, or stop passing one of
# these three into the keycloak service, and the two sides drift. The :? is
# deliberate: better to fail before kc.sh than to register a URI nothing will
# ever match.
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
