# deploy/ — the eyened-platform stack

One `docker compose` project: `database` (MySQL, optional), `redis`, `init`, `server` and
`fileserver` (nginx), plus layers for development, workers, OIDC and image datasets.
`deploy/.env` chooses which.

Requires Docker with Compose 2.26 or newer (`docker compose version`); older versions reject or
silently ignore `depends_on: required: false`.

## First run

```bash
cp .env.example .env && chmod 600 .env    # then fill the secrets
docker compose up -d --build
```

Fill four secrets with `openssl rand -hex 32` — `EYENED_API_SECRET_KEY`,
`EYENED_REDIS_PASSWORD`, `MYSQL_ROOT_PASSWORD`, `EYENED_DATABASE_PASSWORD` — and set
`EYENED_API_ADMIN_PASSWORD` to the password you will log in with. Then open
`http://localhost:8080` (or your `HTTP_PORT`) and sign in as `admin`.

`.env.example` documents every variable.

## Everything else

Choosing a stack, production deployment, TLS, workers, image datasets, upgrades, migrations and
backup/restore are documented at
<https://eyened.github.io/eyened-platform/deployment/>.
