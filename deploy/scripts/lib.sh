# Shared helpers for the deploy entry points. POSIX sh — no bashisms.
# Sourced, never executed. Callers set REPO_ROOT first:
#
#   REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
#   . "$REPO_ROOT/deploy/scripts/lib.sh"
#
# REPO_ROOT is the ONLY thing this library asks of its caller. In particular it
# does NOT depend on the caller's shell options: it sets neither -e nor -u, and
# every command below that can fail checks its own status and calls `die`. The
# behaviour is identical whether the caller ran `set -eu` or nothing at all.
# Do not drop a `|| die` on the grounds that "the entry point sets -e" — the
# worst bug this file has had was a failure that `set -e` could not catch.

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
#
# Same guard as print_day2, and for the same reason: with COMPOSE_BIN unset the
# unquoted expansion vanishes and this runs `up -d` as a command, which fails
# with `up: not found` and — in a caller without `set -e` — carries on. That is
# precisely the silent degradation dc.sh's header comment says the design exists
# to avoid, so both call sites have to be closed, not just one.
compose() {
    : "${COMPOSE_BIN:?compose: call resolve_compose first}"
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
# Every step that can fail is checked, and a temp file that was not built
# correctly is REMOVED rather than moved into place. That is not defensive
# padding: `mv` needs only write permission on the DIRECTORY, so an unguarded
# one will cheerfully publish a half-built or empty temp over a populated .env
# and return 0. A `set -e` in the caller does not help — the failures that
# matter here were already being swallowed before they could set a status.
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

    # A newline ends the sed expression mid-script. sed then fails — but the
    # `> "$_tmp"` redirect has already truncated the temp, so unrefused this
    # arrives as an empty .env rather than as a rejected value.
    if [ "$_val" != "$(printf '%s' "$_val" | tr -d '\n')" ]; then
        die "error: refusing to write a multi-line value for '$_key' into $_file.
      An env file holds one KEY=VALUE per line, so a value containing a
      newline cannot round-trip through it."
    fi

    # Existence and readability are different questions, and a swallowed grep
    # cannot tell them apart: an unreadable file looks exactly like "key not
    # present", which sends a populated .env down the build-from-nothing path.
    if [ -e "$_file" ] && [ ! -r "$_file" ]; then
        die "error: $_file exists but is not readable by this user.
      Fix: chmod u+r '$_file', or re-run as the user that owns it."
    fi

    _esc=$(printf '%s' "$_val" | sed -e 's/[|&\\]/\\&/g') ||
        die "error: could not escape the value for '$_key' (see above)."

    # Create the temp EMPTY and restrict it BEFORE anything is written into it:
    # `>` truncates without changing an existing file's mode, so no secret is
    # ever briefly group- or world-readable, and the mv below carries 600 onto
    # the target. 600 is a deliberate hardening decision — .env holds four
    # secrets — and NOT preservation of whatever mode was there before. Do not
    # "restore" this to the umask default.
    : > "$_tmp" || die "error: could not create the temp file $_tmp.
      Fix: check that its directory exists and is writable."
    chmod 600 "$_tmp" ||
        { rm -f "$_tmp"; die "error: could not restrict permissions on $_tmp."; }

    if grep -q "^[[:space:]]*$_key=" "$_file" 2>/dev/null; then
        sed "s|^[[:space:]]*$_key=.*|$_key=$_esc|" "$_file" > "$_tmp" ||
            { rm -f "$_tmp"; die "error: could not rewrite '$_key' in $_file (see above)."; }
    else
        if [ -e "$_file" ]; then
            cat "$_file" > "$_tmp" ||
                { rm -f "$_tmp"; die "error: could not read $_file (see above)."; }
        fi
        printf '%s=%s\n' "$_key" "$_val" >> "$_tmp" ||
            { rm -f "$_tmp"; die "error: could not append '$_key' to $_tmp."; }
    fi

    mv "$_tmp" "$_file" ||
        { rm -f "$_tmp"; die "error: could not put $_tmp into place as $_file."; }
}

