# Unreleased

Changes merged since v2026.09.0. This section is renamed to the version heading when
the next release is cut. Add an entry here in the same pull request that changes
behaviour — reconstructing it at release time is how things get missed.

---

# EyeNED Platform v2026.09.0

Per-project access control is now enforced, tasks declare the projects they span, and the
API serves requests concurrently for the first time. This release is also relicensed
under AGPL-3.0.

**This release cannot be deployed as a rolling upgrade.** It needs a planned outage of
roughly 45 minutes plus backup time. Read the upgrade notes before you start.

## Highlights

- **Per-project access control is enforced** (#195). v2026.08.0 shipped the service layer
  as preparation; permissions are now checked on every request. Each project membership
  carries one of `read_only`, `grader`, or `project_admin`; platform administrators are
  data superusers. Scope is re-read from the database per request, so grants and
  revocations take effect on the user's next request without re-login. There is no
  feature flag — rollback is redeploying the previous server.
- **Tasks declare their projects** (#222). A task's project span used to be derived by
  walking every image up to its patient. It is now declared in a new `TaskProject` table,
  which is authoritative for visibility. Existing tasks are backfilled automatically.
- **The API serves requests concurrently** (#219). 69 route handlers ran synchronous
  database calls on the event loop, so each worker served one request at a time and one
  slow query froze the rest (#61). They now run in a threadpool.
- **The tasks page is fast** (#212). `GET /api/task` went from ~15.0 s to ~2.0 s of SQL.
- **Task status in the grading window** (#225). The full-screen task overlay is replaced
  by a collapsible column beside the top-row thumbnails, carrying set navigation, subtask
  status buttons, comments, and a link to the task overview.
- **Tasks can drive the viewer layout** (#178). `TaskDefinition.TaskConfig` can hide
  builtin side panels, prepend a `quick-form` panel, configure the task panel, and set
  point-marker appearance.
- **Claim subtasks** (#178). Task pages gain Claim / Unclaim per row,
  claim-all-unassigned, an assignee column, and status/assignee filters. Editing comments
  or creating an annotation auto-claims an unassigned subtask; it never steals an
  assigned one.
- **DICOM export** (#214). A new `eyened_orm.export` module writes selected images as
  Secondary Capture DICOM, with optional pseudonymisation and per-patient date offsets.
- **Warp segmentations into image space** (#229). `SegmentationBase.warp_to_image()`
  projects a 2D mask back into the original image's pixel space.
- **Relicensed under AGPL-3.0** (#215), from GPL-3.0.
- **One Alembic baseline** (#216). The 24 legacy revisions are squashed into
  `orm_baseline`.

## Changed behaviour

Things that worked one way in v2026.08.0 and work differently now.

**Viewer**

- **Masking is on by default** (#211). A grader segmentation with a reference mask now
  renders intersected with it; previously it rendered unmasked. A new Intersection button
  sits next to the eye icon in the Segmentation panel row, and the choice is remembered
  per image.
- **Linking the cursor from a thumbnail needs Shift** (#224, #227). Hovering a main viewer
  always moves the linked cursor and OCT B-scan, including while Shift-panning. Hovering a
  top-row thumbnail does nothing unless Shift is held. Neither updates while a mouse
  button is down.
- The task overlay is gone, replaced by the task panel described above (#225).

**Permissions**

- Reading anything outside your projects returns **404**, not 403 — a 403 would confirm
  the row exists.
- **Modifying another user's annotation is refused** (403), administrators included.
- **Deleting another user's annotation, or deleting a populated task, requires project
  admin.**
- **Adding an image from a project a task does not declare is refused** with 409
  `image_outside_task_declaration`. Extend the task's declaration first.
- **Removing an image no longer widens access.** "Unlink the image to restore access" used
  to work and now silently does nothing. Use `eorm grant-for-task` instead.
- A task is visible only to users holding **every** project in its declaration, so a broad
  declaration hides it from everyone else from the moment it is created. Declarations
  cannot be narrowed in this release.

**API**

- **`GET /api/task` no longer returns project spans by default.** `projects` is `null`
  unless you pass `?include_projects=true`; `null` means "not requested", not "spans
  nothing". `GET /api/task/{id}` still populates it.
- **Two unscoped routes were removed**: `GET /api/instances/images/{...}` and
  `GET /api/instances/thumbnails/{...}`. They authenticated but did not scope, so they
  served other projects' pixels. Use `GET /images/{id}/data` and
  `GET /images/{id}/thumbnail`.
- **`POST /task` requires a non-empty `projects` list**, and `grader` in every project in
  it.
- New: `GET /task/{id}/subtask-assignees`; `unassigned` and `creator_id` filters on
  `GET /task/{id}/subtasks`; `claim` on `PATCH /subtasks/{id}`, which returns 409
  `subtask_already_claimed` if someone else holds it.
- `GET /import/status/{task_id}` now requires authentication.

**CLI**

- **`eorm initialize-database` runs the migration trail to head** instead of creating
  tables and stamping. The database must already exist; `--recreate` drops and creates it
  first.
- `eorm create-user` exits non-zero on a duplicate username instead of printing and
  exiting 0.
- New administration commands: `init-admin`, `grant`, `revoke`, `grant-for-task`,
  `grant-all`, `set-admin`, `set-password`, `deactivate`, `reactivate`,
  `check-declarations`, `check-dangling-references`.

## Bug fixes

- Fundus/OCT registrations did not load: device `PhotoLocators` were being dropped from
  `ImageGET.attrs` (#227).
- Deleting a tag that is still applied returns 409 instead of 500, and the database
  refuses the delete outright (#195).
- `POST /auth/register` with a taken username returns 409 instead of 500 (#195).
- Form saves that fail now raise a toast instead of sticking on "saving"; debounced saves
  flush when the window closes; blank B-scan indices are rejected (#178).
- ETDRS ring masks are computed as independent distance bands, so building the 3 mm grid
  no longer materialises all three rings (#223). Measured areas and counts are unchanged.

## Upgrade notes

This release layers three cutovers that were designed as separate deployments: the Alembic
squash, the RBAC flip, and the task-project declaration. Run them as **one window**, in
this order. Detail for each step is in its runbook — read all three before you start:
`docs/runbooks/2026-08-20-alembic-squash-cutover.md`, `docs/rbac-operations.md`, and
`docs/runbooks/2026-08-25-task-project-declaration-cutover.md`.

**Before the window, with the site still up**

1. `eorm check-dangling-references` — must print
   `No dangling references (5 hops checked).` If it does not, reconcile first. Left alone,
   the migration chain dies part-way through the window with
   `ERROR 1138 Invalid use of NULL value`, which names no table, column, or row.
2. `alembic current` on your current checkout — expect exactly one revision you recognise.
3. Confirm on the target database: strict `sql_mode`, `binlog_format=ROW`,
   `foreign_key_checks=1` (never disable it), and free disk of at least the size of
   `ImageInstance` plus 17% of the schema.

**In the window — stop the application *and* the importer first**

4. Take a full backup.
5. On your **current (old)** checkout: `alembic upgrade head`. This creates `AuditLog` and
   `ProjectMember`, adds `Creator.IsAdmin` and `Creator.Inactive`, and flips five tag
   foreign keys to `ON DELETE RESTRICT`. Verify `alembic current` prints
   `b2e2800000b2 (head)`. **Do not go further until it does** — deploying past this point
   strands the database, because the revisions it still needs are no longer on the trail.
6. Deploy the new release, but **do not start serving traffic**. The new code cannot read
   the database until step 9 finishes.
7. `alembic stamp --purge orm_baseline` (`--purge` is required — the squash drops the
   pre-cutover id from the revision map). Verify `alembic current` prints
   `orm_baseline` — without `(head)`, because step 9's five revisions sit above it.
8. Stop the database and copy its data directory. **This copy is the only rollback path
   for the next step.** With the server stopped the copy is consistent by construction.
   Start the database again.
9. `alembic upgrade head` — applies five revisions ending at `2db0e63195db`, denormalizing
   `ProjectID` down the patient chain and creating `TaskProject`. **This is the long step:
   28 min 47 s measured at dev scale**, dominated by InnoDB rebuilding `ImageInstance` and
   `Series`. Verify `alembic current` and `alembic check`.
10. Bootstrap access control, still before traffic:
    - `EYENED_API_ADMIN_PASSWORD='...' eorm init-admin --username <EYENED_API_ADMIN_USERNAME>`.
      **Set the password.** Omitting it stores `'!'` — a valid hash that verifies nothing —
      and you get an administrator who can never log in.
    - `eorm grant-all` — grants `grader` in every project to every active human account.
    - **Review the result before announcing.** `POST /auth/register` needs no
      authentication and self-registered accounts match the grant filter exactly, so anyone
      who registered before the cutover receives `grader` everywhere. The confirmation
      prompt names no one and counts no one, and totals print after the commit. Run the
      review query in `docs/rbac-operations.md` step 4 and remove anyone you do not
      recognise with `eorm revoke --user <U> --all`.
11. Start the application and the importer.
12. Verify: `eorm check-declarations` (record what it reports; do not act on it), and open
    the tasks page as a non-admin member to confirm they see the tasks they expect.

**Rollback** is redeploying the previous release and restoring the backup — at every
point. Do not use `alembic downgrade`: downgrading past `99724789b34d` drops `TaskProject`,
which cannot be reconstructed for any declaration broader than a task's images.

**Also required**

13. **Reinstall `eyened_orm`** — this release adds `passlib` and `argon2-cffi`.
14. **Review your database connection budget** before raising `WORKERS`. Each API process
    can now open `EYENED_API_POOL_SIZE + EYENED_API_MAX_OVERFLOW` = 20 connections, so
    `WORKERS=4` is 80 from the API alone against MySQL's default `max_connections` of 151.
    The server also **refuses to boot** if `EYENED_API_THREADPOOL_LIMIT` exceeds pool size
    plus overflow; lower all three together.
15. Keep `EYENED_API_PUBLIC_AUTH_DISABLED=false` in production. The dev bypass now promotes
    its account to administrator.

**What this does and does not restrict.** Granting everyone `grader` everywhere writes down
the status quo rather than escalating it — any authenticated user could already do all of
this. But until memberships are pruned to the intended list, **the mechanism is enforcing a
policy that permits nearly everything**. Pruning needs the consortium's membership list; it
cannot be derived from a query, because users who only read are indistinguishable under the
bulk grant.

## New settings

| Setting | Default | Purpose |
|---|---|---|
| `EYENED_API_ADMIN_USERNAME` | `admin` | Names the account `eorm init-admin` bootstraps |
| `EYENED_API_ADMIN_PASSWORD` | — | Read by `eorm init-admin`, not by the server |
| `EYENED_API_THREADPOOL_LIMIT` | 16 | Threadpool size for synchronous route handlers |
| `EYENED_API_POOL_SIZE` | 16 | SQLAlchemy pool size (API only) |
| `EYENED_API_MAX_OVERFLOW` | 4 | SQLAlchemy overflow connections |
| `EYENED_API_POOL_TIMEOUT` | 5 s | Wait before a connection checkout fails |
| `EYENED_API_PASSWORD_HASH_CONCURRENCY` | 4 | Caps concurrent Argon2 hashes on the login routes |
| `EYENED_ALEMBIC_ASSUME_YES` | unset | Skips Alembic's confirmation prompt for non-interactive runs |
| `EYENED_DATABASE_BUFFER_POOL_SIZE` | — | Sets `innodb_buffer_pool_size`; takes effect when the container is recreated |

## Documentation

- [Release notes](https://eyened.github.io/eyened-platform/release_notes/)
- [Getting started](https://eyened.github.io/eyened-platform/getting_started/)
- [DICOM export](https://eyened.github.io/eyened-platform/orm/dicom_export/)
- [Tasks](https://eyened.github.io/eyened-platform/orm/data_model/tasks/)
- [Platform design](https://eyened.github.io/eyened-platform/platform_design/) — API concurrency

---

# EyeNED Platform v2026.08.0

Viewer bookmarks and enface overlays, a service/repository layer with an append-only audit log (RBAC prep), a CFI inference rewrite, CI on client and server, and several viewer/ORM reliability fixes.

## Highlights

- **Viewer view-state** — open main viewers and frame indices persist in the URL (`v=`) and localStorage, and restore after reload (#198).
- **Enface overlays on registered images** — GPU registration hops map enface projections onto linked images; photolocator hit-specs cover raster, radial, and circular locators (#177, #194).
- **Pre-RBAC server architecture** — routes go through repositories and services; mutations write an in-transaction `AuditLog`; session ownership is explicit (#134, #139, #145, #165, #171). Per-request authorization is not enabled yet.
- **CFI inference rewrite** — `eorm run-cfi-models` with ModelInputSpec, automatic model versions, failure tracking, streaming/chunked targets, and deadlock retry (#158).
- **CI** — client Vitest/build/Prettier/ESLint and server pytest run on push/PR into `development` and `main`.
- **CODEOWNERS** — repository-wide review by `@Eyened/platform-core`.

## Bug fixes

- Oversized DICOM volumes and enface/OCT stretch (#196 / #173).
- Patient registration on the task viewer route (#144).
- CirclePhotoLocator viewer crash (#157).
- Multiclass erode/dilate (#131).
- PNG series path resolution defaults to index 0 (#191).
- Copy image public ID from browser and viewer (#140, #143).
- Unused `mysql-connector-python` removed (#199).
- Registration processing exception handling (#147).

## Upgrade notes

1. **Run database migrations** before starting the new server containers. This release adds `AuditLog`.
2. **Reinstall `eyened_orm`** after pulling this release.
3. Prefer **`eorm run-cfi-models`**; legacy CFI inference writers were removed.
4. Do not depend on **`mysql-connector-python`**.
5. Authentication (password + optional OIDC) is unchanged from v2026.07.0.

## Documentation

- [Release notes](https://eyened.github.io/eyened-platform/release_notes/)
- [Getting started](https://eyened.github.io/eyened-platform/getting_started/)
- [CFI / inference](https://eyened.github.io/eyened-platform/orm/inference/)
- [Attributes](https://eyened.github.io/eyened-platform/orm/data_model/attributes/)
