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
# There is no separate list for a site deployment: './eyened install' (bundled
# database) and './eyened prod' (external database) run the SAME layers and
# differ only in whether 'local-db' is in COMPOSE_PROFILES. That is a consequence of
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
# precisely the silent degradation that resolving the binary at RUN time (rather
# than naming it in advance) exists to avoid, so both call sites have to be
# closed, not just one.
compose() {
    : "${COMPOSE_BIN:?compose: call resolve_compose first}"
    ( cd "$DEPLOY_DIR" && $COMPOSE_BIN "$@" )
}

# One generator, no host dependency beyond a POSIX userland. This replaced an
# openssl-OR-python3 pair that died when a host had neither — a real state on a
# minimal Linux image, and the reason the deploy prerequisites list used to
# name two things it did not actually need.
#
# Every value it produces is still GENERATED, never copied from .env.example:
# a signing key taken from a template would give every deployment the same JWT
# key, and .env.example ships none of these five keys at all.
#
# An empty or short secret is far worse than a refusal to start, and a silently
# truncated one is worse still, so the LENGTH is checked rather than trusted:
# `od` failing mid-read, or /dev/urandom being absent in a chroot, both produce
# a short string with a zero exit status somewhere in the pipeline (POSIX sh
# has no pipefail). ${#var} is POSIX. Verified under dash, bash and busybox sh.
gen_hex() {
    _n=$1
    _hex=$(od -An -N"$_n" -tx1 /dev/urandom | tr -d ' \n') ||
        die "error: could not read $_n random bytes from /dev/urandom.
      Fix: check that /dev/urandom exists and is readable here (a chroot or
           a container without /dev mounted is the usual cause)."
    [ "${#_hex}" -eq $((_n * 2)) ] ||
        die "error: /dev/urandom produced ${#_hex} hex characters where $((_n * 2)) were
      expected, so the generated secret would be short or empty.
      Fix: check that /dev/urandom is readable here (a chroot or a container
           without /dev mounted is the usual cause)."
    printf '%s\n' "$_hex"
}

# Read a value from an env file. Last assignment wins; values are taken
# verbatim, which is what compose does too.
env_get() {
    _file=${2:-$DEPLOY_DIR/.env}
    [ -f "$_file" ] || return 0
    sed -n "s/^[[:space:]]*$1=//p" "$_file" | tail -n 1
}

# `sudo` is refused rather than compensated for. Docker itself does not need it
# (the daemon SOCKET needs privilege, not this script), and under sudo
# everything written here lands root-owned — a deploy/.env at mode 600 that the
# invoking user's own later 'docker compose logs' cannot read. That used to be
# handled by chowning the files back afterwards, which needed ~50 lines and had
# to be called from every write path; one of them was missed for months.
# Refusing is five lines and cannot be half-applied.
#
# The condition is the same one the chown used: `sudo` sets SUDO_UID, so a
# genuine root shell (SUDO_UID unset) is still allowed through — this refuses
# the sudo WRAPPER, which is what leaves files owned by someone other than the
# person who will run the next command.
refuse_sudo() {
    if [ "$(id -u)" = 0 ] && [ -n "${SUDO_UID:-}" ]; then
        die "error: do not run this under sudo. Anything it creates would be owned by
      root — deploy/.env at mode 600 worst of all, but a generated compose
      layer or a backup datadir just as surely — and your own later
      'docker compose' calls could not read it. Docker needs a privileged
      DAEMON, not a privileged client. Even where nothing is created — reset,
      which only deletes volumes — sudo in front of it usually means you are
      working around a permission problem rather than intending it.
      Fix: run it as yourself. If docker refuses, add yourself to the docker
           group once: sudo usermod -aG docker \"\$USER\", then log out and in."
    fi
}

# Create storage-mounts.conf from its template if it is not there.
#
# Deliberately NOT part of write_env: the two files have independent lifetimes.
# storage-mounts.conf can be deleted (or never created, on a checkout that
# predates it) while .env is perfectly good, and write_env returns early in
# exactly that case — so folding this in would leave gen-storage.sh dying on a
# missing file that the entry point could have replaced for free.
ensure_storage_mounts() {
    if [ ! -f "$DEPLOY_DIR/storage-mounts.conf" ]; then
        cp "$DEPLOY_DIR/storage-mounts.conf.example" "$DEPLOY_DIR/storage-mounts.conf" ||
            die "error: could not create $DEPLOY_DIR/storage-mounts.conf from its
      .example (see above)."
    fi
}

