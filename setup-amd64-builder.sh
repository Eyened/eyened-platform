#!/bin/bash
# Setup docker buildx for amd64 builds on macOS
# This ensures you can build amd64 Docker images on your Mac

set -euo pipefail

BUILDER_NAME="eyened-amd64-builder"

echo "Setting up Docker buildx for amd64 builds on macOS..."
echo ""

# Check if Docker is running
if ! docker ps >/dev/null 2>&1; then
    echo "✗ Docker is not running. Please start Docker Desktop."
    exit 1
fi

echo "✓ Docker is running"

# Check if buildx is available
if ! docker buildx version >/dev/null 2>&1; then
    echo "⚠ docker buildx is not available."
    echo "  Docker Desktop 12.0+ includes buildx by default."
    echo "  Please update Docker Desktop to the latest version."
    exit 1
fi

echo "✓ docker buildx is available"
echo ""

# Check if builder already exists
if docker buildx ls | grep -q "^$BUILDER_NAME"; then
    echo "✓ Builder '$BUILDER_NAME' already exists"
    docker buildx use "$BUILDER_NAME"
else
    echo "Creating builder '$BUILDER_NAME' for amd64 builds..."
    
    # Create a new builder with amd64 support
    if docker buildx create \
        --name "$BUILDER_NAME" \
        --use \
        --platform linux/amd64,linux/arm64 \
        --bootstrap 2>/dev/null; then
        echo "✓ Builder created and bootstrapped"
    else
        echo "✗ Failed to create builder"
        echo "  Try running: docker buildx create --name $BUILDER_NAME --use --platform linux/amd64"
        exit 1
    fi
fi

echo ""
echo "Verifying builder capabilities..."

# Verify the builder supports linux/amd64
if docker buildx build --platform linux/amd64 --dry-run . >/dev/null 2>&1; then
    echo "✓ Builder supports linux/amd64"
else
    echo "⚠ Builder may not support linux/amd64"
    echo "  This might fail when building amd64 images"
fi

echo ""
echo "✓ Setup complete!"
echo ""
echo "You can now run:"
echo "  ./package.sh          # Build amd64 images and bundle"
echo "  ./build-amd64-bundle.sh  # Alternative amd64 build"
echo ""
echo "Note: Building amd64 images on an ARM64 Mac will use emulation."
echo "For best performance on production amd64 servers, build on an amd64 Linux machine."
echo ""
