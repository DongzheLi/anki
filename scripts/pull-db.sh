#!/bin/sh
# ============================================================================
# pull-db.sh — copy the production anki SQLite DB down to this machine.
#
# Production serves the DB live in WAL mode, so a plain scp of the file can be
# torn. Instead we ask the droplet to make a consistent snapshot with SQLite's
# online backup API, download that, validate it, and only then atomically swap
# it into server/anki.db. A good local DB is never clobbered by a failed or
# half-finished download, and one rolling backup (server/anki.db.prev) is kept.
#
# Run by hand with `make db-pull`, or on a schedule by the LaunchAgent in
# scripts/com.dongzhewei.anki-dbpull.plist (twice a day).
# ============================================================================
set -eu

HOST=do-droplet-443                         # ~/.ssh/config alias (port 443 + key)
REMOTE_DB=/srv/www/anki/server/anki.db

# Resolve the repo root from this script's own location, so it works under
# launchd (which starts the job with cwd=/).
REPO="$(cd "$(dirname "$0")/.." && pwd)"
DB="$REPO/server/anki.db"
TMP="$REPO/server/.anki.db.incoming"
SNAP="/tmp/anki-snapshot.$$.db"             # unique remote temp (this run's PID)

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') db-pull: $*"; }

# A partial download must never linger as the next run's input.
cleanup() { rm -f "$TMP"; }
trap cleanup EXIT

# 1. Consistent snapshot on the droplet — no need to stop the live service.
ssh "$HOST" "python3 -c \"import sqlite3; s=sqlite3.connect('$REMOTE_DB'); d=sqlite3.connect('$SNAP'); s.backup(d); s.close(); d.close()\""

# 2. Download it, then drop the remote temp.
mkdir -p "$REPO/server"
scp -q "$HOST:$SNAP" "$TMP"
ssh "$HOST" "rm -f '$SNAP'"

# 3. Validate before trusting it: integrity check + a real query. If this fails,
#    set -e aborts here and the existing server/anki.db is left untouched.
items="$(python3 -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); assert c.execute('pragma integrity_check').fetchone()[0]=='ok'; print(c.execute('select count(*) from items').fetchone()[0]); c.close()" "$TMP")"

# 4. Swap in: keep one rolling backup, replace atomically, drop stale sidecars
#    (the -wal/-shm belonged to the old DB; the snapshot is self-contained).
[ -e "$DB" ] && cp -p "$DB" "$DB.prev"
mv -f "$TMP" "$DB"
rm -f "$DB-wal" "$DB-shm"
log "synced production db ($items items)"
