#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_COMPOSE_FILE="$SCRIPT_DIR/docker/docker-compose.yaml"
DB_COMPOSE_FILE="$SCRIPT_DIR/database/docker-compose.yaml"
ENV_FILE="$SCRIPT_DIR/.env"

if [[ ! -f "$APP_COMPOSE_FILE" ]]; then
    echo "Error: compose file not found at $APP_COMPOSE_FILE" >&2
    exit 1
fi

if [[ ! -f "$DB_COMPOSE_FILE" ]]; then
    echo "Error: compose file not found at $DB_COMPOSE_FILE" >&2
    exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
    cat > "$ENV_FILE" <<'EOF'
PORT=3876
EYENED_ADMINER_PORT=3879
EYENED_DATABASE_PORT=3878
EYENED_REDIS_PUBLISH_PORT=6379
MYSQL_ROOT_PASSWORD=secure_password
MYSQL_DATABASE=eyened_database
MYSQL_USER=eyened_user
MYSQL_PASSWORD=secure_password
EYENED_DATABASE_USER=eyened_user
EYENED_DATABASE_PASSWORD=secure_password
EYENED_DATABASE_DATABASE=eyened_database
EYENED_DATABASE_HOST=host.docker.internal
EYENED_API_SECRET_KEY=change-me
EYENED_API_PUBLIC_AUTH_DISABLED=false
EYENED_API_DEBUG=false
EYENED_REDIS_PASSWORD=change-me
EYENED_DB_DATA_PATH=$SCRIPT_DIR/.local/mysql
EYENED_QNAP_ROOT=/mnt/qnap-rc-02/Eyened-temp-for-test
EYENED_STORAGE_ROOT=/mnt/qnap-rc-02/Eyened-temp-for-test/storage
EYENED_STORAGE_MOUNTS={"mnt":"/mnt","legacy":"/mnt/qnap-rc-02/Eyened-temp-for-test/images","images":"/mnt/qnap-rc-02/Eyened-temp-for-test/images"}
EOF
    echo "Created $ENV_FILE with defaults. Review values before production use."
fi

resolve_docker_platform() {
    case "$(uname -m)" in
        x86_64|amd64)
            echo "linux/amd64"
            ;;
        aarch64|arm64)
            echo "linux/arm64"
            ;;
        *)
            echo "linux/amd64"
            ;;
    esac
}

DOCKER_PLATFORM="$(resolve_docker_platform)"
export DOCKER_DEFAULT_PLATFORM="$DOCKER_PLATFORM"

set -a
source "$ENV_FILE"
set +a

: "${PORT:=3876}"
: "${EYENED_DATABASE_PORT:=3878}"
: "${EYENED_ADMINER_PORT:=3879}"
: "${EYENED_DATABASE_HOST:=host.docker.internal}"
: "${EYENED_DB_DATA_PATH:=$SCRIPT_DIR/.local/mysql}"
: "${EYENED_QNAP_ROOT:=/mnt/qnap-rc-02/Eyened-temp-for-test}"
: "${EYENED_STORAGE_ROOT:=${EYENED_QNAP_ROOT}/storage}"
: "${EYENED_STORAGE_MOUNTS:={\"mnt\":\"/mnt\",\"legacy\":\"${EYENED_QNAP_ROOT}/images\",\"images\":\"${EYENED_QNAP_ROOT}/images\"}}"

# Database data must stay local and never in the qnap mount.
if [[ "$EYENED_DB_DATA_PATH" == /mnt/qnap-rc-02/Eyened-temp-for-test* ]]; then
    echo "EYENED_DB_DATA_PATH points into /mnt/qnap-rc-02/Eyened-temp-for-test; forcing local path." >&2
    EYENED_DB_DATA_PATH="$SCRIPT_DIR/.local/mysql"
fi

# Enforce requested host ports.
PORT=3876
EYENED_DATABASE_PORT=3878
export PORT EYENED_DATABASE_PORT EYENED_ADMINER_PORT EYENED_DATABASE_HOST EYENED_STORAGE_ROOT EYENED_DB_DATA_PATH EYENED_STORAGE_MOUNTS

mkdir -p "$EYENED_DB_DATA_PATH"

echo "Stopping existing compose stacks for a fresh start..."
docker compose --env-file "$ENV_FILE" -f "$APP_COMPOSE_FILE" down --remove-orphans >/dev/null 2>&1 || true
docker compose --env-file "$ENV_FILE" -f "$DB_COMPOSE_FILE" down --remove-orphans >/dev/null 2>&1 || true

