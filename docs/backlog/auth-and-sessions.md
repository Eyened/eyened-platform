# Auth and sessions

### Validate usernames at every entry point
- **Status:** open
- **Source:** PR #247 review, 2026-09-24
- **Problem:** `Creator.CreatorName` is `String(45)` unique (`orm/eyened_orm/creator.py`), but `CreateUserRequest.username` (`server/routes/admin.py`) has only `min_length=1`, `/auth/register` takes a bare `username: str`, and neither `eorm create-user` nor OIDC provisioning (`preferred_username`, `server/routes/auth.py`) checks. A >45-char name is a 500 under strict `sql_mode` (MySQL 8 default) or silently truncated without it; whitespace-only and leading/trailing-whitespace names are accepted.
- **Fix:** add `check_new_username()` next to `check_new_password()` in `orm/eyened_orm/utils/db_users.py`; call it from admin create, register and the CLI, mapped to 4xx. Derive the max from `Creator.__table__.c.CreatorName.type.length`; reject leading/trailing whitespace rather than strip.
- **Note:** OIDC needs its own decision: rejecting an IdP-supplied name locks that user out.


### Fix or delete the `api_client` branch of `POST /auth/login`
- **Status:** open
- **Source:** RBAC admin P1, reproduced at `30752985` + documentation triage, 2026-09-21; broken since `10b97913`
- **Problem:** `login` declares `response_model=UserResponse` but the `api_client` branch returns `{user, access_token, refresh_token, ...}` → `ResponseValidationError`, 500 on every call; no test covers it. Still advertised in `docs/src/content/docs/api/authentication.mdx` and `api/index.mdx`.
- **Fix:** a response union / separate model, or delete the branch and its docs (`/auth/token` already covers API clients; `eyened_orm.api_client` uses cookie login). Do not fix the docs to describe a 500.

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
