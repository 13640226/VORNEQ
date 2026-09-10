import os

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder


EXPECTED_MIGRATIONS = (
    ("audit", "0001_initial"),
    ("core", "0009_artifact_document_kind"),
    ("documents", "0001_initial"),
    ("documents", "0002_identity_subjects"),
    ("documents", "0003_documentauditlog"),
    ("documents", "0004_document_deletion_lifecycle"),
    ("notes", "0001_initial"),
)

DOCUMENT_TABLE = "documents_document"
ACCESS_TABLE = "documents_documentaccess"
USER_IDENTITY_TABLE = "core_useridentity"


class Command(BaseCommand):
    help = (
        "Read-only staging preflight for pending Inspect-related migrations. "
        "Uses migration records, database introspection, and raw SELECT queries only."
    )

    def handle(self, *args, **options):
        if os.environ.get("VORNEQ_ALLOW_INSPECT_MIGRATION_PREFLIGHT") != "yes":
            raise CommandError(
                "Refusing to run without VORNEQ_ALLOW_INSPECT_MIGRATION_PREFLIGHT=yes."
            )

        self.stdout.write("=== Inspect Staging Migration Preflight ===")

        applied = MigrationRecorder(connection).applied_migrations()
        for app_label, migration_name in EXPECTED_MIGRATIONS:
            state = "APPLIED" if (app_label, migration_name) in applied else "PENDING"
            self.stdout.write(f"Migration {app_label}.{migration_name}: {state}")

        tables = set(connection.introspection.table_names())
        document_exists = DOCUMENT_TABLE in tables
        access_exists = ACCESS_TABLE in tables
        user_identity_exists = USER_IDENTITY_TABLE in tables

        self.stdout.write(f"Table {DOCUMENT_TABLE}: {'present' if document_exists else 'absent'}")
        self.stdout.write(f"Table {ACCESS_TABLE}: {'present' if access_exists else 'absent'}")
        self.stdout.write(
            f"Table {USER_IDENTITY_TABLE}: {'present' if user_identity_exists else 'absent'}"
        )

        unsafe_reasons = []
        documents_0001_applied = ("documents", "0001_initial") in applied
        documents_0002_applied = ("documents", "0002_identity_subjects") in applied
        documents_0004_applied = ("documents", "0004_document_deletion_lifecycle") in applied

        if documents_0001_applied:
            if not document_exists or not access_exists:
                unsafe_reasons.append(
                    "documents.0001 is recorded as applied but one or more Documents tables are absent."
                )
        elif document_exists or access_exists:
            unsafe_reasons.append(
                "Documents tables exist while documents.0001 is still pending; migration recorder and schema diverge."
            )

        if not documents_0001_applied and not document_exists and not access_exists:
            self.stdout.write("Documents total: 0 (tables will be created by pending documents.0001)")
            self.stdout.write("DocumentAccess total: 0 (tables will be created by pending documents.0001)")
            self.stdout.write("Orphan Document.created_by: 0")
            self.stdout.write("Orphan DocumentAccess.user: 0")
            self.stdout.write("Owner inconsistencies: 0")
            self.stdout.write("Collaborator inconsistencies: 0")
            self.stdout.write(
                "documents.0002 data path: empty dataset after documents.0001; no identity backfill rows to convert."
            )
        elif document_exists and access_exists and not documents_0002_applied:
            document_columns = self._columns(DOCUMENT_TABLE)
            access_columns = self._columns(ACCESS_TABLE)
            required_document_columns = {"id", "created_by_id", "is_active"}
            required_access_columns = {"id", "document_id", "user_id", "role"}

            missing_document_columns = required_document_columns - document_columns
            missing_access_columns = required_access_columns - access_columns
            if missing_document_columns:
                unsafe_reasons.append(
                    "Pending documents.0002 cannot be preflighted because pre-0002 Document columns are missing: "
                    + ", ".join(sorted(missing_document_columns))
                )
            if missing_access_columns:
                unsafe_reasons.append(
                    "Pending documents.0002 cannot be preflighted because pre-0002 DocumentAccess columns are missing: "
                    + ", ".join(sorted(missing_access_columns))
                )

            if not missing_document_columns and not missing_access_columns:
                documents_total = self._scalar(
                    f"SELECT COUNT(*) FROM {self._q(DOCUMENT_TABLE)}"
                )
                access_total = self._scalar(
                    f"SELECT COUNT(*) FROM {self._q(ACCESS_TABLE)}"
                )
                self.stdout.write(f"Documents total: {documents_total}")
                self.stdout.write(f"DocumentAccess total: {access_total}")

                if (documents_total or access_total) and not user_identity_exists:
                    unsafe_reasons.append(
                        "core_useridentity is absent while documents.0002 has rows requiring canonical Identity resolution."
                    )
                elif user_identity_exists:
                    identity_columns = self._columns(USER_IDENTITY_TABLE)
                    missing_identity_columns = {"user_id", "identity_id"} - identity_columns
                    if missing_identity_columns:
                        unsafe_reasons.append(
                            "core_useridentity is missing required columns: "
                            + ", ".join(sorted(missing_identity_columns))
                        )
                    else:
                        counts = self._identity_invariant_counts()
                        self.stdout.write(
                            f"Orphan Document.created_by: {counts['orphan_documents']}"
                        )
                        self.stdout.write(
                            f"Orphan DocumentAccess.user: {counts['orphan_accesses']}"
                        )
                        self.stdout.write(
                            f"Owner inconsistencies: {counts['owner_inconsistencies']}"
                        )
                        self.stdout.write(
                            f"Collaborator inconsistencies: {counts['collaborator_inconsistencies']}"
                        )
                        for label, value in counts.items():
                            if value:
                                unsafe_reasons.append(f"documents.0002 invariant failed: {label}={value}")
        elif documents_0002_applied:
            self.stdout.write("documents.0002 data invariants: migration already applied")

        if documents_0004_applied:
            self.stdout.write("documents.0004 data mutation: migration already applied")
        elif document_exists:
            document_columns = self._columns(DOCUMENT_TABLE)
            if "is_active" not in document_columns:
                unsafe_reasons.append(
                    "Pending documents.0004 cannot inspect inactive rows because documents_document.is_active is absent."
                )
            else:
                inactive_count = self._scalar(
                    f"SELECT COUNT(*) FROM {self._q(DOCUMENT_TABLE)} WHERE {self._q('is_active')} = %s",
                    [False],
                )
                self.stdout.write(
                    "documents.0004 pending lifecycle sync rows (is_active=False): "
                    f"{inactive_count}"
                )
                self.stdout.write(
                    "documents.0004 note: forward migration mutates lifecycle_state for these rows; reverse data sync is noop."
                )
        else:
            self.stdout.write(
                "documents.0004 pending lifecycle sync rows: 0 (Documents table absent before documents.0001)"
            )

        if unsafe_reasons:
            self.stdout.write("RESULT: UNSAFE")
            for reason in unsafe_reasons:
                self.stdout.write(f"UNSAFE: {reason}")
            raise CommandError(
                "Migration data preflight failed; no writes or repairs were performed."
            )

        self.stdout.write(
            self.style.SUCCESS(
                "RESULT: SAFE — data invariants required by the pending migrations passed."
            )
        )
        self.stdout.write(
            "This result is not a guarantee that the complete migrate operation is risk-free."
        )

    def _columns(self, table_name):
        with connection.cursor() as cursor:
            description = connection.introspection.get_table_description(cursor, table_name)
        return {column.name for column in description}

    def _q(self, identifier):
        return connection.ops.quote_name(identifier)

    def _scalar(self, sql, params=None):
        with connection.cursor() as cursor:
            cursor.execute(sql, params or [])
            row = cursor.fetchone()
        return row[0]

    def _identity_invariant_counts(self):
        document = self._q(DOCUMENT_TABLE)
        access = self._q(ACCESS_TABLE)
        user_identity = self._q(USER_IDENTITY_TABLE)

        orphan_documents = self._scalar(
            f"""
            SELECT COUNT(*)
            FROM {document} d
            LEFT JOIN {user_identity} owner_ui ON owner_ui.user_id = d.created_by_id
            WHERE owner_ui.identity_id IS NULL
            """
        )
        orphan_accesses = self._scalar(
            f"""
            SELECT COUNT(*)
            FROM {access} a
            LEFT JOIN {user_identity} access_ui ON access_ui.user_id = a.user_id
            WHERE access_ui.identity_id IS NULL
            """
        )
        owner_inconsistencies = self._scalar(
            f"""
            SELECT COUNT(*)
            FROM {access} a
            JOIN {document} d ON d.id = a.document_id
            JOIN {user_identity} access_ui ON access_ui.user_id = a.user_id
            JOIN {user_identity} owner_ui ON owner_ui.user_id = d.created_by_id
            WHERE a.role = %s
              AND (a.user_id <> d.created_by_id OR access_ui.identity_id <> owner_ui.identity_id)
            """,
            ["owner"],
        )
        collaborator_inconsistencies = self._scalar(
            f"""
            SELECT COUNT(*)
            FROM {access} a
            JOIN {document} d ON d.id = a.document_id
            JOIN {user_identity} access_ui ON access_ui.user_id = a.user_id
            JOIN {user_identity} owner_ui ON owner_ui.user_id = d.created_by_id
            WHERE a.role <> %s
              AND access_ui.identity_id = owner_ui.identity_id
            """,
            ["owner"],
        )
        return {
            "orphan_documents": orphan_documents,
            "orphan_accesses": orphan_accesses,
            "owner_inconsistencies": owner_inconsistencies,
            "collaborator_inconsistencies": collaborator_inconsistencies,
        }