# Rewrite COMPOSE_FILE's BASE layer list while preserving any layer the
# operator appended by hand (deploy/.env.example documents appending
# :compose.host-ports.yaml). Only the four known base layers are ever
# replaced; anything else already in COMPOSE_FILE is kept, in order, deduped
# against the new base.
#
# This is called on EVERY first_run_env call, not just the first, because
# first_run_env itself runs on every stack.sh invocation, not only when .env
# is created. A plain re-run of the SAME mode — 're-run ./install.sh',
# 'make up' twice — is reachable and common, and without preserving non-base
# entries it would silently strip an operator's appended host-ports layer
# back out of COMPOSE_FILE on every one of those re-runs. (A dev/client mode
# switch through stack.sh is NOT the scenario this guards: doctor.sh refuses
# a mismatched mode before first_run_env is ever reached, so that path never
# gets here at all.)
_set_compose_file() {
    _new_base=$1
    # A CRLF .env (hand-edited on Windows/WSL) puts a trailing \r on the last
    # layer name. Left in, that \r becomes part of the layer's own identity
    # here: it no longer matches any of the four known base names below, so
    # it is kept as an "extra" and re-appended forever, including onto a
    # freshly-generated base list. Compose itself tolerates the stray \r
    # (trailing whitespace in -f is ignored), so today this only latches a
    # harmless duplicate — but the same mechanism would just as happily
    # preserve a CR-suffixed compose.prod.yaml into a dev COMPOSE_FILE.
    _existing=$(env_get COMPOSE_FILE | tr -d '\r')
    _extra=""
    if [ -n "$_existing" ]; then
        _old_ifs=$IFS
        IFS=':'
        for _layer in $_existing; do
            case "$_layer" in
                compose.yaml|compose.dev.yaml|compose.storage.yaml|compose.prod.yaml|"") ;;
                *)
                    case ":$_extra:" in
                        *":$_layer:"*) ;;
                        *) _extra=${_extra:+$_extra:}$_layer ;;
                    esac
                    ;;
            esac
        done
        IFS=$_old_ifs
    fi
    if [ -n "$_extra" ]; then
        env_set COMPOSE_FILE "$_new_base:$_extra"
    else
        env_set COMPOSE_FILE "$_new_base"
    fi
}

# Give deploy/.env (and storage-mounts.conf) back to the invoking user after a
# run under sudo.
#
# Its own function because TWO paths write .env, not one. install.sh is the
# published client door, and some operators will run it under sudo. Docker
# itself does not need that (the daemon socket is what needs root, not this
# script), but nothing here stops them. Under sudo this process is root, so
# anything it writes ends up root-owned — unreadable, or in
# storage-mounts.conf's case merely un-editable, by the invoking user's own
# later `make up` or plain `docker compose`, which is a worse failure than the
# file being briefly group-readable.
#
# This lived inside first_run_env until it was measured that stack.sh's `prod`
# branch deliberately bypasses first_run_env and calls _set_compose_file (i.e.
# env_set) directly — so `sudo make prod` wrote .env through the same `mv` and
# then never reached the chown, leaving exactly the root-owned mode-600 file
# described above. The reasoning had been done for one .env-writing path and
# not carried to the second. Every path that writes .env must end here.
#
# CALL IT LAST, after every write to those files, never right after .env is
# created: env_set's `mv` (and the storage-mounts.conf `cp`) replace the file
# with a fresh copy owned by the current euid, re-owning it as root and
# undoing an earlier chown. Measured: chowning before _set_compose_file's
# env_set call left .env back at 0:0 after that call ran.
#
# Safe to call on EVERY run and more than once: chowning an already-correct
# owner to itself is a no-op, so this costs nothing on the common case where
# the invoking user was never root to begin with (SUDO_UID unset, block
# skipped entirely). That also means a second sudo run against an
# already-chowned .env must not skip it — the file could have been touched by
# a root run in between.
#
# `sudo` sets SUDO_UID/SUDO_GID to the invoking user, so chown back to that
# rather than leave secrets only root can read.
chown_back_to_invoker() {
    if [ "$(id -u)" = 0 ] && [ -n "${SUDO_UID:-}" ]; then
        chown "$SUDO_UID:${SUDO_GID:-$SUDO_UID}" "$DEPLOY_DIR/.env" ||
            die "error: could not chown $DEPLOY_DIR/.env back to the invoking user
      (uid $SUDO_UID). It was written root-owned at mode 600 and a later
      non-sudo 'make up' or 'docker compose' would not be able to read it.
      Fix: chown $SUDO_UID:${SUDO_GID:-$SUDO_UID} $DEPLOY_DIR/.env by hand."
        if [ -f "$DEPLOY_DIR/storage-mounts.conf" ]; then
            chown "$SUDO_UID:${SUDO_GID:-$SUDO_UID}" "$DEPLOY_DIR/storage-mounts.conf" ||
                die "error: could not chown $DEPLOY_DIR/storage-mounts.conf back to the
      invoking user (uid $SUDO_UID). It was written root-owned and the
      invoking user would not be able to edit their own mount list.
      Fix: chown $SUDO_UID:${SUDO_GID:-$SUDO_UID} $DEPLOY_DIR/storage-mounts.conf by hand."
        fi
    fi
}