echo "Pulling Docker images for platform $DOCKER_PLATFORM..."
docker pull --platform "$DOCKER_PLATFORM" \
    mysql:8.0.27 \
    redis:7-alpine \
    nginx:latest \
    adminer:latest >/dev/null 2>&1 || true

MEDSAM_SOURCE_DIR="$SCRIPT_DIR/MedSAM/Medical-SAM2-main"
if [[ ! -f "$MEDSAM_SOURCE_DIR/sam2_train/__init__.py" ]]; then
    echo "MedSAM source missing at $MEDSAM_SOURCE_DIR, trying local restore..."
    if [[ -f "$SCRIPT_DIR/restore-medsam-source.sh" ]]; then
        bash "$SCRIPT_DIR/restore-medsam-source.sh" || true
    fi
fi

if [[ ! -f "$MEDSAM_SOURCE_DIR/sam2_train/__init__.py" ]]; then
    echo "Error: Medical-SAM2 source not found at $MEDSAM_SOURCE_DIR." >&2
    echo "Automatic restore attempts (local images/archives and GitHub) were not successful." >&2
    echo "Provide one of the following, then rerun ./start.sh:" >&2
    echo "  - git clone --depth 1 --branch main https://github.com/ImprintLab/Medical-SAM2.git MedSAM/Medical-SAM2-main" >&2
    echo "  - MedSAM/Medical-SAM2-main/ (folder)" >&2
    echo "  - MedSAM/Medical-SAM2-main.tar.gz (archive)" >&2
    exit 1
fi

echo "Starting database stack (database, adminer)..."
docker compose --env-file "$ENV_FILE" -f "$DB_COMPOSE_FILE" up -d database adminer

echo "Waiting for database to be ready..."
db_max_attempts=120
db_attempt=0
until docker compose --env-file "$ENV_FILE" -f "$DB_COMPOSE_FILE" exec -T database mysqladmin ping -h localhost -p"${MYSQL_ROOT_PASSWORD:-secure_password}" --silent >/dev/null 2>&1; do
    db_attempt=$((db_attempt + 1))

    # Fail fast if the database container exited instead of waiting forever.
    db_state="$(docker compose --env-file "$ENV_FILE" -f "$DB_COMPOSE_FILE" ps --format json database 2>/dev/null | sed -n 's/.*"State":"\([^"]*\)".*/\1/p' | head -n1)"
    if [[ -n "$db_state" && "$db_state" != "running" ]]; then
        echo "Error: database container state is '$db_state'." >&2
        echo "Recent database logs:" >&2
        docker compose --env-file "$ENV_FILE" -f "$DB_COMPOSE_FILE" logs --tail=80 database >&2 || true
        exit 1
    fi

    if [[ $db_attempt -ge $db_max_attempts ]]; then
        echo "Error: database did not become ready in time." >&2
        echo "Recent database logs:" >&2
        docker compose --env-file "$ENV_FILE" -f "$DB_COMPOSE_FILE" logs --tail=80 database >&2 || true
        exit 1
    fi

    sleep 1
done

echo "Starting application stack (server, client, fileserver, redis)..."
docker compose --env-file "$ENV_FILE" -f "$APP_COMPOSE_FILE" up -d --build

echo "Waiting for MedSAM health from the medsam container ..."
medsam_max_attempts=60
medsam_attempt=0
until docker compose --env-file "$ENV_FILE" -f "$APP_COMPOSE_FILE" exec -T medsam \
    python -c "import urllib.request; urllib.request.urlopen('http://localhost:8010/health', timeout=2).read()" >/dev/null 2>&1; do
    medsam_attempt=$((medsam_attempt + 1))
    if [[ $medsam_attempt -ge $medsam_max_attempts ]]; then
        echo "Error: MedSAM service did not become healthy in time." >&2
        echo "Recent medsam logs:" >&2
        docker compose --env-file "$ENV_FILE" -f "$APP_COMPOSE_FILE" logs --tail=120 medsam >&2 || true
        exit 1
    fi
    sleep 2
done

echo "Waiting for API health from the server container ..."
max_attempts=60
attempt=0
until docker compose --env-file "$ENV_FILE" -f "$APP_COMPOSE_FILE" exec -T server \
    python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2).read()" >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [[ $attempt -ge $max_attempts ]]; then
        echo "Error: API did not become healthy in time." >&2
        echo "Check logs with: docker compose --env-file .env -f docker/docker-compose.yaml logs server" >&2
        exit 1
    fi
    sleep 2
done

echo "Platform is up."
echo "App: http://localhost:${PORT}"
echo "Database: localhost:${EYENED_DATABASE_PORT}"
echo "Adminer: http://localhost:${EYENED_ADMINER_PORT}"
