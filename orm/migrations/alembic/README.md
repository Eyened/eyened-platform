` # Alembic migrations

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

If the database will be affected, Alembic will ask for confirmation before
continuing.

## Running non-interactively

Every command that can alter the database prompts for confirmation of the target
before running. To skip the prompt in an unattended context (CI), set:

    EYENED_ALEMBIC_ASSUME_YES=1

It must be a **process environment variable**. Putting it in the file passed via
`-x env_file=` has no effect, by design: that file is loaded after the flag is
read, so a `.env` pointed at production cannot silently disable the confirmation.

Accepted values are `1`, `true` and `yes` (case-insensitive). Anything else —
including `false` and `0` — leaves the prompt on.

## Common commands

Create a migration:

```bash
alembic revision --autogenerate -m "message"
```

- Review the generated migration file and adjust it as needed.

Apply migrations:

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

## versions_archive/

The 24 revisions that predate `orm_baseline`. They are kept for history and are
deliberately unreachable: `alembic.ini` leaves `version_locations` unset, so
Alembic scans only `versions/`. They cannot build a database from empty — the
old root was a stub whose declared parent had been deleted, and 27 of 44 tables
were created by no migration at all.

Do not move them back into `versions/`. Two roots make `upgrade head` walk both
chains and fail.