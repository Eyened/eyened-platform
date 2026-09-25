# Auth and sessions

### Stop a token outliving `docker compose down -v` or a restore
- **Status:** open
- **Source:** PR #202 Wave G testing, 2026-09-15
- **Problem:** `EYENED_API_SECRET_KEY` lives in `deploy/.env`, which neither `docker compose down -v` nor an XtraBackup restore touches, and `get_current_user` (`server/services/current_user.py`) trusts the `CreatorID` in any validly signed token. Measured: `alice`'s cookie (`CreatorID` 2) from before a reset authenticated as a new `bob` on the same id (200); before `bob` existed it was a 500, not 401.
- **Fix:** bind tokens to something that changes with the account (a truncated HMAC of `PasswordHash`, or a per-account token version) checked on every request, and 401 on a missing Creator. Until then, document rotating `EYENED_API_SECRET_KEY` after a reset or restore.

### Fix or delete the `api_client` branch of `POST /auth/login`
- **Status:** open
- **Source:** documentation triage, 2026-09-21; broken since `10b97913`
- **Problem:** `login` declares `response_model=UserResponse` but the `api_client` branch returns `{user, access_token, refresh_token, ...}` → `ResponseValidationError`, 500 on every call; no test covers it. Still advertised in `docs/src/content/docs/api/authentication.mdx` and `api/index.mdx`.
- **Fix:** a response union / separate model, or delete the branch and its docs (`/auth/token` already covers API clients; `eyened_orm.api_client` uses cookie login). Do not fix the docs to describe a 500.

### Move the auth routes behind an `AuthService`
- **Status:** open
- **Source:** session-ownership refactor, 2026-07-27
- **Problem:** `login`, `get_token`, `get_current_user_info`, `change_password`, `register_user`, `refresh_token` and `oidc_authenticate` in `server/routes/auth.py` take a `Session` only to forward it to `check_login`, `check_oidc_login`, `creator_to_response`, `CurrentUser.get_creator` and `create_user`; each is an exemption in `server/tests/test_no_session_in_service_or_route_signatures.py`. The auth surface has ~5 tests.
- **Fix:** add auth endpoint tests first, then `AuthService(CreatorRepository(db), audit)` with `authenticate()`, `register()`, `change_password()`, `resolve_oidc()`; delete each allow-list entry as its handler moves.
- **Note:** RBAC admin P1 (on `feature/rbac-admin`) already converts the password half; don't redo it here.
