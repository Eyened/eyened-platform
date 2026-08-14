#!/bin/sh
# Generate every storage artifact from deploy/storage-mounts.conf:
#
#   deploy/compose.storage.yaml          bind mounts + EYENED_STORAGE_MOUNTS
#   deploy/nginx/storage.d/storage.conf  one internal nginx location per key
#
# Both are always written, even with no mounts: COMPOSE_FILE names
# compose.storage.yaml, so a missing file breaks compose before make runs.
#
# storage-mounts.conf is one "<key> <absolute-path>" pair per line. Blank lines
# and # comments are ignored. Anything else is an error, never a silently
# dropped mount.
set -eu

REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$REPO_ROOT/deploy/scripts/lib.sh"

SRC="$DEPLOY_DIR/storage-mounts.conf"
COMPOSE_OUT="$DEPLOY_DIR/compose.storage.yaml"
NGINX_OUT="$DEPLOY_DIR/nginx/storage.d/storage.conf"

[ -f "$SRC" ] || die "error: $SRC not found.
      Fix: cp deploy/storage-mounts.conf.example deploy/storage-mounts.conf"
# `-f` above is a TYPE check (regular file only — rejects a directory, FIFO
# or other non-regular node at $SRC, which is exactly what Docker creates at
# a bind-mount source that does not yet exist) and is NOT a readability
# check. `-r` below is readability and is NOT a type check. Neither implies
# the other, so both are required, as two separate guards with distinct
# messages. `done < "$SRC"` further down is a compound command whose own
# redirect failure `set -e` does NOT abort — the loop body would simply
# never run, every mount would silently vanish, and both outputs would be
# regenerated as empty. Check both explicitly, the same way lib.sh's C1 fix
# does, so this never depends on `set -e` to be safe.
[ -r "$SRC" ] || die "error: $SRC exists but is not readable by this user.
      Fix: check its permissions/ownership, e.g. 'ls -l $SRC'."

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# `printf ''`, not `:`, as the truncating command: `:` is a POSIX special
# built-in, and a special built-in's own redirection failure is required to
# exit the shell immediately — bypassing `||` entirely on some shells (dash,
# busybox) rather than reaching `die` with a clear message. `printf` is an
# ordinary utility, so its redirection failure is reported through its exit
# status like any other command and `||` reliably catches it everywhere.
printf '' > "$work/mounts" || die "error: could not create $work/mounts (see any error above)."
printf '' > "$work/keylines" || die "error: could not create $work/keylines (see any error above)."
lineno=0
CR=$(printf '\r')
# `rest` catches a third field, which is how a path containing a space shows
# up. Rejecting it beats mounting a silently truncated path.
while read -r key path rest || [ -n "$key" ]; do
    lineno=$((lineno + 1))
    case "$key" in ''|\#*) continue ;; esac

    # CRLF guard. IFS never contains \r, so a Windows line ending stays glued
    # to the last field `read` captured (usually $path, or $rest if the line
    # over-splits) instead of showing up as its own token — it slips past the
    # key-charset check (which never sees it) and every other check, ending
    # up baked into the nginx alias and the compose bind path. Reject by
    # name rather than silently stripping: a file with CRLF endings needs
    # fixing, and stripping would hide that from the operator.
    case "$key$path$rest" in
        *"$CR"*) die "error: $SRC line $lineno has Windows (CRLF) line endings.
      Fix: convert the file to Unix line endings, e.g. 'dos2unix $SRC' or
      'sed -i \"s/\\r\$//\" $SRC'." ;;
    esac

    if [ -z "$path" ] || [ -n "$rest" ]; then
        die "error: $SRC line $lineno is not a '<key> <absolute-path>' pair:
        $key $path $rest
      One key and one path per line. Paths may not contain spaces."
    fi

    case "$path" in
        /*) ;;
        *)  die "error: storage mount '$key' (line $lineno) must be an absolute host path, got: $path" ;;
    esac

    # B2 — key charset: allow-list [A-Za-z0-9_-]+ only. This is what keeps a
    # key from injecting nginx config syntax into the generated
    # `location /KEY/ {` line (';', '{', '}', '/', whitespace) and keeps it
    # out of the JSON/YAML value below (quotes, '$', backslash, ':').
    case "$key" in
        *[!A-Za-z0-9_-]*|'')
            die "error: storage mount key '$key' (line $lineno) contains characters other than
      letters, digits, '_' and '-'. Rename the key." ;;
    esac

    # B1 — reserved keys: these routes are already owned by nginx config
    # this generator does not control. A duplicate 'location /api/' or
    # 'location /thumbnails/' refuses nginx at startup (loud); a generated
    # 'location /_app/' silently intercepts the SPA's own non-immutable
    # /_app/ requests ahead of client.d/prod.conf's '/_app/immutable/' and
    # 404s them, because it is 'internal;' and a longer prefix than '/'.
    case "$key" in
        api)        die "error: storage mount key 'api' (line $lineno) collides with
      'location /api/' in deploy/nginx/default.conf.template. Rename the key." ;;
        thumbnails) die "error: storage mount key 'thumbnails' (line $lineno) collides with
      'location /thumbnails/' in deploy/nginx/default.conf.template. Rename the key." ;;
        _app)       die "error: storage mount key '_app' (line $lineno) collides with
      'location /_app/immutable/' in deploy/nginx/client.d/prod.conf and would
      silently 404 the SPA's own /_app/ requests. Rename the key." ;;
    esac

    # B3 — path safety. ':' breaks the compose 'PATH:PATH:ro' bind spec
    # (silently misread or opaquely rejected); '\' and '#' are nginx `alias`
    # metacharacters; '/' itself would bind-mount the host root into the
    # container. Quotes and '$' would break out of the single-quoted YAML
    # scalar the JSON value is embedded in.
    case "$path" in
        *:*)  die "error: storage mount path for '$key' (line $lineno) contains ':', which
      breaks the compose bind mount 'PATH:PATH:ro'. Rename the directory." ;;
        *\\*) die "error: storage mount path for '$key' (line $lineno) contains a backslash,
      which is unsafe in the generated nginx 'alias' directive. Rename the directory." ;;
        *\#*) die "error: storage mount path for '$key' (line $lineno) contains '#', which is
      the nginx comment character. Rename the directory." ;;
    esac
    # A '..' path segment trivially bypasses the '/'-root guard below (e.g.
    # '/mnt/a/../../etc' resolves outside the intended tree once nginx's
    # `alias` and the bind mount follow it). Every absolute path with a '..'
    # segment contains it either as '/../ ' in the middle or '/..' at the
    # end, so one pattern pair covers all positions.
    case "$path" in
        */../*|*/..) die "error: storage mount path for '$key' (line $lineno) contains a '..'
      path segment, which can point outside the intended directory. Use a
      direct absolute path with no '..' components." ;;
    esac
    case "$key$path" in
        *[\'\"\$]*) die "error: storage mount '$key' (line $lineno) contains a quote or \$, which
      cannot be passed safely through the generated compose YAML. Rename the
      key or move the directory." ;;
    esac
    if [ "$path" = "/" ]; then
        die "error: storage mount '$key' (line $lineno) points at '/', which would bind-mount
      the host root into the container. Use a specific directory."
    fi

    # B4 — duplicate keys: a repeat yields two identical nginx locations
    # (startup failure) and two identical JSON keys (last one silently wins).
    #
    # This lookup and the two appends below are explicitly `|| die`d rather
    # than left to `set -e`: `set -e` alone is not a policy this script
    # relies on for correctness (see the -f/-r comment above), and a failed
    # append here (e.g. a full disk) must not silently drop a mount while the
    # script still prints its success banner and exits 0.
    prev_line=$(awk -F'\t' -v k="$key" '$1 == k { print $2; exit }' "$work/keylines") ||
        die "error: could not check '$key' (line $lineno) against earlier mounts — see the
      error above."
    if [ -n "$prev_line" ]; then
        die "error: storage mount key '$key' is defined twice: line $prev_line and line $lineno.
      Each key may appear once in $SRC."
    fi
    printf '%s\t%s\n' "$key" "$lineno" >> "$work/keylines" ||
        die "error: could not record mount '$key' (line $lineno) — see the error above."

    printf '%s\t%s\n' "$key" "$path" >> "$work/mounts" ||
        die "error: could not record mount '$key' (line $lineno) — see the error above."
done < "$SRC"

# --- nginx locations -------------------------------------------------------
{
    echo "# GENERATED by deploy/scripts/gen-storage.sh from storage-mounts.conf."
    echo "# Do not edit: your changes will be overwritten on the next run."
    awk -F'\t' '{
        printf "\nlocation /%s/ {\n", $1
        printf "    internal;\n"
        printf "    # the trailing slash on alias matters\n"
        printf "    alias %s/;\n}\n", $2
    }' "$work/mounts"
} > "$work/storage.conf" ||
    die "error: could not write $work/storage.conf (see any error above)."
