## EyeNED Database Setup

Copy `.env.example` to `.env` and set passwords before the first run:

```bash
cp .env.example .env
```

Optionally override `EYENED_DATABASE_PORT` and `EYENED_ADMINER_PORT` in `.env`.
`EYENED_DATABASE_BUFFER_POOL_SIZE` controls the InnoDB buffer pool size and
defaults to `2G`.

Run:

```bash
docker compose up -d
```

Optionally import a data dump from another database:

```bash
./load_dump.sh /path/to/dump
```
