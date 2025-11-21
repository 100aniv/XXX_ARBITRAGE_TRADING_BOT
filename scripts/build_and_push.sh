#!/bin/bash
# ============================================================================
# Arbitrage Engine - Build and Push Docker Image
# Optional script for CI/CD pipeline or manual registry push
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
IMAGE_NAME="${IMAGE_NAME:-arbitrage-engine}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
REGISTRY="${REGISTRY:-}"  # Empty = local only, set to registry URL for push
DOCKERFILE_PATH="docker/Dockerfile"
BUILD_CONTEXT="."

echo -e "${GREEN}[BUILD]${NC} Building Docker image: ${IMAGE_NAME}:${IMAGE_TAG}"

# ============================================================================
# Build image
# ============================================================================
docker build \
    -t "${IMAGE_NAME}:${IMAGE_TAG}" \
    -f "${DOCKERFILE_PATH}" \
    "${BUILD_CONTEXT}"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}[BUILD]${NC} Image built successfully"
else
    echo -e "${RED}[BUILD]${NC} Image build failed"
    exit 1
fi

# ============================================================================
# Tag and push to registry (if configured)
# ============================================================================
if [ ! -z "$REGISTRY" ]; then
    echo -e "${YELLOW}[PUSH]${NC} Tagging image for registry: ${REGISTRY}"
    
    docker tag "${IMAGE_NAME}:${IMAGE_TAG}" "${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
    
    echo -e "${YELLOW}[PUSH]${NC} Pushing to registry..."
    docker push "${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}[PUSH]${NC} Image pushed successfully to ${REGISTRY}"
    else
        echo -e "${RED}[PUSH]${NC} Image push failed"
        exit 1
    fi
else
    echo -e "${YELLOW}[INFO]${NC} No registry configured, skipping push"
fi

# ============================================================================
# Display image info
# ============================================================================
echo -e "${GREEN}[INFO]${NC} Image details:"
docker images "${IMAGE_NAME}:${IMAGE_TAG}"

echo -e "${GREEN}[SUCCESS]${NC} Build complete!"
echo -e "${YELLOW}[INFO]${NC} To run: docker-compose -f docker/docker-compose.yml up -d"