# Refuse a generated value that is not exactly one line.
#
# The heredoc in write_env writes `KEY=$value`. A value carrying a newline is
# therefore not a QUOTING problem — quoting the heredoc would not help, and
# neither would escaping — it is a LINE SHAPE problem: the newline ends the
# assignment and everything after it becomes another line of deploy/.env, which
# compose's dotenv parser reads as a further assignment (or as junk it rejects).
# The file that was supposed to be written once and be correct is then wrong
# from the first run, with a secret half-truncated and a stray key beside it.
#
# Checked rather than merely documented, because the near-miss is one keystroke
# wide: `openssl rand -base64 64` — the obvious alternative spelling of a
# generator here — WRAPS its output at 64 columns. Today's generators emit one
# line of hex; this is what keeps that true when they are replaced.
#
# Only the generated values go through this. write_env's $_layers comes from
# COMPOSE_FILE_DEV / COMPOSE_FILE_CLIENT, both literal constants at the top of
# this file, so a check on it could never fail for any input write_env accepts.
_one_line_or_die() {
    # A literal newline. It has to be written out like this: command
    # substitution strips trailing newlines, so _lf=$(printf '\n') is EMPTY and
    # the `case` below would then match every value.
    _lf='
'
    case $2 in
        *"$_lf"*)
            die "error: the generated $1 is not a single line, so writing it into
      deploy/.env would add stray lines that compose reads as further
      assignments — and would truncate the value itself at the first newline.
      Fix: this is a bug in the generator in deploy/scripts/lib.sh, not in
           anything you configured. A generator here must emit exactly ONE
           line: 'openssl rand -hex 32' does, 'openssl rand -base64 64' does
           not — it wraps at 64 columns." ;;
    esac
}

# Write deploy/.env ONCE, whole, and never touch it again.
#
# No in-place sed, no rewriting of COMPOSE_FILE, no chowning the result back
# afterwards — the three things that made writing this file ~220 lines. The
# consequences are worth stating, because they are improvements and not merely
# simplifications:
#
#   * A layer the operator appends to COMPOSE_FILE by hand — the documented way
#     to enable compose.host-ports.yaml, compose.oidc.yaml and
#     compose.workers.yaml — is now PERMANENTLY safe. Previously every re-run
#     regenerated the base list and merged the extras back in, and the merge
#     could not fully fix a CRLF-latched entry (its own comments said so).
#   * Switching between the dev and client stacks means deleting .env and
#     re-running. That is already what doctor tells you to do.
#   * A variable added to .env.example in a later release does not reach an
#     existing .env. That was ALREADY true — the old in-place writer only ever
#     touched COMPOSE_FILE and the five secrets — so it is not a regression.
#     Give anything new a ${VAR:-default} in compose.yaml.
#
# The file is .env.example plus ONE appended block. Not a second copy of the
# template as a heredoc: that would be a second source of truth for 176 lines
# of documented settings, and it would drift. Compose's dotenv parser takes the
# LAST assignment (measured), as does env_get above, so the appended block wins
# over the template's own COMPOSE_FILE line.

