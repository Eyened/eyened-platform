# Alembic squash cutover — deploying `orm_baseline`

Follow this once per site: the first time you deploy a release built on top
of `orm_baseline`, the new single-revision Alembic root. It replaces a
24-revision migration chain. Do the steps **in the order below**. Getting the
order wrong can destroy a production schema — read this whole document before
you run anything.

## 1. What this is

The 24 revisions under `orm/migrations/alembic/versions/` that predate this
release are replaced by one root revision, `orm_baseline`. `orm_baseline`
builds the same schema those 24 revisions built together; nothing about the
resulting tables and columns changes. What changes is the chain itself: there
is no `down_revision` path from any of the 24 old revision IDs to
`orm_baseline`. A database that Alembic still considers to be on one of those
old IDs cannot `upgrade` its way onto `orm_baseline` — it has to be walked to
head under the *old* chain first, before that chain disappears from the
checkout.

This runbook is that walk. Run it once per site, against that site's own
database.

## 2. The one rule: run `alembic upgrade head` BEFORE you deploy

> **On your current checkout — the one you are running today, before pulling
> this release — run `alembic upgrade head`. Do this before you deploy the
> new release. Not after.**

The release you are about to deploy contains only `orm_baseline`; the 24
legacy revision files are gone from it. If you deploy first, there is no
longer a checkout on disk that can walk your database up to head — you would
have to go find the old chain again (see step 7). Doing it in the order below
avoids that entirely: upgrade first, on the code you already have, then
deploy.

## 3. Do not stamp before upgrading

`alembic stamp orm_baseline` does not inspect the database. It writes one row
saying "this database matches `orm_baseline`." If you run it against a
database that has not first been upgraded to head, you are asserting it has
every table and column `orm_baseline` creates — including the `AuditLog`
table, the `ProjectMember` table, and the `Creator.IsAdmin` /
`Creator.Inactive` columns. It will not have them, and stamping does not
create them. Nothing will ever revisit this database to create them either:
the squash deleted the only revisions that contained that DDL. The
application will start and will fail, at whatever moment it first touches the
missing table or column, with no migration left that can fix it.

## 4. Do not run `Base.metadata.create_all()` to recover

If you do stamp too early, the instinct is to run `Base.metadata.create_all()`
to fill in whatever is missing. Do not. `create_all()` creates missing
*tables* — so it would create `AuditLog` and `ProjectMember` — but it has no
`ALTER` path, so it silently skips missing *columns* on tables that already
exist. `Creator` already exists, so `IsAdmin` and `Inactive` are silently
skipped, and `create_all()` reports nothing wrong. The database is still
broken, and now it looks fixed. If you find yourself in this situation, use
Rollback (step 8) and then Recovery (step 7), not `create_all()`.

## 5. The four steps, per site

Run Alembic from `orm/migrations` (or wherever your checkout keeps
`alembic.ini`; see `orm/migrations/README.md`). `alembic upgrade` prompts for
confirmation of the target database before it runs — read it, it is your last
check that you are pointed at the right database. `alembic current`,
`alembic check`, and `alembic stamp` do not prompt. To target a specific
environment file, add `-x env_file=/path/to/.env`.

| # | Command | Character |
|---|---|---|
| 0 | `alembic current` and `alembic check`, recorded | rollback anchor |
| 1 | `alembic upgrade head` on the **current** checkout | real DDL — backup and window |
| 2 | deploy the release | — |
| 3 | `alembic stamp orm_baseline` | one row, no DDL |
| 4 | `alembic current`, `alembic check` | clean = done |

Write down the output of step 0 before doing anything else — the revision ID
it prints is what step 8 (Rollback) stamps back to if you need it.

## 6. What step 1 actually does

`alembic upgrade head` in step 1 runs real DDL, not a formality. It:

- creates the `AuditLog` table, plus its two indexes (`ix_AuditLog_ActorID`,
  `ix_AuditLog_Timestamp`);
- creates the `ProjectMember` table;
- alters `Creator` twice, adding `IsAdmin` then `Inactive`;
- drops and recreates five tag foreign keys — on `StudyTag`,
  `ImageInstanceTag`, `AnnotationTag`, `SegmentationTag`, and
  `FormAnnotationTag` — changing them from `ON DELETE CASCADE` to
  `ON DELETE RESTRICT`. (`CreatorTag` is deliberately not touched; it keeps
  cascading.)

Scope your maintenance window and your backup around this list, not around
the deploy in step 2. Take the backup immediately before running step 1.

**If step 1 fails partway through, do not re-run `alembic upgrade head` over
the result.** MySQL DDL is not transactional, so a failed upgrade can leave
the schema partially migrated — some of the tables above created, others not.
Recovery is to restore the backup you took before step 1 and retry from a
clean state, not to resume on top of the partial result.

## 7. Recovery if you deployed out of order

If the release ends up deployed before step 1 ran — the checkout on disk now
has only `orm_baseline`, and your database is still stamped at one of the 24
legacy revision IDs — Alembic cannot resolve the site's current revision
against that checkout, and every command fails immediately with:

```
Can't locate revision identified by '<id>'
```

Nothing has been damaged. This failure happens during revision resolution,
before any migration runs. To recover: check out commit `6c675e5` (it carries
all 24 legacy revisions), run `alembic upgrade head` from that checkout, then
redeploy the release and run `alembic stamp orm_baseline` as normal.

## 8. Rollback

**Rolling back after step 3 (the stamp) is exact**, because step 3 ran no
DDL — it wrote one row. To roll back: revert the deployed code to the
previous release, then run `alembic stamp <the revision ID recorded in step
0>`. That puts the `alembic_version` row back exactly where it was; the
schema was never touched by the stamp in either direction.

**Rolling back step 1 (the upgrade) is not the same kind of operation.** The
legacy revisions do have real `downgrade()` bodies, but running them drops
the `AuditLog` and `ProjectMember` tables and drops the `Creator.IsAdmin` /
`Creator.Inactive` columns — including any data written to them since step 1
ran. Do not run `downgrade` reflexively. If you need to undo step 1's DDL,
restore the backup taken before it, rather than downgrading over live data.

## 9. Expect `alembic check` to report drift after stamping — this can be correct

If a site already had schema differences from head before this cutover —
differences `alembic check` would have reported before this release too —
those same differences will still be there after step 3, and step 4's
`alembic check` will still report them. **That is expected, not a failed
release.** The cutover does not fix pre-existing drift; it only replaces the
chain. Compare step 4's output against what you recorded in step 0: if the
drift is the same drift, the deployment worked. Do not roll back a working
deployment because `alembic check` is not clean, if it was equally not clean
at step 0.

## 10. Foreign-key constraint names now diverge — permanently and harmlessly

Production databases keep the `<table>_ibfk_N` constraint names MySQL
assigned in the order the 24 legacy revisions created them. A database built
fresh from `orm_baseline` gets the same foreign keys, but `orm_baseline`
declares its tables alphabetically, so MySQL numbers them alphabetically too
— a different order, so the numbers differ. `alembic check` compares foreign
keys by signature (columns, referenced table, `ON DELETE` action), not by
name, so it does not report this as drift. It is permanent — nothing will
ever bring the numbering back in sync — and harmless.

The one rule this imposes going forward: a future hand-written migration must
never hard-code an `_ibfk_N` name. A name that is correct against a fresh
development database can point at a different constraint on a production
database that went through this cutover. Discover the name at runtime
instead — reflect it with `sa.inspect(op.get_bind()).get_foreign_keys(table)`,
the way `2026_07_30-restrict_tag_deletes.py` does, or drop by column set.
