# `init` exits 0 on a schema behind head, so the stack serves against the old one

- **Source:** whole-PR review of #202, 2026-09-21 (Important 2), deferred in favour of the
  documentation sweep in f5dcb5b5. Design question, not a defect: the current behaviour is
  deliberate and now documented accurately.

**Status:** open

## What

`eorm bootstrap` reports pending migrations and returns 0 when `--auto-migrate` is off
(`orm/eyened_orm/commands/bootstrap.py`, the `else:` branch). `server` gates on
`init: condition: service_completed_successfully` (`deploy/compose.yaml:152-153`), which that
satisfies, so `docker compose up -d --build` brings the new code up against the old schema and
`docker compose ps` reports it healthy.

Three shapes were considered:

- **A. Hard gate.** Pending migrations plus `--no-auto-migrate` exits non-zero, naming the
  migrate command. ~10 lines, and the half-migrated state stops existing. Cost: a forgotten
  migrate step turns a routine upgrade into an outage — compose has already stopped the old
  `server` container by the time `init` fails — and a stack cannot be brought up at all between
  an image upgrade and its maintenance window.
- **B. Tri-state.** Unset exits non-zero (you did not notice); an explicit
  `EYENED_AUTO_MIGRATE=false` reports and continues (you know); `=true` migrates. Keeps
  deliberate deferral working. Cost: three states in a boolean flag, and `deploy/compose.yaml:96`
  sets the variable explicitly, so the "unset" state does not exist inside the stack.
- **C. Fix the health signal instead.** Keep the exit code and have the server's `/health`
  report a schema behind head, so `up` succeeds but `compose ps` shows why the stack is degraded.
  Addresses the real complaint — nothing downstream tells the truth — but it is app surgery, and
  under A an unmigrated stack never starts, so there is nothing left to report.

## Why

The failure is silent and shaped like success. Every other cheap signal in this stack was made
to assert on data rather than status during #202; this one still does not. Until it is settled,
the upgrade path depends on the operator reading `docker compose logs init` and running a second
command, with nothing enforcing it.

Picking A also removes the sharpest edge in `deploy/README.md`'s "Moving an existing database
into this stack", where the operator is mid-cutover on a datadir MySQL has already upgraded
irreversibly.
