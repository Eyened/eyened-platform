# Documentation that readers cannot reach: the publish boundary is in the wrong place

- **Source:** Diátaxis triage of the whole documentation corpus, 2026-09-21 (four parallel
  reviewers: deployment spec, ORM section, API section, viewer + top-level + repo-side).
  Scoped out of the `deploy/` documentation consolidation, which fixes one instance of this.

**Status:** open

## What

Only `docs/src/content/docs/` is published. Everything else in `docs/` ships in the repo and
reaches no reader. Four bodies of material are stranded, and published pages point at all of them:

| Stranded | Size | Pointed at from |
|---|---|---|
| `docs/runbooks/2026-08-20-alembic-squash-cutover.md`, `docs/runbooks/2026-08-25-task-project-declaration-cutover.md`, and the cutover half of `docs/rbac-operations.md` — the whole upgrade procedure for the current release | 3 files | `release_notes.mdx:237-239` ("read all three before you start"), `:281`, `orm/development.mdx:160` |
| `orm/eyened_orm/README.md:195-737` — per-class column, constraint and relationship reference | 737 lines | nothing. Written in Starlight directives (`:::note`) and site-absolute links, so GitHub renders the directives literally and the links 404 |
| `docs/point-widget-schema-examples.md` — `x-eyened-widget: keypoint` reference, 7 worked examples | 282 lines | `orm/form_schemas.mdx:125`, via `../../../point-widget-schema-examples.md`, which is wrong by one level *and* unservable (`.md` outside the content collection) |
| `docs/rbac-operations.md:137-151, 230-316` — "RBAC ships inert" + the accepted-risk register | ~85 lines | `guides/access_control.mdx:10`, `orm/cli.mdx:83` — the latter makes reading it a precondition for a destructive `grant-all` |

Also stranded-adjacent, and simply obsolete:

- `PULL_REQUEST_SUMMARY.md` — **delete.** Last commit `ffd8477c`, 2025-09-22; line 80 is a literal
  `*Generated on: $(date)*`; line 31 claims "Moved to SQLModel" (the ORM is plain SQLAlchemy
  `Base`, `orm/eyened_orm/attributes.py:139`); line 28 names a migration the `orm_baseline` squash
  deleted. Verified 2026-09-21.
- `docs/attributes-model-enhancement-plan.md` — **delete or mark done.** Fully implemented, 7/7
  checkboxes unticked (`:321-327`); all five proposed tables exist at
  `orm/eyened_orm/attributes.py:139,177,361,374,403`.
- `docs/src/content/docs/client/etdrs_panel.mdx` — orphaned 8-line "(moved)" stub from `b7d325bf`.
  Not in `astro.config.mjs`; `git grep etdrs_panel` returns zero hits. Delete and add an Astro
  `redirects` entry (none is configured today).

## Why

Link hygiene *inside* the published tree is perfect — **74 of 74** internal links resolve,
including four deep anchors. **Every** broken reference in the corpus crosses the publish
boundary. This is not neglected documentation; it is documentation on the wrong side of a line.

The sharpest cost is the sysadmin's: the upgrade procedure for the current release is a 45-minute
outage (`release_notes.mdx:127-128`) whose steps exist only in the git repo, while the site tells
the reader to go read them. Second sharpest is the ORM's: the site has no column-level reference
for `Project`, `Patient`, `Study`, `Series` at all, and the 737 lines that would supply it sit in
a Python package.

`2026-08-21-rbac-operations-doc-has-two-homes.md` is the same problem, filed earlier and narrower;
close it into this one when this is picked up.

## Notes for whoever takes it

`docs/rbac-operations.md` is three documents, not two: the one-time cutover (`:16-135`), the
permanent accepted-risk register (`:137-151`, `:230-316`), and contributor how-to (`:153-213`).
They have three different destinations. Its Commands table (`:215-228`) already moved to
`orm/cli.mdx#users-and-access` and should just be deleted.

`docs/README.md:31-36`'s release checklist covers the site only and never mentions `docs/runbooks/`
or `docs/rbac-operations.md` — part of why they drifted. Whatever is decided, put it there.
