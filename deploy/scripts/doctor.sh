#!/bin/sh
# Preflight for both entry points. Runs before anything is built, so a failure
# costs seconds rather than an image build. Every failure names the fix, and
# every check runs even if an earlier one failed: a `die` halfway through this
# file would rob the operator of everything below it, so failure-capable
# commands are guarded explicitly rather than left to `set -e` (which does not
# catch a failing redirect, or a failure inside an `if`/`&&`/`||`).
#
# Usage: doctor.sh [dev|client]
set -eu

MODE=${1:-dev}
REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$REPO_ROOT/deploy/scripts/lib.sh"

case "$MODE" in
    dev|client) ;;
    *) die "usage: doctor.sh [dev|client]" ;;
esac

failed=0
# Both go to stdout: FAIL used to go to stderr, but that means a redirected
# or piped run (`make doctor 2>&1 | tee log`, or capturing just one stream)
# interleaves the report out of order or loses half of it. This file's whole
# purpose is one readable, ordered list, so both share a stream.
ok()      { printf 'ok    %s\n' "$1"; }
problem() { printf 'FAIL  %s\n' "$1"; failed=1; }

# Strip a trailing CR (a CRLF .env, e.g. hand-edited on Windows/WSL) and
# surrounding whitespace, and unwrap one layer of matching quotes. env_get
# (lib.sh:90) returns values verbatim — it has no opinion on either — and
# every comparison below is an exact-match `case`, so an unstripped `\r` or
# a quoted `"change_me"` reads as a DIFFERENT string and silently passes.
# This does not change what lib.sh or compose itself does with the value —
# only what doctor compares against — so a CRLF .env is still worth fixing
# at the source; doctor's checks must simply not be foolable by it either way.
norm() {
    _v=$(printf '%s' "$1" | tr -d '\r')
    _v=${_v%"${_v##*[![:space:]]}"}
    _v=${_v#"${_v%%[![:space:]]*}"}
    case "$_v" in
        \"*\") _v=${_v#\"}; _v=${_v%\"} ;;
        \'*\') _v=${_v#\'}; _v=${_v%\'} ;;
    esac
    printf '%s' "$_v"
}

# --- Docker daemon ---------------------------------------------------------
if docker info >/dev/null 2>&1; then
    ok "docker daemon is reachable"
else
    problem "Docker is not running, or is not installed.
      Fix: start Docker Desktop, or install Docker — https://docs.docker.com/get-docker/"
fi

# --- Compose binary and version floor --------------------------------------
# This does NOT call lib.sh's resolve_compose(): that function calls die() on
# failure, which would exit the whole script here and skip every check below
# it. Detection logic is intentionally identical to resolve_compose (docker
# compose plugin first, then the standalone binary) so the binary this reports
# is the one every other script would actually use.
if docker compose version >/dev/null 2>&1; then
    COMPOSE_BIN="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_BIN="docker-compose"
else
    COMPOSE_BIN=""
fi

if [ -z "$COMPOSE_BIN" ]; then
    problem "Neither 'docker compose' nor 'docker-compose' is available.
      Fix: install Docker — https://docs.docker.com/get-docker/"
else
    version=$($COMPOSE_BIN version --short 2>/dev/null | tr -d 'v ')
    major=${version%%.*}
    rest=${version#*.}
    minor=${rest%%.*}
    case "$major$minor" in
        ''|*[!0-9]*) problem "Could not read a compose version from '$COMPOSE_BIN version --short'.
      Fix: check that Docker Compose is installed correctly." ;;
        *) if [ "$major" -gt 2 ] || { [ "$major" -eq 2 ] && [ "$minor" -ge 26 ]; }; then
               ok "compose $version via '$COMPOSE_BIN' (>= 2.26)"
           else
               problem "Docker Compose $version (via '$COMPOSE_BIN') is older than the required 2.26.
      This is not a soft requirement. The server's dependency on the
      bundled database uses 'required: false', which older versions
      either reject outright (< 2.24) or handle by SILENTLY dropping
      the dependency (< 2.26) — the server then starts before MySQL is
      ready and crash-loops on first boot with nothing explaining why.
      Fix: upgrade Docker, or install the compose plugin —
      https://docs.docker.com/compose/install/"
           fi ;;
    esac
