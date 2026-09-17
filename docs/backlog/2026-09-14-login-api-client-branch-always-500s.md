# `POST /auth/login` with `api_client: true` always returns 500

**Status:** open

## Source

RBAC admin P1 plan-writing, 2026-09-14; reproduced on `feature/rbac-admin` @ `30752985`.

## What

`login` declares `response_model=UserResponse` but its `api_client` branch returns
`{user, access_token, refresh_token, token_type, expires_in}`, so FastAPI raises
`ResponseValidationError` on every call. Broken since `10b97913`. Still advertised in
`docs/src/content/docs/api/authentication.mdx` and `api/index.mdx`.
`eyened_orm.api_client` uses cookie login and is unaffected.

## Why deferred

Fixing it changes the endpoint's response; `/auth/token` already covers the need.
Fix (response union or separate model) or delete branch + docs, in its own change.
