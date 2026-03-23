#!/usr/bin/env bash
# db_restore.sh — Restore all NLP databases into the running MongoDB container.
#
# Usage:
#   ./scripts/db_restore.sh ~/Downloads/nlp_mongo_dump_YYYYMMDD_HHMMSS.tar.gz
#
# WARNING: This overwrites existing data. The stack must be running first.

set -euo pipefail

ARCHIVE="${1:-}"
CONTAINER="nlp_mongodb_dev"

if [[ -z "${ARCHIVE}" ]]; then
  echo "  Usage: ./scripts/db_restore.sh <path/to/nlp_mongo_dump_YYYYMMDD.tar.gz>"
  exit 1
fi

if [[ ! -f "${ARCHIVE}" ]]; then
  echo "  ERROR: Archive not found: ${ARCHIVE}"
  exit 1
fi

# Check container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  echo "  ERROR: Container '${CONTAINER}' is not running."
  echo "         Start the stack first: docker compose up -d"
  exit 1
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
EXTRACT_DIR="/tmp/nlp_restore_${TIMESTAMP}"
CONTAINER_PATH="/tmp/nlp_restore_${TIMESTAMP}"

echo "  Restoring from: ${ARCHIVE}"
echo "  WARNING: This will overwrite existing data in ${CONTAINER}"
read -r -p "  Continue? [y/N] " confirm
[[ "${confirm}" =~ ^[yY]$ ]] || { echo "  Aborted."; exit 0; }

# Extract archive on host
mkdir -p "${EXTRACT_DIR}"
tar -xzf "${ARCHIVE}" -C "${EXTRACT_DIR}"

# Find the inner dump folder
INNER=$(find "${EXTRACT_DIR}" -mindepth 1 -maxdepth 1 -type d | head -1)

# Copy to container
docker cp "${INNER}" "${CONTAINER}:${CONTAINER_PATH}"

# Restore
docker exec "${CONTAINER}" mongorestore --drop "${CONTAINER_PATH}" --quiet

# Cleanup
rm -rf "${EXTRACT_DIR}"
docker exec "${CONTAINER}" rm -rf "${CONTAINER_PATH}"

echo ""
echo "  Restore complete."
echo "  Verify at: http://localhost:8000/stats"
echo ""