fi

# --- Required external tools ------------------------------------------------
# lib.sh needs: tail grep sed cat mv tr chmod cp
# gen-storage.sh needs: mktemp awk mv mkdir wc tr rm
# every script's REPO_ROOT line (lib.sh's own sourcing pattern, used by
# gen-storage.sh, dc.sh and this file) needs: dirname
# doctor.sh itself adds: df awk
# `command -v` alone can return a bare name for a shell builtin or function
# instead of a real binary (a missing external `grep`, for example, would
# silently take a shell-builtin path and still print a name) — `command -p -v`
# forces a defined PATH and is checked for an absolute path so a builtin or
# function does not read as "present".
required_tools="tail grep sed cat mv tr chmod cp mktemp awk mkdir wc rm dirname df"
missing_tools=""
for _t in $required_tools; do
    _p=$(command -p -v "$_t" 2>/dev/null) || _p=""
    case "$_p" in
        /*) ;;
        *) missing_tools="$missing_tools $_t" ;;
    esac
done
if [ -z "$missing_tools" ]; then
    ok "required tools are present in the standard system path ($required_tools)"
else
    problem "These tools are used by the deploy scripts but were not found as real
      executables (a shell builtin or function does not count):
     $missing_tools
      Fix: install them — they are standard on any POSIX host (coreutils,
           grep, sed)."
fi

# --- Whose .env is this, and is OIDC configured usably? --------------------
if [ -f "$DEPLOY_DIR/.env" ]; then
  if [ ! -r "$DEPLOY_DIR/.env" ]; then
    # Same case lib.sh's env_set already guards against (lib.sh:126-129, with
    # the same rationale): an unreadable file looks exactly like "key not
    # present" to env_get's `sed | tail` (tail exits 0 on the empty input a
    # failed sed leaves behind), so every derived check below would silently
    # see empty values and report a WRONG answer (oidc off, wrong entry
    # point, defaults cleared) instead of "could not tell". Report the one
    # real problem and skip the checks that depend on reading the file,
    # rather than let them guess.
    problem "deploy/.env exists but is not readable by this user, so the checks that
      depend on it (entry point, OIDC host, secrets) could not run.
      Fix: chmod u+r deploy/.env, or re-run as the user that owns it."
  else
    # Every value below goes through norm(): env_get (lib.sh:90) returns
    # values verbatim, and every comparison here is an exact-match `case`, so
    # a CRLF .env (trailing \r on every value) or a hand-quoted
    # MYSQL_ROOT_PASSWORD="change_me" would otherwise compare unequal to the
    # bare value being tested for and pass every check that depends on it.
    compose_file=$(norm "$(env_get COMPOSE_FILE)")
    profiles=$(norm "$(env_get COMPOSE_PROFILES)")

    # OIDC endpoints are built from PUBLIC_HOST because the issuer the SERVER
    # validates must be byte-identical to the one the BROWSER was redirected
    # to. The dev override maps PUBLIC_HOST to host-gateway so the server can
    # reach a host-published Keycloak — but if PUBLIC_HOST is 'localhost',
    # /etc/hosts resolves it to the container itself first (::1, then
    # 127.0.0.1, then the gateway), so every token validation pays two
    # refused connections before it succeeds.
    case "$profiles" in
        *oidc*)
            public_host=$(norm "$(env_get PUBLIC_HOST)")
            case "${public_host:-localhost}" in
                localhost|127.0.0.1|::1)
                    problem "COMPOSE_PROFILES enables 'oidc' but PUBLIC_HOST is
      '${public_host:-localhost}'. Inside the server container that name resolves to
      the container itself before it resolves to the host, so reaching
      Keycloak works only after two failed connections — and any change to
      the retry behaviour turns it into an outright failure.
      Fix: set PUBLIC_HOST in deploy/.env to this machine's hostname or LAN
           IP — the same value you type in the browser." ;;
                *) ok "PUBLIC_HOST '$public_host' is usable for OIDC" ;;
            esac ;;
        *) ok "oidc profile is off (PUBLIC_HOST not checked)" ;;
    esac

    # A COMPOSE_FILE naming both layers is accepted silently by compose itself
    # (exit 0, no warning): 'dev:prod' yields the prod image with a stray
    # unrouted client container that fileserver still depends on; 'prod:dev'
    # mounts dev.conf onto the SPA image so nginx proxies to vite while the
    # built SPA sits unused. The has_dev/MODE check below cannot catch this —
    # with both named it reads as a normal dev stack.
    case "$compose_file" in *compose.dev.yaml*) has_dev=yes ;; *) has_dev=no ;; esac
    case "$compose_file" in *compose.prod.yaml*) has_prod=yes ;; *) has_prod=no ;; esac

    if [ "$has_dev" = yes ] && [ "$has_prod" = yes ]; then
        problem "deploy/.env's COMPOSE_FILE names BOTH compose.dev.yaml and
      compose.prod.yaml ('$compose_file'). Compose accepts this silently, but
      the two layers disagree about which image serves the client and which
      nginx config it uses — one of them is not doing what you think.
      Fix: remove deploy/.env and let ./install.sh or 'make up' write it
           fresh, or edit COMPOSE_FILE to name only one of the two layers."
    elif [ "$MODE" = client ] && [ "$has_dev" = yes ]; then
        problem "deploy/.env was written by 'make up' (it names the dev layer), but you
      are running ./install.sh, which builds the production stack. Continuing
      would quietly build the other stack.
      Fix: run 'make up' instead, or remove deploy/.env to start over.
           (Removing .env keeps your data; 'make reset' is what deletes it.)"
    elif [ "$MODE" = dev ] && [ "$has_dev" = no ]; then
        problem "deploy/.env was written by ./install.sh (it has no dev layer), but you
      are running 'make up', which expects the developer stack.
      Fix: run ./install.sh instead, or remove deploy/.env to start over.
           (Removing .env keeps your data; 'make reset' is what deletes it.)"
    else
        ok "deploy/.env matches the '$MODE' entry point"
    fi

    if [ -n "$(norm "$(env_get EYENED_API_SECRET_KEY)")" ]; then
        ok "EYENED_API_SECRET_KEY is set"
    else
        problem "EYENED_API_SECRET_KEY is empty in deploy/.env, so sessions cannot be
      signed. It is normally generated on first run.
      Fix: remove deploy/.env and re-run, or set it to a long random value."
    fi

    # deploy/.env.example ships change_me for all three; first_run_env only
    # generates real values when .env does not yet exist, so a .env copied
    # from the template by hand (rather than created by an entry point) boots
    # the whole stack on published default passwords, silently.
    bad_secrets=""
    for _var in MYSQL_ROOT_PASSWORD EYENED_DATABASE_PASSWORD EYENED_REDIS_PASSWORD; do
        _val=$(norm "$(env_get "$_var")")
        case "$_val" in
            change_me) bad_secrets="$bad_secrets $_var" ;;
        esac
    done
    if [ -z "$bad_secrets" ]; then
        ok "database and Redis passwords are not the published default"
    else
        problem "These variables in deploy/.env are still the published default
      'change_me', so the stack would boot on a known password:
     $bad_secrets
      Fix: remove deploy/.env and re-run so real secrets are generated, or set
           each one by hand to a long random value."
    fi
  fi
else
    ok "no deploy/.env yet — it will be created from .env.example"
fi

# --- HTTP_PORT ------------------------------------------------------------
# env_get defaults to $DEPLOY_DIR/.env and does not check readability itself
# (lib.sh:88-91: a failed `sed` still lets `tail` exit 0) — called unguarded
# against an unreadable .env it would print a raw, unexplained
# "sed: can't read ...: Permission denied" to stderr on top of the one
# problem already reported above. Only read .env here when it is readable;
# otherwise fall back to .env.example, same as when .env does not exist yet.
http_port=""
if [ -r "$DEPLOY_DIR/.env" ]; then
    http_port=$(norm "$(env_get HTTP_PORT)")
fi
[ -n "$http_port" ] || http_port=$(norm "$(env_get HTTP_PORT "$DEPLOY_DIR/.env.example")")

port_probe() {
    # 0 = in use, 1 = free, 2 = cannot tell. Neither nc nor python3 is
    # guaranteed on a stock macOS or WSL host, so "cannot tell" is a real case
    # and must not be reported as "free". `-w 2` on nc: a busybox build
    # without NC_EXTRA has no `-z` and would otherwise block reading stdin
    # instead of returning promptly — not observed on this host's busybox,
    # but cheap portability insurance.
    if command -v nc >/dev/null 2>&1; then
        nc -z -w 2 127.0.0.1 "$1" >/dev/null 2>&1 && return 0 || return 1
    elif command -v python3 >/dev/null 2>&1; then
        python3 -c 'import socket, sys
s = socket.socket(); s.settimeout(1)
sys.exit(0 if s.connect_ex(("127.0.0.1", int(sys.argv[1]))) == 0 else 1)' "$1" && return 0 || return 1
    fi
    return 2
}

case "$http_port" in
    ''|*[!0-9]*)
        problem "HTTP_PORT in deploy/.env is not a plain number ('$http_port'), so it cannot
      be checked or used to publish the platform.
      Fix: set HTTP_PORT in deploy/.env to a numeric port, e.g. 8080." ;;
    *)
        # A re-run must not trip over its own listener — but only if the
        # running fileserver actually publishes THIS $http_port. compose ps
        # alone doesn't prove that: an operator who followed doctor's own
        # advice ("set HTTP_PORT to a free port") after a previous FAIL, while
        # an old instance of this same stack is still up on the old port,
        # would otherwise get a shortcut that is true about "a fileserver
        # from this stack is running" and false about "on the port being
        # asked about" — and the new port goes completely unprobed.
        # compose() dies if COMPOSE_BIN is unset or empty (lib.sh:56), so it
        # is only called when the detection above actually found a binary.
        ours_matches=no
        if [ -n "$COMPOSE_BIN" ]; then
            set +e
            ours=$(compose ps -q fileserver 2>/dev/null)
            set -e
            if [ -n "$ours" ]; then
                set +e
                published=$(compose port fileserver 80 2>/dev/null)
                set -e
                case "$published" in
                    *:"$http_port") ours_matches=yes ;;
                esac
            fi
        fi
        if [ "$ours_matches" = yes ]; then
            ok "port $http_port is held by this stack's own fileserver (this is a re-run)"
        else
            set +e
            port_probe "$http_port"
            probe=$?
            set -e
            case "$probe" in
                0) problem "Port $http_port is already in use, so the platform cannot bind it.
      Fix: set HTTP_PORT in deploy/.env to a free port (on a machine shared
           with other developers, pick one nobody else is using), or stop
           whatever is holding $http_port." ;;
                2) ok "port $http_port: no probe tool (nc/python3) here, check skipped" ;;
                *) ok "port $http_port is free" ;;
            esac
        fi ;;
esac

# --- Disk --------------------------------------------------------------
# "Where Docker will build" is Docker's data root (default /var/lib/docker)
# plus its volumes — usually a different filesystem from this checkout, and
# the one that actually needs the headroom. `docker info` reports it; fall
# back to DEPLOY_DIR (and say so) only when the daemon is unreachable, since
# the daemon check above may already have failed.
set +e
docker_root=$(docker info --format '{{.DockerRootDir}}' 2>/dev/null)
docker_root_status=$?
set -e
if [ "$docker_root_status" -eq 0 ] && [ -n "$docker_root" ]; then
    disk_target=$docker_root
    disk_label="Docker's data root ($docker_root)"
else
    disk_target=$DEPLOY_DIR
    disk_label="$DEPLOY_DIR (Docker's data root could not be determined)"
fi

set +e
avail_kb=$(df -Pk "$disk_target" 2>/dev/null | awk 'NR == 2 {print $4}')
set -e
case "$avail_kb" in
    ''|*[!0-9]*)
        problem "Could not determine free space on $disk_label ('df -Pk' produced no
      readable number).
      Fix: check that '$disk_target' exists and is on a mounted filesystem." ;;
    *)
        if [ "$avail_kb" -ge 10485760 ]; then
            ok "$((avail_kb / 1048576)) GiB free on $disk_label"
        else
            problem "Only $((avail_kb / 1024)) MiB free on $disk_label. Images plus the
      database volume need roughly 10 GiB.
      Fix: free space, or move Docker's data root to a larger filesystem."
        fi ;;
esac

if [ "$failed" -ne 0 ]; then
    echo >&2
    die "preflight failed — nothing was built. Fix the items above and re-run."
fi
echo "preflight passed."
