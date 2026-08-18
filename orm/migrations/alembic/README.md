# Alembic migrations

Alembic reads database settings from the environment. You can pass a specific
env file like this:

```bash
alembic -x env_file=/path/to/.env.dev <command>
```

## Tip: convenience wrapper

Create `~/bin/alembic-dev`:

```bash
#!/usr/bin/env bash
exec alembic -x env_file=/path/to/your/.env.dev "$@"
```
And run:
```bash
chmod +x ~/bin/alembic-dev
```

Then run:

```bash
alembic-dev <command>
```

## Safety

Confirmation is gated by command name, not by whether the database is
actually touched: every command except `revision`, `history`, `current`,
`heads`, `branches`, `show`, `check`, `list_templates` and `stamp` (see
`no_prompt_cmds` in `env.py`) prompts before running. That means an offline
`upgrade --sql` run — which only prints SQL and touches nothing — still
prompts, while `stamp`, which does alter the `alembic_version` table, does
not.

## Running non-interactively

To skip the prompt for the commands that do prompt (see Safety above), in an
unattended context such as CI, set:

    EYENED_ALEMBIC_ASSUME_YES=1

It must be a **process environment variable** — one already present in
`os.environ` before `env.py` runs. Putting it in the file passed via
`-x env_file=` has no effect, by design: that file is loaded after the flag
is read, so a `.env` file passed that way cannot silently disable the
confirmation.

That protection is narrower than it sounds, and covers only alembic's own
`-x env_file=` channel. A variable already exported into your shell — by
`set -a; . .env`, by a shell profile, or injected by a container runtime's
`env_file:` mechanism (as docker-compose does) — lands in `os.environ`
*before the interpreter starts* and switches the guard off just as
completely as passing it directly. That is in fact the intended CI
mechanism: CI injects `EYENED_ALEMBIC_ASSUME_YES=1` as a real environment
variable. The corollary is that it must never be exported in an interactive
shell or a production shell/container — if it is, every prompting command
proceeds silently.

Accepted values are `1`, `true` and `yes` (case-insensitive). Anything else —
including `false` and `0` — leaves the prompt on.

## Fresh databases

`alembic upgrade head` only alters a schema that already exists; it cannot
build one. Against an empty database it fails on the second revision with
`(1146, "Table 'eyened_database.Contact' doesn't exist")`, because 25 of the
44 tables in `Base.metadata` are created by no migration.

Create the schema first, then migrate:

```bash
eorm initialize-database   # create_all() + stamp at head
alembic upgrade head       # no-op until the next revision lands
```

See `orm/README.md` for the background and for what issue #186 changes.

## Common commands

Create a migration:

```bash
alembic revision --autogenerate -m "message"
```

- Review the generated migration file and adjust it as needed.

Apply migrations (existing database):

```bash
alembic upgrade head
```

## Useful extras

Show current DB revision:

```bash
alembic current
```

View migration history:

```bash
alembic history
```