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

If the database will be affected, Alembic will ask for confirmation before
continuing.

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