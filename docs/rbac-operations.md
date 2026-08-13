# RBAC operations

## Cutover

Every step before the last is invisible to users. Memberships are inert rows
until enforcement reads them, and the CLI is a trusted path that works
regardless of enforcement state -- so the grants happen while the system is
still open, and the flip lands with everyone already granted.

1. Deploy the migration alone (`ProjectMember`, `Creator.IsAdmin`,
   `Creator.Inactive` exist; nothing reads them).
2. `eorm init-admin --username <the EYENED_API_ADMIN_USERNAME value>`
3. `eorm grant-all` -- grader in all 44 projects for every creator that can
   authenticate.
4. Review the grant; announce the cutover.
5. Deploy the enforcing server.

**Rollback is redeploying the previous server.** The membership rows stay and
do nothing. There is no feature flag: a flag means two code paths where the
"off" one is fail-open, and it would need testing as carefully as the real one.

## What changes at step 5

| Operation | Before | After |
|---|---|---|
| Read anything, in any project | yes | yes |
| Create annotations; modify and delete **own** | yes | yes |
| Create a task | yes | yes (vacuous -- a new task holds no images) |
| Update task/subtask status; add/remove subtasks and images | yes | yes |
| **Modify another user's annotation** | yes | **no** |
| **Delete another user's annotation** | yes | **no** -- project admin |
| **Delete a populated task** | yes | **no** -- project admin |

The first is the requirement doing its job. The other two are collateral from
`grader` not reaching `project_admin`, and both have a working recovery path:
administrators are data superusers and can perform them immediately.

## RBAC ships inert

Granting everyone `grader` everywhere is **not an escalation** -- it is writing
down the status quo. Today any authenticated user can already do all of this to
all 44 projects; the grant makes that state explicit and, for the first time,
revocable.

But the upper bound is 32 creators x 44 projects = 1,408 memberships against a
~185-row steady state, so the great majority must be revoked before the
platform restricts anything. **Until pruning happens, the mechanism is
installed and enforcing a policy that permits everything.**

Users who read without writing are not distinguishable from anyone else under
the bulk grant, so pruning cannot be driven from authored work alone -- whoever
prunes needs the intended membership list from the consortium, not a query.

## Local development

- **Everyday feature work:** `EYENED_API_PUBLIC_AUTH_DISABLED=true` logs you in
  as the `EYENED_API_ADMIN_USERNAME` account, which sees every project in a
  loaded dump. The dev-bypass branch calls `ensure_admin`, so a pre-cutover
  dump does not show you an empty platform.
- **Working *on* enforcement:** being a permanent administrator hides every 403
  and 404, so drive a dedicated account instead. Scope resolves per request, so
  every change below lands on a refresh -- no re-login, no fixture seed. See
  "The test_user loop" below.
- **Named-account login:** with `PUBLIC_AUTH_DISABLED=false` you authenticate
  as a specific `Creator` and see exactly what its `IsAdmin` flag and
  memberships grant. This path does **not** auto-promote, which is also the
  cheapest way to reproduce a new joiner's view.
- **The joiner flow, for free:** the bundled Keycloak (`dev/keycloak/`) with
  `EYENED_OIDC_CREATE_NEW_ACCOUNTS=true` auto-provisions a fresh login as a
  zero-access user.
- **Testing containment:** a production dump has task 70, which touches several
  projects. Revoke yourself from one of them and the task should vanish from
  `GET /task` entirely rather than appear with fewer subtasks. That single check
  exercises the containment rule, the 404 policy and the absence of partial
  views at once.

## The test_user loop

One account, driven from the CLI, watched in the browser. Log in as it with
`EYENED_API_PUBLIC_AUTH_DISABLED=false`; every step below takes effect on a
refresh.

```bash
eorm create-user --username test_user --password test-pw
```

| # | Scenario | Command | Expect in the client |
|---|---|---|---|
| 1 | Zero-access joiner | *(none -- just log in)* | An empty platform: no projects, no patients, no tasks |
| 2 | First grant | `eorm grant --user test_user --project P --role read_only` | Project P's data appears |
| 3 | Role floor | `eorm grant --user test_user --project P --role grader` | Writes that were refused at `read_only` now succeed |
| 4 | Ownership overlay | *(none)* | As `grader`, editing another user's annotation is 403. A production dump supplies one, so nothing needs seeding |
| 5 | Containment | Grant both projects a spanning task touches, then `eorm revoke --user test_user --project <one of them>` | The task disappears from `GET /task` entirely -- not with fewer subtasks. Exercises the containment rule, the 404 policy and the absence of partial views at once |
| 6 | Administrator overlay | `eorm set-admin --user test_user --on`, then `--off` | Every restriction vanishes, then returns to the granted view |
| 7 | Deactivation | `eorm deactivate --user test_user` | Authentication is refused |
| 8 | Reset | `eorm reactivate --user test_user`, then `eorm revoke --user test_user --all` | Back to scenario 1 |

Forgot the password? `eorm set-password --user test_user`. The `Creator` row
cannot be deleted -- that is what `deactivate` exists for -- so re-minting is
not an option.

For scenario 5, a production dump has task 70, which touches several projects.

## New-dev checklist

