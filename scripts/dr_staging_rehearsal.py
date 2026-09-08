#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

SOURCE_ENV = "STAGING_DATABASE_URL"
TARGET_ENV = "DR_RESTORE_DATABASE_URL"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(args: list[str], *, capture: bool = False) -> str:
    result = subprocess.run(
        args,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if capture else ""


def require_command(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"Required command not found: {name}")


def parse_database_url(url: str) -> tuple[str, int, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise RuntimeError("Invalid PostgreSQL URL")
    host = (parsed.hostname or "").lower()
    port = parsed.port or 5432
    database = parsed.path.lstrip("/")
    if not host or not database:
        raise RuntimeError("Database URL is missing host or database name")
    return host, port, database


def sql(database_url: str, query: str) -> str:
    return run(
        [
            "psql",
            database_url,
            "-X",
            "-A",
            "-t",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            query,
        ],
        capture=True,
    )


@dataclass(frozen=True)
class DatabaseIdentity:
    address: str
    port: int
    database: str
    version_num: int


def database_identity(database_url: str) -> DatabaseIdentity:
    result = sql(
        database_url,
        """
        SELECT
            COALESCE(inet_server_addr()::text, ''),
            inet_server_port(),
            current_database(),
            current_setting('server_version_num');
        """,
    )
    parts = result.split("|")
    if len(parts) != 4:
        raise RuntimeError("Unexpected database identity response")
    return DatabaseIdentity(parts[0], int(parts[1]), parts[2], int(parts[3]))


def require_postgres_18(identity: DatabaseIdentity, label: str) -> None:
    if not 180000 <= identity.version_num < 190000:
        raise RuntimeError(
            f"{label} must be PostgreSQL 18; server_version_num={identity.version_num}"
        )


def guard_source_target(source: str, target: str) -> None:
    if parse_database_url(source) == parse_database_url(target):
        raise RuntimeError("REFUSING RESTORE: source and target URLs identify the same database")

    source_db = database_identity(source)
    target_db = database_identity(target)

    if (
        source_db.address,
        source_db.port,
        source_db.database,
    ) == (
        target_db.address,
        target_db.port,
        target_db.database,
    ):
        raise RuntimeError("REFUSING RESTORE: source and target are the same PostgreSQL database")

    require_postgres_18(source_db, "Source")
    require_postgres_18(target_db, "Target")


def schema_fingerprint(database_url: str) -> str:
    return sql(
        database_url,
        r"""
        SELECT md5(COALESCE(string_agg(
            table_schema || '.' || table_name || '.' || column_name || ':' ||
            data_type || ':' || is_nullable || ':' || ordinal_position,
            E'\n' ORDER BY table_schema, table_name, ordinal_position
        ), ''))
        FROM information_schema.columns
        WHERE table_schema = 'public';
        """,
    )


def schema_rows(database_url: str) -> set[str]:
    result = sql(
        database_url,
        r"""
        SELECT
            table_schema || '.' || table_name || '.' || column_name || ':' ||
            data_type || ':' || is_nullable || ':' || ordinal_position::text
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_schema, table_name, ordinal_position;
        """,
    )
    return {row for row in result.splitlines() if row}


def schema_set_difference(source_url: str, target_url: str) -> tuple[set[str], set[str]]:
    source_rows = schema_rows(source_url)
    target_rows = schema_rows(target_url)
    return source_rows - target_rows, target_rows - source_rows


def table_count(database_url: str) -> str:
    return sql(
        database_url,
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema='public' AND table_type='BASE TABLE';",
    )


def migration_fingerprint(database_url: str) -> str:
    return sql(
        database_url,
        r"""
        SELECT CASE
          WHEN to_regclass('public.django_migrations') IS NULL THEN 'missing'
          ELSE (
            SELECT count(*)::text || ':' || md5(COALESCE(string_agg(
              app || ':' || name, E'\n' ORDER BY app, name
            ), ''))
            FROM django_migrations
          )
        END;
        """,
    )


def content_type_fingerprint(database_url: str) -> str:
    return sql(
        database_url,
        r"""
        SELECT CASE
          WHEN to_regclass('public.django_content_type') IS NULL THEN 'missing'
          ELSE (
            SELECT count(*)::text || ':' || md5(COALESCE(string_agg(
              app_label || ':' || model, E'\n' ORDER BY app_label, model
            ), ''))
            FROM django_content_type
          )
        END;
        """,
    )


@dataclass(frozen=True)
class Fingerprints:
    schema: str
    tables: str
    migrations: str
    content_types: str


def fingerprints(database_url: str) -> Fingerprints:
    return Fingerprints(
        schema_fingerprint(database_url),
        table_count(database_url),
        migration_fingerprint(database_url),
        content_type_fingerprint(database_url),
    )


def create_backup(source: str, backup_file: Path) -> None:
    run([
        "pg_dump",
        "--format=custom",
        "--no-owner",
        "--no-privileges",
        "--file",
        str(backup_file),
        source,
    ])
    if not backup_file.is_file() or backup_file.stat().st_size == 0:
        raise RuntimeError("Backup file was not created correctly")


def restore_backup(target: str, backup_file: Path) -> None:
    run([
        "pg_restore",
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        "--dbname",
        target,
        str(backup_file),
    ])


def write_summary(lines: list[str]) -> None:
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary:
        return
    with open(summary, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def schema_diff_diagnostic_lines(source_url: str, target_url: str) -> list[str]:
    only_source, only_target = schema_set_difference(source_url, target_url)
    lines = ["Schema diff diagnostic:"]

    lines.append(f"  Rows only in source: {len(only_source)}")
    for index, row in enumerate(sorted(only_source)[:20], 1):
        lines.append(f"    {index}. {row}")
    if len(only_source) > 20:
        lines.append(f"    ... and {len(only_source) - 20} more")

    lines.append(f"  Rows only in target: {len(only_target)}")
    for index, row in enumerate(sorted(only_target)[:20], 1):
        lines.append(f"    {index}. {row}")
    if len(only_target) > 20:
        lines.append(f"    ... and {len(only_target) - 20} more")

    if not only_source and not only_target:
        lines.append("  Schema row sets match exactly.")

    return lines


def main() -> int:
    if os.environ.get("CONFIRM_RESTORE") != "yes":
        raise RuntimeError('Refusing to run without CONFIRM_RESTORE="yes"')

    source = os.environ.get(SOURCE_ENV, "")
    target = os.environ.get(TARGET_ENV, "")
    if not source:
        raise RuntimeError(f"{SOURCE_ENV} is required")
    if not target:
        raise RuntimeError(f"{TARGET_ENV} is required")

    for command in ("psql", "pg_dump", "pg_restore"):
        require_command(command)

    guard_source_target(source, target)
    source_fp = fingerprints(source)

    with tempfile.TemporaryDirectory(prefix="vorneq-dr-") as tmp:
        backup_file = Path(tmp) / "staging.dump"
        t0, t0_iso = time.monotonic(), utc_now()
        create_backup(source, backup_file)
        t1, t1_iso = time.monotonic(), utc_now()
        restore_backup(target, backup_file)
        t2, t2_iso = time.monotonic(), utc_now()
        target_fp = fingerprints(target)
        if target_fp != source_fp:
            print("Fingerprint mismatch detected:", file=sys.stderr)
            print(
                f"  schema: source={source_fp.schema}, target={target_fp.schema}",
                file=sys.stderr,
            )
            print(
                f"  public table count: source={source_fp.tables}, target={target_fp.tables}",
                file=sys.stderr,
            )
            print(
                f"  migrations: source={source_fp.migrations}, target={target_fp.migrations}",
                file=sys.stderr,
            )
            print(
                f"  content types: source={source_fp.content_types}, target={target_fp.content_types}",
                file=sys.stderr,
            )
            if source_fp.schema != target_fp.schema:
                diagnostic_lines = schema_diff_diagnostic_lines(source, target)
                for line in diagnostic_lines:
                    print(line, file=sys.stderr)
                write_summary([
                    "## DR Schema Diff Diagnostic",
                    "",
                    *[f"- `{line.strip()}`" for line in diagnostic_lines],
                ])
            raise RuntimeError("Restore verification failed: source/target fingerprints differ")
        t3, t3_iso = time.monotonic(), utc_now()

    backup_seconds = t1 - t0
    restore_seconds = t2 - t1
    verify_seconds = t3 - t2
    rto_seconds = t3 - t0
    restore_point_age_seconds = t3 - t1

    summary_lines = [
        "## DR Staging Rehearsal",
        "",
        "- Result: **PASS**",
        "- Source PostgreSQL: 18",
        "- Target PostgreSQL: 18",
        f"- Backup started: {t0_iso}",
        f"- Backup completed / restore point: {t1_iso}",
        f"- Restore completed: {t2_iso}",
        f"- Verification completed: {t3_iso}",
        f"- Backup duration: {backup_seconds:.1f}s",
        f"- Restore duration: {restore_seconds:.1f}s",
        f"- Verification duration: {verify_seconds:.1f}s",
        f"- Rehearsal RTO: **{rto_seconds:.1f}s**",
        f"- Restore-point age at verification: **{restore_point_age_seconds:.1f}s**",
        "",
        "> RPO is **not established** by this ad hoc rehearsal. Production RPO depends on the real backup cadence and restore-point age at incident time.",
    ]
    write_summary(summary_lines)
    print("\n".join(summary_lines))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"External command failed with exit code {exc.returncode}", file=sys.stderr)
        raise SystemExit(exc.returncode)
    except Exception as exc:
        print(f"DR rehearsal failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
