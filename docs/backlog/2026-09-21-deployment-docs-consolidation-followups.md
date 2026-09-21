# Deployment docs consolidation: final-review findings not yet fixed

- **Source:** whole-branch final review of the deployment-docs consolidation
  (`.superpowers/sdd/dc/final-review.md`), applied 2026-09-21. This entry covers the findings the
  approved fix wave deferred; the eight fixes it did apply (C1, I1, I2, I3, I4, I6, M2, M3) are not
  repeated here.
- **Files:** `docs/src/content/docs/getting_started.mdx`, `docs/src/content/docs/deployment/{index,production,operations}.mdx`,
  `docs/src/content/docs/platform_design.mdx`, `deploy/compose.yaml`, `deploy/compose.workers.yaml`.

---

**Status:** open

## Important

- **I5 — two competing production install procedures.** `getting_started.mdx` and
  `deployment/production.mdx` each document a full production install and disagree: `HTTP_PORT` is
  absent from one and required in the other, the browse URL differs (`localhost:8080` vs
  `<host>:<HTTP_PORT>`), and secret naming differs between the two. Neither page is marked
  authoritative, so a reader who lands on either has no signal that a second, divergent procedure
  exists. Separately, the better upgrade procedure (`git rev-parse` pinning plus the inline
  xtrabackup commands) sits on the `getting_started.mdx` tutorial rather than on
  `operations.mdx`, where an operator upgrading a running stack would look. Deferred because a real
  fix means restructuring `getting_started.mdx` into a single-source tutorial that defers to
  `deployment/` for reference material, which the consolidation plan explicitly put out of scope.

## Out of scope (do not fix without a separate decision)

- **Dangling README references in compose files.** `deploy/compose.yaml:2` and `:53`, and
  `deploy/compose.workers.yaml:1`, still cite `README.md` sections that were deleted when the
  README became a 28-line stub. The current fix wave was explicitly forbidden from touching
  `deploy/compose.yaml` or `deploy/compose.workers.yaml`, so these are left dangling on purpose
  pending a follow-up that is allowed to edit them.

## Minor

- **M1 — `operations.mdx` duplicates itself.** §Routine backups and §Backup and restore both say
  "back up before migrating," and both give external-database and platform-storage guidance
  separately. Worth collapsing into one statement of each, cross-referenced rather than repeated.
- **M4 — `production.mdx` §Sizing restates `platform_design.mdx`.** The connection-budget numbers
  (80 / 151 / the threadpool validator) are duplicated rather than linked, against the project's
  "link out, do not restate" convention for this consolidation. This text is plan-mandated
  verbatim, so changing it is a decision for whoever owns that plan, not a cleanup — flagging here
  rather than editing. The arithmetic itself was checked and is correct.
- **M5 — `index.mdx` never names the services.** The old `deploy/README.md` opened by naming
  `init`, `server`, `fileserver`, `database` and `redis` — names a reader needs to type into
  `docker compose logs <service>` or `docker compose exec <service> ...`. The new `index.mdx` never
  lists them, so the unpublished README stub is currently the better service overview.
- **M6 — `development.mdx`'s `## Contributing` section doesn't belong and is stale.** It documents
  repo process (branch/PR workflow), which serves none of a Deployment-group page's goals, and it
  is factually stale: it tells contributors to branch and PR against `development`, but the
  repository's default branch is `main`. Its "Never commit secrets" line is deployment guidance
  and belongs up in §Configure `deploy/.env` instead. `## Tests` is more weakly justified on this
  page but is defensible as-is. Both sections were inherited unchanged from
  `guides/development_setup.mdx` when it moved, which was the correct call for a move — this is a
  follow-up restructuring, not something the move itself should have done.