clone -> install deps -> `cp dev/sample.env dev/.env` -> start the DB stack ->
`eorm load-dump` -> `eorm init-admin` with a username matching
`EYENED_API_ADMIN_USERNAME` -> `PUBLIC_AUTH_DISABLED=true` for feature work,
`=false` plus the test_user loop below for RBAC work.

## Commands

| Command | Purpose |
|---|---|
| `eorm init-admin --username U [--password P]` | Create or promote the administrator (idempotent) |
| `eorm create-user --username U --password P` | Create a new, non-administrator user account |
| `eorm grant --user U --project P --role R` | Grant or change a role |
| `eorm revoke --user U --project P` | Remove a membership |
| `eorm revoke --user U --all` | Remove every membership the user holds; confirms unless `--yes` |
| `eorm grant-for-task --user U --task N [--task M] --role R` | Grant every project the tasks touch, after review |
| `eorm grant-all` | Cutover step 3 |
| `eorm set-admin --user U --on/--off` | Set or clear administrator status on an existing account |
| `eorm set-password --user U` | Set an existing user's password -- including an account (OIDC-provisioned, an AI model, attribution-only) that was never meant to log in by password at all |
| `eorm deactivate --user U` / `eorm reactivate --user U` | Revoke every project; memberships are kept. Not an absolute lockout -- see the accepted risks |

## Accepted risks

- **The CLI does not authenticate its operator.** Every command above is a
  trusted path (see the module docstrings on `authz/administration.py` and
  `commands/rbac.py`): anyone with shell access can run `eorm set-admin --user
  U --on` and self-promote, and the audit row that records it names no actor
  -- `ActorID` is NULL by design on this path, the same as every other command
  here.
- **`grant-all` grants every project to self-registered accounts.**
  `POST /auth/register` needs no authentication, and grant-all's population
  filter is `IsHuman AND NOT Inactive AND PasswordHash IS NOT NULL` -- which a
  self-registered row matches exactly. Anyone who registers before cutover
  receives `grader` in all 44 projects. Accepted by decision on 2026-08-13; no
  code change. The confirmation prompt discloses nothing to decide on: it is a
  bare yes/no question that names no creator and does not so much as count
  them, and `--yes` skips it entirely. The totals (`N membership(s) written for
  M creator(s) across P project(s)`) print after the commit -- after the rows
  exist. So the grant cannot be reviewed through the CLI *before* it is
  written, and there is nothing at the prompt that would tell you that one of
  the creators is a stranger. **Step 4 of the cutover is the mitigation, and it is
  a query rather than a prompt: read `ProjectMember` (or the `Creator` rows the
  filter above selects) once the write is done, and look for accounts nobody
  recognises.**
- **Deactivation revokes access, it does not black out the account.** A
  deactivated user cannot log in, cannot refresh a token, and cannot change
  their password; `get_access_scope` refuses them with a 401, so every route
  that reads or writes project data is closed to them on the next request even
  with a valid token. What still answers is `GET /auth/me`, for an unexpired
  access token they already hold -- it resolves the token without re-reading
  `Inactive`. It returns their own account details and nothing else, and the
  token expires on its own schedule. If you need the account shut immediately
  rather than on expiry, deactivation is not the tool.
- **Deactivation is not absolute against OIDC.** A deactivated password-only
  account has `EmployeeIdentifier = NULL`, and the OIDC existing-account lookup
  matches on that column, so such an account is invisible to it. With
  `EYENED_OIDC_CREATE_NEW_ACCOUNTS=true` the same human can sign in through the
  IdP under a different username and receive a **new, active** account. Three
  things bound it: the setting defaults to `False`; an exact username match is
  refused with 409 rather than linked; and the new account holds no
  memberships, so it reaches no project data until someone grants it. Verified
  by execution.
- **Objects touching no projects are unrestricted.** 3 tasks and 230 subtasks
  hold no images today, and every task is empty between creation and its first
  image. Any authenticated user can see, modify and delete them. Accepted in
  v0.3 to keep the rule one sentence long.
- **Adding an image can evict collaborators.** Adding an image from a new
  project narrows who can see the task; anyone lacking the new project loses all
  of it. Nothing is deleted and nothing leaks, but grading in progress can
  become unreachable to the people doing it. `eorm grant-for-task` and the
  `projects` field on `TaskGET` are the remedies.
- **Removing an image can widen access.** When the last image of a project
  leaves a task, subtask comments and grading state recorded while it spanned
  more become visible to users who could not see them before.
- **15 mis-scoped `FormAnnotation` rows** land in the wrong project's scope
  until a DBA script runs. `Patient.ProjectID` is the sole project authority, so
  a row whose `PatientID` disagrees with its image surfaces to the wrong
  project's members. Nothing here stops the population growing (the write-time
  guard was dropped, 2026-08-10). Two things bound it. For a grader, both sides
  of a new mismatch must already be in reach — the create path checks the
  patient's project at `grader` and resolves the image through a scoped read —
  so what remains is an authorised user mislabelling data they can already see,
  not an escalation. For an **administrator, and for any deployment running
  `public_auth_disabled`, neither check applies at all**: admins are unbounded by
  construction, so an admin-authenticated client can still write a mismatched
  row freely. That is the case the dropped guard would have caught, and the one
  to re-open if the row count keeps climbing.
