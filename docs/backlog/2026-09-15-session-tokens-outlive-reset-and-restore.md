# Session tokens outlive reset and restore

- **Source:** Wave G review/testing of the `deploy/` consolidation (PR #202), observed while
  exercising `./eyened reset` and `./eyened restore` on a scratch stack.
- **Files:** `server/services/current_user.py` (`CurrentUser`, `get_current_user`),
  `server/routes/auth.py` (`create_access_token`, `create_refresh_token`,
  `get_current_user_info`), `server/main.py` (the generic exception handler), `deploy/scripts/lib.sh`
  (`write_env` — `EYENED_API_SECRET_KEY` is generated once and never rewritten), `eyened`
  (`cmd_reset` deletes only volumes; it never touches `deploy/.env`).

---

**Status:** open

`EYENED_API_SECRET_KEY` is the JWT signing key that `write_env` generates once and never
rewrites. `./eyened reset` deletes only the database and platform-storage volumes; it does
not touch `deploy/.env`, so the key survives. `./eyened restore` replaces the datadir but
likewise never rewrites `.env`. Both access and refresh tokens carry only `sub` (`CreatorID`)
and `username` — `get_current_user` trusts the `CreatorID` in a validly-signed token and never
checks that the row it names is the same identity the token was issued to.

Measured on a scratch stack: a cookie issued to `alice` (`CreatorID` 2) before `./eyened
reset`, presented again after a reset and after a freshly created account `bob` happened to
land on the same id (`CreatorID` 2), authenticated as `bob` — HTTP 200. Before `bob` existed,
the same cookie returned HTTP 500 ("An unexpected error occurred") rather than 401: the code
path assumes a `CreatorID` decoded from a valid token always resolves to a row.

This is pre-existing application behaviour — the JWT scheme was never `deploy/`'s to design —
but `./eyened reset` and `./eyened restore` are what make reusing a `CreatorID` across a
population change routine rather than exceptional, so `deploy/` is what makes it reachable in
practice.

**Options (no decision):**
- Bind tokens to something that changes with the account: a per-account token version, or a
  password-hash fingerprint, checked on every request.
- Rotate `EYENED_API_SECRET_KEY` in `./eyened reset` (and possibly `./eyened restore`), which
  invalidates every outstanding token at once instead of per-account.
- Have the token-resolution path return 401 rather than let a missing `Creator` propagate to a
  500.
