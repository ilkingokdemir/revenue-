#!/usr/bin/env bash
# Daily MongoDB backup helper.
#
# Usage:
#   ./scripts/backup_mongo.sh                # writes to /app/backups/<date>.archive.gz
#   ./scripts/backup_mongo.sh /custom/dir    # writes to a custom directory
#   ./scripts/backup_mongo.sh /custom/dir 14 # also rotates older than 14 days
#
# Cron example (every day at 03:15):
#   15 3 * * * /app/scripts/backup_mongo.sh /var/backups/myhotelbox 30 >> /var/log/mongo-backup.log 2>&1

set -euo pipefail

OUT_DIR="${1:-/app/backups}"
RETENTION_DAYS="${2:-7}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

# Read MONGO_URL + DB_NAME from backend/.env without exporting other secrets
if [[ -f /app/backend/.env ]]; then
  MONGO_URL="$(grep -E '^MONGO_URL=' /app/backend/.env | cut -d= -f2-)"
  DB_NAME="$(grep -E '^DB_NAME=' /app/backend/.env | cut -d= -f2-)"
fi

: "${MONGO_URL:?MONGO_URL not set}"
: "${DB_NAME:?DB_NAME not set}"

mkdir -p "$OUT_DIR"
ARCHIVE="$OUT_DIR/${DB_NAME}-${TS}.archive.gz"

echo "[backup_mongo] writing $ARCHIVE"
mongodump --uri="$MONGO_URL" --db="$DB_NAME" --archive="$ARCHIVE" --gzip

# Quick sanity (header + size > 0)
if [[ ! -s "$ARCHIVE" ]]; then
  echo "[backup_mongo] FATAL: archive empty" >&2
  exit 2
fi

SIZE_HUMAN="$(du -h "$ARCHIVE" | cut -f1)"
echo "[backup_mongo] ok size=$SIZE_HUMAN"

# Retention: delete .archive.gz files older than RETENTION_DAYS
find "$OUT_DIR" -maxdepth 1 -type f -name "${DB_NAME}-*.archive.gz" -mtime +"$RETENTION_DAYS" -print -delete

echo "[backup_mongo] done"
