## EyeNED Database Setup

Copy `.env.example` to `.env` and set passwords before the first run:

```bash
cp .env.example .env
```

Optionally override `EYENED_DATABASE_PORT` and `EYENED_ADMINER_PORT` in `.env`.

Run:

```bash
docker compose up -d
```

Optionally import a data dump from another database:

```bash
./load_dump.sh /path/to/dump
```
