# Documentation

### Fix documentation claims that are wrong against the code
- **Status:** open
- **Source:** documentation triage, 2026-09-21
- **Problem:** breaks a reader's work: `client/panels/etdrs.mdx:31` says right click sets the disc edge, but it deletes the point (`PointTool.svelte.ts`; same error in-app at `EtdrsPanelHelp.svelte:31`); `orm/data_model/attributes.mdx:96` gives slug `etdrs-area`, the name is `"ETDRS area"`; `orm/inference.mdx:27` and `orm/cli.mdx:119` claim `run-cfi-models` scans everything, it defaults to `ColorFundus`; `api/tasks.mdx:16` omits the required `projects`; `api/segmentations.mdx` documents JSON, it is multipart; `api/import.mdx` hides that failures are HTTP 200 `success=False` and that it is admin-only; `api/search.mdx` omits that `order_by` is required and `include_count`.
- **Fix:** correct each page (file:line on both sides in the triage); then the structural ones: `attributes.mdx:84` lost its `#### Registration` heading, `api/index.mdx:10` contradicts `api/reference.mdx:10` on 403 (reference is right).
- **Note:** smaller ones: Argon2 figures in `platform_design.mdx:66` are unset passlib defaults; `platform_design.mdx:48` misses `PUT /form-annotations/{id}/value`; `client/index.mdx:22` marks panels "Always" though `layout.hide` removes them; `orm/development.mdx:36` / `orm/README.md:19` say `from_imagesets` (it is `create_from_imagesets`); `orm/form_schemas.mdx` sends a new deployer to `create-user` instead of `init-admin`. Generating `orm/cli.mdx`'s option tables from Click would stop most ORM drift.

### Move stranded material across the publish boundary
- **Status:** open
- **Source:** documentation triage, 2026-09-21
- **Problem:** only `docs/src/content/docs/` is published, and published pages link out of it: `orm/eyened_orm/README.md:195-737` (column-level ORM reference, no site equivalent), `docs/point-widget-schema-examples.md` (linked from `orm/form_schemas.mdx:125` by a wrong, unservable path), and `docs/rbac-operations.md`'s accepted-risk register (a precondition for `grant-all` per `orm/cli.mdx:83`).
- **Fix:** move each into the content collection; delete `PULL_REQUEST_SUMMARY.md`, `docs/attributes-model-enhancement-plan.md` (fully implemented) and the orphaned `client/etdrs_panel.mdx` stub (add an Astro `redirects` entry). Add the rule to `docs/README.md`'s release checklist.

### Write the missing tutorials and split mixed-mode pages
- **Status:** open (writing, not triage)
- **Source:** documentation triage, 2026-09-21
- **Problem:** no tutorial exists (worst: no grader walkthrough; `orm/getting_started.mdx:81-91`'s closing example does not run). `getting_started.mdx`, `thumbnails.mdx`, `guides/authentication.mdx`, `orm/form_schemas.mdx` and `client/panels/etdrs.mdx` mix modes; `release_notes.mdx` carries ordered upgrade procedure. No server-settings reference exists (concurrency defaults are published in three places). `index.mdx` has no ORM door and demotes the viewer. Six panel pages publish author TODOs.
- **Fix:** a clinician tutorial first; move upgrade steps to an `upgrading/` section; add a settings reference page; one declared reader per page (`orm/development.mdx:8` is the model).

### Tidy the deployment pages
- **Status:** open
- **Source:** deployment-docs consolidation final review, 2026-09-21
- **Problem:** `deploy/compose.yaml:2,53` and `deploy/compose.workers.yaml:1` cite `README.md` sections that no longer exist; `operations.mdx` says "back up before migrating" in both §Routine backups and §Backup and restore; `production.mdx` §Sizing restates `platform_design.mdx`'s connection budget; `deployment/index.mdx` never names the services (`init`, `server`, `fileserver`, `database`, `redis`); `development.mdx` §Contributing is repo process and says to PR against `development` though the default branch is `main`.
- **Fix:** repoint the compose comments to the published pages; collapse the backup advice; link rather than restate §Sizing (check with the plan's owner first — it was mandated verbatim); list the services; move "Never commit secrets" to §Configure `deploy/.env` and drop §Contributing.
