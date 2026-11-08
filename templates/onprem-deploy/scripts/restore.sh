#!/usr/bin/env bash
# Restore a backup into an EMPTY database, then prove it with:
#   agentsmith ops restore-drill --restored-url "$RESTORE_URL"
set -euo pipefail
: "${RESTORE_URL:?RESTORE_URL is required: the empty database to restore into}"
file="${1:?usage: restore.sh <backup.dump>}"
( cd "$(dirname "$file")" && shasum -a 256 --check "$(basename "$file").sha256" )
pg_restore --no-owner --exit-on-error --dbname="$RESTORE_URL" "$file"
echo "Restored. Now run: agentsmith ops restore-drill --restored-url <that URL>"
