# Deploy slim-down: final-review findings not yet fixed

- **Source:** whole-branch review of the compose-only slim-down on PR #202 (`5c34b234..895e70f8`).
- **Files:** `deploy/README.md`, `deploy/.env.example`, `deploy/compose.storage.example.yaml`,
  `docs/src/content/docs/{getting_started,guides/development_setup,release_notes}.mdx`,
  `docs/rbac-operations.md`, `.github/workflows/deploy-validate.yml`.

---

**Status:** open

Deleting `./eyened` and `deploy/scripts/` also deleted three protections the shell gave
implicitly. The new docs lose them without saying so. All three are doc fixes.

## Important

1. **`deploy/.env` ends up readable by any user on the host.** The old `lib.sh` wrote it at mode
   600 because it holds five secrets. Every documented first run is now `cp .env.example .env`,
   which gives 644 or 664 depending on umask. On a shared host, anyone who can read
   `EYENED_API_SECRET_KEY` can forge an admin JWT. Fix: `cp .env.example .env && chmod 600 .env`
   in `deploy/README.md` (First run and GPU host), `getting_started.mdx`,
   `development_setup.mdx` and `docs/rbac-operations.md`.

   **Status: DONE.** `chmod 600 .env` is now documented unconditionally at all four copy sites
   (`deploy/README.md`, `getting_started.mdx`, `deployment/development.mdx`,
   `docs/rbac-operations.md`). The unconditional-versus-shared-host question is settled as
   unconditional: the file holds five secrets and a conditional instruction is one a reader skips.
2. **Workers on the platform host lose their dataset mounts.** `gen-storage.sh` added every worker
   service to the mounts whenever `compose.workers.yaml` was loaded. Now those entries ship
   commented out in `compose.storage.example.yaml`. But the workers still receive
   `EYENED_STORAGE_MOUNTS`, so they read `/data/<key>/…`, which their containers do not have.
   Thumbnail (`default` queue) and inference jobs then fail, visible only in the RQ logs. Fix:
   - add a step to README "Image datasets" and a line to "Workers": with `compose.workers.yaml`
     in `COMPOSE_FILE`, uncomment the worker entries in `compose.storage.yaml`;
   - reword the example file's comment from a restriction into that instruction.
3. **Automatic migration on every `up` is not flagged as a breaking change.** The old
   `bootstrap.sh` never migrated an existing database. `init` now applies pending migrations on
   every `up`, and MySQL cannot roll back DDL. This bites hardest on a dev stack, whose `init`
   runs the mounted `orm/`: pointed at a shared database, it applies unmerged migrations there.
   Fix: add a "Breaking" bullet to the release notes, and one sentence to the README's
   external-database paragraph and to the development guide: set `EYENED_AUTO_MIGRATE=false` for
   a stack pointed at a shared or production database.

## Minor

- ~~`deploy/.env.example:21-22`: "Compose refuses to start while one is empty" is false for
  `EYENED_API_ADMIN_PASSWORD`. Compose leaves it optional, and `init` fails instead, only on an
  empty database.~~ **FIXED 2026-09-21**: the sentence is now scoped to the four `:?` variables,
  and `EYENED_API_ADMIN_PASSWORD` carries its own note. Six variables are `:?` in total; the
  fourth-and-sixth gap is `EYENED_DATABASE_USER` (not a secret) and `KEYCLOAK_ADMIN_PASSWORD`
  (OIDC layer only).
- `release_notes.mdx` (`eorm` confirmation-prompts bullet): "which is what makes an unattended
  first-run bootstrap possible" is stale. `eorm bootstrap` calls `upgrade_to_head` directly. Drop
  the clause.
- The upgrade path has never run end to end: rebuild, `init` recreated with the new image,
  migration of a schema behind head. Only a fresh database and an idempotent re-run were shown.
  If compose did not recreate `init`, the old image would exit 0 without migrating, a silent
  success. Check it once by hand before the release upgrade guide relies on it.
- CI builds only the prod images (server and fileserver). The dev `client` image, which
  depends on the `.dockerignore` re-include of `deploy/entrypoint-client.sh`, and the worker
  images are never built.
- The CI smoke job asserts nothing about seeding. Add `SELECT COUNT(*) FROM FormSchema` > 0.
- `docs/rbac-operations.md:207`: the new-developer checklist never says to switch `.env` to the
  dev `COMPOSE_FILE`.
- `getting_started.mdx`: the example `- /data/my-dataset:/data/my-dataset:ro` uses the same path
  on host and container. Use `/srv/datasets/my-dataset`, as the example file does.
- `deploy/README.md` (external database): `MYSQL_ROOT_PASSWORD` must still be set, because
  interpolation covers profile-disabled services.
- `bootstrap.py`: prints "Empty database" whenever `alembic_version` is missing, even when the
  database has tables. The migration then fails loudly, so only the log line misleads.
