# The cutover grant skipped every legacy-credential human

**Source:** found 2026-09-17 while specifying P2's `has_credential` flag. **Status:** open.

**What.** `grant_all` drives off `CreatorRepository.list_authenticatable`, which
filters on `PasswordHash.is_not(None)`. In the production dump 15 human rows have
only the legacy `Creator.Password` column set, which `AuthService.authenticate`
still accepts — it falls through to a pbkdf2-sha256 comparison and migrates the
row to Argon2 on success. The 1,364-row cutover passed over all 15.

**Why.** They can log in today and hold zero project memberships, which under
RBAC means they see nothing. Ten have annotation history — 13,582 annotations
between them, the largest single account holding 6,394. One ("Graders") is a
shared account rather than a person. All 15 are active, non-admin, and share a
bulk-migration `DateInserted` of 2024-10-30.

**Resolution.** Decide per account: grader still working (grant), dormant (leave
or deactivate), or a shared login that should not exist under RBAC.
`GET /admin/users` makes the population visible — `has_credential: true` with an
empty membership list is exactly this set — so the diagnosis is a console query
once P2 ships.
