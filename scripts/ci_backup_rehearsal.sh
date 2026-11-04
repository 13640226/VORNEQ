#!/usr/bin/env bash
# CI-02/CI-03: runs inside the digest-pinned postgres image as an unprivileged
# user on an --internal Docker network (no internet). Only the disposable
# database reachable as "postgres" is used.
set -euo pipefail
export HOME=/tmp

test "$(id -u)" != "0"
if command -v sudo >/dev/null 2>&1; then echo "sudo present" >&2; exit 1; fi
pg_dump --version
pg_restore --version

if (exec 3<>/dev/tcp/pypi.org/443) 2>/dev/null; then echo "egress to pypi.org is open" >&2; exit 1; fi
echo "egress blocked: pypi.org unreachable"

cp -r /src /tmp/app
cd /tmp/app

row="$(psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -Atc "SELECT current_database() || '|' || current_user || '|' || host(inet_server_addr())")"
echo "identity: $row"
IFS='|' read -r db user addr <<<"$row"
test "$db" = "source_db"
test "$user" = "vorneq"
case "$addr" in
  10.*|172.1[6-9].*|172.2[0-9].*|172.3[0-1].*|192.168.*) ;;
  *) echo "database address $addr is not a private job-network address" >&2; exit 1 ;;
esac

psql "$DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL'
CREATE TABLE restore_probe (
    id integer PRIMARY KEY,
    payload text NOT NULL
);
INSERT INTO restore_probe (id, payload) VALUES (1, 'vorneq-backup-rehearsal');
SQL
createdb -h postgres -U vorneq restore_db

bash scripts/postgres_backup.sh backup
backup_file="$(find "$BACKUP_DIR" -type f -name 'vorneq_*.dump' | head -n 1)"
test -n "$backup_file"
bash scripts/postgres_backup.sh --restore "$backup_file" --confirm-restore

restored="$(psql "$RESTORE_DATABASE_URL" -Atc "SELECT payload FROM restore_probe WHERE id = 1")"
test "$restored" = "vorneq-backup-rehearsal"
echo "backup/restore rehearsal OK"
