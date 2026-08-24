#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$SCRIPT_DIR/MedSAM/Medical-SAM2-main"
TARGET_PARENT="$SCRIPT_DIR/MedSAM"
MEDSAM2_GIT_URL="${MEDSAM2_GIT_URL:-https://github.com/ImprintLab/Medical-SAM2.git}"
MEDSAM2_GIT_REF="${MEDSAM2_GIT_REF:-main}"

FOUND_BROKEN_IMAGE=()

if [[ -d "$TARGET_DIR/sam2_train" ]]; then
    echo "Medical-SAM2 source already present at $TARGET_DIR"
    exit 0
fi

mkdir -p "$TARGET_PARENT"

restore_from_dir() {
    local src_dir="$1"
    if [[ ! -f "$src_dir/sam2_train/__init__.py" ]]; then
        return 1
    fi

    rm -rf "$TARGET_DIR"
    mkdir -p "$TARGET_PARENT"
    mv "$src_dir" "$TARGET_DIR"

    if [[ -f "$TARGET_DIR/sam2_train/__init__.py" ]]; then
        echo "Restored Medical-SAM2 source to $TARGET_DIR"
        return 0
    fi
    return 1
}

extract_from_archive() {
    local archive_path="$1"
    local tmp_dir
    tmp_dir="$(mktemp -d)"
    cleanup_tmp() {
        rm -rf "$tmp_dir" >/dev/null 2>&1 || true
    }
    trap cleanup_tmp RETURN

    if ! tar -xf "$archive_path" -C "$tmp_dir"; then
        echo "Failed to extract archive: $archive_path"
        return 1
    fi

    # Find the first directory that contains sam2_train/__init__.py.
    local src_dir
    src_dir="$(find "$tmp_dir" -type f -path '*/sam2_train/__init__.py' -print | head -n1 | sed 's#/sam2_train/__init__.py$##')"
    if [[ -z "$src_dir" ]]; then
        echo "Archive does not contain sam2_train/__init__.py: $archive_path"
        return 1
    fi

    rm -rf "$TARGET_DIR"
    mkdir -p "$TARGET_PARENT"
    if restore_from_dir "$src_dir"; then
        echo "Restored Medical-SAM2 source from archive: $archive_path"
        return 0
    fi

    echo "Archive extraction did not produce expected layout: $archive_path"
    return 1
}

# Try restoring from local archives first.
ARCHIVE_CANDIDATES=(
    "$TARGET_PARENT/Medical-SAM2-main.tar.gz"
    "$TARGET_PARENT/Medical-SAM2-main.tgz"
    "$TARGET_PARENT/Medical-SAM2-main.tar"
    "$SCRIPT_DIR/Medical-SAM2-main.tar.gz"
    "$SCRIPT_DIR/Medical-SAM2-main.tgz"
    "$SCRIPT_DIR/Medical-SAM2-main.tar"
)

for archive in "${ARCHIVE_CANDIDATES[@]}"; do
    if [[ -f "$archive" ]]; then
        echo "Trying to restore Medical-SAM2 from archive: $archive"
        if extract_from_archive "$archive"; then
            exit 0
        fi
    fi
done

restore_from_container_id() {
    local container_id="$1"
    local display_name="$2"
    local copied_any=0

    local dir_candidate
    for dir_candidate in \
        "/app/MedSAM/Medical-SAM2-main" \
        "/workspace/MedSAM/Medical-SAM2-main" \
        "/opt/MedSAM/Medical-SAM2-main" \
        "/Medical-SAM2-main"; do

        local tmp_dir
        tmp_dir="$(mktemp -d)"
        if docker cp "$container_id:$dir_candidate" "$tmp_dir/" >/dev/null 2>&1; then
            copied_any=1
            local src_dir
            src_dir="$(find "$tmp_dir" -type f -path '*/sam2_train/__init__.py' -print | head -n1 | sed 's#/sam2_train/__init__.py$##')"
            if [[ -n "$src_dir" ]] && restore_from_dir "$src_dir"; then
                rm -rf "$tmp_dir" >/dev/null 2>&1 || true
                echo "Restored Medical-SAM2 source from $display_name ($dir_candidate)"
                return 0
            fi
        fi
        rm -rf "$tmp_dir" >/dev/null 2>&1 || true
    done

    local archive_candidate
    for archive_candidate in \
        "/app/MedSAM/Medical-SAM2-main.tar.gz" \
        "/app/MedSAM/Medical-SAM2-main.tgz" \
        "/app/MedSAM/Medical-SAM2-main.tar" \
        "/Medical-SAM2-main.tar.gz" \
        "/Medical-SAM2-main.tgz" \
        "/Medical-SAM2-main.tar"; do

        local tmp_archive
        tmp_archive="$(mktemp)"
        if docker cp "$container_id:$archive_candidate" "$tmp_archive" >/dev/null 2>&1; then
            copied_any=1
            if extract_from_archive "$tmp_archive"; then
                rm -f "$tmp_archive" >/dev/null 2>&1 || true
                echo "Restored Medical-SAM2 source from $display_name ($archive_candidate)"
                return 0
            fi
        fi
        rm -f "$tmp_archive" >/dev/null 2>&1 || true
    done

    if [[ "$copied_any" -eq 0 ]]; then
        FOUND_BROKEN_IMAGE+=("$display_name")
    fi

    return 1
}