mkdir -p "$(dirname "$NGINX_OUT")"
mv "$work/storage.conf" "$NGINX_OUT"

# --- compose overlay -------------------------------------------------------
if [ -s "$work/mounts" ]; then
    json=$(awk -F'\t' '{printf "%s\"%s\":\"%s\"", (NR > 1 ? "," : ""), $1, $2}' "$work/mounts")
    {
        echo "# GENERATED by deploy/scripts/gen-storage.sh from storage-mounts.conf."
        echo "# Do not edit: your changes will be overwritten on the next run."
        echo "services:"
        echo "  server:"
        echo "    environment:"
        echo "      EYENED_STORAGE_MOUNTS: '{$json}'"
        echo "    volumes:"
        awk -F'\t' '{printf "      - %s:%s:ro\n", $2, $2}' "$work/mounts"
        echo "  fileserver:"
        echo "    volumes:"
        awk -F'\t' '{printf "      - %s:%s:ro\n", $2, $2}' "$work/mounts"
    } > "$work/compose.storage.yaml" ||
        die "error: could not write $work/compose.storage.yaml (see any error above)."
else
    {
        echo "# GENERATED by deploy/scripts/gen-storage.sh — no storage mounts configured."
        echo "# EYENED_STORAGE_MOUNTS is deliberately absent rather than '{}': any"
        echo "# non-empty value switches the ORM into local mode, and local mode with"
        echo "# nothing to resolve is worse than the API adapter it replaces."
        echo "services: {}"
    } > "$work/compose.storage.yaml" ||
        die "error: could not write $work/compose.storage.yaml (see any error above)."
fi
mv "$work/compose.storage.yaml" "$COMPOSE_OUT"

count=$(wc -l < "$work/mounts" | tr -d ' ')
echo "==> generated compose.storage.yaml and nginx/storage.d/storage.conf ($count mount(s))"