write_env() {
    _mode=$1
    case "$_mode" in
        dev)    _layers=$COMPOSE_FILE_DEV ;;
        client) _layers=$COMPOSE_FILE_CLIENT ;;
        *)      die "write_env: expected 'dev' or 'client', got '$_mode'" ;;
    esac

    # Written once, and a re-run must not touch it. This is not tidiness: an
    # existing .env's MYSQL_ROOT_PASSWORD is already baked into an INITIALISED
    # MySQL datadir, which applies its passwords only while the data directory
    # is empty. Regenerating over it leaves the file and the datadir
    # disagreeing — every connection refused with 'Access denied', on a stack
    # where every container still reports healthy. Saying so rather than
    # returning in silence, because "nothing happened" is the one thing an
    # operator re-running to change something needs told. (A run of the OTHER
    # entry point is a different case, and doctor refuses it before this is
    # ever reached.)
    if [ -f "$DEPLOY_DIR/.env" ]; then
        echo "==> deploy/.env exists — left exactly as it is, secrets and all."
        echo "    To start over (the other stack, or fresh secrets) delete it and"
        echo "    re-run. Deleting it keeps your data; './eyened reset' deletes that."
        return 0
    fi

    [ -f "$DEPLOY_DIR/.env.example" ] ||
        die "error: $DEPLOY_DIR/.env.example is missing, so there is no template to
      build deploy/.env from.
      Fix: restore it — git checkout deploy/.env.example"

    # Generate BEFORE the write, each through a plain assignment whose status
    # is checked. Inside a command substitution in the heredoc below, a
    # generator's `die` would exit only that subshell: the key would be written
    # EMPTY and the run would carry on with status 0.
    _secret=$(gen_hex 32)   || die "error: could not generate a signing key; see above."
    _redis_pw=$(gen_hex 32) || die "error: could not generate a Redis password; see above."
    _root_pw=$(gen_hex 12)  || die "error: could not generate a database root password; see above."
    _db_pw=$(gen_hex 12)    || die "error: could not generate a database password; see above."
    # The bundled Keycloak's bootstrap admin. Generated even when
    # compose.oidc.yaml is not in play — it costs nothing, and it means
    # appending that layer later needs no second trip through this function,
    # which by then would refuse to run. It is also the ONE key here that
    # compose does not require: compose.oidc.yaml has ${KEYCLOAK_ADMIN_PASSWORD
    # :-admin}, so absent means 'admin' rather than a refusal (measured, exit
    # 0). That is why doctor keeps its own check of this one and not of the
    # four above.
    _kc_pw=$(gen_hex 12)    || die "error: could not generate a Keycloak admin password; see above."

    # Shape, not just status: a generator can exit 0 and still hand back
    # something that cannot be written as one `KEY=value` line. See
    # _one_line_or_die above for why this is the failure mode that matters.
    _one_line_or_die "signing key"               "$_secret"
    _one_line_or_die "Redis password"            "$_redis_pw"
    _one_line_or_die "database root password"    "$_root_pw"
    _one_line_or_die "database password"         "$_db_pw"
    _one_line_or_die "Keycloak admin password"   "$_kc_pw"

    # Create the temp EMPTY and restrict it BEFORE anything goes in: `>`
    # truncates without changing an existing file's mode, so no secret is ever
    # briefly group- or world-readable, and `mv` carries 600 onto the target.
    # 600 is a deliberate hardening decision — this file holds five secrets —
    # not preservation of whatever mode was there before.
    #
    # The name matches .gitignore's deploy/.env.* so a temp left behind by a
    # crash can never be committed by accident.
    #
    # `true >`, NOT `: >`. They look interchangeable and are not: `:` is a
    # SPECIAL built-in, and POSIX says a redirection error on one of those
    # exits a non-interactive shell outright — so the `|| die` after it can
    # never run. Measured on this host: with an unwritable deploy/, `: >` gave
    # dash and /bin/sh exit 2 and a bare "cannot create ...: Permission
    # denied", with or without `set -e`, while `true >` reached the die in
    # every shell. bash catches both, which is exactly why a guard written
    # this way survives being tested.
    _tmp="$DEPLOY_DIR/.env.tmp.$$"
    true > "$_tmp" || die "error: could not create $_tmp.
      Fix: check that $DEPLOY_DIR exists and is writable by you."
    chmod 600 "$_tmp" ||
        { rm -f "$_tmp"; die "error: could not restrict permissions on $_tmp."; }

    {
        cat "$DEPLOY_DIR/.env.example" &&
        # UNQUOTED <<EOF, deliberately: $_secret, $_redis_pw, $_root_pw,
        # $_db_pw, $_kc_pw and $_layers must be expanded here, or the block
        # below would write out the literal variable names instead of their
        # values. That is safe today only because gen_hex emits plain hex and
        # the two $_layers lists are constants — none of them can contain a $,
        # backtick or backslash for the shell to re-expand. Whoever changes
        # what gen_hex or the layer lists produce must keep that property, or
        # re-quote this heredoc (and switch every $var below to `printf`
        # instead, since a quoted heredoc does not expand them at all).
        #
        # That is the only property left to keep by hand. The other one this
        # block needs — that each value is a single LINE — is enforced above by
        # _one_line_or_die rather than trusted, because re-quoting the heredoc
        # would not fix a newline: it would still end the assignment early.
        cat <<EOF

# ============================================================================
# Written once, by the installer, and never rewritten. Everything below
# overrides the same key above it: compose reads the LAST assignment.
#
# Editing this block is fine — nothing here will overwrite your changes. To
# start over (a different stack, regenerated secrets), DELETE this whole file
# and re-run the installer. Deleting it keeps your data; './eyened reset' is
# what deletes that.
#
# Appending your own layer to COMPOSE_FILE below is safe and permanent:
#   :compose.host-ports.yaml   publish MySQL and Redis on the host
#   :compose.oidc.yaml         the bundled Keycloak
#   :compose.workers.yaml      RQ workers on this host
# ============================================================================
COMPOSE_FILE=$_layers
EYENED_API_SECRET_KEY=$_secret
EYENED_REDIS_PASSWORD=$_redis_pw
MYSQL_ROOT_PASSWORD=$_root_pw
EYENED_DATABASE_PASSWORD=$_db_pw
KEYCLOAK_ADMIN_PASSWORD=$_kc_pw
EOF
    } >> "$_tmp" || { rm -f "$_tmp"; die "error: could not write $_tmp (see above)."; }

    mv "$_tmp" "$DEPLOY_DIR/.env" ||
        { rm -f "$_tmp"; die "error: could not put $_tmp into place as $DEPLOY_DIR/.env."; }

    echo "==> created deploy/.env with generated secrets"
    echo "    On a shared machine, set COMPOSE_PROJECT_NAME and HTTP_PORT in"
    echo "    deploy/.env to something nobody else is using, then re-run."
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

Day-to-day commands — run them from the deploy/ directory. No wrapper and no
-f flags: the install recorded which layers this stack uses.

  cd $DEPLOY_DIR
  $COMPOSE_BIN logs -f
  $COMPOSE_BIN down
  $COMPOSE_BIN up -d
========================================================================
EOF
}