# Try copying from local images.
declare -a CANDIDATE_IMAGES=(
    "eyeneed-bundle-medsam:latest"
    "eyeneed-bundle-medsam"
    "eyened-bundle-medsam:latest"
    "eyened-bundle-medsam"
    "medsam:latest"
)

if command -v docker >/dev/null 2>&1; then
    while IFS= read -r discovered; do
        [[ -z "$discovered" ]] && continue
        CANDIDATE_IMAGES+=("$discovered")
    done < <(docker image ls --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | awk 'tolower($0) ~ /medsam/ {print}')
fi

declare -A SEEN_IMAGES=()
for img in "${CANDIDATE_IMAGES[@]}"; do
    [[ -z "$img" ]] && continue
    if [[ -n "${SEEN_IMAGES[$img]:-}" ]]; then
        continue
    fi
    SEEN_IMAGES[$img]=1

    if docker image inspect "$img" >/dev/null 2>&1; then
        echo "Trying to restore Medical-SAM2 from image: $img"
        cid="$(docker create "$img")"
        cleanup() {
            docker rm -f "$cid" >/dev/null 2>&1 || true
        }
        trap cleanup EXIT

        if restore_from_container_id "$cid" "image $img"; then
            cleanup
            trap - EXIT
            exit 0
        fi

        cleanup
        trap - EXIT
    fi
done

# Try copying from running/stopped containers that include "medsam" in their name.
while IFS= read -r container_id; do
    [[ -z "$container_id" ]] && continue
    cname="$(docker inspect --format '{{.Name}}' "$container_id" 2>/dev/null | sed 's#^/##')"
    echo "Trying to restore Medical-SAM2 from container: $cname"
    if restore_from_container_id "$container_id" "container $cname"; then
        exit 0
    fi
done < <(docker ps -a --format '{{.ID}} {{.Names}}' | awk '$2 ~ /medsam/ {print $1}')

# Final fallback: restore from GitHub when online.
if command -v git >/dev/null 2>&1; then
    echo "Trying to restore Medical-SAM2 from GitHub: $MEDSAM2_GIT_URL (ref: $MEDSAM2_GIT_REF)"
    tmp_clone="$(mktemp -d)"
    cleanup_clone() {
        rm -rf "$tmp_clone" >/dev/null 2>&1 || true
    }
    trap cleanup_clone RETURN

    if git clone --depth 1 --branch "$MEDSAM2_GIT_REF" "$MEDSAM2_GIT_URL" "$tmp_clone/repo" >/dev/null 2>&1; then
        if restore_from_dir "$tmp_clone/repo"; then
            echo "Restored Medical-SAM2 source from GitHub"
            trap - RETURN
            cleanup_clone
            exit 0
        fi
        echo "GitHub clone succeeded but repository layout is not compatible (missing sam2_train/__init__.py)."
    else
        echo "GitHub restore attempt failed (network unavailable or repository access issue)."
    fi

    trap - RETURN
    cleanup_clone
fi

echo "Could not restore Medical-SAM2 source from local images/containers."
if [[ "${#FOUND_BROKEN_IMAGE[@]}" -gt 0 ]]; then
    echo "The following local images were found but do not contain Medical-SAM2 source:"
    printf '  - %s\n' "${FOUND_BROKEN_IMAGE[@]}"
    echo "Rebuild your MedSAM bundle image after adding MedSAM/Medical-SAM2-main to this workspace."
fi
echo "Expected local path: $TARGET_DIR"
echo "Provide Medical-SAM2-main as one of:"
echo "  - clone source: git clone --depth 1 --branch $MEDSAM2_GIT_REF $MEDSAM2_GIT_URL $TARGET_DIR"
echo "  - folder: $TARGET_DIR"
echo "  - archive: $TARGET_PARENT/Medical-SAM2-main.tar.gz (or .tgz/.tar)"
exit 1
