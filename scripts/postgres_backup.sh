#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-backups}"
COMMAND="backup"
DRY_RUN=false
RESTORE_FILE=""
CONFIRM_RESTORE=false

usage() {
  cat <<'EOF'
Usage:
  scripts/postgres_backup.sh [backup] [--dry-run]
  scripts/postgres_backup.sh --list
  scripts/postgres_backup.sh --restore <file> [--dry-run] --confirm-restore

Environment:
  DATABASE_URL           Required for backups.
  RESTORE_DATABASE_URL   Required for restores. Never defaults to DATABASE_URL.
  BACKUP_DIR             Backup directory (default: backups).
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    backup)
      COMMAND="backup"
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --list)
      COMMAND="list"
      shift
      ;;
    --restore)
      COMMAND="restore"
      [[ $# -ge 2 ]] || { echo "--restore requires a file" >&2; exit 2; }
      RESTORE_FILE="$2"
      shift 2
      ;;
    --confirm-restore)
      CONFIRM_RESTORE=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

mkdir -p "$BACKUP_DIR"

case "$COMMAND" in
  list)
    find "$BACKUP_DIR" -maxdepth 1 -type f -name 'vorneq_*.dump' -print | sort
    ;;

  backup)
    : "${DATABASE_URL:?DATABASE_URL is required for backup}"
    timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
    output="$BACKUP_DIR/vorneq_${timestamp}.dump"

    if [[ "$DRY_RUN" == true ]]; then
      echo "DRY RUN: pg_dump --format=custom --no-owner --no-privileges --file=$output <DATABASE_URL>"
      exit 0
    fi

    pg_dump \
      --format=custom \
      --no-owner \
      --no-privileges \
      --file="$output" \
      "$DATABASE_URL"

    test -s "$output"
    echo "Backup created: $output"
    ;;

  restore)
    : "${RESTORE_DATABASE_URL:?RESTORE_DATABASE_URL is required for restore}"
    [[ -n "$RESTORE_FILE" ]] || { echo "Restore file is required" >&2; exit 2; }
    [[ -f "$RESTORE_FILE" ]] || { echo "Backup file not found: $RESTORE_FILE" >&2; exit 1; }

    if [[ "$DRY_RUN" == true ]]; then
      echo "DRY RUN: pg_restore --clean --if-exists --no-owner --no-privileges --dbname=<RESTORE_DATABASE_URL> $RESTORE_FILE"
      exit 0
    fi

    [[ "$CONFIRM_RESTORE" == true ]] || {
      echo "Refusing restore without --confirm-restore" >&2
      exit 2
    }

    pg_restore \
      --clean \
      --if-exists \
      --no-owner \
      --no-privileges \
      --dbname="$RESTORE_DATABASE_URL" \
      "$RESTORE_FILE"

    echo "Restore completed into RESTORE_DATABASE_URL."
    ;;

  *)
    echo "Unsupported command: $COMMAND" >&2
    exit 2
    ;;
esac
