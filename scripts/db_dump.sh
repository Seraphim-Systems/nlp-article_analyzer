#!/usr/bin/env bash
# db_dump.sh — Export all NLP databases from the running MongoDB container.
#
# Usage:
#   ./scripts/db_dump.sh                    # saves to ~/Downloads/
#   ./scripts/db_dump.sh /path/to/dir       # saves to specified directory
#
# Output: nlp_mongo_dump_YYYYMMDD_HHMMSS.tar.gz
# Restore: ./scripts/db_restore.sh <path/to/archive.tar.gz>

set -euo pipefail

OUTPUT_DIR="${1:-$HOME/Downloads}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE_NAME="nlp_mongo_dump_${TIMESTAMP}.tar.gz"
CONTAINER="nlp_mongodb_dev"
DUMP_PATH="/tmp/nlp_dump_${TIMESTAMP}"

echo "  Dumping MongoDB from container: ${CONTAINER}"

# Check container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  echo "  ERROR: Container '${CONTAINER}' is not running."
  echo "         Start the stack first: docker compose up -d"
  exit 1
fi

# Run mongodump inside container
docker exec "${CONTAINER}" mongodump --out "${DUMP_PATH}" --quiet
echo "  Dump complete inside container"

# Copy dump to host
docker cp "${CONTAINER}:${DUMP_PATH}" "/tmp/nlp_dump_host_${TIMESTAMP}"
echo "  Copied to host"

# Compress
mkdir -p "${OUTPUT_DIR}"
tar -czf "${OUTPUT_DIR}/${ARCHIVE_NAME}" -C "/tmp" "nlp_dump_host_${TIMESTAMP}"

# Cleanup
rm -rf "/tmp/nlp_dump_host_${TIMESTAMP}"
docker exec "${CONTAINER}" rm -rf "${DUMP_PATH}"

FINAL_PATH="${OUTPUT_DIR}/${ARCHIVE_NAME}"
SIZE=$(du -sh "${FINAL_PATH}" | cut -f1)

echo ""
echo "  Done: ${FINAL_PATH}  (${SIZE})"
echo ""
echo "  To restore on another machine:"
echo "    1. Copy the archive to the target machine"
echo "    2. Start the stack: docker compose up -d"
echo "    3. Run: ./scripts/db_restore.sh ${FINAL_PATH}"
echo ""
