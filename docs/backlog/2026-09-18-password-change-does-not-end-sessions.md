# A password change ends no session, and a session never expires

**Status:** open

## Source

RBAC admin P3b brainstorm (account lifecycle over HTTP), 2026-09-18. Deferred out of P3b:
its endpoints behave the same without it, and the fix changes authentication for every
user, not only the admin surface.

## 1. A password change or reset ends no existing session

**What.** `/auth/refresh` (`server/routes/auth.py`) re-mints both tokens and checks only
`Inactive`. A refresh token opened with the old password therefore keeps renewing after
`eorm set-password`, an admin reset, or `/auth/change-password`. Proposed fix (Django's
session-auth-hash pattern): put a truncated HMAC of `PasswordHash` in both tokens and
compare it where the Creator is already loaded (refresh, `get_access_scope`).
`/auth/change-password` re-issues the caller's own cookies, which is Django's
`update_session_auth_hash`. It needs no migration and adds no query, and it covers every
`PasswordHash` writer (`account_admin.py`, `auth_service.py`, `bootstrap.py`). Tokens
minted before the deploy fail the check, so every user has to log in once more.

**Why.** Revoking on a password change is the common default but not a requirement.
RFC 9700 §4.14.2 says an authorization server "MAY" revoke refresh tokens on a password
change. OWASP's Forgot Password Cheat Sheet says to invalidate sessions automatically or
offer it to the user. NIST SP 800-63B-4 does not address it. Django revokes by default,
Keycloak offers it as a checkbox, and Auth0 does not revoke refresh tokens. Until this
lands, the way to cut off a compromised account is deactivation, not a reset.

Not covered by this fix: a "log out everywhere" that leaves the password unchanged, and a
refresh token that is still unexpired when an account is reactivated. Both need a per-user
token-version or `notBefore` column, which requires a migration (Keycloak's approach).

## 2. Three routes authenticate without the `Inactive` check

**What.** `get_access_scope` (`server/services/access_scope.py`) re-reads the Creator on
every request and rejects `Inactive`, but three routes depend on `get_current_user` alone:
`GET /auth/me`, `POST /auth/change-password` (harmless, because `authenticate` rejects
`Inactive`) and `GET /import/status/{task_id}`. Fix: do the `Inactive` read inside
`get_current_user`. On routes that also resolve a scope, the second `db.get` is an
identity-map hit.

**Why.** A deactivated user can still read their own profile and poll import jobs until
their access token expires (30 minutes).

## 3. Sliding refresh has no absolute session lifetime

**What.** Every refresh mints a new 7-day refresh token, so an active session never ends.
Fix: carry the original login time through refreshes and refuse to refresh once it is
older than a cap.

**Why.** NIST SP 800-63B-4 sets an overall session timeout for AAL1 of at most 30 days
(SHOULD).
