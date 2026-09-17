# `GET /auth/me` returns 500 when the token's Creator row is gone

**Status:** open

## Source

RBAC admin P1 spec, out-of-scope list, 2026-09-11.

## What

A valid access token for a deleted `Creator` makes `AuthService.get_creator` return
`None`, which the route dereferences: `AttributeError`, 500. `/auth/refresh` answers
the same case with 401.

Not the deactivated case: `/auth/me` returning 200 for a deactivated account with an
unexpired token is deliberate and pinned by `test_a_deactivated_account_cannot_authenticate`.

## Why deferred

Pre-existing behaviour change; kept out of the P1 refactor.
