# Alembic squash cutover — deploying `orm_baseline`

> **Note to whoever is preparing this document for a site — not to the
> operator running the cutover. Delete this note once you've done this:**
> fill in the contact below before sending this document anywhere.
> `<contact>` is a placeholder, not a value. Several points in this
> document tell the operator to stop and reach out, and all of them depend
> on it being filled in — do not let it ship with nobody named to reach.

**Contact:** `<contact>`

If anything you see while running this differs from what this document
describes, stop before running anything else and reach out to the contact
above. Do not improvise a fix; several of the wrong ones look like they
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
document) instead of reaching for `create_all()` or anything else clever. Do
not run `alembic upgrade head` on the deployed checkout while you wait,
either: that checkout has no legacy chain in it, only `orm_baseline`, so
there is no missing DDL for it to walk your database through — running it
cannot fix this, whatever the current state of `alembic_version` is.

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
only rollback path this procedure has (§8) — there is no other. If you have
not taken one, stop and contact us before running step 1.

| # | Command | Character |
|---|---|---|
| 0 | `alembic current` | precondition check — see below |
| 1 | `alembic upgrade head` on the **current** checkout | real DDL — backup and window |
| 2 | `alembic current` again | **gate: must print `b2e2800000b2 (head)` before deploying** |
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

**Step 2 is a gate, not a formality — state it as an assertion, not a
comparison.** It must print exactly `b2e2800000b2 (head)`, the single legacy
head: among the 24 revisions at `6c675e5`, `b2e2800000b2` is the only one
nothing lists as its `down_revision`, and it is the same constant at every
site. The `(head)` suffix is expected, not a warning — Alembic appends it to
any revision that is the real head of the chain it's being read against, and
at this point in the checkout you're running today, it is. Quoting the
assertion as a bare id would stop a *correct* cutover at its first gate. Do
not fall back on "compare it to what step 1 printed" either — that reduces
the gate to reading terminal scrollback, which fails the operator whose
window has scrolled, or who skipped step 1 entirely, which is exactly the
case this gate exists to catch.

This gate has two distinct failure branches, not one:

- **An earlier revision.** This means the checkout you're running today
  predates the full legacy chain, so `alembic upgrade head` in step 1
  stopped there — correctly, at that checkout's own head, just not the
  site's ultimate legacy head. This is self-service, not an escalation:
  check out commit `6c675e5` (it carries all 24 legacy revisions; §7 has
  more detail on this checkout), run `alembic upgrade head` from there, and
  re-run step 2.
- **Nothing, or an id you don't recognise.** Stop before step 3 and contact
  us. A partially-failed step 1 is possible and can go unnoticed; deploying
  on top of one walks straight into the trap §3 describes — once deployed,
  the checkout that could still run the missing DDL is gone.

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

## §8 — Rollback, split by what actually needs undoing

A single blanket instruction is what made the earlier drafts of this section
wrong — once by telling every rollback to restore the backup regardless of
how much time had passed, which can destroy live clinical data written since
cutover; once by forbidding *all* stamping as a way back, which also rules
out the one stamp that is safe. Which of the three cases below applies
depends on how far the cutover got.

**Code only, step 1 succeeded, before step 4.** If you have already
deployed, redeploy the previous release — the database is already at the
legacy head (`b2e2800000b2`), so change nothing else. If you have not
deployed yet, there is nothing to undo.

**Code only, step 1 succeeded, after step 4.** Redeploy the previous
release, then run `alembic stamp b2e2800000b2` from that checkout. **If you
are not certain step 2 printed the head, do not stamp — contact us
instead**; this whole case depends on step 1 having genuinely finished.
This stamp prompts for confirmation just like step 4 did (see §5): run it
interactively, or set `EYENED_ALEMBIC_ASSUME_YES=1` for it. Done correctly,
it is **exact and lossless**: after step 1 the schema genuinely is at the
legacy head, so this stamp states a true fact rather than an earlier, false
one. Skip it and the old checkout cannot resolve `orm_baseline` — every
Alembic command run against it fails with §7's `Can't locate revision
identified by 'orm_baseline'`, in a situation §7 does not describe (that
section is about deploying too early, not reverting after a completed
cutover).

**Step 1's own DDL must be undone.** **Redeploy the previous release
first**, then restore the backup taken before step 1 — **and only while the
maintenance window is still open, before the new release has taken any
writes.** Restoring underneath a still-deployed new release leaves it
running against the pre-step-1 schema — no `AuditLog`, no `ProjectMember`,
no `Creator.IsAdmin` / `Creator.Inactive` — which is exactly the failure
state §3 exists to prevent; redeploying first avoids that. The restore also
returns `alembic_version` to its pre-step-1 value, which is what the old
checkout can resolve. Once the new release has taken writes, restoring the
backup loses them — past that point, contact us instead of restoring.

Stamping `b2e2800000b2` above is **not** the rollback anchor returning. The
anchor an earlier draft of this document used was a *per-site* value the
operator had to record during step 0 and might not still have on hand hours
later. `b2e2800000b2` is a constant, hardcoded here exactly like `6c675e5` —
every site's legacy chain has the same single head, always. The prohibition
that still holds is on stamping an **earlier** revision: that leaves Alembic
believing already-applied migrations are unapplied, and the next
`alembic upgrade head` would try to replay `CREATE TABLE AuditLog` against a
table that already exists, failing part-way through a production schema.

## §9 — Expect `alembic check` to report drift after stamping

At a site carrying schema differences from before this cutover, step 5's
`alembic check` will still report them after stamping. **Drift here does not
mean the cutover failed.** Record it and contact us — do not roll back a
deployment because of it.

## §10 — Foreign-key constraint names now diverge, permanently and harmlessly

MySQL numbers a table's `<table>_ibfk_N` constraints **per table**, in the
order the foreign keys are attached to that table — and only when no
explicit name is supplied. Alembic renders each table's foreign keys sorted
inside its `create_table` call, so a database built fresh from `orm_baseline`
numbers them in that sorted order: `StudyTag`'s `CREATE TABLE` declares
`CreatorID`, then `StudyID`, then `TagID`, so `TagID` becomes the third.
Production's numbering instead follows the order the constraints were
originally declared across the legacy chain, plus wherever a later migration
added one — a different history, so a different number for the same
foreign key.

**Do not attribute this to `2026_07_30-restrict_tag_deletes.py`'s
drop-and-recreate of the five tag foreign keys.** That migration discovers
each constraint's existing name and passes it straight back into
`op.create_foreign_key(name, ...)` — MySQL only auto-assigns a fresh
`_ibfk_N` number when no name is supplied, so the number those five
constraints already had is preserved, not moved. That migration is the
*correct* example: discover the name, then reuse it, which is exactly the
pattern §10's own rule below asks a future migration to follow.

`alembic check` compares foreign keys by signature (columns, referenced
table, `ON DELETE` action), not by name, so it does not report any of this
as drift. It is permanent — nothing will bring the numbering back in sync —
and harmless.

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

This deliberately repeats the notice at the top of this document rather than
assuming one reading was enough. A procedure whose failure mode is a
destroyed production schema is allowed to say "stop and ask" twice.
