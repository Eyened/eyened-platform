# Shared helpers for the deploy entry points. POSIX sh — no bashisms.
# Sourced, never executed. Callers set REPO_ROOT first:
#
#   REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
#   . "$REPO_ROOT/deploy/scripts/lib.sh"

: "${REPO_ROOT:?lib.sh: set REPO_ROOT before sourcing}"
DEPLOY_DIR="$REPO_ROOT/deploy"

# The two layer lists. COMPOSE_FILE must name every layer — nothing here is
# discovered implicitly, which is why the dev layer is compose.dev.yaml and
# not compose.override.yaml (the name Compose would auto-load).
#
# There is no separate list for a site deployment: install.sh (bundled
# database) and prod mode (external database) run the SAME layers and differ
# only in whether 'local-db' is in COMPOSE_PROFILES. That is a consequence of
# the server's depends_on using `required: false` — see compose.yaml.
COMPOSE_FILE_DEV="compose.yaml:compose.dev.yaml:compose.storage.yaml"
COMPOSE_FILE_CLIENT="compose.yaml:compose.storage.yaml:compose.prod.yaml"

die() {
    printf '%s\n' "$*" >&2
    exit 1
}

# Resolve the compose binary once. A host may have the `docker compose`
# plugin, the standalone `docker-compose`, or both — so nothing may hardcode
# either form, including the commands we print for the operator to run later.
resolve_compose() {
    if docker compose version >/dev/null 2>&1; then
        COMPOSE_BIN="docker compose"
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_BIN="docker-compose"
    else
        die "error: neither 'docker compose' nor 'docker-compose' is available.
      Fix: install Docker — https://docs.docker.com/get-docker/"
    fi
}

# Run compose from deploy/, where .env and the layer files live.
# $COMPOSE_BIN is deliberately unquoted: "docker compose" must split in two.
compose() {
    ( cd "$DEPLOY_DIR" && $COMPOSE_BIN "$@" )
}

# A signing key must never be copied from a template — that would give every
# deployment the same JWT key. Two sources, and a hard failure if neither is
# present: an empty signing key is far worse than a refusal to start.
gen_secret() {
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -hex 32
    elif command -v python3 >/dev/null 2>&1; then
        python3 -c 'import secrets; print(secrets.token_hex(32))'
    else
        die "error: need 'openssl' or 'python3' to generate a signing key, and
      neither is installed. Install either one and re-run."
    fi
}

gen_password() {
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -hex 12
    elif command -v python3 >/dev/null 2>&1; then
        python3 -c 'import secrets; print(secrets.token_hex(12))'
    else
        die "error: need 'openssl' or 'python3' to generate a password, and
      neither is installed. Install either one and re-run."
    fi
}

# Read a value from an env file. Last assignment wins; values are taken
# verbatim, which is what compose does too.
env_get() {
    _file=${2:-$DEPLOY_DIR/.env}
    [ -f "$_file" ] || return 0
    sed -n "s/^[[:space:]]*$1=//p" "$_file" | tail -n 1
}

# Write a value into an env file, replacing any existing assignment.
# `sed -i` is not portable (GNU takes no argument, BSD requires one), so this
# writes a temp file and moves it.
#
# The value is escaped for sed's REPLACEMENT side, where & means "the whole
# match" and | is the delimiter. Generated hex secrets contain neither, but a
# hand-set PLATFORM_STORAGE_PATH or COMPOSE_FILE could, and a silently
# corrupted .env line is a very hard failure to trace back to here.
env_set() {
    _key=$1
    _val=$2
    _file=${3:-$DEPLOY_DIR/.env}
    _tmp="$_file.tmp.$$"
    _esc=$(printf '%s' "$_val" | sed -e 's/[|&\\]/\\&/g')
    if grep -q "^[[:space:]]*$_key=" "$_file" 2>/dev/null; then
        sed "s|^[[:space:]]*$_key=.*|$_key=$_esc|" "$_file" > "$_tmp"
    else
        cat "$_file" > "$_tmp" 2>/dev/null || :
        printf '%s=%s\n' "$_key" "$_val" >> "$_tmp"
    fi
    mv "$_tmp" "$_file"
}

# First-run setup for the dev and install modes of stack.sh. MODE is dev or
# client and decides which layer list is recorded — that one line is what lets
# every later command be a bare `docker compose ...` with no -f flags.
#
# Every secret is generated BEFORE .env is created, and each generator's status
# is checked through a plain assignment. Inside `env_set K "$(gen_secret)"` the
# generator's `die` would exit only the command substitution's subshell: the
# key would be written EMPTY and the run would continue with status 0. Failing
# before the copy also means a failed run leaves no half-written .env behind.
first_run_env() {
    _mode=$1
    if [ ! -f "$DEPLOY_DIR/.env" ]; then
        _secret=$(gen_secret) || die "error: could not generate a signing key; see above."
        _redis_pw=$(gen_secret) || die "error: could not generate a Redis password; see above."
        _root_pw=$(gen_password) || die "error: could not generate a database root password; see above."
        _db_pw=$(gen_password) || die "error: could not generate a database password; see above."
        cp "$DEPLOY_DIR/.env.example" "$DEPLOY_DIR/.env"
        env_set EYENED_API_SECRET_KEY "$_secret"
        env_set EYENED_REDIS_PASSWORD "$_redis_pw"
        env_set MYSQL_ROOT_PASSWORD "$_root_pw"
        env_set EYENED_DATABASE_PASSWORD "$_db_pw"
        echo "==> created deploy/.env with generated secrets"
        echo "    On a shared machine, set COMPOSE_PROJECT_NAME and HTTP_PORT"
        echo "    in deploy/.env to something nobody else is using."
    fi

    case "$_mode" in
        dev)    env_set COMPOSE_FILE "$COMPOSE_FILE_DEV" ;;
        client) env_set COMPOSE_FILE "$COMPOSE_FILE_CLIENT" ;;
        *)      die "first_run_env: expected 'dev' or 'client', got '$_mode'" ;;
    esac

    [ -f "$DEPLOY_DIR/storage-mounts.conf" ] || \
        cp "$DEPLOY_DIR/storage-mounts.conf.example" "$DEPLOY_DIR/storage-mounts.conf"
}

# The day-2 commands, printed with the binary THIS host actually has. Naming
# the wrong one recreates exactly the failure resolve_compose exists to avoid.
#
# The guard is not belt-and-braces: the here-document below is expanded by a
# child process, so an unset COMPOSE_BIN does NOT abort the caller. Without the
# guard this function either prints the whole block with an empty binary name
# ("  logs -f") or, under `set -u`, prints nothing at all — and returns 0 either
# way. Checking it as a plain command instead makes the failure stop the script.
print_day2() {
    : "${COMPOSE_BIN:?print_day2: call resolve_compose first}"
    _host=$(env_get PUBLIC_HOST)
    _port=$(env_get HTTP_PORT)
    cat <<EOF

========================================================================
The platform is running.

  Open:  http://${_host:-localhost}:${_port:-8080}/

Day-to-day commands — run them from the deploy/ directory. No make and no
-f flags: the install recorded which layers this stack uses.

  cd $DEPLOY_DIR
  $COMPOSE_BIN logs -f
  $COMPOSE_BIN down
  $COMPOSE_BIN up -d
========================================================================
EOF
}
