# Alembic squash cutover — deploying `orm_baseline`

**Contact:** `<contact>` — if anything you see while running this differs
from what this document describes, stop before running anything else and
reach out. Do not improvise a fix; several of the wrong ones look like they
worked (see §4).

Follow this once per site: the first time you deploy a release built on top
of `orm_baseline`, the new single-revision Alembic root. It replaces a
24-revision migration chain. Do the steps **in the order below**. Getting the
order wrong can destroy a production schema — read this whole document
before you run anything.

This document uses **step N** for the numbered rows of the table in §5, and
**§N** for its own section numbers, because the two numberings overlap and
mean different things — a cross-reference always says which one it means.

## §1 — What this is

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

## §2 — The one rule: run `alembic upgrade head` BEFORE you deploy

> **On your current checkout — the one you are running today, before pulling
> this release — run `alembic upgrade head`. Do this before you deploy the
> new release. Not after.**

The release you are about to deploy contains only `orm_baseline`; the 24
legacy revision files are gone from it. If you deploy first, there is no
longer a checkout on disk that can walk your database up to head — you would
have to go find the old chain again (see §7). Doing it in the order below
avoids that entirely: upgrade first, on the code you already have, then
deploy.

## §3 — Do not stamp before upgrading

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

## §4 — Do not run `Base.metadata.create_all()` to recover

If you do stamp too early, the instinct is to run `Base.metadata.create_all()`
to fill in whatever is missing. Do not. `create_all()` creates missing
*tables* — so it would create `AuditLog` and `ProjectMember` — but it has no
`ALTER` path, so it silently skips missing *columns* on tables that already
exist. `Creator` already exists, so `IsAdmin` and `Inactive` are silently
skipped, and `create_all()` reports nothing wrong. The database is still
broken, and now it looks fixed.

There is no self-service fix for "already stamped without upgrading first" in
this document — it isn't one of the situations §7 (Recovery) or §8 (Rollback)
covers. If you find yourself here, stop and contact us (see the top of this
document) instead of reaching for `create_all()` or anything else clever.

## §5 — The steps, per site

Run Alembic from `orm/migrations` (`orm/README.md`). To target a specific
environment file, put `-x env_file=/path/to/.env` **before** the subcommand —
`-x` is a global option, not one `upgrade` or `stamp` accept after the fact:

```bash
alembic -x env_file=/path/to/.env upgrade head
```

Confirmation prompts: `current` and `check` are read-only and never prompt.
Every other command below — **`upgrade` and `stamp` both** — prints
`Target database: ... Proceed? [y/N]` and waits for `y` before it touches
anything. Read it; it is your last check that you are pointed at the right
database. `stamp` prompting is easy to miss if you script it: run step 4
interactively, or export `EYENED_ALEMBIC_ASSUME_YES=1` for that one command —
without a TTY, the prompt raises `EOFError` and the stamp silently does not
happen.

**Take a full backup of the database immediately before step 1.** It is the
only rollback path this procedure has (§8) — there is no other.

| # | Command | Character |
|---|---|---|
| 0 | `alembic current` | precondition check — see below |
| 1 | `alembic upgrade head` on the **current** checkout | real DDL — backup and window |
| 2 | `alembic current` again | gate: must show the legacy head before deploying |
| 3 | deploy the release | — |
| 4 | `alembic stamp orm_baseline` | one row, no DDL — prompts, see above |
| 5 | `alembic current`, `alembic check` | clean = done |

**Step 0 is a precondition check, not a baseline to compare against later.**
It must print exactly one revision id that you recognise as this site's
current position. If it prints nothing (a database that was never stamped,
or one built with `create_all()`), prints more than one, or prints an id you
don't recognise — stop before step 1 and contact us. Do not run
`alembic check` here instead: on a database behind head, `check` errors
(`CommandError: Target database is not up to date.`) before it produces any
diff, so it cannot serve as a starting point at this step.

**Step 2 is a gate, not a formality.** Compare its output to what step 1
reported reaching. A partially-failed step 1 is possible and can go
unnoticed; deploying on top of one walks straight into the trap §3 describes
— once deployed, the checkout that could still run the missing DDL is gone.
If step 2's output doesn't match what step 1 completed, or step 1 showed any
error at all, stop before step 3 and contact us.

