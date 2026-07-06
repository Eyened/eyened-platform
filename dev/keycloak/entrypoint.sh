#!/bin/bash
set -euo pipefail

REDIRECT_URI="http://${DEV_PUBLIC_HOST:?}:${DEV_NGINX_PORT:?}/users/oidc-callback"
WEB_ORIGIN="http://${DEV_PUBLIC_HOST}:${DEV_NGINX_PORT}"

mkdir -p /opt/keycloak/data/import
sed \
  -e "s|__REDIRECT_URI__|${REDIRECT_URI}|g" \
  -e "s|__WEB_ORIGIN__|${WEB_ORIGIN}|g" \
  /opt/keycloak/import-template/realm-eyened-dev.json \
  > /opt/keycloak/data/import/realm-eyened-dev.json

exec /opt/keycloak/bin/kc.sh start-dev --import-realm
