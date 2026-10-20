#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="hermes-test-runtime"

cd "$ROOT_DIR"

echo "[Hermes] Building the isolated test runtime..."
docker build --tag "$IMAGE_NAME" .

echo "[Hermes] Running the complete test suite with the repository read-only..."
docker run --rm \
  --mount "type=bind,source=${ROOT_DIR},target=/app,readonly" \
  --workdir /app \
  --entrypoint sh \
  "$IMAGE_NAME" \
  -c 'uv pip install --system pytest pytest-cov && pytest -q -o addopts="" -p no:cacheprovider'
