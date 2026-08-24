#!/bin/bash
# Build amd64 bundle - Run this script on an amd64 Linux machine for production deployment
# 
# Usage: ./build-amd64-bundle.sh
# Requirements: Docker/Docker Compose on an amd64 Linux system
#
# This script creates an amd64-compatible Docker image bundle for deploying
# the EyeNED CVI application on amd64 Linux servers.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

BUNDLE_DIR="bundle"
BUNDLE_NAME="eyeneed-bundle-amd64.tar"
OUTPUT_FILE="$BUNDLE_DIR/$BUNDLE_NAME"

# Determine target platform
ARCH=$(uname -m)
if [[ "$ARCH" == "x86_64" || "$ARCH" == "amd64" ]]; then
    PLATFORM="linux/amd64"
else
    PLATFORM="linux/amd64"
    echo "⚠ Warning: defaulting to $PLATFORM though host is $ARCH"
fi

# Ensure Docker is available
if ! command -v docker >/dev/null 2>&1; then
    echo "✗ Error: docker is not installed or not in PATH"
    exit 1
fi
if ! docker info >/dev/null 2>&1; then
    echo "✗ Error: cannot connect to Docker daemon. Is the daemon running or do you need sudo?"
    exit 1
fi

MEDSAM_SOURCE_DIR="$SCRIPT_DIR/MedSAM/Medical-SAM2-main"
if [[ ! -f "$MEDSAM_SOURCE_DIR/sam2_train/__init__.py" ]]; then
    echo "✗ Error: Missing Medical-SAM2 source at $MEDSAM_SOURCE_DIR"
    echo "Provide one of the following before building the bundle image:"
    echo "  - MedSAM/Medical-SAM2-main/ (folder)"
    echo "  - MedSAM/Medical-SAM2-main.tar.gz (then run ./restore-medsam-source.sh)"
    exit 1
fi

# Ensure the bundle directory exists
mkdir -p "$BUNDLE_DIR"

echo "Building Docker images for linux/amd64..."
# Clean up dangling images to avoid manifest issues
docker image prune -f --filter "dangling=true" 2>/dev/null || true

# Build server image
echo "  Building server image..."
docker build --pull --platform "$PLATFORM" -f docker/Dockerfile.server -t eyeneed-bundle-server:latest .
echo "    ✓ Server image: eyeneed-bundle-server:latest"

# Build client image
echo "  Building client image..."
docker build --pull --platform "$PLATFORM" -f docker/Dockerfile.client -t eyeneed-bundle-client:latest .
echo "    ✓ Client image: eyeneed-bundle-client:latest"

# Build MedSAM image
echo "  Building MedSAM image..."
docker build --pull --platform "$PLATFORM" -f docker/Dockerfile.medsam -t eyeneed-bundle-medsam:latest .
echo "    ✓ MedSAM image: eyeneed-bundle-medsam:latest"

echo ""
echo "Pulling upstream images..."
for img in mysql:8.0.27 redis:7-alpine nginx:latest adminer:latest; do
    echo "  $img..."
    docker pull --platform "$PLATFORM" "$img" || echo "    (may already be cached or platform not available)"
done

echo ""
echo "Identifying images to be packaged..."

# List of images to save
IMAGES_TO_SAVE=(
    "eyeneed-bundle-server:latest"
    "eyeneed-bundle-client:latest"
    "eyeneed-bundle-medsam:latest"
    "mysql:8.0.27"
    "redis:7-alpine"
    "nginx:latest"
    "adminer:latest"
)

# Verify all images exist
for img in "${IMAGES_TO_SAVE[@]}"; do
    if ! docker image inspect "$img" >/dev/null 2>&1; then
        echo "✗ Error: Image not found: $img"
        exit 1
    fi
done

echo ""
echo "Creating Docker image bundle..."
echo "  Output: $OUTPUT_FILE"

# Remove existing bundle
if [[ -f "$OUTPUT_FILE" ]]; then
    rm "$OUTPUT_FILE"
fi

# Save all images to tar file
docker save "${IMAGES_TO_SAVE[@]}" -o "$OUTPUT_FILE"

if [[ ! -f "$OUTPUT_FILE" ]]; then
    echo "✗ Error: Failed to create bundle"
    exit 1
fi

# Get file size
if command -v stat >/dev/null; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        size=$(stat -f%z "$OUTPUT_FILE" 2>/dev/null || du -h "$OUTPUT_FILE" | awk '{print $1}')
    else
        # Linux
        size=$(stat -c%s "$OUTPUT_FILE" 2>/dev/null || du -h "$OUTPUT_FILE" | awk '{print $1}')
    fi
else
    size=$(du -h "$OUTPUT_FILE" | awk '{print $1}')
fi

echo ""
echo "✓ Bundle created successfully!"
echo "  File: $OUTPUT_FILE"
echo "  Size: $size"
echo "  Contains:"
for img in "${IMAGES_TO_SAVE[@]}"; do
    echo "    • $img"
done

echo ""
echo "Next steps:"
echo "  1. Transfer the bundle to your amd64 Linux deployment machine:"
echo "     scp $OUTPUT_FILE user@target-machine:/deployment/path/"
echo ""
echo "  2. On the target machine, run:"
echo "     cd /deployment/path"
echo "     chmod +x deploy.sh verify.sh"
echo "     ./verify.sh"
echo "     ./deploy.sh"
echo ""
