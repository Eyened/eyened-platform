# Three PR #247 review fixes are parked behind PR #202

**Status:** open

## Source

RBAC admin whole-branch review of PR #247, 2026-09-22 (four reviewers over
`bab68deb..67212813`). Five findings were accepted as worth fixing; two were fixed
inline and these three were parked because PR #202 ("One deploy/ compose stack")
rewrites the files they land in.

## What

**1. `PUBLIC_AUTH_DISABLED` has no guardrail, and the account surface behind it grew.**
`server/services/current_user.py:78-101` resolves *and* `ensure_admin`-promotes the
`admin_username` account for any request with no credentials, and
`server/routes/auth.py:148` returns `True` from `is_authenticated` unconditionally under
the flag. P2 put the user roster behind it; P3a/P3b added `POST /admin/users`,
`PUT /admin/users/{id}/active` and `PUT /admin/users/{id}/password` — including the
bootstrap admin's own password. Nothing but a `print` at `server/main.py:125-126` stands
between a misconfigured instance and persistent takeover of every account.

**Do not implement the obvious fix without re-checking the premise.** The candidate was a
`model_validator` on `Settings` refusing `public_auth_disabled` unless `debug`, which was
free because `dev/sample.env` shipped `EYENED_API_DEBUG=true`. PR #202 deletes
`dev/sample.env` and replaces it with `deploy/.env.example`, which ships
`EYENED_API_DEBUG=false` alongside `EYENED_API_PUBLIC_AUTH_DISABLED=false`. After #202 that
validator breaks the documented new-dev checklist on the first run. Re-derive the fence
against the `deploy/` env model — the alternative considered was skipping
`include_router(admin.router)` under the flag, rejected because the admin console (step 4 of
the RBAC admin HTTP client spec) is developed in exactly that mode.

**2. `docs/rbac-operations.md` has drifted behind the password policy.**
- `:168` documents `eorm create-user --username test_user --password test-pw`. That password
  is 7 characters; `create-user` now routes through `AccountAdministration.create` ->
  `check_new_password`, which rejects anything under 15. The test_user loop dead-ends on its
  first copy-pasteable line.
- `:199-207` states the policy for `init-admin` only. It now also binds `create-user` and
  `set-password` (`account_admin.py:75` and `:194`), and the command table warns of neither.
- `:67-70` claims re-running `init-admin` with an unchanged password is unaffected "since the
  policy only applies when a password would actually be set". False for legacy-credential
  accounts: `ensure_admin` computes `password_reset = bool(password) and not (creator.PasswordHash
  and verify_password(...))`, and a legacy account has `PasswordHash` NULL, so the policy runs
  and a sub-15-character legacy password fails the command. The population is real — see
  [the cutover entry](2026-09-17-cutover-skipped-legacy-credential-humans.md), 15 rows in the
  production dump.

**3. `RELEASE_NOTES.md` omits the password policy.** The Unreleased section carries four CLI
audit-row details but not the policy now enforced on `/auth/register`, `/auth/change-password`,
`eorm create-user`, `eorm set-password` and `eorm init-admin`; not the nine-operation `/admin`
surface with `is_admin` on `UserResponse`; and not `ensure_admin` clearing the legacy
`Creator.Password` column on a reset. The file's own preamble asks for the entry in the same PR
that changes behaviour. `docs/src/content/docs/release_notes.mdx` needs the same text.

## Why

Item 1 is the security-relevant one: the flag is dev-only by convention with nothing enforcing
it, and this branch is what made it worth exploiting rather than merely permissive.

Items 2 and 3 are why parking is not free — the documentation currently publishes a command that
fails and a safety claim that is wrong for a known population, and it will keep doing so until
#202 merges and these can be rewritten on top of it. Re-read `docs/rbac-operations.md` and
`release_notes.mdx` at that point rather than replaying the line numbers above; #202 rewrites
both, including the test_user loop and the new-dev checklist.

## Blocked on

PR #202 (`feature/deploy-consolidation-v2`), open and not a draft as of 2026-09-22. It deletes
`dev/sample.env`, adds `deploy/.env.example`, touches `server/config.py` (a comment at line 128,
adjacent to where item 1's validator would go) and rewrites `docs/rbac-operations.md` and
`docs/src/content/docs/release_notes.mdx`.
