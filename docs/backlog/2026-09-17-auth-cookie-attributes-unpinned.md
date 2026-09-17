# Cookie attributes on the auth responses are unpinned

**Status:** open

## Source

RBAC admin P1 plan, Departure E; whole-branch review, 2026-09-17.

## What

Three `response.set_cookie`/`delete_cookie` regions in `server/routes/auth.py`
have no test: `login`'s cookie set, `oidc_authenticate`'s cookie set/delete,
and `refresh`'s cookie rotation.

This is a **plan issue, not an implementation one**. The P1 plan's Departure E
dropped cookie-attribute pins on the grounds that they would "restate literal
`set_cookie` kwargs in code that does not move." That reasoning conflates two
different things: restating a source literal in a test (which this branch's
characterization-test rule correctly avoids elsewhere) versus asserting on
the *response's* `Set-Cookie` header -- `HttpOnly`, `SameSite`, `Max-Age`,
`Path`. The latter is a wire-contract assertion, not a restatement of source,
and all four of those attributes are security-relevant (session-cookie
scope, CSRF exposure, lifetime).

All three regions were verified byte-identical to `main` on this branch, so
there is no current defect -- the risk is a *future* change silently
weakening one of them. This belongs with the `check_oidc_login` extraction
(see the `routes/auth.py::check_oidc_login` / `oidc_authenticate` entries in
`server/tests/test_no_session_in_service_or_route_signatures.py`), since that
is the change that will actually move this code.

## Why

Without a wire-contract test, a future refactor of the OIDC/cookie code path
can drop `HttpOnly` or loosen `SameSite` and the suite stays green.