**Between step 3 and step 4, Alembic itself cannot resolve this database.**
The deployed checkout contains only `orm_baseline`; the database is still
stamped at the legacy head from step 1, which that checkout's script
directory no longer has. Any Alembic CLI command run against the deployed
checkout during this window will fail to resolve the current revision. That
is expected, and it resolves the moment step 4 completes. This is a claim
about Alembic's own commands only — it says nothing about whether the
application itself is working, which this document has not verified.

## §6 — What step 1 actually does

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

Scope your maintenance window around this list, not around the deploy in
step 3. Take the backup immediately before running step 1 (§5).

**If step 1 fails partway through, do not re-run `alembic upgrade head` over
the result.** MySQL DDL is not transactional, so a failed upgrade can leave
the schema partially migrated — some of the tables above created, others not.
Recovery is to restore the backup you took before step 1 and retry from a
clean state, not to resume on top of the partial result.

## §7 — Recovery if you deployed out of order

If the release ends up deployed before step 1 ran — the checkout on disk now
has only `orm_baseline`, and your database is still stamped at one of the 24
legacy revision IDs — Alembic cannot resolve the site's current revision
against that checkout, and every command fails immediately with:

```
Can't locate revision identified by '<id>'
```

Nothing has been damaged. This failure happens during revision resolution,
before any migration runs. To recover: check out commit `6c675e5` (it carries
all 24 legacy revisions) into an environment with `eyened_orm` installed —
`env.py` imports it, so `alembic` will not run without it — run
`alembic upgrade head` from that checkout, then redeploy the release and run
`alembic stamp orm_baseline` as normal.

## §8 — Rollback

**Rollback is restoring the backup taken before step 1. Nothing more
clever.**

Do not stamp your way back. After a real step 1, the schema is at the legacy
head. Stamping an earlier revision leaves Alembic believing migrations it has
already applied are unapplied, so the next `alembic upgrade head` would try
to replay `CREATE TABLE AuditLog` against a table that already exists —
failing part-way through a production schema. Restoring the backup is the
only route offered here because it returns the schema and the
`alembic_version` row together, in one action, exactly as they were.

If only the *code* needs reverting and step 1 succeeded, that is not a
rollback: redeploy the previous release and leave the database at the legacy
head. Contact us before stamping anything.

## §9 — Expect `alembic check` to report drift after stamping

At a site carrying schema differences from before this cutover, step 5's
`alembic check` will still report them after stamping. **Drift here does not
mean the cutover failed.** Record it and contact us — do not roll back a
deployment because of it.

## §10 — Foreign-key constraint names now diverge, permanently and harmlessly

Production keeps the `<table>_ibfk_N` numbers MySQL assigned as each foreign
key was attached to a given table, over the life of the legacy chain — that
numbering is **per table**, in attachment order, not related to which table
was created first. `2026_07_30-restrict_tag_deletes.py` dropped and
recreated the `TagID` foreign key on the five tables listed in §6, which
moved each of those constraints to the end of its table's numbering. A
database built fresh from `orm_baseline` creates every one of a table's
foreign keys inside that table's single `CREATE TABLE` statement, in
whatever order they're declared there — a different history, so a different
number. `alembic check` compares foreign keys by signature (columns,
referenced table, `ON DELETE` action), not by name, so it does not report
this as drift. It is permanent — nothing will bring the numbering back in
sync — and harmless.

The one rule this imposes going forward: a future hand-written migration must
never hard-code an `_ibfk_N` name. A name that is correct against a fresh
development database can point at a different constraint on a production
database that went through this cutover. Discover the name at runtime
instead — reflect it with `sa.inspect(op.get_bind()).get_foreign_keys(table)`,
the way `2026_07_30-restrict_tag_deletes.py` does, or drop by column set.

## If anything doesn't match

This document describes what should happen at each step. If an output, an
error, or a state doesn't match what's written here — at any point, not only
the ones that name it explicitly — stop before running the next command and
contact `<contact>`. Guessing your way past a mismatch is how a recoverable
situation becomes a destroyed schema.
