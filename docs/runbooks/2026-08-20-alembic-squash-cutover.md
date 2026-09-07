# Alembic squash cutover — deploying `orm_baseline`

The 24 legacy revisions under `orm/migrations/alembic/versions/` are replaced by one root revision, `orm_baseline`. No `down_revision` path leads from the old ids to it, so each database must be walked to the legacy head **before** the release is deployed. Run this once per site.

## Rules

- Run `alembic upgrade head` on your **current** checkout before deploying, never after.
- Run every Alembic command from `orm/migrations`.
- Put `-x env_file=` **before** the subcommand: `alembic -x env_file=/path/to/.env upgrade head`.
- Take a full backup immediately before step 1. It is the only rollback path — no backup, stop.
- Do not stamp before upgrading — it claims tables whose DDL the squash deleted. If you already have, stop and escalate.
- Do not run `Base.metadata.create_all()` to recover — it creates missing tables but silently skips missing columns, so it looks like it worked.
- Do not stamp any revision earlier than `b2e2800000b2` — the next `upgrade head` replays `CREATE TABLE AuditLog` against an existing table.
- `upgrade` always prompts naming the target database, then `Proceed? [y/N]`; `stamp` does too on this checkout, but not on the pre-cutover checkout used for rollback below — your last check you're pointed at the right one; `current` and `check` never do. Run them interactively, or set `EYENED_ALEMBIC_ASSUME_YES=1` for that one command, which skips that check — without a TTY the prompt raises an uncaught `EOFError` and the command aborts with a traceback.
- Anything that does not match this document: stop before the next command and escalate.

## Steps

**0. `alembic current`** — precondition check, on your current checkout.

- Expect: exactly one revision id you recognise as this site's position.
- Nothing, more than one, or an id you don't recognise: stop before step 1 and escalate. Do not substitute `alembic check` — it errors on a behind-head database.

**1. `alembic upgrade head`** — on your **current** checkout. Real DDL: back up first, inside a maintenance window scoped to this step.

- Does: creates `AuditLog` (plus indexes `ix_AuditLog_ActorID`, `ix_AuditLog_Timestamp`) and `ProjectMember`, adds `Creator.IsAdmin` then `Creator.Inactive`, and drops and recreates five tag foreign keys — `StudyTag`, `ImageInstanceTag`, `AnnotationTag`, `SegmentationTag`, `FormAnnotationTag` — as `ON DELETE RESTRICT`.
- Expect: the upgrade completes.
- Otherwise: do not re-run over the result (MySQL DDL is not transactional) — restore the backup and retry from clean.

**2. `alembic current`** — the gate. Do not deploy until it passes.

- Expect: `b2e2800000b2 (head)`. The revision id is the part that matters; `(head)` is expected here.
- An earlier revision: check out `6c675e5` (it carries all 24 legacy revisions; needs `eyened_orm` installed), run `alembic upgrade head` from there, re-run step 2.
- Nothing, or an id you don't recognise: stop before step 3 and escalate.

**3. Deploy the release.**

- Expect: from here until step 4 completes, every Alembic command fails to resolve this database. That is expected — do not act on it.

**4. `alembic stamp --purge orm_baseline`** — one row, no DDL; `--purge` is required, it skips resolving the id the squash removed from the map. Prompts.

- Expect: the stamp completes.
- Otherwise: stop and escalate.

**5. `alembic current`, then `alembic check`.**

- Expect: `orm_baseline (head)` and a clean check — done.
- Drift reported here is expected at a site carrying pre-existing schema differences: record it and escalate, do not roll back.

## Recovery and rollback

| Situation | Action |
|---|---|
| Deployed before step 1 ran; every command fails with `Can't locate revision identified by '<id>'` | Nothing is damaged. Check out `6c675e5` into an environment with `eyened_orm` installed, run `alembic upgrade head`, redeploy, then run step 4. |
| Roll back code only; step 1 succeeded; before step 4 | If already deployed, redeploy the previous release; if not, there is nothing to undo. Change nothing in the database. |
| Roll back code only; step 1 succeeded; after step 4 | Redeploy the previous release, then `alembic stamp --purge b2e2800000b2` from that checkout (this checkout does **not** prompt on `stamp` — confirm yourself you are pointed at the right database before running it; `--purge` is required — the database holds `orm_baseline`, which that checkout's map doesn't contain). If you are not certain step 2 printed the head, do not stamp — escalate. |
| Step 1's own DDL must be undone | Redeploy the previous release **first**, then restore the pre-step-1 backup — only while the maintenance window is still open. Once the new release has taken writes, restoring loses them: escalate instead. |