# First-run setup for the dev and install modes of stack.sh. MODE is dev or
# client and decides which layer list is recorded — that one line is what lets
# every later command be a bare `docker compose ...` with no -f flags.
#
# Every secret is generated BEFORE .env is created, and each generator's status
# is checked through a plain assignment. Inside `env_set K "$(gen_secret)"` the
# generator's `die` would exit only the command substitution's subshell: the
# key would be written EMPTY and the run would continue with status 0.
#
# The `cp` needs its own check for the same reason and is not covered by the
# hoist: without one, a missing .env.example produces a plausible-looking .env
# holding nothing but the four generated secrets, the "created" banner, and
# exit 0 — and since the guard below is `[ ! -f .env ]`, no later run ever
# repairs it.
#
# CONTRACT: COMPOSE_FILE's base layer list is rewritten on every call (via
# _set_compose_file above), not only when .env is first created — only the
# four known base layer names are ever touched, so a layer the operator
# appended by hand survives. doctor.sh and bootstrap.sh only ever READ
# COMPOSE_FILE and neither assumes it is left untouched across runs, so
# neither is affected by this.
first_run_env() {
    _mode=$1
    if [ ! -f "$DEPLOY_DIR/.env" ]; then
        _secret=$(gen_secret) || die "error: could not generate a signing key; see above."
        _redis_pw=$(gen_secret) || die "error: could not generate a Redis password; see above."
        _root_pw=$(gen_password) || die "error: could not generate a database root password; see above."
        _db_pw=$(gen_password) || die "error: could not generate a database password; see above."
        # The bundled Keycloak's bootstrap admin. Generated for the same reason
        # as the four above: .env.example cannot ship a credential, and this
        # console is published (see KEYCLOAK_BIND). Generated even when the
        # oidc profile is off — it costs nothing, and it means enabling the
        # profile later does not need a second trip through this function.
        _kc_pw=$(gen_password) || die "error: could not generate a Keycloak admin password; see above."
        cp "$DEPLOY_DIR/.env.example" "$DEPLOY_DIR/.env" ||
            die "error: could not create $DEPLOY_DIR/.env from .env.example; see above."
        # Restrict it before the first secret goes in, not after.
        chmod 600 "$DEPLOY_DIR/.env" ||
            die "error: could not restrict permissions on $DEPLOY_DIR/.env."
        env_set EYENED_API_SECRET_KEY "$_secret"
        env_set EYENED_REDIS_PASSWORD "$_redis_pw"
        env_set MYSQL_ROOT_PASSWORD "$_root_pw"
        env_set EYENED_DATABASE_PASSWORD "$_db_pw"
        env_set KEYCLOAK_ADMIN_PASSWORD "$_kc_pw"

        echo "==> created deploy/.env with generated secrets"
        echo "    On a shared machine, set COMPOSE_PROJECT_NAME and HTTP_PORT"
        echo "    in deploy/.env to something nobody else is using."
    fi

    case "$_mode" in
        dev)    _set_compose_file "$COMPOSE_FILE_DEV" ;;
        client) _set_compose_file "$COMPOSE_FILE_CLIENT" ;;
        *)      die "first_run_env: expected 'dev' or 'client', got '$_mode'" ;;
    esac

    if [ ! -f "$DEPLOY_DIR/storage-mounts.conf" ]; then
        cp "$DEPLOY_DIR/storage-mounts.conf.example" "$DEPLOY_DIR/storage-mounts.conf" ||
            die "error: could not create $DEPLOY_DIR/storage-mounts.conf from its .example; see above."
    fi

    # Last, after _set_compose_file and the storage-mounts.conf cp above — see
    # chown_back_to_invoker's own header for why the order matters and why
    # this runs on every call rather than only on first run.
    chown_back_to_invoker
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
