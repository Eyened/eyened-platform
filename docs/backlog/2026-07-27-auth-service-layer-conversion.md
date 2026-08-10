# Auth service-layer conversion (last unconverted domain)

**Status:** open

## Source

Session-ownership refactor (RBAC Step 2 P0), branch `feature/rbac-step2-authz`.
Plan: `docs/superpowers/plans/2026-07-24-session-ownership-refactor.md`.
Surfaced by Task 19's signature guard, which failed as written because the plan's
declared-exception list did not cover the `auth.py` route handlers.
Guard: `server/tests/test_no_session_in_service_or_route_signatures.py`.

## What

`server/routes/auth.py` is the last domain that never received the Recipe R1–R7
treatment (repository owns the `Session`; service takes repositories and no
`Session`; route takes `Depends(get_x_service)`). Instead it was carved out as a
"declared exception".

Concretely, seven handlers — `login`, `get_token`, `get_current_user_info`,
`change_password`, `register_user`, `refresh_token`, `oidc_authenticate` — still
take `session: Session = Depends(get_db)`. None of them touches the database
itself (the guard's second test proves this); each holds the session **only to
forward it** to `check_login`, `check_oidc_login`, `creator_to_response`,
`CurrentUser.get_creator`, `create_user`, or `CreatorRepository(...)`.
(`change_password`/`register_user` also depend on `AuditService`, but via a
separate `Depends(get_audit_service)` parameter, not by forwarding `session`
— see the 2026-07-27 update below.)

The fix is **not** "turn the resolvers into FastAPI dependencies" — that doesn't
work for most of them:

- `check_login` receives credentials from three different sources (JSON body in
  `login`, OAuth2 form data in `get_token`, `current_user.username` + a body
  field in `change_password`), so no single dependency can serve all callers.
- `creator_to_response` queries `CreatorTagLink` to build its response — that is
  a repository read, not a dependency.
- `CurrentUser.get_creator` is a method on the principal, invoked after
  `get_current_user` has already resolved.

The actual work is an `AuthService(CreatorRepository(db), audit)` exposing
`authenticate()`, `register()`, `change_password()`, `resolve_oidc()`, with the
response building moved behind a repository read, and handlers depending on
`Depends(get_auth_service)`.

## Why

- Removes the seven named exemptions in the Task 19 guard, making it near-universal
  (only `import_api.py::import_single_image` would remain, and that module is
  slated for deprecation).
- Makes auth logic unit-testable without HTTP.

**Closed separately (2026-07-27, commit `8d3359f`):** the partial kill-switch --
inline `AuditService(session)` construction in `auth.py` and `import_api.py`
bypassing `settings.db_log.enabled` -- no longer needs the full extraction. The
fix-wave-1 review flagged it as a standalone bug (four call sites always ran
with `enabled=True`), and it was closed directly: `change_password`/
`register_user`/`import_single_image` now take
`audit: AuditService = Depends(get_audit_service)`; `check_login` (not a route
handler) passes `enabled=settings.db_log.enabled` explicitly. That commit also
fixed the `AuditService.record()` JSON-serialization crash on enum/datetime
`changes` values and narrowed the guard's `import_api.py` exclusion from
whole-file to the one function that needs it. This item's remaining rationale
(guard exemption count, testability) stands on its own.

## Why it was deferred (2026-07-27)

- **Coverage.** `auth.py` is 818 lines and 10 endpoints with **5 tests total**, 4
  of which were added during this refactor (Task 16's login-migration test, Task
  19's three `/auth/refresh` tests). Every other service conversion had an
  existing service-test suite to rewire — that is what made the Recipe safe here.
  Refactoring the login path against 5 tests risks shipping a broken login.
- **Blast radius.** 14 route files depend on `get_current_user` / `CurrentUser`;
  changing the principal's shape touches all of them.
- **Timing.** RBAC Step 2 proper rewrites exactly this surface (per-request
  scoping, capability floors, ownership overlay). A pure-refactor pass
  immediately before that rewrite is likely thrown away, and would land
  hard-to-verify changes in the security path right before the security work.

## Recommended sequencing

1. Build auth endpoint/unit test coverage first — RBAC Step 2 needs it regardless.
2. Fold the service extraction into RBAC Step 2's auth work, once the capability
   model has determined what `AuthService`'s interface should be.
3. Removing each guard exemption is the completion signal: the exemption entries
   in `server/tests/test_no_session_in_service_or_route_signatures.py` carry their
   rationale and removal condition in code.
