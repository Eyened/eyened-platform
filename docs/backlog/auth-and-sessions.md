# Auth and sessions

### Validate usernames at every entry point
- **Status:** open
- **Source:** PR #247 review, 2026-09-24
- **Problem:** `Creator.CreatorName` is `String(45)` unique (`orm/eyened_orm/creator.py`), but `CreateUserRequest.username` (`server/routes/admin.py`) has only `min_length=1`, `/auth/register` takes a bare `username: str`, and neither `eorm create-user` nor OIDC provisioning (`preferred_username`, `server/routes/auth.py`) checks. A >45-char name is a 500 under strict `sql_mode` (MySQL 8 default) or silently truncated without it; whitespace-only and leading/trailing-whitespace names are accepted.
- **Fix:** add `check_new_username()` next to `check_new_password()` in `orm/eyened_orm/utils/db_users.py`; call it from admin create, register and the CLI, mapped to 4xx. Derive the max from `Creator.__table__.c.CreatorName.type.length`; reject leading/trailing whitespace rather than strip.
- **Note:** OIDC needs its own decision: rejecting an IdP-supplied name locks that user out.

### Fence `PUBLIC_AUTH_DISABLED`
- **Status:** open, blocked on PR #202
- **Source:** PR #247 review, 2026-09-22
- **Problem:** under the flag `get_current_user` (`server/services/current_user.py`) resolves and `ensure_admin`-promotes `admin_username` for any credential-less request, and `is_authenticated` (`server/routes/auth.py`) returns `True`. That now exposes the roster, `POST /admin/users` and `PUT /admin/users/{id}/active|password` (including the admin's own password); only a `print` in `server/main.py` guards it.
- **Fix:** re-derive the fence against PR #202's `deploy/` env model once it merges.
- **Note:** a `Settings` validator requiring `debug` breaks the new-dev checklist after #202 (`deploy/.env.example` ships `EYENED_API_DEBUG=false`); skipping `include_router(admin.router)` under the flag was rejected because the admin console is developed in that mode.

### End existing sessions on a password change or reset
- **Status:** open
- **Source:** RBAC admin P3b brainstorm, 2026-09-18
- **Problem:** `/auth/refresh` checks only `Inactive`, so a refresh token minted before `eorm set-password`, an admin reset or `/auth/change-password` keeps renewing. Until fixed, deactivation (not a reset) is the way to cut off a compromised account.
- **Fix:** put a truncated HMAC of `PasswordHash` in both tokens and compare it where the Creator is already loaded (refresh, `get_access_scope`); `/auth/change-password` re-issues the caller's cookies. No migration, no extra query; covers every `PasswordHash` writer. Every user must log in once after deploy.
- **Note:** "log out everywhere" without a password change, and refresh after reactivation, need a per-user token-version / `notBefore` column (migration) and are not covered.

### Make `get_current_user` reject deleted and deactivated accounts
- **Status:** open
- **Source:** RBAC admin P1 spec (2026-09-11) + P3b brainstorm (2026-09-18)
- **Problem:** the token paths in `get_current_user` never read the Creator. `GET /auth/me` for a deleted Creator dereferences `None` → 500 (refresh gives 401); a deactivated user can still call `GET /auth/me` and `GET /import/status/{task_id}` until the access token expires (30 min).
- **Fix:** read the Creator inside `get_current_user` and 401 on missing or `Inactive`; on routes that also resolve a scope the second `db.get` is an identity-map hit.
- **Note:** `/auth/me` returning 200 for a deactivated account is currently pinned by `test_a_deactivated_account_cannot_authenticate`; update that test deliberately.

### Cap the absolute session lifetime
- **Status:** open
- **Source:** RBAC admin P3b brainstorm, 2026-09-18
- **Problem:** every `/auth/refresh` mints a fresh 7-day refresh token, so an active session never ends (NIST 800-63B-4 AAL1: SHOULD ≤ 30 days).
- **Fix:** carry the original login time through refreshes and refuse to refresh past a cap.

### Fix or delete the `api_client` branch of `POST /auth/login`
- **Status:** open
- **Source:** RBAC admin P1, reproduced at `30752985`; broken since `10b97913`
- **Problem:** `login` declares `response_model=UserResponse` but the `api_client` branch returns `{user, access_token, refresh_token, ...}` → `ResponseValidationError`, 500 on every call. Still advertised in `docs/src/content/docs/api/authentication.mdx` and `api/index.mdx`.
- **Fix:** a response union / separate model, or delete the branch and its docs (`/auth/token` already covers API clients; `eyened_orm.api_client` uses cookie login).

### Check new passwords against a breached/common-password list
- **Status:** open
- **Source:** RBAC admin P3b password policy, 2026-09-18
- **Problem:** `check_new_password` enforces length 15–128 and a context blocklist but not the NIST 800-63B-4 §3.1.1.2 SHALL for a compromised/common-password blocklist.
- **Fix:** in `check_new_password`, either a bundled public list filtered to ≥15 chars (offline, deterministic) or the HIBP k-anonymity range API (outbound call per change; may be blocked on SURF Research Cloud).

### Move OIDC login into `AuthService` and pin the auth cookie attributes
- **Status:** partial — password path is in `AuthService`; OIDC path and cookie tests left
- **Source:** auth service-layer conversion (2026-07-27) + RBAC admin P1 review (2026-09-17)
- **Problem:** `check_oidc_login` / `oidc_authenticate` in `server/routes/auth.py` still take a `Session` (allow-listed in `server/tests/test_no_session_in_service_or_route_signatures.py`). No test asserts the `Set-Cookie` attributes (`HttpOnly`, `SameSite`, `Max-Age`, `Path`) of `login`, `oidc_authenticate` or `refresh`, so a refactor can weaken them silently.
- **Fix:** add wire-contract tests on the response `Set-Cookie` headers first, then extract a `resolve_oidc()` into `AuthService` and delete the two allow-list entries.
- **Note:** no deployment uses OIDC and there is no token-validation harness; build one for the extraction.
