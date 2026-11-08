#!/usr/bin/env bash
# Back up the database to BACKUP_DIR, with a checksum. Run from cron, or from the
# Helm CronJob (backup.enabled). Encrypt BACKUP_DIR at rest: this writes a dump.
set -euo pipefail
: "${DATABASE_URL:?DATABASE_URL is required}"
: "${BACKUP_DIR:?BACKUP_DIR is required}"
mkdir -p "$BACKUP_DIR"
file="$BACKUP_DIR/agentsmith-$(date -u +%Y%m%dT%H%M%SZ).dump"
pg_dump --format=custom --no-owner --file="$file" "$DATABASE_URL"
( cd "$BACKUP_DIR" && shasum -a 256 "$(basename "$file")" > "$(basename "$file").sha256" )
echo "$file"
